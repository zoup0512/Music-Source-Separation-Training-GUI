"""
Unit tests for configuration loader.

Tests configuration loading from YAML/JSON files, default fallback,
and validation error handling.

Validates:
- Requirements 10.1: Load configuration from YAML or JSON file
- Requirements 10.2: Use sensible defaults when configuration file is missing
- Requirements 10.3: Fail with descriptive errors for invalid configuration
"""

import json
import tempfile
from pathlib import Path

import pytest
import yaml

from api_server.utils import load_config, save_config, ConfigurationError
from api_server.models.config import ServerConfig


class TestLoadConfigDefaults:
    """Tests for default configuration fallback."""
    
    def test_load_config_no_path(self):
        """Test that load_config() with no path returns default config."""
        config = load_config()
        
        assert isinstance(config, ServerConfig)
        assert config.server.host == "0.0.0.0"
        assert config.server.port == 8000
        assert config.files.max_file_size_mb == 500
    
    def test_load_config_nonexistent_file(self, tmp_path):
        """Test that load_config() with nonexistent file returns defaults."""
        nonexistent = tmp_path / "nonexistent.yaml"
        config = load_config(nonexistent)
        
        assert isinstance(config, ServerConfig)
        assert config.server.host == "0.0.0.0"
        assert config.server.port == 8000


