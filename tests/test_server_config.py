"""
Unit tests for ServerConfig data model.

Tests configuration loading, validation, and default values.
"""

import pytest
from pydantic import ValidationError
from api_server.models import (
    ServerConfig,
    ServerSettings,
    FileSettings,
    CleanupSettings,
    ModelSettings,
    AuthSettings,
    RateLimitSettings,
    DatabaseSettings,
    LoggingSettings,
)


class TestServerSettings:
    """Tests for ServerSettings model."""
    
    def test_default_values(self):
        """Test that default values are set correctly."""
        settings = ServerSettings()
        assert settings.host == "0.0.0.0"
        assert settings.port == 8000
        assert settings.workers == 1
    
    def test_custom_values(self):
        """Test setting custom values."""
        settings = ServerSettings(host="127.0.0.1", port=9000, workers=4)
        assert settings.host == "127.0.0.1"
        assert settings.port == 9000
        assert settings.workers == 4
    
    def test_port_validation_min(self):
        """Test that port must be >= 1."""
        with pytest.raises(ValidationError) as exc_info:
            ServerSettings(port=0)
        assert "greater than or equal to 1" in str(exc_info.value).lower()
    
    def test_port_validation_max(self):
        """Test that port must be <= 65535."""
        with pytest.raises(ValidationError) as exc_info:
            ServerSettings(port=65536)
        assert "less than or equal to 65535" in str(exc_info.value).lower()
    
    def test_workers_validation(self):
        """Test that workers must be >= 1."""
        with pytest.raises(ValidationError) as exc_info:
            ServerSettings(workers=0)
        assert "greater than or equal to 1" in str(exc_info.value).lower()


class TestFileSettings:
    """Tests for FileSettings model."""
    
    def test_default_values(self):
        """Test that default values are set correctly."""
        settings = FileSettings()
        assert settings.max_file_size_mb == 500
        assert settings.upload_dir == "./api_uploads"
        assert settings.output_dir == "./api_outputs"
    
    def test_custom_values(self):
        """Test setting custom values."""
        settings = FileSettings(
            max_file_size_mb=1000,
            upload_dir="/tmp/uploads",
            output_dir="/tmp/outputs"
        )
        assert settings.max_file_size_mb == 1000
        assert settings.upload_dir == "/tmp/uploads"
        assert settings.output_dir == "/tmp/outputs"
    
    def test_max_file_size_validation_min(self):
        """Test that max_file_size_mb must be >= 1."""
        with pytest.raises(ValidationError) as exc_info:
            FileSettings(max_file_size_mb=0)
        assert "greater than or equal to 1" in str(exc_info.value).lower()
    
    def test_max_file_size_validation_max(self):
        """Test that max_file_size_mb must be <= 10000."""
        with pytest.raises(ValidationError) as exc_info:
            FileSettings(max_file_size_mb=10001)
        assert "less than or equal to 10000" in str(exc_info.value).lower()


class TestCleanupSettings:
    """Tests for CleanupSettings model."""
    
    def test_default_values(self):
        """Test that default values are set correctly."""
        settings = CleanupSettings()
        assert settings.enabled is True
        assert settings.completed_retention_hours == 24
        assert settings.failed_retention_hours == 24
        assert settings.metadata_retention_days == 7
    
    def test_custom_values(self):
        """Test setting custom values."""
        settings = CleanupSettings(
            enabled=False,
            completed_retention_hours=48,
            failed_retention_hours=12,
            metadata_retention_days=30
        )
        assert settings.enabled is False
        assert settings.completed_retention_hours == 48
        assert settings.failed_retention_hours == 12
        assert settings.metadata_retention_days == 30
    
    def test_retention_validation(self):
        """Test that retention values must be >= 1."""
        with pytest.raises(ValidationError):
            CleanupSettings(completed_retention_hours=0)
        with pytest.raises(ValidationError):
            CleanupSettings(failed_retention_hours=0)
        with pytest.raises(ValidationError):
            CleanupSettings(metadata_retention_days=0)


