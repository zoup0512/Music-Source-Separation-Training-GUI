# Requirements Document: API Server for Music Source Separation

## Introduction

This document specifies the requirements for adding RESTful API server functionality to the MSST-GUI (Music Source Separation Training GUI) project. The API server will expose the existing audio source separation capabilities via HTTP endpoints, enabling programmatic access to the inference functionality currently available only through the GUI interface.

The API server will allow external applications and services to submit audio files for source separation, configure separation parameters, track processing status, and retrieve results asynchronously.

## Glossary

- **API_Server**: The HTTP server component that exposes source separation functionality via RESTful endpoints
- **Separation_Task**: An asynchronous job that processes an audio file to separate it into constituent sources (vocals, instrumental, drums, etc.)
- **Task_ID**: A unique identifier assigned to each Separation_Task for tracking and result retrieval
- **Source**: An individual audio component extracted from a mixture (e.g., vocals, drums, bass, instrumental)
- **TTA**: Test Time Augmentation - a technique that processes audio with polarity and channel inversions to improve separation quality
- **Client**: An external application or service that consumes the API_Server endpoints
- **Model_Config**: A configuration file that defines the neural network architecture and parameters for source separation
- **Inference_Engine**: The existing proc_folder functionality from inference.py that performs the actual audio separation

## Requirements

### Requirement 1: Task Submission

**User Story:** As a developer, I want to submit audio files for source separation via HTTP POST, so that I can integrate audio separation into my application workflow.

#### Acceptance Criteria

1. WHEN a Client submits an audio file via POST request, THE API_Server SHALL accept files in WAV, FLAC, MP3, OGG, and M4A formats
2. WHEN a Client submits a separation request, THE API_Server SHALL validate the file size does not exceed 500MB
3. WHEN a Client submits a separation request, THE API_Server SHALL validate the audio file is readable and contains valid audio data
4. WHEN a valid audio file is submitted, THE API_Server SHALL create a Separation_Task and return a unique Task_ID
5. WHEN an invalid file is submitted, THE API_Server SHALL return an HTTP 400 error with a descriptive error message
6. WHEN a Client submits a separation request, THE API_Server SHALL accept optional parameters for model_type, instruments, use_tta, extract_instrumental, output_format, and pcm_type
7. WHEN no model_type is specified, THE API_Server SHALL use a default model configuration
8. WHEN the API_Server receives a submission request, THE API_Server SHALL return the Task_ID within 2 seconds

### Requirement 2: Asynchronous Task Processing

**User Story:** As a developer, I want separation tasks to process asynchronously, so that my application doesn't block while waiting for long-running audio processing.

#### Acceptance Criteria

1. WHEN a Separation_Task is created, THE API_Server SHALL queue it for background processing without blocking the HTTP response
2. WHEN a Separation_Task begins processing, THE API_Server SHALL update its status to "processing"
3. WHEN a Separation_Task completes successfully, THE API_Server SHALL update its status to "completed"
4. IF a Separation_Task encounters an error, THEN THE API_Server SHALL update its status to "failed" and store the error message
5. WHEN multiple Separation_Tasks are queued, THE API_Server SHALL process them in FIFO order
6. WHEN a Separation_Task is processing, THE API_Server SHALL update progress information at least every 5 seconds

### Requirement 3: Task Status Tracking

**User Story:** As a developer, I want to query the status of my separation tasks, so that I can monitor progress and know when results are ready.

#### Acceptance Criteria

1. WHEN a Client requests task status with a valid Task_ID, THE API_Server SHALL return the current status (pending, processing, completed, or failed)
2. WHEN a Client requests task status, THE API_Server SHALL return progress information including percentage complete and current processing stage
3. WHEN a Client requests status for a non-existent Task_ID, THE API_Server SHALL return an HTTP 404 error
4. WHEN a Separation_Task is in "processing" status, THE API_Server SHALL include estimated time remaining in the status response
5. WHEN a Separation_Task has "failed" status, THE API_Server SHALL include the error message in the status response
6. WHEN a Client requests task status, THE API_Server SHALL respond within 500 milliseconds

