# Design Document: API Server for Music Source Separation

## Overview

This design document describes the architecture and implementation approach for adding RESTful API server functionality to the MSST-GUI project. The API server will expose the existing audio source separation capabilities through HTTP endpoints, enabling programmatic access to the inference functionality.

The design leverages FastAPI as the web framework due to its native async support, automatic OpenAPI documentation generation, and excellent performance characteristics. For asynchronous task processing, we'll use a lightweight in-process task queue with threading to avoid the complexity of external message brokers while maintaining the ability to scale to distributed systems later if needed.

### Key Design Decisions

1. **FastAPI Framework**: Chosen for built-in async support, automatic OpenAPI/Swagger documentation, type validation via Pydantic, and excellent performance
2. **In-Process Task Queue**: Using Python's concurrent.futures.ThreadPoolExecutor for simplicity, with clear migration path to Celery/Redis if distributed processing is needed
3. **SQLite Database**: For task metadata storage (status, progress, timestamps) - simple, serverless, sufficient for single-instance deployments
4. **File-Based Storage**: Separated audio files stored in organized directory structure with Task_ID-based naming
5. **Stateless API Design**: All state persisted to database/filesystem, enabling graceful restarts and horizontal scaling potential


## Architecture

The API server follows a layered architecture with clear separation of concerns:

