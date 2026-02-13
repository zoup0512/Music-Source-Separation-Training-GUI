# Configuration Loader

The configuration loader provides functionality to load server configuration from YAML or JSON files with automatic fallback to sensible defaults.

## Usage

### Basic Usage

```python
from api_server.utils import load_config

# Load from YAML file
config = load_config("api_server_config.yaml")

# Load from JSON file
config = load_config("config.json")

# Use defaults (no file)
config = load_config()
```

### Accessing Configuration Values

```python
config = load_config("api_server_config.yaml")

# Server settings
print(f"Host: {config.server.host}")
print(f"Port: {config.server.port}")
print(f"Workers: {config.server.workers}")

# File settings
print(f"Max file size: {config.files.max_file_size_mb} MB")
print(f"Upload dir: {config.files.upload_dir}")

# Model settings
print(f"Default model: {config.models.default_model_type}")
print(f"Device IDs: {config.models.device_ids}")

# Authentication
if config.auth.enabled:
    print(f"Auth enabled with {len(config.auth.api_keys)} keys")
```

### Saving Configuration

```python
from api_server.utils import save_config
from api_server.models.config import ServerConfig

# Create custom configuration
config = ServerConfig()
config.server.port = 9000
config.server.workers = 4

# Save to YAML
save_config(config, "custom_config.yaml")

# Save to JSON
save_config(config, "custom_config.json")
```

### Error Handling

```python
from api_server.utils import load_config, ConfigurationError

try:
    config = load_config("config.yaml")
except ConfigurationError as e:
    print(f"Configuration error: {e}")
    # Handle error (e.g., exit with error message)
```

## Features

### Default Fallback (Requirement 10.2)

If the configuration file is missing, the loader automatically uses sensible defaults:

```python
# File doesn't exist - uses defaults
config = load_config("nonexistent.yaml")
# Logs warning: "Configuration file not found: nonexistent.yaml. Using default configuration."
```

### Validation (Requirement 10.3)

Invalid configuration values are caught with descriptive error messages:

```python
# config.yaml contains: server: { port: 70000 }
try:
    config = load_config("config.yaml")
except ConfigurationError as e:
    print(e)
    # Output: Invalid configuration in 'config.yaml':
    #   - Value constraint violation for server.port: Input should be less than or equal to 65535
```

### Supported Formats (Requirement 10.1)

- **YAML**: `.yaml` or `.yml` extensions
- **JSON**: `.json` extension

### Partial Configuration

You can provide partial configuration - missing values use defaults:

```yaml
# minimal_config.yaml
server:
  port: 9000
```

```python
config = load_config("minimal_config.yaml")
# config.server.port = 9000 (custom)
# config.server.host = "0.0.0.0" (default)
# config.server.workers = 1 (default)
```

## Configuration Structure

See `api_server_config.yaml` for a complete example with all available options.

### Main Sections

- **server**: Host, port, worker threads
- **files**: File size limits, upload/output directories
- **cleanup**: Automatic cleanup settings
- **models**: Model configuration and GPU settings
- **auth**: API key authentication
- **rate_limit**: Rate limiting per API key
- **database**: Database file path
- **logging**: Log level and file path

## Validation Rules

The loader validates all configuration values:

- Port must be between 1 and 65535
- Workers must be >= 1
- File size must be between 1 and 10000 MB
- Retention periods must be >= 1
- Device IDs must be non-negative
- Log level must be one of: DEBUG, INFO, WARNING, ERROR, CRITICAL
- Upload and output directories must be different
- If auth is enabled, at least one API key must be provided

## Examples

### Development Configuration

```yaml
server:
  host: "127.0.0.1"
  port: 8000
  workers: 1

models:
  force_cpu: true

logging:
  level: "DEBUG"
```

### Production Configuration

```yaml
server:
  host: "0.0.0.0"
  port: 8000
  workers: 4

files:
  max_file_size_mb: 1000
  upload_dir: "/var/lib/api_server/uploads"
  output_dir: "/var/lib/api_server/outputs"

cleanup:
  enabled: true
  completed_retention_hours: 48

models:
  default_model_type: "mdx23c"
  device_ids: [0, 1, 2, 3]

auth:
  enabled: true
  api_keys:
    - "secure-key-1"
    - "secure-key-2"

rate_limit:
  enabled: true
  requests_per_hour: 500

database:
  path: "/var/lib/api_server/api_server.db"

logging:
  level: "INFO"
  file: "/var/log/api_server.log"
```