### Requirement 4: Result Retrieval

**User Story:** As a developer, I want to download separated audio sources, so that I can use them in my application.

#### Acceptance Criteria

1. WHEN a Client requests results for a completed Separation_Task, THE API_Server SHALL return download URLs for all separated sources
2. WHEN a Client downloads a separated source file, THE API_Server SHALL stream the audio file with appropriate Content-Type headers
3. WHEN a Client requests results for a Task_ID that is not completed, THE API_Server SHALL return an HTTP 409 error indicating the task is not ready
4. WHEN a Client requests results for a failed Separation_Task, THE API_Server SHALL return an HTTP 410 error with the failure reason
5. WHEN separated audio files are generated, THE API_Server SHALL store them in the output format specified in the original request (WAV or FLAC)
6. WHEN no output format was specified, THE API_Server SHALL default to WAV format with PCM_24 encoding
7. WHEN a Client downloads result files, THE API_Server SHALL support HTTP range requests for partial downloads

### Requirement 5: Task Cleanup

**User Story:** As a system administrator, I want old task data to be automatically cleaned up, so that the server doesn't run out of disk space.

#### Acceptance Criteria

1. WHEN a Separation_Task has been completed for more than 24 hours, THE API_Server SHALL delete the associated audio files
2. WHEN a Separation_Task has been completed for more than 7 days, THE API_Server SHALL delete the task metadata
3. WHEN a Separation_Task has failed for more than 24 hours, THE API_Server SHALL delete any partial output files
4. WHEN the API_Server starts up, THE API_Server SHALL resume any incomplete Separation_Tasks from a previous session
5. WHERE cleanup is configured, THE API_Server SHALL allow administrators to customize retention periods via configuration

### Requirement 6: API Documentation

**User Story:** As a developer, I want interactive API documentation, so that I can understand and test the API endpoints without reading source code.

#### Acceptance Criteria

1. WHEN a Client accesses the API documentation endpoint, THE API_Server SHALL serve an OpenAPI 3.0 specification
2. WHEN a Client accesses the API documentation UI, THE API_Server SHALL provide a Swagger UI interface for interactive testing
3. WHEN viewing API documentation, THE API_Server SHALL include example requests and responses for all endpoints
4. WHEN viewing API documentation, THE API_Server SHALL document all request parameters, their types, and whether they are required or optional
5. WHEN viewing API documentation, THE API_Server SHALL document all possible HTTP status codes and their meanings

### Requirement 7: Error Handling and Validation

**User Story:** As a developer, I want clear error messages, so that I can quickly diagnose and fix integration issues.

#### Acceptance Criteria

1. WHEN the API_Server encounters an error, THE API_Server SHALL return a JSON response with an error code and human-readable message
2. WHEN a Client provides invalid parameters, THE API_Server SHALL return an HTTP 400 error with details about which parameters are invalid
3. WHEN the API_Server is overloaded, THE API_Server SHALL return an HTTP 503 error indicating the service is temporarily unavailable
4. WHEN a Client specifies an unsupported model_type, THE API_Server SHALL return an HTTP 400 error listing valid model types
5. WHEN a Client specifies invalid instrument names, THE API_Server SHALL return an HTTP 400 error listing valid instruments for the selected model
6. IF the Inference_Engine crashes during processing, THEN THE API_Server SHALL catch the exception, mark the task as failed, and continue processing other tasks
7. WHEN the API_Server cannot load a required model file, THE API_Server SHALL return an HTTP 500 error on task submission

### Requirement 8: Authentication and Rate Limiting

**User Story:** As a system administrator, I want to control API access, so that I can prevent abuse and manage server resources.

#### Acceptance Criteria

