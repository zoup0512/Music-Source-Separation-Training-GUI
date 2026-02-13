"""
Test loading configuration from YAML file.

Validates that the ServerConfig model can load from the actual config file.
"""

import yaml
from pathlib import Path
from api_server.models import ServerConfig


def test_load_from_yaml_file():
    """Test loading configuration from the actual YAML file."""
    config_path = Path("api_server_config.yaml")
    
    # Load YAML file
    with open(config_path, 'r') as f:
        config_dict = yaml.safe_load(f)
    
    # Create ServerConfig from loaded data
    config = ServerConfig(**config_dict)
    
    # Verify values match the YAML file
    assert config.server.host == "0.0.0.0"
    assert config.server.port == 8000
    assert config.server.workers == 2
    
    assert config.files.max_file_size_mb == 500
    assert config.files.upload_dir == "./api_uploads"
    assert config.files.output_dir == "./api_outputs"
    
    assert config.cleanup.enabled is True
    assert config.cleanup.completed_retention_hours == 24
    assert config.cleanup.failed_retention_hours == 24
    assert config.cleanup.metadata_retention_days == 7
    
    assert config.models.default_model_type == "mdx23c"
    assert config.models.model_cache_size == 3
    assert config.models.force_cpu is False
    assert config.models.device_ids == [0]
    
    assert config.auth.enabled is False
    assert config.auth.api_keys == []
    
    assert config.rate_limit.enabled is False
    assert config.rate_limit.requests_per_hour == 100
    
    assert config.database.path == "./api_server.db"
    
    assert config.logging.level == "INFO"
    assert config.logging.file == "./api_server.log"


def test_export_to_yaml():
    """Test exporting configuration back to YAML format."""
    config = ServerConfig()
    
    # Export to dict
    config_dict = config.model_dump_yaml()
    
    # Convert to YAML string
    yaml_str = yaml.dump(config_dict, default_flow_style=False, sort_keys=False)
    
    # Verify it's valid YAML
    reloaded = yaml.safe_load(yaml_str)
    assert isinstance(reloaded, dict)
    assert "server" in reloaded
    assert "files" in reloaded
    assert "cleanup" in reloaded
    assert "models" in reloaded
    assert "auth" in reloaded
    assert "rate_limit" in reloaded
    assert "database" in reloaded
    assert "logging" in reloaded
