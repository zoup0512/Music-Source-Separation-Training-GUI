# Implementation Plan: API Server for Music Source Separation

## Overview

This implementation plan breaks down the API server feature into discrete coding tasks. The approach follows a bottom-up strategy: first establishing core infrastructure (database, configuration, models), then building the task processing layer, and finally implementing the REST API endpoints. Each task builds incrementally on previous work, with testing integrated throughout.

The implementation uses Python with FastAPI for the web framework, SQLite for persistence, and integrates with the existing inference.py functionality.

## Tasks

- [x] 1. Set up project structure and dependencies
  - Create api_server/ directory with __init__.py
  - Create subdirectories: api/, core/, models/, workers/, utils/
  - Add FastAPI, uvicorn, pydantic, sqlalchemy, hypothesis to requirements
  - Create api_server_config.yaml with default configuration values
  - _Requirements: 10.1, 10.2_

- [x] 2. Implement configuration management
  - [x] 2.1 Create ServerConfig data model with Pydantic
    - Define all configuration fields (host, port, workers, file limits, cleanup settings, auth, rate limiting)
    - Implement validation for configuration values
    - _Requirements: 10.4, 10.5, 10.6_
  
  - [x] 2.2 Create configuration loader
    - Implement load_config() function to read YAML/JSON files
    - Implement default configuration fallback
    - Add configuration validation with descriptive error messages
    - _Requirements: 10.1, 10.2, 10.3_
  
  - [x] 2.3 Write property test for configuration loading
    - **Property 40: Configuration file loading**
    - **Property 41: Default configuration fallback**
    - **Property 42: Invalid configuration rejection**
    - **Property 43: Configuration parameter support**
    - **Validates: Requirements 10.1, 10.2, 10.3, 10.4, 10.5, 10.6**

- [x] 3. Implement database layer
  - [x] 3.1 Create Task data model and SQLAlchemy schema
    - Define Task class with all fields (task_id, status, timestamps, parameters, progress, results)
    - Define TaskStatus enum
    - Create SQLite table schema with indexes
    - _Requirements: 2.2, 2.3, 2.4, 3.1_
  
  - [x] 3.2 Create database manager
    - Implement DatabaseManager class with connection handling
    - Implement CRUD operations: create_task, get_task, update_task_status, list_tasks
    - Implement cleanup queries for old tasks
    - Add database initialization and migration support
    - _Requirements: 2.2, 2.3, 2.4, 3.1, 5.1, 5.2, 5.3_
  
  - [x] 3.3 Write unit tests for database operations
    - Test task creation, retrieval, updates
    - Test status transitions
    - Test cleanup queries
    - _Requirements: 2.2, 2.3, 2.4, 3.1_



- [x] 4. Implement Model Manager
  - [x] 4.1 Create ModelInfo data model
    - Define ModelInfo class with model metadata fields
    - _Requirements: 12.1, 12.2_
  
  - [x] 4.2 Implement ModelManager class
    - Implement model discovery by scanning configs/ and pretrain/ directories
    - Implement get_available_models() to return list of ModelInfo
    - Implement get_model_info(model_type) for specific model details
    - Implement validate_model_params() for parameter validation
    - Implement load_model() with caching using LRU cache
    - Add startup validation for model checkpoint files
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5, 7.4, 7.5_
  
  - [x] 4.3 Write property tests for Model Manager
    - **Property 50: Model listing completeness**
    - **Property 51: Model details completeness**
    - **Property 52: Non-existent model handling**
    - **Property 53: Startup model validation**
    - **Property 54: Missing model graceful handling**
    - **Validates: Requirements 12.1, 12.2, 12.3, 12.4, 12.5**
  
  - [x] 4.4 Write unit tests for model validation
    - Test parameter validation for different models
    - Test invalid model_type and instrument combinations
    - _Requirements: 7.4, 7.5_

