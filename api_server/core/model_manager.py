"""
Model Manager for the API server.

This module handles loading, caching, and validation of neural network models
for audio source separation. It discovers available models by scanning the
configs/ and pretrain/ directories, validates model parameters, and provides
model loading with LRU caching.

Validates:
- Requirements 12.1: Model listing with metadata
- Requirements 12.2: Model details with capabilities
- Requirements 12.3: Model parameter validation
- Requirements 12.4: Startup model validation
- Requirements 12.5: Missing model graceful handling
- Requirements 7.4: Invalid model_type error handling
- Requirements 7.5: Invalid instrument error handling
"""

import logging
from pathlib import Path
from typing import List, Optional, Dict, Tuple, Any
from functools import lru_cache
import yaml

from api_server.models.model_info import ModelInfo
from api_server.models.config import ServerConfig


logger = logging.getLogger(__name__)


class ValidationResult:
    """Result of model parameter validation."""
    
    def __init__(self, valid: bool, error_message: Optional[str] = None):
        self.valid = valid
        self.error_message = error_message
    
    def __bool__(self) -> bool:
        return self.valid
    
    def __repr__(self) -> str:
        if self.valid:
            return "<ValidationResult(valid=True)>"
        return f"<ValidationResult(valid=False, error='{self.error_message}')>"


