"""
Model information data models for the API server.

This module defines the ModelInfo model for describing available models
and their capabilities.

Validates:
- Requirements 12.1: Model listing with metadata
- Requirements 12.2: Model details with capabilities
"""

from typing import Optional, List
from pydantic import BaseModel, Field


class ModelInfo(BaseModel):
    """
    Model information data model.
    
    Describes available models and their capabilities for audio source separation.
    Used by the Model Manager to provide model metadata to API consumers.
    
    Validates:
    - Requirements 12.1: Model type and configuration paths
    - Requirements 12.2: Model capabilities (instruments, sample rate, stereo support)
    """
    
    model_type: str = Field(
        ...,
        description="Model type identifier (e.g., 'mdx23c', 'htdemucs')"
    )
    
    config_path: str = Field(
        ...,
        description="Path to model configuration file"
    )
    
    checkpoint_path: Optional[str] = Field(
        default=None,
        description="Path to model checkpoint file (None if not found)"
    )
    
    instruments: List[str] = Field(
        default_factory=list,
        description="List of supported instruments/sources (e.g., ['vocals', 'instrumental'])"
    )
    
    sample_rate: int = Field(
        default=44100,
        ge=8000,
        le=192000,
        description="Audio sample rate in Hz"
    )
    
    supports_stereo: bool = Field(
        default=True,
        description="Whether the model supports stereo input"
    )
    
    supports_mono: bool = Field(
        default=True,
        description="Whether the model supports mono input"
    )
    
    description: Optional[str] = Field(
        default=None,
        description="Human-readable description of the model"
    )
    
    def __repr__(self) -> str:
        """String representation of ModelInfo."""
        return (
            f"<ModelInfo(model_type='{self.model_type}', "
            f"instruments={self.instruments}, "
            f"sample_rate={self.sample_rate})>"
        )
    
    def to_dict(self) -> dict:
        """
        Convert ModelInfo to dictionary representation.
        
        Returns:
            Dictionary with all model information fields
        """
        return {
            "model_type": self.model_type,
            "config_path": self.config_path,
            "checkpoint_path": self.checkpoint_path,
            "instruments": self.instruments,
            "sample_rate": self.sample_rate,
            "supports_stereo": self.supports_stereo,
            "supports_mono": self.supports_mono,
            "description": self.description,
        }