- [x] 5. Implement Inference Engine Wrapper
  - [x] 5.1 Create InferenceEngine class
    - Implement separate_audio() method that wraps proc_folder functionality
    - Adapt single-file processing from folder-based approach
    - Construct argument dictionary compatible with parse_args_inference()
    - Implement progress callback mechanism
    - Add exception handling and error conversion
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 7.6_
  
  - [x] 5.2 Implement progress tracking
    - Hook into tqdm progress bars from inference.py
    - Extract progress percentage and stage information
    - Invoke callback to update task status in database
    - _Requirements: 2.6, 3.2_
  
  - [x] 5.3 Write unit tests for inference wrapper
    - Test successful separation with mock model
    - Test error handling and exception conversion
    - Test progress callback invocation
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 7.6_

- [x] 6. Checkpoint - Ensure core components work
  - Ensure all tests pass, ask the user if questions arise.



- [x] 7. Implement Worker Pool
  - [x] 7.1 Create WorkerPool class
    - Implement initialization with ThreadPoolExecutor
    - Implement submit_task() to queue tasks for processing
    - Implement GPU/CPU device assignment logic
    - Implement worker crash recovery
    - Implement graceful shutdown
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5_
  
  - [x] 7.2 Implement task execution worker function
    - Create worker function that processes a single task
    - Load model using ModelManager
    - Invoke InferenceEngine.separate_audio()
    - Update task status throughout processing
    - Handle exceptions and mark tasks as failed
    - _Requirements: 2.2, 2.3, 2.4, 7.6_
  
  - [x] 7.3 Write property tests for worker pool
    - **Property 45: Multi-GPU task distribution**
    - **Property 46: CPU-only sequential processing**
    - **Property 47: Worker pool concurrency limit**
    - **Property 48: Task queuing when workers busy**
    - **Property 49: Worker crash recovery**
    - **Validates: Requirements 11.1, 11.2, 11.3, 11.4, 11.5**
  
  - [x] 7.4 Write unit tests for task execution
    - Test successful task execution
    - Test task failure handling
    - Test status updates during processing
    - _Requirements: 2.2, 2.3, 2.4_

- [x] 8. Implement Task Manager
  - [x] 8.1 Create TaskManager class
    - Implement create_task() with file validation and storage
    - Implement get_task() for task retrieval
    - Implement update_task_status() for status updates
    - Implement cancel_task() for task cancellation
    - Implement cleanup_old_tasks() with configurable retention
    - Generate UUID4 Task_IDs
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 2.1, 3.1, 5.1, 5.2, 5.3, 5.5_
  
  - [x] 8.2 Write property tests for Task Manager
    - **Property 1: File format and size validation**
    - **Property 2: Audio content validation**
    - **Property 5: Task creation and uniqueness**
    - **Property 20: Completed task file cleanup**
    - **Property 21: Task metadata cleanup**
    - **Property 22: Failed task cleanup**
    - **Property 24: Configurable retention periods**
    - **Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5, 5.1, 5.2, 5.3, 5.5**
  
  - [x] 8.3 Write unit tests for task operations
    - Test task creation with various file types
    - Test task cancellation
    - Test cleanup with different retention periods
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 5.1, 5.2, 5.3_



- [x] 9. Implement authentication and rate limiting
  - [x] 9.1 Create AuthMiddleware class
    - Implement FastAPI middleware for API key validation
    - Check Authorization header for Bearer token
    - Return 401 for missing/invalid keys when auth enabled
    - Bypass auth for health and docs endpoints
    - _Requirements: 8.1, 8.2, 8.6_
  
  - [x] 9.2 Create RateLimiter class
    - Implement sliding window rate limiting algorithm
    - Track request counts per API key in memory
    - Return 429 with Retry-After header when limit exceeded
    - Add rate limit headers to all responses
    - _Requirements: 8.3, 8.4, 8.5_
  
  - [x] 9.3 Write property tests for authentication
    - **Property 30: Authentication enforcement**
    - **Property 31: Authentication bypass when disabled**
    - **Validates: Requirements 8.1, 8.2, 8.6**
  
  - [x] 9.4 Write property tests for rate limiting
    - **Property 32: Rate limit enforcement**
    - **Property 33: Rate limit headers**
    - **Validates: Requirements 8.3, 8.4, 8.5**

