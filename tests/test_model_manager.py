"""
Unit tests for ModelManager class.

Tests model discovery, validation, and loading functionality.
"""

import pytest
import tempfile
import yaml
from pathlib import Path
from unittest.mock import Mock, patch

from api_server.core.model_manager import ModelManager, ValidationResult
from api_server.models.config import ServerConfig
from api_server.models.model_info import ModelInfo


@pytest.fixture
def temp_dirs():
    """Create temporary directories for configs and pretrain."""
    with tempfile.TemporaryDirectory() as configs_dir, \
         tempfile.TemporaryDirectory() as pretrain_dir:
        yield Path(configs_dir), Path(pretrain_dir)


@pytest.fixture
def sample_config():
    """Create a sample server configuration."""
    return ServerConfig()


@pytest.fixture
def sample_model_config():
    """Create a sample model configuration dictionary."""
    return {
        'audio': {
            'sample_rate': 44100,
            'num_channels': 2,
            'chunk_size': 261120,
            'n_fft': 8192,
            'hop_length': 1024,
        },
        'training': {
            'instruments': ['vocals', 'instrumental'],
            'batch_size': 4,
        },
        'model': {
            'num_channels': 128,
        }
    }


def create_model_config_file(configs_dir: Path, model_name: str, config_data: dict) -> Path:
    """Helper to create a model config file."""
    config_file = configs_dir / f"config_{model_name}.yaml"
    with open(config_file, 'w') as f:
        yaml.safe_dump(config_data, f)
    return config_file


def create_checkpoint_file(pretrain_dir: Path, model_name: str, extension: str = ".ckpt") -> Path:
    """Helper to create a dummy checkpoint file."""
    checkpoint_file = pretrain_dir / f"{model_name}{extension}"
    checkpoint_file.write_text("dummy checkpoint data")
    return checkpoint_file


class TestModelManagerInitialization:
    """Test ModelManager initialization and discovery."""
    
    def test_init_with_empty_directories(self, temp_dirs, sample_config):
        """Test initialization with empty configs directory."""
        configs_dir, pretrain_dir = temp_dirs
        
        manager = ModelManager(sample_config, str(configs_dir), str(pretrain_dir))
        
        assert len(manager.get_available_models()) == 0
    
    def test_init_with_nonexistent_directories(self, sample_config):
        """Test initialization with non-existent directories."""
        manager = ModelManager(
            sample_config,
            "/nonexistent/configs",
            "/nonexistent/pretrain"
        )
        
        assert len(manager.get_available_models()) == 0
    
    def test_discover_single_model(self, temp_dirs, sample_config, sample_model_config):
        """Test discovery of a single model."""
        configs_dir, pretrain_dir = temp_dirs
        
        # Create model config
        create_model_config_file(configs_dir, "mdx23c", sample_model_config)
        
        manager = ModelManager(sample_config, str(configs_dir), str(pretrain_dir))
        
        models = manager.get_available_models()
        assert len(models) == 1
        assert models[0].model_type == "mdx23c"
        assert models[0].instruments == ['vocals', 'instrumental']
        assert models[0].sample_rate == 44100
    
    def test_discover_multiple_models(self, temp_dirs, sample_config, sample_model_config):
        """Test discovery of multiple models."""
        configs_dir, pretrain_dir = temp_dirs
        
        # Create multiple model configs
        create_model_config_file(configs_dir, "mdx23c", sample_model_config)
        
        htdemucs_config = sample_model_config.copy()
        htdemucs_config['training']['instruments'] = ['vocals', 'bass', 'drums', 'other']
        create_model_config_file(configs_dir, "htdemucs", htdemucs_config)
        
        manager = ModelManager(sample_config, str(configs_dir), str(pretrain_dir))
        
        models = manager.get_available_models()
        assert len(models) == 2
        
        model_types = {m.model_type for m in models}
        assert model_types == {"mdx23c", "htdemucs"}
    
    def test_model_with_checkpoint(self, temp_dirs, sample_config, sample_model_config):
        """Test model discovery with checkpoint file present."""
        configs_dir, pretrain_dir = temp_dirs
        
        # Create model config and checkpoint
        create_model_config_file(configs_dir, "mdx23c", sample_model_config)
        checkpoint_path = create_checkpoint_file(pretrain_dir, "mdx23c")
        
        manager = ModelManager(sample_config, str(configs_dir), str(pretrain_dir))
        
        model_info = manager.get_model_info("mdx23c")
        assert model_info is not None
        assert model_info.checkpoint_path == str(checkpoint_path)
    
    def test_model_without_checkpoint(self, temp_dirs, sample_config, sample_model_config):
        """Test model discovery without checkpoint file."""
        configs_dir, pretrain_dir = temp_dirs
        
        # Create model config without checkpoint
        create_model_config_file(configs_dir, "mdx23c", sample_model_config)
        
        manager = ModelManager(sample_config, str(configs_dir), str(pretrain_dir))
        
        model_info = manager.get_model_info("mdx23c")
        assert model_info is not None
        assert model_info.checkpoint_path is None
    
    def test_checkpoint_with_different_extensions(self, temp_dirs, sample_config, sample_model_config):
        """Test checkpoint discovery with different file extensions."""
        configs_dir, pretrain_dir = temp_dirs
        
        # Test .pth extension
        create_model_config_file(configs_dir, "model1", sample_model_config)
        checkpoint1 = create_checkpoint_file(pretrain_dir, "model1", ".pth")
        
        # Test .pt extension
        model2_config = sample_model_config.copy()
        create_model_config_file(configs_dir, "model2", model2_config)
        checkpoint2 = create_checkpoint_file(pretrain_dir, "model2", ".pt")
        
        manager = ModelManager(sample_config, str(configs_dir), str(pretrain_dir))
        
        model1 = manager.get_model_info("model1")
        assert model1.checkpoint_path == str(checkpoint1)
        
        model2 = manager.get_model_info("model2")
        assert model2.checkpoint_path == str(checkpoint2)


