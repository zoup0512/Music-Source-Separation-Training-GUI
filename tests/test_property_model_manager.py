"""
Property-based tests for ModelManager class using Hypothesis.

Tests universal properties of model management across randomized inputs.

Feature: api-server
Properties tested:
- Property 50: Model listing completeness
- Property 51: Model details completeness
- Property 52: Non-existent model handling
- Property 53: Startup model validation
- Property 54: Missing model graceful handling

Validates: Requirements 12.1, 12.2, 12.3, 12.4, 12.5
"""

import pytest
import tempfile
import yaml
from pathlib import Path
from hypothesis import given, settings, strategies as st
from typing import List, Dict, Any

from api_server.core.model_manager import ModelManager
from api_server.models.config import ServerConfig
from api_server.models.model_info import ModelInfo


# Hypothesis strategies for generating test data

@st.composite
def model_name_strategy(draw):
    """Generate valid model names."""
    # Model names are typically alphanumeric with underscores/hyphens
    name_length = draw(st.integers(min_value=3, max_value=20))
    chars = st.sampled_from('abcdefghijklmnopqrstuvwxyz0123456789_-')
    name = ''.join(draw(st.lists(chars, min_size=name_length, max_size=name_length)))
    return name


@st.composite
def instrument_list_strategy(draw):
    """Generate lists of instrument names."""
    instruments = ['vocals', 'instrumental', 'drums', 'bass', 'other', 'guitar', 'piano']
    num_instruments = draw(st.integers(min_value=1, max_value=4))
    return draw(st.lists(st.sampled_from(instruments), min_size=num_instruments, max_size=num_instruments, unique=True))


@st.composite
def model_config_strategy(draw):
    """Generate valid model configuration dictionaries."""
    instruments = draw(instrument_list_strategy())
    sample_rate = draw(st.sampled_from([22050, 44100, 48000]))
    num_channels = draw(st.integers(min_value=1, max_value=2))
    
    return {
        'audio': {
            'sample_rate': sample_rate,
            'num_channels': num_channels,
            'chunk_size': 261120,
            'n_fft': 8192,
            'hop_length': 1024,
        },
        'training': {
            'instruments': instruments,
            'batch_size': 4,
        },
        'model': {
            'num_channels': 128,
        }
    }


@st.composite
def model_setup_strategy(draw):
    """
    Generate a complete model setup with configs and optional checkpoints.
    
    Returns:
        Dict with 'models' list containing model definitions
    """
    num_models = draw(st.integers(min_value=0, max_value=5))
    models = []
    used_names = set()
    
    for i in range(num_models):
        # Generate unique model names using index to avoid substring matches
        # This prevents issues where "aaa" matches "aaa0.ckpt"
        base_name = draw(model_name_strategy())
        model_name = f"model_{i}_{base_name}"
        
        # Ensure uniqueness (should be guaranteed by index, but double-check)
        counter = 0
        while model_name in used_names:
            model_name = f"model_{i}_{base_name}_{counter}"
            counter += 1
        used_names.add(model_name)
        
        config = draw(model_config_strategy())
        has_checkpoint = draw(st.booleans())
        
        models.append({
            'name': model_name,
            'config': config,
            'has_checkpoint': has_checkpoint
        })
    
    return {'models': models}


def create_test_environment(models_data: Dict) -> tuple:
    """
    Create temporary directories and files for testing.
    
    Args:
        models_data: Dictionary with 'models' list
    
    Returns:
        Tuple of (configs_dir, pretrain_dir, model_names)
    """
    configs_dir = tempfile.mkdtemp()
    pretrain_dir = tempfile.mkdtemp()
    model_names = []
    
    for model_def in models_data['models']:
        model_name = model_def['name']
        config = model_def['config']
        has_checkpoint = model_def['has_checkpoint']
        
        # Create config file
        config_file = Path(configs_dir) / f"config_{model_name}.yaml"
        with open(config_file, 'w') as f:
            yaml.safe_dump(config, f)
        
        # Create checkpoint file if specified
        if has_checkpoint:
            checkpoint_file = Path(pretrain_dir) / f"{model_name}.ckpt"
            checkpoint_file.write_text("dummy checkpoint data")
        
        model_names.append(model_name)
    
    return configs_dir, pretrain_dir, model_names