```
┌─────────────────────────────────────────────────────────────┐
│                     FastAPI Application                      │
│  ┌────────────┐  ┌──────────────┐  ┌────────────────────┐  │
│  │  REST API  │  │   OpenAPI    │  │  Authentication    │  │
│  │ Endpoints  │  │     Docs     │  │   Middleware       │  │
│  └────────────┘  └──────────────┘  └────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    Business Logic Layer                      │
│  ┌────────────┐  ┌──────────────┐  ┌────────────────────┐  │
│  │   Task     │  │    Model     │  │     Result         │  │
│  │  Manager   │  │   Manager    │  │    Manager         │  │
│  └────────────┘  └──────────────┘  └────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    Task Processing Layer                     │
│  ┌────────────┐  ┌──────────────┐  ┌────────────────────┐  │
│  │   Worker   │  │  Inference   │  │    Progress        │  │
│  │    Pool    │  │   Engine     │  │    Tracker         │  │
│  └────────────┘  └──────────────┘  └────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                      Persistence Layer                       │
│  ┌────────────┐  ┌──────────────┐  ┌────────────────────┐  │
│  │   SQLite   │  │  File System │  │   Configuration    │  │
│  │  Database  │  │   Storage    │  │      Store         │  │
│  └────────────┘  └──────────────┘  └────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

**REST API Endpoints**: Handle HTTP requests, validate input, invoke business logic, format responses

**Task Manager**: Orchestrates task lifecycle (creation, queuing, status updates, cleanup)

**Model Manager**: Loads and caches neural network models, validates model configurations

**Result Manager**: Handles result file storage, retrieval, and cleanup

**Worker Pool**: Manages concurrent task execution using thread pool

**Inference Engine**: Wraps existing proc_folder functionality for audio separation

**Progress Tracker**: Monitors and reports task progress during processing

**Database**: Persists task metadata, status, and configuration

**File System Storage**: Stores uploaded audio files and separated output files



## Components and Interfaces

### 1. REST API Endpoints

The API exposes the following endpoints:

#### POST /api/v1/separate
Submit a new separation task.

**Request**:
- Content-Type: multipart/form-data
- Body:
  - `file`: Audio file (required)
  - `model_type`: String (optional, default: "mdx23c")
  - `instruments`: Array of strings (optional, default: model-specific)
  - `use_tta`: Boolean (optional, default: false)
  - `extract_instrumental`: Boolean (optional, default: false)
  - `output_format`: String "wav" or "flac" (optional, default: "wav")
  - `pcm_type`: String "PCM_16" or "PCM_24" (optional, default: "PCM_24")

**Response** (201 Created):
```json
{
  "task_id": "uuid-string",
  "status": "pending",
  "created_at": "2024-01-15T10:30:00Z"
}
```

#### GET /api/v1/tasks/{task_id}
Get task status and progress.

**Response** (200 OK):
```json
{
  "task_id": "uuid-string",
  "status": "processing",
  "progress": 45.5,
  "stage": "Processing vocals",
  "created_at": "2024-01-15T10:30:00Z",
  "started_at": "2024-01-15T10:30:05Z",
  "estimated_completion": "2024-01-15T10:32:00Z"
}
```

#### GET /api/v1/tasks/{task_id}/results
Get download URLs for completed task results.

**Response** (200 OK):
```json
{
  "task_id": "uuid-string",
  "status": "completed",
  "results": {
    "vocals": "/api/v1/download/uuid-string/vocals.wav",
    "instrumental": "/api/v1/download/uuid-string/instrumental.wav"
  },
  "completed_at": "2024-01-15T10:31:45Z"
}
```

#### GET /api/v1/download/{task_id}/{filename}
Download a separated audio file.

**Response** (200 OK):
- Content-Type: audio/wav or audio/flac
- Body: Audio file stream
- Headers: Content-Disposition, Content-Length, Accept-Ranges

#### DELETE /api/v1/tasks/{task_id}
Cancel a pending/processing task or delete a completed task.

**Response** (204 No Content)

#### GET /api/v1/models
List available models and their capabilities.

**Response** (200 OK):
```json
{
  "models": [
    {
      "model_type": "mdx23c",
      "instruments": ["vocals", "instrumental"],
      "sample_rate": 44100,
      "supports_stereo": true
    }
  ]
}
```

#### GET /api/v1/health
Health check endpoint.

**Response** (200 OK):
```json
{
  "status": "healthy",
  "checks": {
    "database": "ok",
    "disk_space": "ok",
    "gpu_available": true,
    "models_loaded": 3
  }
}
```

#### GET /api/v1/metrics
Server metrics and statistics.

**Response** (200 OK):
```json
{
  "active_tasks": 2,
  "queued_tasks": 5,
  "completed_tasks_24h": 150,
  "failed_tasks_24h": 3,
  "average_processing_time_seconds": 45.2,
  "uptime_seconds": 86400
}
```

#### GET /docs
Swagger UI for interactive API documentation (auto-generated by FastAPI).

#### GET /openapi.json
OpenAPI 3.0 specification (auto-generated by FastAPI).



### 2. Task Manager

The Task Manager orchestrates the complete lifecycle of separation tasks.

**Interface**:
```python
class TaskManager:
    def create_task(
        self,
        audio_file: UploadFile,
        model_type: str,
        instruments: Optional[List[str]],
        use_tta: bool,
        extract_instrumental: bool,
        output_format: str,
        pcm_type: str
    ) -> Task:
        """Create a new separation task and queue it for processing."""
        pass
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """Retrieve task by ID."""
        pass
    
    def update_task_status(
        self,
        task_id: str,
        status: TaskStatus,
        progress: Optional[float] = None,
        error_message: Optional[str] = None
    ) -> None:
        """Update task status and progress."""
        pass
    
    def cancel_task(self, task_id: str) -> bool:
        """Cancel a pending or processing task."""
        pass
    
    def cleanup_old_tasks(self) -> int:
        """Remove old completed/failed tasks and their files."""
        pass
```

**Responsibilities**:
- Generate unique Task_IDs using UUID4
- Validate input parameters against model capabilities
- Save uploaded audio files to temporary storage
- Create task records in database
- Submit tasks to worker pool
- Track task status transitions
- Implement cleanup policies



### 3. Model Manager

The Model Manager handles loading, caching, and validation of neural network models.

**Interface**:
```python
class ModelManager:
    def __init__(self, config: ServerConfig):
        """Initialize with server configuration."""
        pass
    
    def get_available_models(self) -> List[ModelInfo]:
        """Return list of available models with their capabilities."""
        pass
    
    def get_model_info(self, model_type: str) -> Optional[ModelInfo]:
        """Get detailed information about a specific model."""
        pass
    
    def validate_model_params(
        self,
        model_type: str,
        instruments: Optional[List[str]]
    ) -> ValidationResult:
        """Validate that requested instruments are supported by model."""
        pass
    
    def load_model(self, model_type: str, device: str) -> Tuple[nn.Module, Config]:
        """Load model and config for inference (cached)."""
        pass