class TestModelManagerQueries:
    """Test ModelManager query methods."""
    
    def test_get_available_models_returns_list(self, temp_dirs, sample_config, sample_model_config):
        """Test that get_available_models returns a list."""
        configs_dir, pretrain_dir = temp_dirs
        create_model_config_file(configs_dir, "mdx23c", sample_model_config)
        
        manager = ModelManager(sample_config, str(configs_dir), str(pretrain_dir))
        
        models = manager.get_available_models()
        assert isinstance(models, list)
        assert all(isinstance(m, ModelInfo) for m in models)
    
    def test_get_model_info_existing_model(self, temp_dirs, sample_config, sample_model_config):
        """Test getting info for an existing model."""
        configs_dir, pretrain_dir = temp_dirs
        create_model_config_file(configs_dir, "mdx23c", sample_model_config)
        
        manager = ModelManager(sample_config, str(configs_dir), str(pretrain_dir))
        
        model_info = manager.get_model_info("mdx23c")
        assert model_info is not None
        assert model_info.model_type == "mdx23c"
        assert model_info.instruments == ['vocals', 'instrumental']
    
    def test_get_model_info_nonexistent_model(self, temp_dirs, sample_config):
        """Test getting info for a non-existent model."""
        configs_dir, pretrain_dir = temp_dirs
        
        manager = ModelManager(sample_config, str(configs_dir), str(pretrain_dir))
        
        model_info = manager.get_model_info("nonexistent")
        assert model_info is None


