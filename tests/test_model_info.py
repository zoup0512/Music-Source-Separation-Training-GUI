"""
Unit tests for ModelInfo data model.

Tests the ModelInfo class for model metadata representation.
"""

import pytest
from api_server.models import ModelInfo


def test_model_info_creation():
    """Test creating a ModelInfo instance with required fields."""
    model_info = ModelInfo(
        model_type="mdx23c",
        config_path="/path/to/config.yaml",
        checkpoint_path="/path/to/checkpoint.ckpt",
        instruments=["vocals", "instrumental"],
        sample_rate=44100,
        supports_stereo=True,
        supports_mono=True,
        description="MDX23C model for vocal separation"
    )
    
    assert model_info.model_type == "mdx23c"
    assert model_info.config_path == "/path/to/config.yaml"
    assert model_info.checkpoint_path == "/path/to/checkpoint.ckpt"
    assert model_info.instruments == ["vocals", "instrumental"]
    assert model_info.sample_rate == 44100
    assert model_info.supports_stereo is True
    assert model_info.supports_mono is True
    assert model_info.description == "MDX23C model for vocal separation"


def test_model_info_minimal():
    """Test creating a ModelInfo with only required fields."""
    model_info = ModelInfo(
        model_type="htdemucs",
        config_path="/path/to/config.yaml"
    )
    
    assert model_info.model_type == "htdemucs"
    assert model_info.config_path == "/path/to/config.yaml"
    assert model_info.checkpoint_path is None
    assert model_info.instruments == []
    assert model_info.sample_rate == 44100  # Default
    assert model_info.supports_stereo is True  # Default
    assert model_info.supports_mono is True  # Default
    assert model_info.description is None


def test_model_info_to_dict():
    """Test converting ModelInfo to dictionary."""
    model_info = ModelInfo(
        model_type="mdx23c",
        config_path="/path/to/config.yaml",
        instruments=["vocals", "drums", "bass", "other"],
        sample_rate=48000
    )
    
    result = model_info.to_dict()
    
    assert result["model_type"] == "mdx23c"
    assert result["config_path"] == "/path/to/config.yaml"
    assert result["instruments"] == ["vocals", "drums", "bass", "other"]
    assert result["sample_rate"] == 48000
    assert "supports_stereo" in result
    assert "supports_mono" in result


def test_model_info_sample_rate_validation():
    """Test that sample rate validation works."""
    # Valid sample rates
    ModelInfo(model_type="test", config_path="/path", sample_rate=8000)
    ModelInfo(model_type="test", config_path="/path", sample_rate=44100)
    ModelInfo(model_type="test", config_path="/path", sample_rate=192000)
    
    # Invalid sample rates should raise validation error
    with pytest.raises(Exception):  # Pydantic ValidationError
        ModelInfo(model_type="test", config_path="/path", sample_rate=7999)
    
    with pytest.raises(Exception):  # Pydantic ValidationError
        ModelInfo(model_type="test", config_path="/path", sample_rate=192001)


def test_model_info_repr():
    """Test string representation of ModelInfo."""
    model_info = ModelInfo(
        model_type="mdx23c",
        config_path="/path/to/config.yaml",
        instruments=["vocals", "instrumental"],
        sample_rate=44100
    )
    
    repr_str = repr(model_info)
    assert "mdx23c" in repr_str
    assert "vocals" in repr_str or "instrumental" in repr_str
    assert "44100" in repr_str


def test_model_info_with_no_checkpoint():
    """Test ModelInfo when checkpoint file is not found."""
    model_info = ModelInfo(
        model_type="missing_model",
        config_path="/path/to/config.yaml",
        checkpoint_path=None,
        instruments=["vocals"]
    )
    
    assert model_info.checkpoint_path is None
    assert model_info.model_type == "missing_model"


def test_model_info_multiple_instruments():
    """Test ModelInfo with multiple instruments."""
    instruments = ["vocals", "drums", "bass", "other", "piano", "guitar"]
    model_info = ModelInfo(
        model_type="multi_instrument",
        config_path="/path/to/config.yaml",
        instruments=instruments
    )
    
    assert len(model_info.instruments) == 6
    assert model_info.instruments == instruments