```

**Responsibilities**:
- Scan pretrain directory for available model checkpoints
- Parse model configuration files
- Cache loaded models in memory to avoid repeated loading
- Validate instrument compatibility with models
- Provide model metadata to API consumers



### 4. Worker Pool

The Worker Pool manages concurrent execution of separation tasks.

**Interface**:
```python
class WorkerPool:
    def __init__(
        self,
        max_workers: int,
        device_ids: List[int],
        task_manager: TaskManager
    ):
        """Initialize worker pool with specified concurrency."""
        pass
    
    def submit_task(self, task_id: str) -> Future:
        """Submit a task for asynchronous processing."""
        pass
    
    def shutdown(self, wait: bool = True) -> None:
        """Gracefully shutdown worker pool."""
        pass
    
    def get_active_count(self) -> int:
        """Return number of currently executing tasks."""
        pass
```

**Implementation Details**:
- Uses `concurrent.futures.ThreadPoolExecutor` for thread-based concurrency
- Worker count configured based on available GPU/CPU resources
- Each worker processes one task at a time
- Tasks queued in FIFO order
- Failed tasks logged but don't crash workers
- Graceful shutdown waits for active tasks to complete

**GPU Management**:
- If multiple GPUs available, distribute tasks round-robin across devices
- If single GPU, serialize tasks to prevent OOM errors
- If CPU-only, limit workers to prevent memory exhaustion



### 5. Inference Engine Wrapper

Wraps the existing inference.py functionality for use in the API server.

**Interface**:
```python
class InferenceEngine:
    def __init__(self, model_manager: ModelManager):
        """Initialize with model manager."""
        pass
    
    def separate_audio(
        self,
        task_id: str,
        input_path: str,
        output_dir: str,
        model_type: str,
        config_path: str,
        instruments: List[str],
        use_tta: bool,
        extract_instrumental: bool,
        output_format: str,
        pcm_type: str,
        device: str,
        progress_callback: Callable[[float, str], None]
    ) -> Dict[str, str]:
        """
        Perform audio separation and return paths to output files.
        
        Returns:
            Dictionary mapping instrument names to output file paths
        """
        pass
```

**Implementation Details**:
- Adapts existing `proc_folder()` function to work with single files
- Constructs argument dictionary compatible with `parse_args_inference()`
- Invokes existing inference pipeline
- Reports progress via callback function
- Returns mapping of instrument names to output file paths
- Handles exceptions and converts to task failures

**Progress Reporting**:
- Hook into existing tqdm progress bars
- Extract progress percentage and current stage
- Invoke callback to update task status in database



### 6. Authentication Middleware

Optional authentication layer for API access control.

**Interface**:
```python
class AuthMiddleware:
    def __init__(self, api_keys: List[str], enabled: bool):
        """Initialize with list of valid API keys."""
        pass
    
    async def __call__(
        self,
        request: Request,
        call_next: Callable
    ) -> Response:
        """Validate API key in Authorization header."""
        pass
```

**Implementation Details**:
- Checks for `Authorization: Bearer <api_key>` header
- Validates key against configured list
- Returns 401 Unauthorized if key missing or invalid
- Bypasses check if authentication disabled in config
- Excludes health and documentation endpoints from auth



### 7. Rate Limiter

Optional rate limiting to prevent API abuse.

**Interface**:
```python
class RateLimiter:
    def __init__(
        self,
        requests_per_hour: int,
        enabled: bool
    ):
        """Initialize rate limiter with limits."""
        pass
    
    async def check_rate_limit(
        self,
        api_key: str
    ) -> Tuple[bool, Optional[int]]:
        """
        Check if request is within rate limit.
        
        Returns:
            (allowed, retry_after_seconds)
        """
        pass
    
    def reset_limits(self) -> None:
        """Reset all rate limit counters (for testing)."""
        pass
