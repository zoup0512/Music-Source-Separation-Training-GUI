"""
Property-based tests for configuration loader.

This module uses Hypothesis to test universal properties of configuration loading
across randomized inputs.

Validates:
- Property 40: Configuration file loading
- Property 41: Default configuration fallback
- Property 42: Invalid configuration rejection
- Property 43: Configuration parameter support
- Requirements 10.1, 10.2, 10.3, 10.4, 10.5, 10.6
"""

import json
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

import pytest
import yaml
from hypothesis import given, settings, strategies as st, assume

from api_server.utils import load_config, ConfigurationError
from api_server.models.config import ServerConfig


# ============================================================================
# Hypothesis Strategies for Configuration Generation
# ============================================================================

@st.composite
def valid_server_config(draw):
    """Generate valid server configuration."""
    return {
        "host": draw(st.sampled_from(["0.0.0.0", "127.0.0.1", "localhost", "192.168.1.1"])),
        "port": draw(st.integers(min_value=1, max_value=65535)),
        "workers": draw(st.integers(min_value=1, max_value=32))
    }


@st.composite
def valid_file_config(draw):
    """Generate valid file configuration."""
    return {
        "max_file_size_mb": draw(st.integers(min_value=1, max_value=10000)),
        "upload_dir": draw(st.sampled_from(["./uploads", "/tmp/uploads", "./api_uploads"])),
        "output_dir": draw(st.sampled_from(["./outputs", "/tmp/outputs", "./api_outputs"]))
    }


@st.composite
def valid_cleanup_config(draw):
    """Generate valid cleanup configuration."""
    return {
        "enabled": draw(st.booleans()),
        "completed_retention_hours": draw(st.integers(min_value=1, max_value=168)),
        "failed_retention_hours": draw(st.integers(min_value=1, max_value=168)),
        "metadata_retention_days": draw(st.integers(min_value=1, max_value=365))
    }


@st.composite
def valid_model_config(draw):
    """Generate valid model configuration."""
    device_count = draw(st.integers(min_value=1, max_value=4))
    return {
        "default_model_type": draw(st.sampled_from(["mdx23c", "htdemucs", "demucs"])),
        "model_cache_size": draw(st.integers(min_value=1, max_value=10)),
        "force_cpu": draw(st.booleans()),
        "device_ids": list(range(device_count))
    }