class TestModelSettings:
    """Tests for ModelSettings model."""
    
    def test_default_values(self):
        """Test that default values are set correctly."""
        settings = ModelSettings()
        assert settings.default_model_type == "mdx23c"
        assert settings.model_cache_size == 3
        assert settings.force_cpu is False
        assert settings.device_ids == [0]
    
    def test_custom_values(self):
        """Test setting custom values."""
        settings = ModelSettings(
            default_model_type="htdemucs",
            model_cache_size=5,
            force_cpu=True,
            device_ids=[0, 1, 2]
        )
        assert settings.default_model_type == "htdemucs"
        assert settings.model_cache_size == 5
        assert settings.force_cpu is True
        assert settings.device_ids == [0, 1, 2]
    
    def test_device_ids_validation_negative(self):
        """Test that device IDs must be non-negative."""
        with pytest.raises(ValidationError) as exc_info:
            ModelSettings(device_ids=[-1])
        assert "non-negative" in str(exc_info.value).lower()
    
    def test_device_ids_empty_defaults_to_zero(self):
        """Test that empty device_ids defaults to [0]."""
        settings = ModelSettings(device_ids=[])
        assert settings.device_ids == [0]
    
    def test_model_cache_size_validation(self):
        """Test that model_cache_size must be >= 1."""
        with pytest.raises(ValidationError) as exc_info:
            ModelSettings(model_cache_size=0)
        assert "greater than or equal to 1" in str(exc_info.value).lower()