```

**Implementation Details**:
- Tracks request counts per API key using in-memory dictionary
- Implements sliding window algorithm
- Returns 429 Too Many Requests when limit exceeded
- Includes `Retry-After` header with seconds until reset
- Adds rate limit headers to all responses:
  - `X-RateLimit-Limit`: Total requests allowed per hour
  - `X-RateLimit-Remaining`: Requests remaining in current window
  - `X-RateLimit-Reset`: Unix timestamp when limit resets



## Data Models

### Task

Represents a separation task throughout its lifecycle.

```python
from enum import Enum
from datetime import datetime
from typing import Optional, List, Dict

class TaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class Task:
    task_id: str                          # UUID4 identifier
    status: TaskStatus                    # Current task status
    created_at: datetime                  # Task creation timestamp
    started_at: Optional[datetime]        # Processing start timestamp
    completed_at: Optional[datetime]      # Completion timestamp
    
    # Input parameters
    input_file_path: str                  # Path to uploaded audio file
    model_type: str                       # Model type identifier
    config_path: str                      # Path to model config file
    instruments: List[str]                # Requested instruments
    use_tta: bool                         # Test time augmentation flag
    extract_instrumental: bool            # Extract instrumental flag
    output_format: str                    # "wav" or "flac"
    pcm_type: str                         # "PCM_16" or "PCM_24"
    
    # Progress tracking
    progress: float                       # 0.0 to 100.0
    current_stage: Optional[str]          # Human-readable stage description
    estimated_completion: Optional[datetime]  # Estimated completion time
    
    # Results
    output_files: Dict[str, str]          # Instrument -> file path mapping
    error_message: Optional[str]          # Error details if failed
    
    # Metadata
    file_size_bytes: int                  # Original file size
    processing_time_seconds: Optional[float]  # Total processing time
```

**Database Schema** (SQLite):
```sql
CREATE TABLE tasks (
    task_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    
    input_file_path TEXT NOT NULL,
    model_type TEXT NOT NULL,
    config_path TEXT NOT NULL,
    instruments TEXT NOT NULL,  -- JSON array
    use_tta INTEGER NOT NULL,
    extract_instrumental INTEGER NOT NULL,
    output_format TEXT NOT NULL,
    pcm_type TEXT NOT NULL,
    
    progress REAL DEFAULT 0.0,
    current_stage TEXT,
    estimated_completion TIMESTAMP,
    
    output_files TEXT,  -- JSON object
    error_message TEXT,
    
    file_size_bytes INTEGER NOT NULL,
    processing_time_seconds REAL
);

CREATE INDEX idx_status ON tasks(status);
CREATE INDEX idx_created_at ON tasks(created_at);
CREATE INDEX idx_completed_at ON tasks(completed_at);
```



### ModelInfo

Describes available models and their capabilities.

```python
class ModelInfo:
    model_type: str                       # Model type identifier
    config_path: str                      # Path to config file
    checkpoint_path: Optional[str]        # Path to checkpoint file
    instruments: List[str]                # Supported instruments
    sample_rate: int                      # Audio sample rate
    supports_stereo: bool                 # Stereo input support
    supports_mono: bool                   # Mono input support
    description: Optional[str]            # Human-readable description