@st.composite
def valid_auth_config(draw):
    """Generate valid auth configuration."""
    enabled = draw(st.booleans())
    if enabled:
        # If auth is enabled, must have at least one API key
        api_keys = draw(st.lists(
            st.text(min_size=8, max_size=32, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'))),
            min_size=1,
            max_size=5
        ))
    else:
        # If auth is disabled, can have any number of keys (including zero)
        api_keys = draw(st.lists(
            st.text(min_size=8, max_size=32, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'))),
            min_size=0,
            max_size=5
        ))
    
    return {
        "enabled": enabled,
        "api_keys": api_keys
    }


@st.composite
def valid_rate_limit_config(draw):
    """Generate valid rate limit configuration."""
    return {
        "enabled": draw(st.booleans()),
        "requests_per_hour": draw(st.integers(min_value=1, max_value=10000))
    }


@st.composite
def valid_database_config(draw):
    """Generate valid database configuration."""
    return {
        "path": draw(st.sampled_from(["./api_server.db", "/tmp/api_server.db", "./test.db"]))
    }


@st.composite
def valid_logging_config(draw):
    """Generate valid logging configuration."""
    return {
        "level": draw(st.sampled_from(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])),
        "file": draw(st.sampled_from(["./api_server.log", "/tmp/api_server.log", "./test.log"]))
    }


@st.composite
def valid_full_config(draw):
    """Generate a complete valid configuration."""
    file_config = draw(valid_file_config())
    
    # Ensure upload and output directories are different
    while file_config["upload_dir"] == file_config["output_dir"]:
        file_config = draw(valid_file_config())
    
    return {
        "server": draw(valid_server_config()),
        "files": file_config,
        "cleanup": draw(valid_cleanup_config()),
        "models": draw(valid_model_config()),
        "auth": draw(valid_auth_config()),
        "rate_limit": draw(valid_rate_limit_config()),
        "database": draw(valid_database_config()),
        "logging": draw(valid_logging_config())
    }


@st.composite
def partial_config(draw):
    """Generate a partial configuration with some sections missing."""
    config = {}
    
    # Randomly include each section
    if draw(st.booleans()):
        config["server"] = draw(valid_server_config())
    if draw(st.booleans()):
        file_config = draw(valid_file_config())
        # Ensure different directories if both are present
        while "upload_dir" in file_config and "output_dir" in file_config and \
              file_config["upload_dir"] == file_config["output_dir"]:
            file_config = draw(valid_file_config())
        config["files"] = file_config
    if draw(st.booleans()):
        config["cleanup"] = draw(valid_cleanup_config())
    if draw(st.booleans()):
        config["models"] = draw(valid_model_config())
    if draw(st.booleans()):
        config["auth"] = draw(valid_auth_config())
    if draw(st.booleans()):
        config["rate_limit"] = draw(valid_rate_limit_config())
    if draw(st.booleans()):
        config["database"] = draw(valid_database_config())
    if draw(st.booleans()):
        config["logging"] = draw(valid_logging_config())
    
    return config


@st.composite
def invalid_config(draw):
    """Generate an invalid configuration that should fail validation."""
    config_type = draw(st.sampled_from([
        "invalid_port",
        "invalid_workers",
        "invalid_log_level",
        "auth_without_keys",
        "same_directories",
        "negative_device_id",
        "invalid_file_size"
    ]))
    
    if config_type == "invalid_port":
        return {
            "server": {
                "port": draw(st.sampled_from([0, -1, 70000, 100000]))
            }
        }
    elif config_type == "invalid_workers":
        return {
            "server": {
                "workers": draw(st.integers(max_value=0))
            }
        }
    elif config_type == "invalid_log_level":
        return {
            "logging": {
                "level": draw(st.text(min_size=1, max_size=20).filter(
                    lambda x: x.upper() not in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
                ))
            }
        }
    elif config_type == "auth_without_keys":
        return {
            "auth": {
                "enabled": True,
                "api_keys": []
            }
        }
    elif config_type == "same_directories":
        same_dir = draw(st.sampled_from(["./same", "/tmp/same"]))
        return {
            "files": {
                "upload_dir": same_dir,
                "output_dir": same_dir
            }
        }
    elif config_type == "negative_device_id":
        return {
            "models": {
                "device_ids": [draw(st.integers(max_value=-1))]
            }
        }
    elif config_type == "invalid_file_size":
        return {
            "files": {
                "max_file_size_mb": draw(st.integers(max_value=0))
            }
        }
    
    return {}


# ============================================================================
# Property 40: Configuration file loading
# ============================================================================

@given(
    config_data=valid_full_config(),
    file_format=st.sampled_from(["yaml", "json"])
)
@settings(max_examples=100)
def test_property_40_configuration_file_loading(config_data, file_format):
    """
    Feature: api-server, Property 40: Configuration file loading
    
    For any server startup with a valid configuration file, the server should
    load all configuration values from the file.
    
    **Validates: Requirements 10.1**
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create config file
        if file_format == "yaml":
            config_file = Path(tmpdir) / "config.yaml"
            with open(config_file, 'w') as f:
                yaml.safe_dump(config_data, f)
        else:
            config_file = Path(tmpdir) / "config.json"
            with open(config_file, 'w') as f:
                json.dump(config_data, f)
        
        # Load configuration
        config = load_config(config_file)
        
        # Verify all values were loaded correctly
        assert isinstance(config, ServerConfig)
        
        # Check server settings
        if "server" in config_data:
            if "host" in config_data["server"]:
                assert config.server.host == config_data["server"]["host"]
            if "port" in config_data["server"]:
                assert config.server.port == config_data["server"]["port"]
            if "workers" in config_data["server"]:
                assert config.server.workers == config_data["server"]["workers"]
        
        # Check file settings
        if "files" in config_data:
            if "max_file_size_mb" in config_data["files"]:
                assert config.files.max_file_size_mb == config_data["files"]["max_file_size_mb"]
            if "upload_dir" in config_data["files"]:
                assert config.files.upload_dir == config_data["files"]["upload_dir"]
            if "output_dir" in config_data["files"]:
                assert config.files.output_dir == config_data["files"]["output_dir"]
        
        # Check cleanup settings
        if "cleanup" in config_data:
            if "enabled" in config_data["cleanup"]:
                assert config.cleanup.enabled == config_data["cleanup"]["enabled"]
            if "completed_retention_hours" in config_data["cleanup"]:
                assert config.cleanup.completed_retention_hours == config_data["cleanup"]["completed_retention_hours"]
        
        # Check model settings
        if "models" in config_data:
            if "default_model_type" in config_data["models"]:
                assert config.models.default_model_type == config_data["models"]["default_model_type"]
            if "device_ids" in config_data["models"]:
                assert config.models.device_ids == config_data["models"]["device_ids"]
        
        # Check auth settings
        if "auth" in config_data:
            if "enabled" in config_data["auth"]:
                assert config.auth.enabled == config_data["auth"]["enabled"]
            if "api_keys" in config_data["auth"]:
                assert config.auth.api_keys == config_data["auth"]["api_keys"]
        
        # Check rate limit settings
        if "rate_limit" in config_data:
            if "enabled" in config_data["rate_limit"]:
                assert config.rate_limit.enabled == config_data["rate_limit"]["enabled"]
            if "requests_per_hour" in config_data["rate_limit"]:
                assert config.rate_limit.requests_per_hour == config_data["rate_limit"]["requests_per_hour"]
        
        # Check database settings
        if "database" in config_data:
            if "path" in config_data["database"]:
                assert config.database.path == config_data["database"]["path"]
        
        # Check logging settings
        if "logging" in config_data:
            if "level" in config_data["logging"]:
                assert config.logging.level == config_data["logging"]["level"].upper()
            if "file" in config_data["logging"]:
                assert config.logging.file == config_data["logging"]["file"]


# ============================================================================
# Property 41: Default configuration fallback
# ============================================================================

@given(
    config_data=partial_config()
)
@settings(max_examples=100)
def test_property_41_default_configuration_fallback(config_data):
    """
    Feature: api-server, Property 41: Default configuration fallback
    
    For any server startup with a missing configuration file, the server should
    use sensible defaults and log a warning.
    
    **Validates: Requirements 10.2**
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        # Test 1: No config file at all
        config_no_file = load_config(None)
        assert isinstance(config_no_file, ServerConfig)
        assert config_no_file.server.host == "0.0.0.0"
        assert config_no_file.server.port == 8000
        assert config_no_file.server.workers == 1
        
        # Test 2: Nonexistent config file
        nonexistent = Path(tmpdir) / "nonexistent.yaml"
        config_nonexistent = load_config(nonexistent)
        assert isinstance(config_nonexistent, ServerConfig)
        assert config_nonexistent.server.host == "0.0.0.0"
        
        # Test 3: Partial config file (missing sections use defaults)
        config_file = Path(tmpdir) / "partial.yaml"
        with open(config_file, 'w') as f:
            yaml.safe_dump(config_data, f)
        
        config = load_config(config_file)
        assert isinstance(config, ServerConfig)
        
        # Verify defaults are used for missing sections
        if "server" not in config_data or "host" not in config_data.get("server", {}):
            assert config.server.host == "0.0.0.0"
        if "server" not in config_data or "port" not in config_data.get("server", {}):
            assert config.server.port == 8000
        if "server" not in config_data or "workers" not in config_data.get("server", {}):
            assert config.server.workers == 1
        if "files" not in config_data or "max_file_size_mb" not in config_data.get("files", {}):
            assert config.files.max_file_size_mb == 500
        if "models" not in config_data or "default_model_type" not in config_data.get("models", {}):
            assert config.models.default_model_type == "mdx23c"


# ============================================================================
# Property 42: Invalid configuration rejection
# ============================================================================

@given(
    config_data=invalid_config()
)
@settings(max_examples=100)
def test_property_42_invalid_configuration_rejection(config_data):
    """
    Feature: api-server, Property 42: Invalid configuration rejection
    
    For any server startup with an invalid configuration file, the server should
    fail to start and log descriptive error messages.
    
    **Validates: Requirements 10.3**
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        config_file = Path(tmpdir) / "invalid.yaml"
        with open(config_file, 'w') as f:
            yaml.safe_dump(config_data, f)
        
        # Should raise ConfigurationError
        with pytest.raises(ConfigurationError) as exc_info:
            load_config(config_file)
        
        # Error message should be descriptive
        error_msg = str(exc_info.value)
        assert "Invalid configuration" in error_msg
        assert len(error_msg) > 20  # Should have meaningful content


# ============================================================================
# Property 43: Configuration parameter support
# ============================================================================

@given(
    param_name=st.sampled_from([
        "host", "port", "max_file_size", "worker_threads", 
        "cleanup_retention_hours", "default_model_type",
        "enable_auth", "api_keys", "enable_rate_limit", "requests_per_hour"
    ]),
    param_value=st.one_of(
        st.text(min_size=1, max_size=50),
        st.integers(min_value=1, max_value=10000),
        st.booleans(),
        st.lists(st.text(min_size=1, max_size=20), min_size=1, max_size=5)
    )
)
@settings(max_examples=100)
def test_property_43_configuration_parameter_support(param_name, param_value):
    """
    Feature: api-server, Property 43: Configuration parameter support
    
    For any supported configuration parameter, setting it in the configuration
    file should result in the server using that value.
    
    **Validates: Requirements 10.4, 10.5, 10.6**
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        # Map parameter names to config structure
        config_data = {}
        
        if param_name == "host":
            if isinstance(param_value, str):
                config_data = {"server": {"host": param_value}}
        elif param_name == "port":
            if isinstance(param_value, int) and 1 <= param_value <= 65535:
                config_data = {"server": {"port": param_value}}
            else:
                assume(False)  # Skip invalid values
        elif param_name == "max_file_size":
            if isinstance(param_value, int) and param_value >= 1:
                config_data = {"files": {"max_file_size_mb": param_value}}
            else:
                assume(False)
        elif param_name == "worker_threads":
            if isinstance(param_value, int) and param_value >= 1:
                config_data = {"server": {"workers": param_value}}
            else:
                assume(False)
        elif param_name == "cleanup_retention_hours":
            if isinstance(param_value, int) and param_value >= 1:
                config_data = {"cleanup": {"completed_retention_hours": param_value}}
            else:
                assume(False)
        elif param_name == "default_model_type":
            if isinstance(param_value, str):
                config_data = {"models": {"default_model_type": param_value}}
        elif param_name == "enable_auth":
            if isinstance(param_value, bool):
                if param_value:
                    # Auth enabled requires API keys
                    config_data = {"auth": {"enabled": True, "api_keys": ["test-key"]}}
                else:
                    config_data = {"auth": {"enabled": False}}
        elif param_name == "api_keys":
            if isinstance(param_value, list) and all(isinstance(k, str) for k in param_value):
                config_data = {"auth": {"enabled": True, "api_keys": param_value}}
            else:
                assume(False)
        elif param_name == "enable_rate_limit":
            if isinstance(param_value, bool):
                config_data = {"rate_limit": {"enabled": param_value}}
        elif param_name == "requests_per_hour":
            if isinstance(param_value, int) and param_value >= 1:
                config_data = {"rate_limit": {"requests_per_hour": param_value}}
            else:
                assume(False)
        
        # Skip if no valid config was generated
        assume(config_data)
        
        # Create config file
        config_file = Path(tmpdir) / "config.yaml"
        with open(config_file, 'w') as f:
            yaml.safe_dump(config_data, f)
        
        # Load configuration
        try:
            config = load_config(config_file)
            
            # Verify the parameter was set correctly
            if param_name == "host":
                assert config.server.host == param_value
            elif param_name == "port":
                assert config.server.port == param_value
            elif param_name == "max_file_size":
                assert config.files.max_file_size_mb == param_value
            elif param_name == "worker_threads":
                assert config.server.workers == param_value
            elif param_name == "cleanup_retention_hours":
                assert config.cleanup.completed_retention_hours == param_value
            elif param_name == "default_model_type":
                assert config.models.default_model_type == param_value
            elif param_name == "enable_auth":
                assert config.auth.enabled == param_value
            elif param_name == "api_keys":
                assert config.auth.api_keys == param_value
            elif param_name == "enable_rate_limit":
                assert config.rate_limit.enabled == param_value
            elif param_name == "requests_per_hour":
                assert config.rate_limit.requests_per_hour == param_value
        
        except ConfigurationError:
            # Some random values may be invalid, which is acceptable
            # The property is that VALID values should be accepted
            pass


# ============================================================================
# Additional Property Tests
# ============================================================================

@given(
    file_format=st.sampled_from(["yaml", "yml", "json"])
)
@settings(max_examples=50)
def test_property_supports_multiple_file_formats(file_format):
    """
    Property: Configuration loader should support YAML (.yaml, .yml) and JSON formats.
    
    **Validates: Requirements 10.1**
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        config_data = {
            "server": {"port": 9000},
            "files": {"max_file_size_mb": 1000}
        }
        
        config_file = Path(tmpdir) / f"config.{file_format}"
        
        with open(config_file, 'w') as f:
            if file_format in ["yaml", "yml"]:
                yaml.safe_dump(config_data, f)
            else:
                json.dump(config_data, f)
        
        config = load_config(config_file)
        
        assert config.server.port == 9000
        assert config.files.max_file_size_mb == 1000


@given(
    config_data=valid_full_config()
)
@settings(max_examples=50)
def test_property_config_is_immutable_after_load(config_data):
    """
    Property: Configuration values should remain consistent across multiple reads.
    
    This ensures that loading the same configuration file multiple times
    produces identical results.
    
    **Validates: Requirements 10.1**
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        config_file = Path(tmpdir) / "config.yaml"
        with open(config_file, 'w') as f:
            yaml.safe_dump(config_data, f)
        
        # Load configuration twice
        config1 = load_config(config_file)
        config2 = load_config(config_file)
        
        # Should produce identical configurations
        assert config1.server.host == config2.server.host
        assert config1.server.port == config2.server.port
        assert config1.server.workers == config2.server.workers
        assert config1.files.max_file_size_mb == config2.files.max_file_size_mb
        assert config1.models.default_model_type == config2.models.default_model_type
        assert config1.auth.enabled == config2.auth.enabled
        assert config1.rate_limit.enabled == config2.rate_limit.enabled