class TestLoadConfigYAML:
    """Tests for loading configuration from YAML files."""
    
    def test_load_valid_yaml(self, tmp_path):
        """Test loading valid YAML configuration."""
        config_file = tmp_path / "config.yaml"
        config_data = {
            "server": {
                "host": "127.0.0.1",
                "port": 9000,
                "workers": 4
            },
            "files": {
                "max_file_size_mb": 1000
            }
        }
        
        with open(config_file, 'w') as f:
            yaml.safe_dump(config_data, f)
        
        config = load_config(config_file)
        
        assert config.server.host == "127.0.0.1"
        assert config.server.port == 9000
        assert config.server.workers == 4
        assert config.files.max_file_size_mb == 1000
    
    def test_load_partial_yaml(self, tmp_path):
        """Test loading partial YAML with defaults for missing values."""
        config_file = tmp_path / "config.yml"
        config_data = {
            "server": {
                "port": 8080
            }
        }
        
        with open(config_file, 'w') as f:
            yaml.safe_dump(config_data, f)
        
        config = load_config(config_file)
        
        # Custom value
        assert config.server.port == 8080
        
        # Default values
        assert config.server.host == "0.0.0.0"
        assert config.server.workers == 1
        assert config.files.max_file_size_mb == 500
    
    def test_load_empty_yaml(self, tmp_path):
        """Test loading empty YAML file returns defaults."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("")
        
        config = load_config(config_file)
        
        assert isinstance(config, ServerConfig)
        assert config.server.host == "0.0.0.0"
    
    def test_load_yaml_with_all_sections(self, tmp_path):
        """Test loading YAML with all configuration sections."""
        config_file = tmp_path / "config.yaml"
        config_data = {
            "server": {"host": "localhost", "port": 8080, "workers": 2},
            "files": {
                "max_file_size_mb": 250,
                "upload_dir": "/tmp/uploads",
                "output_dir": "/tmp/outputs"
            },
            "cleanup": {
                "enabled": True,
                "completed_retention_hours": 48,
                "failed_retention_hours": 12,
                "metadata_retention_days": 14
            },
            "models": {
                "default_model_type": "htdemucs",
                "model_cache_size": 5,
                "force_cpu": False,
                "device_ids": [0, 1]
            },
            "auth": {
                "enabled": True,
                "api_keys": ["key1", "key2"]
            },
            "rate_limit": {
                "enabled": True,
                "requests_per_hour": 200
            },
            "database": {
                "path": "/var/lib/api_server.db"
            },
            "logging": {
                "level": "DEBUG",
                "file": "/var/log/api_server.log"
            }
        }
        
        with open(config_file, 'w') as f:
            yaml.safe_dump(config_data, f)
        
        config = load_config(config_file)
        
        assert config.server.host == "localhost"
        assert config.server.port == 8080
        assert config.files.max_file_size_mb == 250
        assert config.cleanup.completed_retention_hours == 48
        assert config.models.default_model_type == "htdemucs"
        assert config.models.device_ids == [0, 1]
        assert config.auth.enabled is True
        assert config.auth.api_keys == ["key1", "key2"]
        assert config.rate_limit.enabled is True
        assert config.rate_limit.requests_per_hour == 200
        assert config.database.path == "/var/lib/api_server.db"
        assert config.logging.level == "DEBUG"


class TestLoadConfigJSON:
    """Tests for loading configuration from JSON files."""
    
    def test_load_valid_json(self, tmp_path):
        """Test loading valid JSON configuration."""
        config_file = tmp_path / "config.json"
        config_data = {
            "server": {
                "host": "0.0.0.0",
                "port": 7000,
                "workers": 3
            },
            "models": {
                "default_model_type": "mdx23c",
                "device_ids": [0]
            }
        }
        
        with open(config_file, 'w') as f:
            json.dump(config_data, f)
        
        config = load_config(config_file)
        
        assert config.server.host == "0.0.0.0"
        assert config.server.port == 7000
        assert config.server.workers == 3
        assert config.models.default_model_type == "mdx23c"
    
    def test_load_partial_json(self, tmp_path):
        """Test loading partial JSON with defaults for missing values."""
        config_file = tmp_path / "config.json"
        config_data = {
            "files": {
                "max_file_size_mb": 750
            }
        }
        
        with open(config_file, 'w') as f:
            json.dump(config_data, f)
        
        config = load_config(config_file)
        
        # Custom value
        assert config.files.max_file_size_mb == 750
        
        # Default values
        assert config.server.port == 8000
        assert config.models.default_model_type == "mdx23c"


class TestLoadConfigValidation:
    """Tests for configuration validation and error handling."""
    
    def test_invalid_port_value(self, tmp_path):
        """Test that invalid port value raises ConfigurationError."""
        config_file = tmp_path / "config.yaml"
        config_data = {
            "server": {
                "port": 70000  # Invalid: > 65535
            }
        }
        
        with open(config_file, 'w') as f:
            yaml.safe_dump(config_data, f)
        
        with pytest.raises(ConfigurationError) as exc_info:
            load_config(config_file)
        
        error_msg = str(exc_info.value)
        assert "Invalid configuration" in error_msg
        assert "server.port" in error_msg
    
    def test_invalid_workers_value(self, tmp_path):
        """Test that invalid workers value raises ConfigurationError."""
        config_file = tmp_path / "config.yaml"
        config_data = {
            "server": {
                "workers": 0  # Invalid: must be >= 1
            }
        }
        
        with open(config_file, 'w') as f:
            yaml.safe_dump(config_data, f)
        
        with pytest.raises(ConfigurationError) as exc_info:
            load_config(config_file)
        
        error_msg = str(exc_info.value)
        assert "Invalid configuration" in error_msg
        assert "server.workers" in error_msg
    
    def test_invalid_log_level(self, tmp_path):
        """Test that invalid log level raises ConfigurationError."""
        config_file = tmp_path / "config.yaml"
        config_data = {
            "logging": {
                "level": "INVALID_LEVEL"
            }
        }
        
        with open(config_file, 'w') as f:
            yaml.safe_dump(config_data, f)
        
        with pytest.raises(ConfigurationError) as exc_info:
            load_config(config_file)
        
        error_msg = str(exc_info.value)
        assert "Invalid configuration" in error_msg
        assert "logging.level" in error_msg
    
    def test_auth_enabled_without_keys(self, tmp_path):
        """Test that auth enabled without keys raises ConfigurationError."""
        config_file = tmp_path / "config.yaml"
        config_data = {
            "auth": {
                "enabled": True,
                "api_keys": []
            }
        }
        
        with open(config_file, 'w') as f:
            yaml.safe_dump(config_data, f)
        
        with pytest.raises(ConfigurationError) as exc_info:
            load_config(config_file)
        
        error_msg = str(exc_info.value)
        assert "Invalid configuration" in error_msg
        assert "auth" in error_msg.lower()
    
    def test_same_upload_output_directories(self, tmp_path):
        """Test that same upload/output directories raises ConfigurationError."""
        config_file = tmp_path / "config.yaml"
        config_data = {
            "files": {
                "upload_dir": "/tmp/data",
                "output_dir": "/tmp/data"
            }
        }
        
        with open(config_file, 'w') as f:
            yaml.safe_dump(config_data, f)
        
        with pytest.raises(ConfigurationError) as exc_info:
            load_config(config_file)
        
        error_msg = str(exc_info.value)
        assert "Invalid configuration" in error_msg
        assert "must be different" in error_msg.lower()
    
    def test_negative_device_id(self, tmp_path):
        """Test that negative device ID raises ConfigurationError."""
        config_file = tmp_path / "config.yaml"
        config_data = {
            "models": {
                "device_ids": [-1]
            }
        }
        
        with open(config_file, 'w') as f:
            yaml.safe_dump(config_data, f)
        
        with pytest.raises(ConfigurationError) as exc_info:
            load_config(config_file)
        
        error_msg = str(exc_info.value)
        assert "Invalid configuration" in error_msg
        assert "models.device_ids" in error_msg
    
    def test_invalid_yaml_syntax(self, tmp_path):
        """Test that invalid YAML syntax raises ConfigurationError."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("server:\n  port: [invalid yaml")
        
        with pytest.raises(ConfigurationError) as exc_info:
            load_config(config_file)
        
        error_msg = str(exc_info.value)
        assert "Failed to read configuration file" in error_msg
    
    def test_invalid_json_syntax(self, tmp_path):
        """Test that invalid JSON syntax raises ConfigurationError."""
        config_file = tmp_path / "config.json"
        config_file.write_text('{"server": {"port": }')
        
        with pytest.raises(ConfigurationError) as exc_info:
            load_config(config_file)
        
        error_msg = str(exc_info.value)
        assert "Failed to read configuration file" in error_msg
    
    def test_unsupported_file_format(self, tmp_path):
        """Test that unsupported file format raises ConfigurationError."""
        config_file = tmp_path / "config.txt"
        config_file.write_text("some text")
        
        with pytest.raises(ConfigurationError) as exc_info:
            load_config(config_file)
        
        error_msg = str(exc_info.value)
        assert "Failed to read configuration file" in error_msg
        assert "Unsupported configuration file format" in error_msg


class TestSaveConfig:
    """Tests for saving configuration to files."""
    
    def test_save_config_yaml(self, tmp_path):
        """Test saving configuration to YAML file."""
        config = ServerConfig()
        config.server.port = 9000
        config.files.max_file_size_mb = 1000
        
        config_file = tmp_path / "output.yaml"
        save_config(config, config_file)
        
        assert config_file.exists()
        
        # Load it back and verify
        loaded_config = load_config(config_file)
        assert loaded_config.server.port == 9000
        assert loaded_config.files.max_file_size_mb == 1000
    
    def test_save_config_json(self, tmp_path):
        """Test saving configuration to JSON file."""
        config = ServerConfig()
        config.server.host = "localhost"
        config.server.workers = 5
        
        config_file = tmp_path / "output.json"
        save_config(config, config_file)
        
        assert config_file.exists()
        
        # Load it back and verify
        loaded_config = load_config(config_file)
        assert loaded_config.server.host == "localhost"
        assert loaded_config.server.workers == 5
    
    def test_save_config_unsupported_format(self, tmp_path):
        """Test that saving to unsupported format raises ValueError."""
        config = ServerConfig()
        config_file = tmp_path / "output.txt"
        
        with pytest.raises(ValueError) as exc_info:
            save_config(config, config_file)
        
        assert "Unsupported configuration file format" in str(exc_info.value)


class TestConfigLoaderIntegration:
    """Integration tests for configuration loader."""
    
    def test_round_trip_yaml(self, tmp_path):
        """Test saving and loading configuration preserves all values."""
        # Create custom config
        original = ServerConfig()
        original.server.host = "192.168.1.1"
        original.server.port = 8888
        original.server.workers = 8
        original.files.max_file_size_mb = 2000
        original.cleanup.enabled = False
        original.models.default_model_type = "htdemucs"
        original.auth.enabled = True
        original.auth.api_keys = ["test-key-1", "test-key-2"]
        
        # Save to file
        config_file = tmp_path / "test.yaml"
        save_config(original, config_file)
        
        # Load from file
        loaded = load_config(config_file)
        
        # Verify all values match
        assert loaded.server.host == original.server.host
        assert loaded.server.port == original.server.port
        assert loaded.server.workers == original.server.workers
        assert loaded.files.max_file_size_mb == original.files.max_file_size_mb
        assert loaded.cleanup.enabled == original.cleanup.enabled
        assert loaded.models.default_model_type == original.models.default_model_type
        assert loaded.auth.enabled == original.auth.enabled
        assert loaded.auth.api_keys == original.auth.api_keys
    
    def test_path_as_string(self, tmp_path):
        """Test that config_path can be provided as string."""
        config_file = tmp_path / "config.yaml"
        config_data = {"server": {"port": 9999}}
        
        with open(config_file, 'w') as f:
            yaml.safe_dump(config_data, f)
        
        # Pass as string instead of Path
        config = load_config(str(config_file))
        
        assert config.server.port == 9999
    
    def test_path_as_path_object(self, tmp_path):
        """Test that config_path can be provided as Path object."""
        config_file = tmp_path / "config.yaml"
        config_data = {"server": {"port": 7777}}
        
        with open(config_file, 'w') as f:
            yaml.safe_dump(config_data, f)
        
        # Pass as Path object
        config = load_config(config_file)
        
        assert config.server.port == 7777