```

### ServerConfig

Server configuration loaded from YAML/JSON file.

```python
class ServerConfig:
    # Server settings
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 1                      # Number of concurrent tasks
    
    # File handling
    max_file_size_mb: int = 500
    upload_dir: str = "./api_uploads"
    output_dir: str = "./api_outputs"
    
    # Task cleanup
    cleanup_enabled: bool = True
    completed_retention_hours: int = 24
    failed_retention_hours: int = 24
    metadata_retention_days: int = 7
    
    # Model settings
    default_model_type: str = "mdx23c"
    model_cache_size: int = 3             # Number of models to keep in memory
    force_cpu: bool = False
    device_ids: List[int] = [0]
    
    # Authentication
    enable_auth: bool = False
    api_keys: List[str] = []
    
    # Rate limiting
    enable_rate_limit: bool = False
    requests_per_hour: int = 100
    
    # Database
    database_path: str = "./api_server.db"
    
    # Logging
    log_level: str = "INFO"
    log_file: str = "./api_server.log"
```

**Configuration File Format** (YAML):
```yaml
server:
  host: "0.0.0.0"
  port: 8000
  workers: 2

files:
  max_file_size_mb: 500
  upload_dir: "./api_uploads"
  output_dir: "./api_outputs"

cleanup:
  enabled: true
  completed_retention_hours: 24
  failed_retention_hours: 24
  metadata_retention_days: 7

models:
  default_model_type: "mdx23c"
  model_cache_size: 3
  force_cpu: false
  device_ids: [0]

auth:
  enabled: false
  api_keys: []

rate_limit:
  enabled: false
  requests_per_hour: 100

database:
  path: "./api_server.db"

logging:
  level: "INFO"
  file: "./api_server.log"