class TestModelManagerValidation:
    """Test ModelManager parameter validation."""
    
    def test_validate_valid_model_type(self, temp_dirs, sample_config, sample_model_config):
        """Test validation with valid model type."""
        configs_dir, pretrain_dir = temp_dirs
        create_model_config_file(configs_dir, "mdx23c", sample_model_config)
        
        manager = ModelManager(sample_config, str(configs_dir), str(pretrain_dir))
        
        result = manager.validate_model_params("mdx23c")
        assert result.valid is True
        assert result.error_message is None
    
    def test_validate_invalid_model_type(self, temp_dirs, sample_config, sample_model_config):
        """Test validation with invalid model type."""
        configs_dir, pretrain_dir = temp_dirs
        create_model_config_file(configs_dir, "mdx23c", sample_model_config)
        
        manager = ModelManager(sample_config, str(configs_dir), str(pretrain_dir))
        
        result = manager.validate_model_params("invalid_model")
        assert result.valid is False
        assert "Unsupported model_type" in result.error_message
        assert "invalid_model" in result.error_message
    
    def test_validate_valid_instruments(self, temp_dirs, sample_config, sample_model_config):
        """Test validation with valid instruments."""
        configs_dir, pretrain_dir = temp_dirs
        create_model_config_file(configs_dir, "mdx23c", sample_model_config)
        
        manager = ModelManager(sample_config, str(configs_dir), str(pretrain_dir))
        
        result = manager.validate_model_params("mdx23c", ["vocals"])
        assert result.valid is True
        
        result = manager.validate_model_params("mdx23c", ["vocals", "instrumental"])
        assert result.valid is True
    
    def test_validate_invalid_instruments(self, temp_dirs, sample_config, sample_model_config):
        """Test validation with invalid instruments."""
        configs_dir, pretrain_dir = temp_dirs
        create_model_config_file(configs_dir, "mdx23c", sample_model_config)
        
        manager = ModelManager(sample_config, str(configs_dir), str(pretrain_dir))
        
        result = manager.validate_model_params("mdx23c", ["drums"])
        assert result.valid is False
        assert "Unsupported instruments" in result.error_message
        assert "drums" in result.error_message
    
    def test_validate_mixed_valid_invalid_instruments(self, temp_dirs, sample_config, sample_model_config):
        """Test validation with mix of valid and invalid instruments."""
        configs_dir, pretrain_dir = temp_dirs
        create_model_config_file(configs_dir, "mdx23c", sample_model_config)
        
        manager = ModelManager(sample_config, str(configs_dir), str(pretrain_dir))
        
        result = manager.validate_model_params("mdx23c", ["vocals", "drums", "bass"])
        assert result.valid is False
        assert "drums" in result.error_message or "bass" in result.error_message
    
    def test_validate_no_instruments_specified(self, temp_dirs, sample_config, sample_model_config):
        """Test validation with no instruments specified."""
        configs_dir, pretrain_dir = temp_dirs
        create_model_config_file(configs_dir, "mdx23c", sample_model_config)
        
        manager = ModelManager(sample_config, str(configs_dir), str(pretrain_dir))
        
        result = manager.validate_model_params("mdx23c", None)
        assert result.valid is True
        
        result = manager.validate_model_params("mdx23c", [])
        assert result.valid is True


class TestModelManagerLoading:
    """Test ModelManager model loading."""
    
    def test_load_model_with_valid_checkpoint(self, temp_dirs, sample_config, sample_model_config):
        """Test loading a model with valid checkpoint."""
        configs_dir, pretrain_dir = temp_dirs
        create_model_config_file(configs_dir, "mdx23c", sample_model_config)
        create_checkpoint_file(pretrain_dir, "mdx23c")
        
        manager = ModelManager(sample_config, str(configs_dir), str(pretrain_dir))
        
        # Should not raise an exception
        model, config = manager.load_model("mdx23c", "cpu")
        assert config is not None
        assert 'audio' in config
        assert 'training' in config
    
    def test_load_model_without_checkpoint(self, temp_dirs, sample_config, sample_model_config):
        """Test loading a model without checkpoint file."""
        configs_dir, pretrain_dir = temp_dirs
        create_model_config_file(configs_dir, "mdx23c", sample_model_config)
        
        manager = ModelManager(sample_config, str(configs_dir), str(pretrain_dir))
        
        with pytest.raises(ValueError, match="has no checkpoint file"):
            manager.load_model("mdx23c", "cpu")
    
    def test_load_nonexistent_model(self, temp_dirs, sample_config):
        """Test loading a non-existent model."""
        configs_dir, pretrain_dir = temp_dirs
        
        manager = ModelManager(sample_config, str(configs_dir), str(pretrain_dir))
        
        with pytest.raises(ValueError, match="not found"):
            manager.load_model("nonexistent", "cpu")


class TestValidationResult:
    """Test ValidationResult helper class."""
    
    def test_valid_result(self):
        """Test valid ValidationResult."""
        result = ValidationResult(valid=True)
        assert result.valid is True
        assert result.error_message is None
        assert bool(result) is True
    
    def test_invalid_result(self):
        """Test invalid ValidationResult."""
        result = ValidationResult(valid=False, error_message="Test error")
        assert result.valid is False
        assert result.error_message == "Test error"
        assert bool(result) is False
    
    def test_repr(self):
        """Test ValidationResult string representation."""
        valid_result = ValidationResult(valid=True)
        assert "valid=True" in repr(valid_result)
        
        invalid_result = ValidationResult(valid=False, error_message="Error")
        assert "valid=False" in repr(invalid_result)
        assert "Error" in repr(invalid_result)
