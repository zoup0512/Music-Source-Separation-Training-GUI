"""
Configuration data models for the API server.

This module defines Pydantic models for server configuration with validation.
"""

from typing import List, Optional
from pydantic import BaseModel, Field, field_validator, model_validator
from pathlib import Path


class ServerSettings(BaseModel):
    """Server connection and worker settings."""
    
    host: str = Field(
        default="0.0.0.0",
        description="Host address to bind to"
    )
    port: int = Field(
        default=8000,
        ge=1,
        le=65535,
        description="Port to listen on"
    )
    workers: int = Field(
        default=1,
        ge=1,
        description="Number of concurrent worker threads for task processing"
    )


class FileSettings(BaseModel):
    """File handling settings."""
    
    max_file_size_mb: int = Field(
        default=500,
        ge=1,
        le=10000,
        description="Maximum file size for uploads in MB"
    )
    upload_dir: str = Field(
        default="./api_uploads",
        description="Directory for storing uploaded audio files"
    )
    output_dir: str = Field(
        default="./api_outputs",
        description="Directory for storing separated audio output files"
    )


class CleanupSettings(BaseModel):
    """Task cleanup settings."""
    
    enabled: bool = Field(
        default=True,
        description="Enable automatic cleanup of old tasks"
    )
    completed_retention_hours: int = Field(
        default=24,
        ge=1,
        description="Hours to retain completed task files before deletion"
    )
    failed_retention_hours: int = Field(
        default=24,
        ge=1,
        description="Hours to retain failed task files before deletion"
    )
    metadata_retention_days: int = Field(
        default=7,
        ge=1,
        description="Days to retain task metadata in database before deletion"
    )


class ModelSettings(BaseModel):
    """Model configuration settings."""
    
    default_model_type: str = Field(
        default="mdx23c",
        description="Default model type to use when not specified"
    )
    model_cache_size: int = Field(
        default=3,
        ge=1,
        description="Number of models to keep loaded in memory (LRU cache)"
    )
    force_cpu: bool = Field(
        default=False,
        description="Force CPU-only processing (disable GPU)"
    )
    device_ids: List[int] = Field(
        default_factory=lambda: [0],
        description="GPU device IDs to use for processing"
    )
    
    @field_validator('device_ids')
    @classmethod
    def validate_device_ids(cls, v: List[int]) -> List[int]:
        """Validate that device IDs are non-negative."""
        if not v:
            return [0]  # Default to device 0 if empty
        for device_id in v:
            if device_id < 0:
                raise ValueError(f"Device ID must be non-negative, got {device_id}")
        return v


class AuthSettings(BaseModel):
    """Authentication settings."""
    
    enabled: bool = Field(
        default=False,
        description="Enable API key authentication"
    )
    api_keys: List[str] = Field(
        default_factory=list,
        description="List of valid API keys"
    )
    
    @model_validator(mode='after')
    def validate_auth_keys(self):
        """Validate that API keys are provided when auth is enabled."""
        if self.enabled and not self.api_keys:
            raise ValueError("Authentication is enabled but no API keys are configured")
        return self


class RateLimitSettings(BaseModel):
    """Rate limiting settings."""
    
    enabled: bool = Field(
        default=False,
        description="Enable rate limiting per API key"
    )
    requests_per_hour: int = Field(
        default=100,
        ge=1,
        description="Maximum requests per hour per API key"
    )


class DatabaseSettings(BaseModel):
    """Database settings."""
    
    path: str = Field(
        default="./api_server.db",
        description="Path to SQLite database file"
    )


class LoggingSettings(BaseModel):
    """Logging settings."""
    
    level: str = Field(
        default="INFO",
        description="Log level: DEBUG, INFO, WARNING, ERROR, CRITICAL"
    )
    file: str = Field(
        default="./api_server.log",
        description="Path to log file"
    )
    
    @field_validator('level')
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate that log level is valid."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(
                f"Invalid log level '{v}'. Must be one of: {', '.join(valid_levels)}"
            )
        return v_upper


class ServerConfig(BaseModel):
    """
    Complete server configuration model.
    
    This model represents all configuration settings for the API server,
    loaded from a YAML or JSON configuration file.
    
    Validates:
    - Requirements 10.4: Server configuration parameters
    - Requirements 10.5: Authentication settings
    - Requirements 10.6: Rate limiting settings
    """
    
    server: ServerSettings = Field(default_factory=ServerSettings)
    files: FileSettings = Field(default_factory=FileSettings)
    cleanup: CleanupSettings = Field(default_factory=CleanupSettings)
    models: ModelSettings = Field(default_factory=ModelSettings)
    auth: AuthSettings = Field(default_factory=AuthSettings)
    rate_limit: RateLimitSettings = Field(default_factory=RateLimitSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    
    @model_validator(mode='after')
    def validate_directories(self):
        """Validate that directory paths are reasonable."""
        # Ensure upload and output directories are different
        upload_path = Path(self.files.upload_dir).resolve()
        output_path = Path(self.files.output_dir).resolve()
        
        if upload_path == output_path:
            raise ValueError(
                "Upload directory and output directory must be different"
            )
        
        return self
    
    def model_dump_yaml(self) -> dict:
        """
        Export configuration as a dictionary suitable for YAML serialization.
        
        Returns:
            Dictionary with nested structure matching YAML format
        """
        return self.model_dump(mode='json', exclude_none=True)