```



## Correctness Properties

A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.

### Property Reflection

After analyzing all acceptance criteria, several opportunities for consolidation emerged:

- File validation properties (1.1, 1.2, 1.3) can be combined into a comprehensive input validation property
- Status transition properties (2.2, 2.3, 2.4) represent a state machine that can be tested as status transition invariants
- Error response properties (7.1, 7.2, 7.4, 7.5) share common structure and can be consolidated
- Configuration properties (10.4, 10.5, 10.6) test the same mechanism with different parameters
- Authentication and rate limiting properties test conditional behavior based on configuration

The following properties eliminate redundancy while maintaining comprehensive coverage.



### Input Validation Properties

Property 1: File format and size validation
*For any* file submission, the API server should accept files with valid audio extensions (WAV, FLAC, MP3, OGG, M4A) under 500MB and reject all others with appropriate HTTP 400 errors
**Validates: Requirements 1.1, 1.2, 1.5**

Property 2: Audio content validation
*For any* submitted file, if the file is readable and contains valid audio data, it should be accepted; if corrupted or invalid, it should be rejected with HTTP 400
**Validates: Requirements 1.3, 1.5**

Property 3: Parameter acceptance
*For any* separation request, all optional parameters (model_type, instruments, use_tta, extract_instrumental, output_format, pcm_type) should be accepted when provided with valid values
**Validates: Requirements 1.6**

Property 4: Invalid parameter rejection
*For any* separation request with invalid parameters (unsupported model_type, invalid instruments, etc.), the API server should return HTTP 400 with details about which parameters are invalid
**Validates: Requirements 7.2, 7.4, 7.5**



### Task Lifecycle Properties

Property 5: Task creation and uniqueness
*For any* valid audio file submission, the API server should create a task and return a unique Task_ID that differs from all other Task_IDs
**Validates: Requirements 1.4**

Property 6: Asynchronous task queuing
*For any* task creation request, the HTTP response should return immediately with a Task_ID while the task is queued for background processing
**Validates: Requirements 2.1**

Property 7: Status transition validity
*For any* task, status transitions should follow valid state machine paths: pending → processing → (completed | failed | cancelled), and no task should transition to an invalid state
**Validates: Requirements 2.2, 2.3, 2.4**

Property 8: FIFO task processing order
*For any* sequence of tasks submitted to an empty queue, they should begin processing in the same order they were submitted
**Validates: Requirements 2.5**

Property 9: Task status retrieval
*For any* valid Task_ID, requesting task status should return a response containing the current status (pending, processing, completed, failed, or cancelled)
**Validates: Requirements 3.1**

Property 10: Progress information presence
*For any* task status request, the response should include progress information (percentage and current stage)
**Validates: Requirements 3.2**

Property 11: Non-existent task handling
*For any* Task_ID that does not exist in the system, status requests should return HTTP 404
**Validates: Requirements 3.3**

Property 12: Processing task metadata
*For any* task in "processing" status, the status response should include an estimated completion time
**Validates: Requirements 3.4**

Property 13: Failed task error details
*For any* task in "failed" status, the status response should include an error message describing the failure
**Validates: Requirements 3.5**



### Result Retrieval Properties

Property 14: Completed task results
*For any* completed task, requesting results should return download URLs for all separated source files
**Validates: Requirements 4.1**

Property 15: File download headers
*For any* download request for an existing file, the response should include appropriate Content-Type headers and stream the audio file content
**Validates: Requirements 4.2**

Property 16: Premature result request handling
*For any* task that is not in "completed" status, requesting results should return HTTP 409
**Validates: Requirements 4.3**

Property 17: Failed task result handling
*For any* task in "failed" status, requesting results should return HTTP 410 with the failure reason
**Validates: Requirements 4.4**

Property 18: Output format preservation
*For any* task with a specified output format (WAV or FLAC), all generated output files should be in that format
**Validates: Requirements 4.5**

Property 19: HTTP range request support
*For any* download request with a Range header, the server should return partial content (HTTP 206) with the requested byte range
**Validates: Requirements 4.7**



### Cleanup Properties

Property 20: Completed task file cleanup
*For any* task that has been in "completed" status for more than the configured retention period, the associated audio files should be deleted
**Validates: Requirements 5.1**

Property 21: Task metadata cleanup
*For any* task that has been completed for more than the configured metadata retention period, the task metadata should be deleted from the database
**Validates: Requirements 5.2**

Property 22: Failed task cleanup
*For any* task that has been in "failed" status for more than the configured retention period, any partial output files should be deleted
**Validates: Requirements 5.3**

Property 23: Task resumption on restart
*For any* incomplete tasks (pending or processing status) when the server restarts, those tasks should be resumed or requeued for processing
**Validates: Requirements 5.4**

Property 24: Configurable retention periods
*For any* configured retention period values, the cleanup process should respect those values when determining which tasks to clean up
**Validates: Requirements 5.5**



### Documentation Properties

Property 25: OpenAPI specification completeness
*For any* API endpoint, the OpenAPI specification should document all request parameters (with types and required/optional status), all response schemas, and all possible HTTP status codes
**Validates: Requirements 6.3, 6.4, 6.5**



### Error Handling Properties

Property 26: JSON error response format
*For any* error condition, the API server should return a JSON response containing an error code and human-readable message
**Validates: Requirements 7.1**

Property 27: Service overload handling
*For any* request when the server is overloaded (all workers busy and queue full), the API server should return HTTP 503
**Validates: Requirements 7.3**

Property 28: Inference engine error isolation
*For any* task where the inference engine crashes during processing, the task should be marked as failed with an error message, and other queued tasks should continue processing
**Validates: Requirements 7.6**

Property 29: Model loading error handling
*For any* task submission when required model files cannot be loaded, the API server should return HTTP 500
**Validates: Requirements 7.7**



### Authentication and Rate Limiting Properties

Property 30: Authentication enforcement
*For any* request when authentication is enabled, requests without a valid API key in the Authorization header should return HTTP 401
**Validates: Requirements 8.1, 8.2**

Property 31: Authentication bypass when disabled
*For any* request when authentication is disabled, requests should succeed regardless of whether an API key is provided
**Validates: Requirements 8.6**

Property 32: Rate limit enforcement
*For any* API key when rate limiting is enabled, after making N requests (where N is the configured limit), the next request should return HTTP 429 with a Retry-After header
**Validates: Requirements 8.3, 8.4**

Property 33: Rate limit headers
*For any* response when rate limiting is enabled, the response should include X-RateLimit-Limit, X-RateLimit-Remaining, and X-RateLimit-Reset headers
**Validates: Requirements 8.5**



### Health and Monitoring Properties

Property 34: Health check success
*For any* health check request when all systems are operational (models loaded, sufficient disk space, database accessible), the response should return HTTP 200
**Validates: Requirements 9.1**

Property 35: Health check completeness
*For any* health check response, it should include status information for all critical dependencies (model loading, disk space, GPU availability)
**Validates: Requirements 9.2**

Property 36: Degraded health detection
*For any* health check request when available disk space is below 10GB, the response should report degraded health status
**Validates: Requirements 9.3**

Property 37: Unhealthy status detection
*For any* health check request when required model files are inaccessible, the response should report unhealthy status
**Validates: Requirements 9.4**

Property 38: Metrics completeness
*For any* metrics request, the response should include statistics for active tasks, queued tasks, completed tasks, and average processing time
**Validates: Requirements 9.5**

Property 39: Request logging
*For any* API request, error, or task processing event, the server should write a structured log entry to the log file
**Validates: Requirements 9.6**



### Configuration Properties

Property 40: Configuration file loading
*For any* server startup with a valid configuration file, the server should load all configuration values from the file
**Validates: Requirements 10.1**

Property 41: Default configuration fallback
*For any* server startup without a configuration file, the server should use default values and log a warning
**Validates: Requirements 10.2**

Property 42: Invalid configuration rejection
*For any* server startup with an invalid configuration file, the server should fail to start and log descriptive error messages
**Validates: Requirements 10.3**

Property 43: Configuration parameter support
*For any* supported configuration parameter (host, port, max_file_size, worker_threads, cleanup_retention_hours, default_model_type, enable_auth, api_keys, enable_rate_limit, requests_per_hour), setting it in the configuration file should result in the server using that value
**Validates: Requirements 10.4, 10.5, 10.6**

Property 44: Configuration change requires restart
*For any* configuration value change while the server is running, the change should not take effect until the server is restarted
**Validates: Requirements 10.7**



### Concurrent Processing Properties

Property 45: Multi-GPU task distribution
*For any* set of tasks when multiple GPUs are available, tasks should be distributed across all available GPUs
**Validates: Requirements 11.1**

Property 46: CPU-only sequential processing
*For any* set of tasks when only CPU is available, tasks should be processed sequentially (one at a time)
**Validates: Requirements 11.2**

Property 47: Worker pool concurrency limit
*For any* time during server operation, the number of concurrently processing tasks should not exceed the configured worker count
**Validates: Requirements 11.3**

Property 48: Task queuing when workers busy
*For any* task submission when all workers are busy, the task should be queued and begin processing when a worker becomes available
**Validates: Requirements 11.4**

Property 49: Worker crash recovery
*For any* worker crash during task processing, the worker should be restarted and the failed task should be requeued
**Validates: Requirements 11.5**



### Model Management Properties

Property 50: Model listing completeness
*For any* request to the models list endpoint, the response should include all available models with their model_type and configuration paths
**Validates: Requirements 12.1**

Property 51: Model details completeness
*For any* valid model_type, requesting model details should return supported instruments, sample rate, and stereo support information
**Validates: Requirements 12.2**

Property 52: Non-existent model handling
*For any* model_type that does not exist, requesting model details should return HTTP 404
**Validates: Requirements 12.3**

Property 53: Startup model validation
*For any* server startup, the server should validate that all configured models have their required checkpoint files present
**Validates: Requirements 12.4**

Property 54: Missing model graceful handling
*For any* configured model with missing checkpoint files, the server should log a warning and exclude that model from the available models list
**Validates: Requirements 12.5**



## Error Handling

The API server implements comprehensive error handling at multiple layers:

### HTTP Error Responses

All errors return JSON responses with consistent structure:

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error description",
    "details": {
      "field": "Additional context"
    }
  }
}
```