- [x] 10. Implement REST API endpoints
  - [x] 10.1 Create FastAPI application and request/response models
    - Initialize FastAPI app with metadata
    - Define Pydantic models for all request/response schemas
    - Configure CORS middleware
    - Add authentication and rate limiting middleware
    - _Requirements: 6.1, 6.2_
  
  - [x] 10.2 Implement POST /api/v1/separate endpoint
    - Accept multipart/form-data with audio file and parameters
    - Validate file format, size, and content
    - Validate model parameters
    - Create task via TaskManager
    - Submit task to WorkerPool
    - Return 201 with Task_ID
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 2.1_
  
  - [x] 10.3 Implement GET /api/v1/tasks/{task_id} endpoint
    - Retrieve task from database
    - Return task status and progress
    - Return 404 for non-existent tasks
    - Include estimated completion for processing tasks
    - Include error message for failed tasks
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_
  
  - [x] 10.4 Implement GET /api/v1/tasks/{task_id}/results endpoint
    - Check task status
    - Return 409 if not completed
    - Return 410 if failed
    - Return download URLs for completed tasks
    - _Requirements: 4.1, 4.3, 4.4_
  
  - [x] 10.5 Implement GET /api/v1/download/{task_id}/{filename} endpoint
    - Stream audio file with appropriate headers
    - Support HTTP range requests
    - Return 404 for non-existent files
    - _Requirements: 4.2, 4.7_
  
  - [x] 10.6 Implement DELETE /api/v1/tasks/{task_id} endpoint
    - Cancel pending/processing tasks
    - Delete completed task files and metadata
    - Return 204 on success
    - _Requirements: 5.1, 5.2_



  - [x] 10.7 Implement GET /api/v1/models endpoint
    - Return list of available models from ModelManager
    - Include model capabilities and metadata
    - _Requirements: 12.1_
  
  - [x] 10.8 Implement GET /api/v1/models/{model_type} endpoint
    - Return detailed model information
    - Return 404 for non-existent models
    - _Requirements: 12.2, 12.3_
  
  - [x] 10.9 Implement GET /api/v1/health endpoint
    - Check database connectivity
    - Check disk space availability
    - Check GPU availability
    - Check model loading status
    - Return 200 if healthy, appropriate status if degraded/unhealthy
    - _Requirements: 9.1, 9.2, 9.3, 9.4_
  
  - [x] 10.10 Implement GET /api/v1/metrics endpoint
    - Query database for task statistics
    - Calculate active, queued, completed, failed task counts
    - Calculate average processing time
    - Return server uptime
    - _Requirements: 9.5_
  
  - [x] 10.11 Write property tests for API endpoints
    - **Property 3: Parameter acceptance**
    - **Property 4: Invalid parameter rejection**
    - **Property 6: Asynchronous task queuing**
    - **Property 7: Status transition validity**
    - **Property 9: Task status retrieval**
    - **Property 10: Progress information presence**
    - **Property 11: Non-existent task handling**
    - **Property 14: Completed task results**
    - **Property 15: File download headers**
    - **Property 16: Premature result request handling**
    - **Property 17: Failed task result handling**
    - **Property 19: HTTP range request support**
    - **Validates: Requirements 1.6, 2.1, 3.1, 3.2, 3.3, 4.1, 4.2, 4.3, 4.4, 4.7, 7.2, 7.4, 7.5**
  
  - [x] 10.12 Write unit tests for endpoint error handling
    - Test 400 errors for invalid inputs
    - Test 503 errors for overload conditions
    - Test JSON error response format
    - _Requirements: 7.1, 7.2, 7.3_

- [x] 11. Checkpoint - Ensure API endpoints work
  - Ensure all tests pass, ask the user if questions arise.



- [x] 12. Implement server startup and lifecycle management
  - [x] 12.1 Create server initialization
    - Load configuration
    - Initialize database
    - Initialize ModelManager and validate models
    - Initialize TaskManager
    - Initialize WorkerPool
    - Resume incomplete tasks from previous session
    - _Requirements: 5.4, 10.1, 10.2, 12.4, 12.5_
  
  - [x] 12.2 Create cleanup background task
    - Implement periodic cleanup task using FastAPI background tasks
    - Run cleanup every hour
    - Call TaskManager.cleanup_old_tasks()
    - _Requirements: 5.1, 5.2, 5.3_
  
  - [x] 12.3 Create graceful shutdown handler
    - Implement shutdown event handler
    - Stop accepting new tasks
    - Wait for active tasks to complete (with timeout)
    - Close database connections
    - Shutdown worker pool
    - _Requirements: 11.5_
  
  - [x] 12.4 Create main entry point
    - Create api_server/main.py with uvicorn server startup
    - Add command-line arguments for config file path
    - Configure logging
    - _Requirements: 9.6, 10.1_
  
  - [x] 12.5 Write property tests for server lifecycle
    - **Property 23: Task resumption on restart**
    - **Property 44: Configuration change requires restart**
    - **Validates: Requirements 5.4, 10.7**
  
  - [x] 12.6 Write unit tests for startup and shutdown
    - Test server initialization with valid config
    - Test graceful shutdown
    - Test task resumption
    - _Requirements: 5.4, 10.1, 10.2_