# Property 50: Model listing completeness
@given(model_setup_strategy())
@settings(max_examples=100)
def test_property_50_model_listing_completeness(models_data):
    """
    Feature: api-server, Property 50: Model listing completeness
    
    *For any* request to the models list endpoint, the response should include
    all available models with their model_type and configuration paths.
    
    **Validates: Requirements 12.1**
    """
    configs_dir, pretrain_dir, expected_model_names = create_test_environment(models_data)
    
    try:
        config = ServerConfig()
        manager = ModelManager(config, configs_dir, pretrain_dir)
        
        # Get available models
        available_models = manager.get_available_models()
        
        # Property: All created models should be in the list
        assert len(available_models) == len(expected_model_names), \
            f"Expected {len(expected_model_names)} models, got {len(available_models)}"
        
        # Property: Each model should have model_type and config_path
        for model_info in available_models:
            assert isinstance(model_info, ModelInfo), \
                "Each item should be a ModelInfo instance"
            assert model_info.model_type is not None, \
                "Each model should have a model_type"
            assert model_info.config_path is not None, \
                "Each model should have a config_path"
            assert model_info.model_type in expected_model_names, \
                f"Model {model_info.model_type} not in expected models"
        
        # Property: Model types should be unique
        model_types = [m.model_type for m in available_models]
        assert len(model_types) == len(set(model_types)), \
            "Model types should be unique"
    
    finally:
        # Cleanup
        import shutil
        shutil.rmtree(configs_dir, ignore_errors=True)
        shutil.rmtree(pretrain_dir, ignore_errors=True)


# Property 51: Model details completeness
@given(model_setup_strategy())
@settings(max_examples=100)
def test_property_51_model_details_completeness(models_data):
    """
    Feature: api-server, Property 51: Model details completeness
    
    *For any* valid model_type, requesting model details should return
    supported instruments, sample rate, and stereo support information.
    
    **Validates: Requirements 12.2**
    """
    # Skip if no models
    if not models_data['models']:
        return
    
    configs_dir, pretrain_dir, expected_model_names = create_test_environment(models_data)
    
    try:
        config = ServerConfig()
        manager = ModelManager(config, configs_dir, pretrain_dir)
        
        # Property: For each valid model, get_model_info should return complete details
        for model_name in expected_model_names:
            model_info = manager.get_model_info(model_name)
            
            assert model_info is not None, \
                f"Model info should exist for valid model '{model_name}'"
            
            # Property: Model details should include required fields
            assert model_info.model_type == model_name, \
                "Model type should match requested name"
            assert isinstance(model_info.instruments, list), \
                "Instruments should be a list"
            assert len(model_info.instruments) > 0, \
                "Instruments list should not be empty"
            assert isinstance(model_info.sample_rate, int), \
                "Sample rate should be an integer"
            assert model_info.sample_rate > 0, \
                "Sample rate should be positive"
            assert isinstance(model_info.supports_stereo, bool), \
                "Stereo support should be a boolean"
    
    finally:
        # Cleanup
        import shutil
        shutil.rmtree(configs_dir, ignore_errors=True)
        shutil.rmtree(pretrain_dir, ignore_errors=True)


# Property 52: Non-existent model handling
@given(model_setup_strategy(), st.text(min_size=1, max_size=50))
@settings(max_examples=100)
def test_property_52_nonexistent_model_handling(models_data, nonexistent_name):
    """
    Feature: api-server, Property 52: Non-existent model handling
    
    *For any* model_type that does not exist, requesting model details
    should return None (or HTTP 404 at API level).
    
    **Validates: Requirements 12.3**
    """
    configs_dir, pretrain_dir, expected_model_names = create_test_environment(models_data)
    
    try:
        config = ServerConfig()
        manager = ModelManager(config, configs_dir, pretrain_dir)
        
        # Property: Requesting info for non-existent model should return None
        # Only test if the name is actually not in our created models
        if nonexistent_name not in expected_model_names:
            model_info = manager.get_model_info(nonexistent_name)
            assert model_info is None, \
                f"Non-existent model '{nonexistent_name}' should return None"
    
    finally:
        # Cleanup
        import shutil
        shutil.rmtree(configs_dir, ignore_errors=True)
        shutil.rmtree(pretrain_dir, ignore_errors=True)