### Error Categories

**Client Errors (4xx)**:
- 400 Bad Request: Invalid parameters, unsupported formats, validation failures
- 401 Unauthorized: Missing or invalid API key (when auth enabled)
- 404 Not Found: Non-existent Task_ID or model
- 409 Conflict: Requesting results for incomplete task
- 410 Gone: Requesting results for failed task
- 429 Too Many Requests: Rate limit exceeded

**Server Errors (5xx)**:
- 500 Internal Server Error: Model loading failures, unexpected exceptions
- 503 Service Unavailable: Server overloaded, all workers busy

### Exception Handling Strategy

**Request Validation Layer**:
- Pydantic models validate all input parameters
- File size and format validation before processing
- Model and instrument compatibility checks

**Task Processing Layer**:
- Try-catch around inference engine calls
- Worker crashes isolated to individual tasks
- Failed tasks marked with error messages
- Other tasks continue processing

**Resource Management**:
- Database connection errors logged and retried
- File I/O errors caught and reported
- Disk space monitored continuously

### Logging

All errors logged with:
- Timestamp
- Request ID
- Error type and message
- Stack trace (for server errors)
- User context (API key, if applicable)



## Testing Strategy

The API server will be validated through a dual testing approach combining unit tests and property-based tests.

### Unit Tests

