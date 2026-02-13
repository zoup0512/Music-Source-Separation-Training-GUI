"""
Task data models for the API server.

This module defines the Task model and TaskStatus enum for tracking
separation tasks throughout their lifecycle.

Validates:
- Requirements 2.2: Task status updates
- Requirements 2.3: Task completion tracking
- Requirements 2.4: Task failure tracking
- Requirements 3.1: Task status retrieval
"""

from enum import Enum
from datetime import datetime, timezone
from typing import Optional, List, Dict
from sqlalchemy import (
    Column, String, Integer, Float, DateTime, Text, Index, Enum as SQLEnum
)
from sqlalchemy.orm import declarative_base
import json


Base = declarative_base()


class TaskStatus(str, Enum):
    """
    Task status enumeration.
    
    Represents the lifecycle states of a separation task:
    - PENDING: Task created and queued for processing
    - PROCESSING: Task currently being processed
    - COMPLETED: Task successfully completed
    - FAILED: Task failed with an error
    - CANCELLED: Task cancelled by user
    """
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Task(Base):
    """
    Task data model for audio separation tasks.
    
    Represents a separation task throughout its lifecycle, storing all
    input parameters, progress tracking, and results.
    
    Validates:
    - Requirements 2.2: Task status tracking
    - Requirements 2.3: Task completion
    - Requirements 2.4: Task failure handling
    - Requirements 3.1: Task status retrieval
    """
    
    __tablename__ = "tasks"
    
    # Primary identifier
    task_id = Column(String, primary_key=True, nullable=False)
    
    # Status tracking
    status = Column(
        SQLEnum(TaskStatus),
        nullable=False,
        default=TaskStatus.PENDING,
        index=True
    )
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), index=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True, index=True)
    
    # Input parameters
    input_file_path = Column(String, nullable=False)
    model_type = Column(String, nullable=False)
    config_path = Column(String, nullable=False)
    instruments = Column(Text, nullable=False)  # JSON array
    use_tta = Column(Integer, nullable=False, default=0)  # Boolean as integer
    extract_instrumental = Column(Integer, nullable=False, default=0)  # Boolean as integer
    output_format = Column(String, nullable=False, default="wav")
    pcm_type = Column(String, nullable=False, default="PCM_24")
    
    # Progress tracking
    progress = Column(Float, nullable=False, default=0.0)
    current_stage = Column(String, nullable=True)
    estimated_completion = Column(DateTime, nullable=True)
    
    # Results
    output_files = Column(Text, nullable=True)  # JSON object
    error_message = Column(Text, nullable=True)
    
    # Metadata
    file_size_bytes = Column(Integer, nullable=False)
    processing_time_seconds = Column(Float, nullable=True)
    
    def __init__(
        self,
        task_id: str,
        input_file_path: str,
        model_type: str,
        config_path: str,
        instruments: List[str],
        file_size_bytes: int,
        use_tta: bool = False,
        extract_instrumental: bool = False,
        output_format: str = "wav",
        pcm_type: str = "PCM_24",
        status: TaskStatus = TaskStatus.PENDING,
        created_at: Optional[datetime] = None,
    ):
        """
        Initialize a new Task.
        
        Args:
            task_id: Unique task identifier (UUID4)
            input_file_path: Path to uploaded audio file
            model_type: Model type identifier
            config_path: Path to model config file
            instruments: List of requested instruments
            file_size_bytes: Original file size in bytes
            use_tta: Test time augmentation flag
            extract_instrumental: Extract instrumental flag
            output_format: Output format ("wav" or "flac")
            pcm_type: PCM type ("PCM_16" or "PCM_24")
            status: Initial task status
            created_at: Task creation timestamp (defaults to now)
        """
        self.task_id = task_id
        self.status = status
        self.created_at = created_at or datetime.now(timezone.utc)
        self.started_at = None
        self.completed_at = None
        
        self.input_file_path = input_file_path
        self.model_type = model_type
        self.config_path = config_path
        self.instruments = json.dumps(instruments)
        self.use_tta = 1 if use_tta else 0
        self.extract_instrumental = 1 if extract_instrumental else 0
        self.output_format = output_format
        self.pcm_type = pcm_type
        
        self.progress = 0.0
        self.current_stage = None
        self.estimated_completion = None
        
        self.output_files = None
        self.error_message = None
        
        self.file_size_bytes = file_size_bytes
        self.processing_time_seconds = None
    
    def get_instruments(self) -> List[str]:
        """
        Get instruments list from JSON string.
        
        Returns:
            List of instrument names
        """
        return json.loads(self.instruments)
    
    def set_instruments(self, instruments: List[str]) -> None:
        """
        Set instruments list as JSON string.
        
        Args:
            instruments: List of instrument names
        """
        self.instruments = json.dumps(instruments)
    
    def get_output_files(self) -> Optional[Dict[str, str]]:
        """
        Get output files dictionary from JSON string.
        
        Returns:
            Dictionary mapping instrument names to file paths, or None
        """
        if self.output_files is None:
            return None
        return json.loads(self.output_files)
    
    def set_output_files(self, output_files: Dict[str, str]) -> None:
        """
        Set output files dictionary as JSON string.
        
        Args:
            output_files: Dictionary mapping instrument names to file paths
        """
        self.output_files = json.dumps(output_files)
    
    def get_use_tta(self) -> bool:
        """Get use_tta as boolean."""
        return bool(self.use_tta)
    
    def get_extract_instrumental(self) -> bool:
        """Get extract_instrumental as boolean."""
        return bool(self.extract_instrumental)
    
    def to_dict(self) -> dict:
        """
        Convert task to dictionary representation.
        
        Returns:
            Dictionary with all task fields
        """
        return {
            "task_id": self.task_id,
            "status": self.status.value,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "input_file_path": self.input_file_path,
            "model_type": self.model_type,
            "config_path": self.config_path,
            "instruments": self.get_instruments(),
            "use_tta": self.get_use_tta(),
            "extract_instrumental": self.get_extract_instrumental(),
            "output_format": self.output_format,
            "pcm_type": self.pcm_type,
            "progress": self.progress,
            "current_stage": self.current_stage,
            "estimated_completion": self.estimated_completion.isoformat() if self.estimated_completion else None,
            "output_files": self.get_output_files(),
            "error_message": self.error_message,
            "file_size_bytes": self.file_size_bytes,
            "processing_time_seconds": self.processing_time_seconds,
        }
    
    def __repr__(self) -> str:
        """String representation of Task."""
        return (
            f"<Task(task_id='{self.task_id}', "
            f"status='{self.status.value}', "
            f"model_type='{self.model_type}')>"
        )


# Create indexes for efficient querying
Index('idx_status', Task.status)
Index('idx_created_at', Task.created_at)
Index('idx_completed_at', Task.completed_at)