1. WHERE authentication is enabled, THE API_Server SHALL require an API key in the Authorization header for all requests
2. WHERE authentication is enabled, WHEN a Client provides an invalid API key, THEN THE API_Server SHALL return an HTTP 401 error
3. WHERE rate limiting is enabled, THE API_Server SHALL limit each API key to a configurable number of requests per hour
4. WHERE rate limiting is enabled, WHEN a Client exceeds their rate limit, THEN THE API_Server SHALL return an HTTP 429 error with a Retry-After header
5. WHERE rate limiting is enabled, THE API_Server SHALL include rate limit information in response headers (X-RateLimit-Limit, X-RateLimit-Remaining, X-RateLimit-Reset)
6. WHERE authentication is disabled, THE API_Server SHALL allow all requests without requiring an API key

### Requirement 9: Health and Monitoring

**User Story:** As a system administrator, I want to monitor server health, so that I can ensure the service is operating correctly.

#### Acceptance Criteria

1. WHEN a Client requests the health endpoint, THE API_Server SHALL return HTTP 200 if all systems are operational
2. WHEN a Client requests the health endpoint, THE API_Server SHALL include status of critical dependencies (model loading, disk space, GPU availability)
3. WHEN available disk space falls below 10GB, THE API_Server SHALL report degraded health status
4. WHEN the API_Server cannot access required model files, THE API_Server SHALL report unhealthy status
5. WHEN a Client requests server metrics, THE API_Server SHALL return statistics including active tasks, queued tasks, completed tasks, and average processing time
6. WHEN the API_Server processes tasks, THE API_Server SHALL log all requests, errors, and processing times to a structured log file

### Requirement 10: Configuration Management

**User Story:** As a system administrator, I want to configure the API server via a configuration file, so that I can customize behavior without modifying code.

#### Acceptance Criteria

1. WHEN the API_Server starts, THE API_Server SHALL load configuration from a YAML or JSON file
2. WHEN the configuration file is missing, THE API_Server SHALL use sensible defaults and log a warning
3. WHEN the configuration file contains invalid values, THE API_Server SHALL fail to start and log descriptive error messages
4. THE API_Server SHALL support configuration of host, port, max_file_size, worker_threads, cleanup_retention_hours, and default_model_type
5. THE API_Server SHALL support configuration of authentication settings including enable_auth and api_keys list
6. THE API_Server SHALL support configuration of rate limiting including enable_rate_limit and requests_per_hour
7. WHEN configuration values are updated, THE API_Server SHALL require a restart to apply changes

### Requirement 11: Concurrent Processing

**User Story:** As a system administrator, I want to process multiple separation tasks concurrently, so that I can maximize hardware utilization.

#### Acceptance Criteria

1. WHERE multiple GPUs are available, THE API_Server SHALL distribute Separation_Tasks across available GPUs
2. WHERE only CPU is available, THE API_Server SHALL process Separation_Tasks sequentially to avoid memory exhaustion
3. WHEN the API_Server is configured with a worker pool, THE API_Server SHALL process up to N tasks concurrently where N is the configured worker count
4. WHEN all workers are busy, THE API_Server SHALL queue additional Separation_Tasks until a worker becomes available
5. WHEN a worker crashes, THE API_Server SHALL restart the worker and requeue the failed task
6. THE API_Server SHALL prevent concurrent tasks from exceeding available GPU memory

### Requirement 12: Model Management

**User Story:** As a developer, I want to query available models and their capabilities, so that I can choose the appropriate model for my use case.

#### Acceptance Criteria

1. WHEN a Client requests the models list endpoint, THE API_Server SHALL return all available model types and their configuration paths
2. WHEN a Client requests model details, THE API_Server SHALL return supported instruments, sample rate, and whether the model supports stereo input
3. WHEN a Client requests model details for a non-existent model, THE API_Server SHALL return an HTTP 404 error
4. WHEN the API_Server starts, THE API_Server SHALL validate that all configured models have their required checkpoint files present
5. WHEN a model checkpoint file is missing, THE API_Server SHALL log a warning and exclude that model from the available models list