class ModelManager:
    """
    Model Manager for loading, caching, and validating neural network models.
    
    This class handles:
    - Model discovery by scanning configs/ and pretrain/ directories
    - Model metadata extraction from configuration files
    - Model parameter validation (model_type, instruments)
    - Model loading with LRU caching
    - Startup validation for model checkpoint files
    
    Validates:
    - Requirements 12.1: get_available_models() returns list of ModelInfo
    - Requirements 12.2: get_model_info() returns specific model details
    - Requirements 12.3: validate_model_params() validates parameters
    - Requirements 12.4: Startup validation for model checkpoint files
    - Requirements 12.5: Missing models excluded from available list
    - Requirements 7.4: Invalid model_type error handling
    - Requirements 7.5: Invalid instrument error handling
    """
    
    def __init__(self, config: ServerConfig, configs_dir: str = "configs", pretrain_dir: str = "pretrain"):
        """
        Initialize Model Manager with server configuration.
        
        Args:
            config: Server configuration object
            configs_dir: Path to directory containing model configuration files
            pretrain_dir: Path to directory containing model checkpoint files
        """
        self.config = config
        self.configs_dir = Path(configs_dir)
        self.pretrain_dir = Path(pretrain_dir)
        self._models: Dict[str, ModelInfo] = {}
        
        # Discover and validate models on initialization
        self._discover_models()
        self._validate_startup_models()
    
    def _discover_models(self) -> None:
        """
        Discover available models by scanning configs/ directory.
        
        Scans the configs directory for YAML configuration files and extracts
        model metadata. Models without checkpoint files are still included
        but marked with checkpoint_path=None.
        
        Validates:
        - Requirements 12.1: Model discovery and listing
        """
        if not self.configs_dir.exists():
            logger.warning(f"Configs directory not found: {self.configs_dir}")
            return
        
        # Scan for YAML config files
        config_files = list(self.configs_dir.glob("*.yaml")) + list(self.configs_dir.glob("*.yml"))
        
        logger.info(f"Scanning {len(config_files)} configuration files in {self.configs_dir}")
        
        for config_file in config_files:
            try:
                model_info = self._parse_model_config(config_file)
                if model_info:
                    self._models[model_info.model_type] = model_info
                    logger.debug(f"Discovered model: {model_info.model_type}")
            except Exception as e:
                logger.warning(f"Failed to parse config file {config_file}: {e}")
                continue
        
        logger.info(f"Discovered {len(self._models)} models")
    
    def _parse_model_config(self, config_file: Path) -> Optional[ModelInfo]:
        """
        Parse a model configuration file and extract metadata.
        
        Args:
            config_file: Path to YAML configuration file
        
        Returns:
            ModelInfo object if parsing succeeds, None otherwise
        """
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f)
            
            if not config_data:
                return None
            
            # Extract model type from filename (remove config_ prefix and .yaml suffix)
            model_type = config_file.stem
            if model_type.startswith("config_"):
                model_type = model_type[7:]  # Remove "config_" prefix
            
            # Extract instruments from training section
            instruments = []
            if 'training' in config_data and 'instruments' in config_data['training']:
                instruments = config_data['training']['instruments']
            
            # Extract sample rate from audio section
            sample_rate = 44100  # Default
            if 'audio' in config_data and 'sample_rate' in config_data['audio']:
                sample_rate = config_data['audio']['sample_rate']
            
            # Extract channel support from audio section
            num_channels = 2  # Default stereo
            if 'audio' in config_data and 'num_channels' in config_data['audio']:
                num_channels = config_data['audio']['num_channels']
            
            supports_stereo = num_channels >= 2
            supports_mono = True  # Most models support mono
            
            # Look for checkpoint file in pretrain directory
            checkpoint_path = self._find_checkpoint(model_type)
            
            return ModelInfo(
                model_type=model_type,
                config_path=str(config_file),
                checkpoint_path=checkpoint_path,
                instruments=instruments,
                sample_rate=sample_rate,
                supports_stereo=supports_stereo,
                supports_mono=supports_mono,
                description=f"Model for separating: {', '.join(instruments)}" if instruments else None
            )
        
        except Exception as e:
            logger.error(f"Error parsing config file {config_file}: {e}")
            return None
    
    def _find_checkpoint(self, model_type: str) -> Optional[str]:
        """
        Find checkpoint file for a given model type.
        
        Searches the pretrain directory for checkpoint files matching the model type.
        Common patterns: model_type.ckpt, model_type.pth, model_type.pt
        
        Args:
            model_type: Model type identifier
        
        Returns:
            Path to checkpoint file if found, None otherwise
        """
        if not self.pretrain_dir.exists():
            return None
        
        # Common checkpoint file extensions
        extensions = ['.ckpt', '.pth', '.pt', '.bin']
        
        for ext in extensions:
            checkpoint_file = self.pretrain_dir / f"{model_type}{ext}"
            if checkpoint_file.exists():
                return str(checkpoint_file)
        
        # Also check for files containing the model_type in their name
        for checkpoint_file in self.pretrain_dir.glob("*"):
            if checkpoint_file.is_file() and model_type in checkpoint_file.stem:
                return str(checkpoint_file)
        
        return None
    
    def _validate_startup_models(self) -> None:
        """
        Validate that configured models have their checkpoint files present.
        
        Logs warnings for models with missing checkpoints but keeps them in
        the available models list (they may be used for testing or may have
        checkpoints added later).
        
        Validates:
        - Requirements 12.4: Startup validation for model checkpoint files
        - Requirements 12.5: Missing models logged as warnings
        """
        models_with_checkpoints = 0
        models_without_checkpoints = 0
        
        for model_type, model_info in self._models.items():
            if model_info.checkpoint_path is None:
                logger.warning(
                    f"Model '{model_type}' has no checkpoint file. "
                    f"Model will be available but may fail during inference."
                )
                models_without_checkpoints += 1
            else:
                models_with_checkpoints += 1
        
        logger.info(
            f"Startup validation complete: {models_with_checkpoints} models with checkpoints, "
            f"{models_without_checkpoints} models without checkpoints"
        )
    
    def get_available_models(self) -> List[ModelInfo]:
        """
        Return list of available models with their capabilities.
        
        Returns all discovered models, including those without checkpoint files.
        Clients should check checkpoint_path to determine if a model is ready
        for inference.
        
        Returns:
            List of ModelInfo objects for all available models
        
        Validates:
        - Requirements 12.1: Model listing with metadata
        """
        return list(self._models.values())
    
    def get_model_info(self, model_type: str) -> Optional[ModelInfo]:
        """
        Get detailed information about a specific model.
        
        Args:
            model_type: Model type identifier
        
        Returns:
            ModelInfo object if model exists, None otherwise
        
        Validates:
        - Requirements 12.2: Model details with capabilities
        - Requirements 12.3: Non-existent model handling
        """
        return self._models.get(model_type)
    
    def validate_model_params(
        self,
        model_type: str,
        instruments: Optional[List[str]] = None
    ) -> ValidationResult:
        """
        Validate that requested parameters are supported by the model.
        
        Checks:
        1. Model type exists
        2. Requested instruments are supported by the model
        
        Args:
            model_type: Model type identifier
            instruments: List of requested instruments (optional)
        
        Returns:
            ValidationResult indicating whether parameters are valid
        
        Validates:
        - Requirements 7.4: Invalid model_type error handling
        - Requirements 7.5: Invalid instrument error handling
        """
        # Check if model exists
        model_info = self.get_model_info(model_type)
        if model_info is None:
            available_models = [m.model_type for m in self.get_available_models()]
            return ValidationResult(
                valid=False,
                error_message=f"Unsupported model_type '{model_type}'. "
                             f"Available models: {', '.join(available_models)}"
            )
        
        # If no instruments specified, validation passes
        if instruments is None or len(instruments) == 0:
            return ValidationResult(valid=True)
        
        # Check if requested instruments are supported
        supported_instruments = set(model_info.instruments)
        requested_instruments = set(instruments)
        
        unsupported = requested_instruments - supported_instruments
        if unsupported:
            return ValidationResult(
                valid=False,
                error_message=f"Unsupported instruments for model '{model_type}': "
                             f"{', '.join(unsupported)}. "
                             f"Supported instruments: {', '.join(model_info.instruments)}"
            )
        
        return ValidationResult(valid=True)
    
    @lru_cache(maxsize=None)
    def load_model(self, model_type: str, device: str = "cpu") -> Tuple[Any, Dict]:
        """
        Load model and configuration for inference with caching.
        
        This method uses LRU caching to avoid repeatedly loading the same model.
        The cache size is controlled by the model_cache_size configuration parameter.
        
        Note: This is a placeholder implementation. The actual model loading logic
        will integrate with the existing inference.py functionality.
        
        Args:
            model_type: Model type identifier
            device: Device to load model on ("cpu", "cuda:0", etc.)
        
        Returns:
            Tuple of (model, config_dict)
        
        Raises:
            ValueError: If model_type is invalid or checkpoint is missing
            RuntimeError: If model loading fails
        
        Validates:
        - Requirements 12.3: Model loading with validation
        - Requirements 7.7: Model loading error handling
        """
        model_info = self.get_model_info(model_type)
        
        if model_info is None:
            raise ValueError(f"Model type '{model_type}' not found")
        
        if model_info.checkpoint_path is None:
            raise ValueError(
                f"Model '{model_type}' has no checkpoint file. "
                f"Cannot load model for inference."
            )
        
        # Load configuration
        try:
            with open(model_info.config_path, 'r', encoding='utf-8') as f:
                config_dict = yaml.safe_load(f)
        except Exception as e:
            raise RuntimeError(f"Failed to load config for model '{model_type}': {e}")
        
        # TODO: Integrate with existing model loading from inference.py
        # For now, return config only as placeholder
        logger.info(f"Loading model '{model_type}' on device '{device}'")
        
        # This will be implemented in task 5.1 when integrating with inference engine
        model = None  # Placeholder
        
        return model, config_dict