- [x] 13. Implement logging
  - [x] 13.1 Configure structured logging
    - Set up Python logging with JSON formatter
    - Configure log levels from config file
    - Configure log file rotation
    - _Requirements: 9.6_
  
  - [x] 13.2 Add logging throughout application
    - Log all API requests with request ID
    - Log all task status changes
    - Log all errors with stack traces
    - Log authentication and rate limiting events
    - _Requirements: 9.6_
  
  - [x] 13.3 Write property test for logging
    - **Property 39: Request logging**
    - **Validates: Requirements 9.6**



- [x] 14. Implement health check properties
  - [x] 14.1 Write property tests for health checks
    - **Property 34: Health check success**
    - **Property 35: Health check completeness**
    - **Property 36: Degraded health detection**
    - **Property 37: Unhealthy status detection**
    - **Property 38: Metrics completeness**
    - **Validates: Requirements 9.1, 9.2, 9.3, 9.4, 9.5**

- [x] 15. Implement output format handling
  - [x] 15.1 Add output format logic to InferenceEngine
    - Pass output_format and pcm_type to inference wrapper
    - Ensure generated files match requested format
    - _Requirements: 4.5, 4.6_
  
  - [x] 15.2 Write property tests for output format
    - **Property 18: Output format preservation**
    - **Validates: Requirements 4.5**

- [x] 16. Implement task ordering property
  - [x] 16.1 Write property test for FIFO ordering
    - **Property 8: FIFO task processing order**
    - **Validates: Requirements 2.5**

- [x] 17. Implement error handling properties
  - [x] 17.1 Write property tests for error handling
    - **Property 26: JSON error response format**
    - **Property 27: Service overload handling**
    - **Property 28: Inference engine error isolation**
    - **Property 29: Model loading error handling**
    - **Validates: Requirements 7.1, 7.3, 7.6, 7.7**

- [x] 18. Implement status transition property
  - [x] 18.1 Write property test for status transitions
    - **Property 7: Status transition validity**
    - **Property 12: Processing task metadata**
    - **Property 13: Failed task error details**
    - **Validates: Requirements 2.2, 2.3, 2.4, 3.4, 3.5**

- [x] 19. Implement documentation validation
  - [x] 19.1 Write property test for OpenAPI documentation
    - **Property 25: OpenAPI specification completeness**
    - **Validates: Requirements 6.3, 6.4, 6.5**

- [x] 20. Create integration tests
  - [x] 20.1 Write end-to-end integration tests
    - Test complete workflow: submit task → check status → download results
    - Test concurrent task submissions
    - Test authentication and rate limiting integration
    - Test cleanup integration
    - _Requirements: 1.1, 2.1, 3.1, 4.1, 5.1, 8.1, 8.3_

- [x] 21. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 22. Create documentation
  - [x] 22.1 Create README for API server
    - Document installation and setup
    - Document configuration options
    - Document how to run the server
    - Include example API requests
    - _Requirements: 6.1, 6.2_
  
  - [x] 22.2 Add inline code documentation
    - Add docstrings to all classes and functions
    - Document all parameters and return values
    - Add usage examples in docstrings
    - _Requirements: 6.1_

## Notes

- Tasks marked with `*` are optional property-based and unit tests that can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation at key milestones
- Property tests validate universal correctness properties across randomized inputs
- Unit tests validate specific examples, edge cases, and integration points
- The implementation builds incrementally: infrastructure → processing → API → lifecycle
- All code integrates with existing inference.py without modifying it