class TestAuthSettings:
    """Tests for AuthSettings model."""
    
    def test_default_values(self):
        """Test that default values are set correctly."""
        settings = AuthSettings()
        assert settings.enabled is False
        assert settings.api_keys == []
    
    def test_auth_disabled_with_no_keys(self):
        """Test that auth can be disabled with no keys."""
        settings = AuthSettings(enabled=False, api_keys=[])
        assert settings.enabled is False
        assert settings.api_keys == []
    
    def test_auth_enabled_with_keys(self):
        """Test that auth can be enabled with keys."""
        settings = AuthSettings(enabled=True, api_keys=["key1", "key2"])
        assert settings.enabled is True
        assert settings.api_keys == ["key1", "key2"]
    
    def test_auth_enabled_without_keys_fails(self):
        """Test that enabling auth without keys raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            AuthSettings(enabled=True, api_keys=[])
        error_msg = str(exc_info.value).lower()
        assert "no api keys" in error_msg or "api keys are configured" in error_msg


class TestRateLimitSettings:
    """Tests for RateLimitSettings model."""
    
    def test_default_values(self):
        """Test that default values are set correctly."""
        settings = RateLimitSettings()
        assert settings.enabled is False
        assert settings.requests_per_hour == 100
    
    def test_custom_values(self):
        """Test setting custom values."""
        settings = RateLimitSettings(enabled=True, requests_per_hour=500)
        assert settings.enabled is True
        assert settings.requests_per_hour == 500
    
    def test_requests_per_hour_validation(self):
        """Test that requests_per_hour must be >= 1."""
        with pytest.raises(ValidationError) as exc_info:
            RateLimitSettings(requests_per_hour=0)
        assert "greater than or equal to 1" in str(exc_info.value).lower()


class TestDatabaseSettings:
    """Tests for DatabaseSettings model."""
    
    def test_default_values(self):
        """Test that default values are set correctly."""
        settings = DatabaseSettings()
        assert settings.path == "./api_server.db"
    
    def test_custom_values(self):
        """Test setting custom values."""
        settings = DatabaseSettings(path="/var/lib/api_server.db")
        assert settings.path == "/var/lib/api_server.db"


class TestLoggingSettings:
    """Tests for LoggingSettings model."""
    
    def test_default_values(self):
        """Test that default values are set correctly."""
        settings = LoggingSettings()
        assert settings.level == "INFO"
        assert settings.file == "./api_server.log"
    
    def test_custom_values(self):
        """Test setting custom values."""
        settings = LoggingSettings(level="DEBUG", file="/var/log/api_server.log")
        assert settings.level == "DEBUG"
        assert settings.file == "/var/log/api_server.log"
    
    def test_log_level_validation_valid(self):
        """Test that valid log levels are accepted."""
        for level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            settings = LoggingSettings(level=level)
            assert settings.level == level
    
    def test_log_level_validation_case_insensitive(self):
        """Test that log level validation is case-insensitive."""
        settings = LoggingSettings(level="debug")
        assert settings.level == "DEBUG"
        
        settings = LoggingSettings(level="Info")
        assert settings.level == "INFO"
    
    def test_log_level_validation_invalid(self):
        """Test that invalid log levels raise validation error."""
        with pytest.raises(ValidationError) as exc_info:
            LoggingSettings(level="INVALID")
        assert "invalid log level" in str(exc_info.value).lower()


class TestServerConfig:
    """Tests for complete ServerConfig model."""
    
    def test_default_values(self):
        """Test that default configuration is created correctly."""
        config = ServerConfig()
        assert config.server.host == "0.0.0.0"
        assert config.server.port == 8000
        assert config.files.max_file_size_mb == 500
        assert config.cleanup.enabled is True
        assert config.models.default_model_type == "mdx23c"
        assert config.auth.enabled is False
        assert config.rate_limit.enabled is False
        assert config.database.path == "./api_server.db"
        assert config.logging.level == "INFO"
    
    def test_custom_nested_values(self):
        """Test setting custom nested values."""
        config = ServerConfig(
            server=ServerSettings(host="127.0.0.1", port=9000, workers=4),
            files=FileSettings(max_file_size_mb=1000),
            auth=AuthSettings(enabled=True, api_keys=["test-key"])
        )
        assert config.server.host == "127.0.0.1"
        assert config.server.port == 9000
        assert config.server.workers == 4
        assert config.files.max_file_size_mb == 1000
        assert config.auth.enabled is True
        assert config.auth.api_keys == ["test-key"]
    
    def test_from_dict(self):
        """Test creating config from dictionary."""
        config_dict = {
            "server": {
                "host": "localhost",
                "port": 8080,
                "workers": 2
            },
            "files": {
                "max_file_size_mb": 250
            },
            "models": {
                "default_model_type": "htdemucs",
                "device_ids": [0, 1]
            }
        }
        config = ServerConfig(**config_dict)
        assert config.server.host == "localhost"
        assert config.server.port == 8080
        assert config.server.workers == 2
        assert config.files.max_file_size_mb == 250
        assert config.models.default_model_type == "htdemucs"
        assert config.models.device_ids == [0, 1]
    
    def test_directory_validation_same_paths(self):
        """Test that upload and output directories must be different."""
        with pytest.raises(ValidationError) as exc_info:
            ServerConfig(
                files=FileSettings(
                    upload_dir="./data",
                    output_dir="./data"
                )
            )
        assert "must be different" in str(exc_info.value).lower()
    
    def test_model_dump_yaml(self):
        """Test exporting configuration as dictionary."""
        config = ServerConfig()
        config_dict = config.model_dump_yaml()
        
        assert isinstance(config_dict, dict)
        assert "server" in config_dict
        assert "files" in config_dict
        assert "cleanup" in config_dict
        assert "models" in config_dict
        assert "auth" in config_dict
        assert "rate_limit" in config_dict
        assert "database" in config_dict
        assert "logging" in config_dict
    
    def test_partial_config(self):
        """Test that partial configuration uses defaults for missing values."""
        config_dict = {
            "server": {
                "port": 9000
            }
        }
        config = ServerConfig(**config_dict)
        
        # Custom value
        assert config.server.port == 9000
        
        # Default values
        assert config.server.host == "0.0.0.0"
        assert config.server.workers == 1
        assert config.files.max_file_size_mb == 500