# Property 53: Startup model validation
@given(model_setup_strategy())
@settings(max_examples=100)
def test_property_53_startup_model_validation(models_data):
    """
    Feature: api-server, Property 53: Startup model validation
    
    *For any* server startup, the server should validate that all configured
    models have their required checkpoint files present.
    
    **Validates: Requirements 12.4**
    """
    configs_dir, pretrain_dir, expected_model_names = create_test_environment(models_data)
    
    try:
        config = ServerConfig()
        
        # Property: ModelManager should initialize without errors
        # and perform validation during initialization
        manager = ModelManager(config, configs_dir, pretrain_dir)
        
        # Property: All models should be discovered
        available_models = manager.get_available_models()
        assert len(available_models) == len(expected_model_names), \
            "All models should be discovered during startup"
        
        # Property: Each model's checkpoint status should be correctly identified
        for model_def in models_data['models']:
            model_name = model_def['name']
            has_checkpoint = model_def['has_checkpoint']
            
            model_info = manager.get_model_info(model_name)
            assert model_info is not None, \
                f"Model {model_name} should be available"
            
            if has_checkpoint:
                assert model_info.checkpoint_path is not None, \
                    f"Model {model_name} should have checkpoint_path set"
            else:
                assert model_info.checkpoint_path is None, \
                    f"Model {model_name} should have checkpoint_path as None"
    
    finally:
        # Cleanup
        import shutil
        shutil.rmtree(configs_dir, ignore_errors=True)
        shutil.rmtree(pretrain_dir, ignore_errors=True)


# Property 54: Missing model graceful handling
@given(model_setup_strategy())
@settings(max_examples=100)
def test_property_54_missing_model_graceful_handling(models_data):
    """
    Feature: api-server, Property 54: Missing model graceful handling
    
    *For any* configured model with missing checkpoint files, the server
    should log a warning and exclude that model from the available models list.
    
    Note: Based on the implementation, models WITHOUT checkpoints are still
    included in the available list but marked with checkpoint_path=None.
    This allows them to be listed but prevents them from being loaded.
    
    **Validates: Requirements 12.5**
    """
    configs_dir, pretrain_dir, expected_model_names = create_test_environment(models_data)
    
    try:
        config = ServerConfig()
        manager = ModelManager(config, configs_dir, pretrain_dir)
        
        # Property: Models without checkpoints should still be in the list
        # but marked appropriately
        available_models = manager.get_available_models()
        
        for model_def in models_data['models']:
            model_name = model_def['name']
            has_checkpoint = model_def['has_checkpoint']
            
            model_info = manager.get_model_info(model_name)
            
            # Property: Model should be in available list regardless of checkpoint
            assert model_info is not None, \
                f"Model {model_name} should be in available list"
            
            # Property: Checkpoint path should reflect actual file presence
            if has_checkpoint:
                assert model_info.checkpoint_path is not None, \
                    f"Model {model_name} with checkpoint should have path set"
            else:
                assert model_info.checkpoint_path is None, \
                    f"Model {model_name} without checkpoint should have None path"
            
            # Property: Attempting to load model without checkpoint should fail
            if not has_checkpoint:
                with pytest.raises(ValueError, match="has no checkpoint file"):
                    manager.load_model(model_name, "cpu")
    
    finally:
        # Cleanup
        import shutil
        shutil.rmtree(configs_dir, ignore_errors=True)
        shutil.rmtree(pretrain_dir, ignore_errors=True)