Unit tests focus on specific examples, edge cases, and integration points:

**API Endpoint Tests**:
- Test each endpoint with valid inputs
- Test authentication and rate limiting middleware
- Test error responses for invalid inputs
- Test file upload and download functionality

**Component Tests**:
- Task Manager: task creation, status updates, cleanup
- Model Manager: model loading, caching, validation
- Worker Pool: task queuing, concurrent execution
- Inference Engine Wrapper: integration with existing inference.py

**Integration Tests**:
- End-to-end task submission and completion
- Database persistence and retrieval
- File storage and cleanup
- Server startup and shutdown

**Edge Cases**:
- Empty files, corrupted audio files
- Extremely large files (near size limit)
- Concurrent requests to same task
- Server restart with incomplete tasks
- Disk space exhaustion scenarios

### Property-Based Tests

Property-based tests verify universal properties across randomized inputs. Each property test will:
- Run minimum 100 iterations with randomized inputs
- Reference the design document property number
- Use pytest with Hypothesis library for Python

**Test Configuration**:
```python
@given(...)
@settings(max_examples=100)
def test_property_N_description():
    """
    Feature: api-server, Property N: [property text]
    """
    # Test implementation
```

**Key Property Tests**:

1. Input validation properties (Properties 1-4): Generate random files with various formats, sizes, and content
2. Task lifecycle properties (Properties 5-13): Generate random task sequences and verify state transitions
3. Result retrieval properties (Properties 14-19): Generate random task states and verify result access
4. Cleanup properties (Properties 20-24): Generate tasks with random timestamps and verify cleanup
5. Authentication properties (Properties 30-31): Generate random API keys and verify access control
6. Rate limiting properties (Properties 32-33): Generate request sequences and verify limits
7. Configuration properties (Properties 40-44): Generate random configuration values and verify behavior
8. Concurrent processing properties (Properties 45-49): Generate random task loads and verify concurrency

### Testing Tools

- **pytest**: Test framework
- **Hypothesis**: Property-based testing library
- **pytest-asyncio**: Async test support
- **httpx**: HTTP client for API testing
- **pytest-mock**: Mocking support
- **coverage.py**: Code coverage measurement

### Test Data Generation

Property tests will use Hypothesis strategies to generate:
- Random audio files (various formats, sizes, sample rates)
- Random task parameters (model types, instruments, options)
- Random API keys and request sequences
- Random timestamps for cleanup testing
- Random configuration values

### Coverage Goals

- Minimum 80% code coverage
- All API endpoints covered by tests
- All error paths tested
- All correctness properties validated

### Continuous Testing

- Tests run on every commit
- Property tests run with reduced iterations (10) in CI for speed
- Full property test suite (100 iterations) run nightly
- Integration tests run against real models in staging environment

