"""
Configuration loader for the API server.

This module provides functionality to load server configuration from YAML or JSON files,
with fallback to default values and comprehensive validation.

Validates:
- Requirements 10.1: Load configuration from YAML or JSON file
- Requirements 10.2: Use sensible defaults when configuration file is missing
- Requirements 10.3: Fail to start with descriptive errors for invalid configuration
"""

import json
import logging
from pathlib import Path
from typing import Optional, Union

import yaml
from pydantic import ValidationError

from api_server.models.config import ServerConfig


logger = logging.getLogger(__name__)


class ConfigurationError(Exception):
    """Raised when configuration loading or validation fails."""
    pass


def load_config(config_path: Optional[Union[str, Path]] = None) -> ServerConfig:
    """
    Load server configuration from a YAML or JSON file.
    
    This function attempts to load configuration from the specified file path.
    If the file is missing, it logs a warning and returns default configuration.
    If the file exists but contains invalid values, it raises ConfigurationError
    with descriptive error messages.
    
    Args:
        config_path: Path to configuration file (YAML or JSON). If None, uses defaults.
    
    Returns:
        ServerConfig: Validated server configuration object
    
    Raises:
        ConfigurationError: If configuration file exists but is invalid
    
    Examples:
        >>> # Load from YAML file
        >>> config = load_config("api_server_config.yaml")
        
        >>> # Load from JSON file
        >>> config = load_config("config.json")
        
        >>> # Use defaults (no file)
        >>> config = load_config()
    
    Validates:
        - Requirements 10.1: Load configuration from YAML or JSON file
        - Requirements 10.2: Use sensible defaults when configuration file is missing
        - Requirements 10.3: Fail with descriptive errors for invalid configuration
    """
    # If no config path provided, use defaults
    if config_path is None:
        logger.warning(
            "No configuration file specified, using default configuration"
        )
        return ServerConfig()
    
    config_file = Path(config_path)
    
    # If config file doesn't exist, use defaults and log warning
    if not config_file.exists():
        logger.warning(
            f"Configuration file not found: {config_file}. "
            f"Using default configuration."
        )
        return ServerConfig()
    
    # Load configuration from file
    try:
        config_data = _load_config_file(config_file)
    except Exception as e:
        raise ConfigurationError(
            f"Failed to read configuration file '{config_file}': {e}"
        ) from e
    
    # Validate and create ServerConfig
    try:
        config = ServerConfig(**config_data)
        logger.info(f"Successfully loaded configuration from {config_file}")
        return config
    except ValidationError as e:
        # Format validation errors into descriptive messages
        error_messages = _format_validation_errors(e)
        raise ConfigurationError(
            f"Invalid configuration in '{config_file}':\n" + "\n".join(error_messages)
        ) from e


def _load_config_file(config_file: Path) -> dict:
    """
    Load configuration data from YAML or JSON file.
    
    Args:
        config_file: Path to configuration file
    
    Returns:
        Dictionary containing configuration data
    
    Raises:
        ValueError: If file format is not supported
        yaml.YAMLError: If YAML parsing fails
        json.JSONDecodeError: If JSON parsing fails
    """
    suffix = config_file.suffix.lower()
    
    with open(config_file, 'r', encoding='utf-8') as f:
        if suffix in ['.yaml', '.yml']:
            return yaml.safe_load(f) or {}
        elif suffix == '.json':
            return json.load(f)
        else:
            raise ValueError(
                f"Unsupported configuration file format: {suffix}. "
                f"Supported formats: .yaml, .yml, .json"
            )


def _format_validation_errors(validation_error: ValidationError) -> list[str]:
    """
    Format Pydantic validation errors into human-readable messages.
    
    Args:
        validation_error: Pydantic ValidationError
    
    Returns:
        List of formatted error messages
    """
    error_messages = []
    
    for error in validation_error.errors():
        # Get the field path (e.g., "server.port" or "auth.api_keys")
        field_path = ".".join(str(loc) for loc in error['loc'])
        
        # Get the error message
        msg = error['msg']
        
        # Get the error type for additional context
        error_type = error['type']
        
        # Format based on error type
        if error_type == 'missing':
            error_messages.append(
                f"  - Missing required field: {field_path}"
            )
        elif error_type in ['value_error', 'assertion_error']:
            error_messages.append(
                f"  - Invalid value for {field_path}: {msg}"
            )
        elif 'greater_than' in error_type or 'less_than' in error_type:
            error_messages.append(
                f"  - Value constraint violation for {field_path}: {msg}"
            )
        else:
            error_messages.append(
                f"  - Error in {field_path}: {msg}"
            )
    
    return error_messages


def save_config(config: ServerConfig, config_path: Union[str, Path]) -> None:
    """
    Save server configuration to a YAML or JSON file.
    
    This is a utility function for generating configuration files from
    ServerConfig objects. Useful for creating template configurations.
    
    Args:
        config: ServerConfig object to save
        config_path: Path where configuration file should be saved
    
    Raises:
        ValueError: If file format is not supported
        IOError: If file cannot be written
    
    Examples:
        >>> config = ServerConfig()
        >>> save_config(config, "api_server_config.yaml")
    """
    config_file = Path(config_path)
    suffix = config_file.suffix.lower()
    
    config_data = config.model_dump_yaml()
    
    with open(config_file, 'w', encoding='utf-8') as f:
        if suffix in ['.yaml', '.yml']:
            yaml.safe_dump(config_data, f, default_flow_style=False, sort_keys=False)
        elif suffix == '.json':
            json.dump(config_data, f, indent=2)
        else:
            raise ValueError(
                f"Unsupported configuration file format: {suffix}. "
                f"Supported formats: .yaml, .yml, .json"
            )
    
    logger.info(f"Configuration saved to {config_file}")
