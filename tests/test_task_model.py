"""
Unit tests for Task data model.

Tests task creation, status transitions, and data serialization.
"""

import pytest
from datetime import datetime, timezone
from api_server.models.task import Task, TaskStatus


class TestTaskStatus:
    """Tests for TaskStatus enum."""
    
    def test_status_values(self):
        """Test that all status values are defined correctly."""
        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.PROCESSING.value == "processing"
        assert TaskStatus.COMPLETED.value == "completed"
        assert TaskStatus.FAILED.value == "failed"
        assert TaskStatus.CANCELLED.value == "cancelled"
    
    def test_status_is_string_enum(self):
        """Test that TaskStatus is a string enum."""
        assert isinstance(TaskStatus.PENDING, str)
        assert isinstance(TaskStatus.PROCESSING, str)


class TestTask:
    """Tests for Task model."""
    
    def test_task_creation_minimal(self):
        """Test creating a task with minimal required parameters."""
        task = Task(
            task_id="test-uuid-123",
            input_file_path="/tmp/audio.wav",
            model_type="mdx23c",
            config_path="/configs/mdx23c.yaml",
            instruments=["vocals", "instrumental"],
            file_size_bytes=1024000
        )
        
        assert task.task_id == "test-uuid-123"
        assert task.input_file_path == "/tmp/audio.wav"
        assert task.model_type == "mdx23c"
        assert task.config_path == "/configs/mdx23c.yaml"
        assert task.get_instruments() == ["vocals", "instrumental"]
        assert task.file_size_bytes == 1024000
        assert task.status == TaskStatus.PENDING
        assert task.progress == 0.0
        assert task.get_use_tta() is False
        assert task.get_extract_instrumental() is False
        assert task.output_format == "wav"
        assert task.pcm_type == "PCM_24"
    
    def test_task_creation_with_all_parameters(self):
        """Test creating a task with all parameters."""
        created_at = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        task = Task(
            task_id="test-uuid-456",
            input_file_path="/tmp/audio.flac",
            model_type="htdemucs",
            config_path="/configs/htdemucs.yaml",
            instruments=["vocals", "drums", "bass", "other"],
            file_size_bytes=2048000,
            use_tta=True,
            extract_instrumental=True,
            output_format="flac",
            pcm_type="PCM_16",
            status=TaskStatus.PROCESSING,
            created_at=created_at
        )
        
        assert task.task_id == "test-uuid-456"
        assert task.status == TaskStatus.PROCESSING
        assert task.created_at == created_at
        assert task.get_use_tta() is True
        assert task.get_extract_instrumental() is True
        assert task.output_format == "flac"
        assert task.pcm_type == "PCM_16"
        assert task.get_instruments() == ["vocals", "drums", "bass", "other"]
    
    def test_instruments_json_serialization(self):
        """Test that instruments are properly serialized to/from JSON."""
        task = Task(
            task_id="test-uuid-789",
            input_file_path="/tmp/audio.mp3",
            model_type="mdx23c",
            config_path="/configs/mdx23c.yaml",
            instruments=["vocals", "instrumental"],
            file_size_bytes=512000
        )
        
        # Check JSON storage
        assert '"vocals"' in task.instruments
        assert '"instrumental"' in task.instruments
        
        # Check retrieval
        assert task.get_instruments() == ["vocals", "instrumental"]
        
        # Test setting new instruments
        task.set_instruments(["drums", "bass"])
        assert task.get_instruments() == ["drums", "bass"]
    
    def test_output_files_json_serialization(self):
        """Test that output files are properly serialized to/from JSON."""
        task = Task(
            task_id="test-uuid-101",
            input_file_path="/tmp/audio.wav",
            model_type="mdx23c",
            config_path="/configs/mdx23c.yaml",
            instruments=["vocals", "instrumental"],
            file_size_bytes=1024000
        )
        
        # Initially None
        assert task.get_output_files() is None
        
        # Set output files
        output_files = {
            "vocals": "/output/vocals.wav",
            "instrumental": "/output/instrumental.wav"
        }
        task.set_output_files(output_files)
        
        # Check retrieval
        assert task.get_output_files() == output_files
    
    def test_boolean_fields_storage(self):
        """Test that boolean fields are stored as integers."""
        task = Task(
            task_id="test-uuid-202",
            input_file_path="/tmp/audio.wav",
            model_type="mdx23c",
            config_path="/configs/mdx23c.yaml",
            instruments=["vocals"],
            file_size_bytes=1024000,
            use_tta=True,
            extract_instrumental=False
        )
        
        # Check integer storage
        assert task.use_tta == 1
        assert task.extract_instrumental == 0
        
        # Check boolean retrieval
        assert task.get_use_tta() is True
        assert task.get_extract_instrumental() is False
    
    def test_to_dict_conversion(self):
        """Test converting task to dictionary."""
        created_at = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        task = Task(
            task_id="test-uuid-303",
            input_file_path="/tmp/audio.wav",
            model_type="mdx23c",
            config_path="/configs/mdx23c.yaml",
            instruments=["vocals", "instrumental"],
            file_size_bytes=1024000,
            use_tta=True,
            extract_instrumental=False,
            output_format="wav",
            pcm_type="PCM_24",
            created_at=created_at
        )
        
        task_dict = task.to_dict()
        
        assert task_dict["task_id"] == "test-uuid-303"
        assert task_dict["status"] == "pending"
        assert task_dict["created_at"] == created_at.isoformat()
        assert task_dict["input_file_path"] == "/tmp/audio.wav"
        assert task_dict["model_type"] == "mdx23c"
        assert task_dict["instruments"] == ["vocals", "instrumental"]
        assert task_dict["use_tta"] is True
        assert task_dict["extract_instrumental"] is False
        assert task_dict["output_format"] == "wav"
        assert task_dict["pcm_type"] == "PCM_24"
        assert task_dict["progress"] == 0.0
        assert task_dict["file_size_bytes"] == 1024000
    
    def test_to_dict_with_optional_fields(self):
        """Test to_dict with optional fields populated."""
        created_at = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        started_at = datetime(2024, 1, 15, 10, 30, 5, tzinfo=timezone.utc)
        completed_at = datetime(2024, 1, 15, 10, 31, 45, tzinfo=timezone.utc)
        estimated_completion = datetime(2024, 1, 15, 10, 32, 0, tzinfo=timezone.utc)
        
        task = Task(
            task_id="test-uuid-404",
            input_file_path="/tmp/audio.wav",
            model_type="mdx23c",
            config_path="/configs/mdx23c.yaml",
            instruments=["vocals"],
            file_size_bytes=1024000,
            created_at=created_at
        )
        
        task.status = TaskStatus.COMPLETED
        task.started_at = started_at
        task.completed_at = completed_at
        task.progress = 100.0
        task.current_stage = "Finalizing"
        task.estimated_completion = estimated_completion
        task.processing_time_seconds = 100.5
        task.set_output_files({"vocals": "/output/vocals.wav"})
        
        task_dict = task.to_dict()
        
        assert task_dict["status"] == "completed"
        assert task_dict["started_at"] == started_at.isoformat()
        assert task_dict["completed_at"] == completed_at.isoformat()
        assert task_dict["progress"] == 100.0
        assert task_dict["current_stage"] == "Finalizing"
        assert task_dict["estimated_completion"] == estimated_completion.isoformat()
        assert task_dict["processing_time_seconds"] == 100.5
        assert task_dict["output_files"] == {"vocals": "/output/vocals.wav"}
    
    def test_to_dict_with_error(self):
        """Test to_dict with error message."""
        task = Task(
            task_id="test-uuid-505",
            input_file_path="/tmp/audio.wav",
            model_type="mdx23c",
            config_path="/configs/mdx23c.yaml",
            instruments=["vocals"],
            file_size_bytes=1024000
        )
        
        task.status = TaskStatus.FAILED
        task.error_message = "Model loading failed"
        
        task_dict = task.to_dict()
        
        assert task_dict["status"] == "failed"
        assert task_dict["error_message"] == "Model loading failed"
    
    def test_repr(self):
        """Test string representation of task."""
        task = Task(
            task_id="test-uuid-606",
            input_file_path="/tmp/audio.wav",
            model_type="mdx23c",
            config_path="/configs/mdx23c.yaml",
            instruments=["vocals"],
            file_size_bytes=1024000
        )
        
        repr_str = repr(task)
        assert "test-uuid-606" in repr_str
        assert "pending" in repr_str
        assert "mdx23c" in repr_str
    
    def test_status_transitions(self):
        """Test that status can be updated through lifecycle."""
        task = Task(
            task_id="test-uuid-707",
            input_file_path="/tmp/audio.wav",
            model_type="mdx23c",
            config_path="/configs/mdx23c.yaml",
            instruments=["vocals"],
            file_size_bytes=1024000
        )
        
        # Initial state
        assert task.status == TaskStatus.PENDING
        
        # Start processing
        task.status = TaskStatus.PROCESSING
        task.started_at = datetime.now(timezone.utc)
        assert task.status == TaskStatus.PROCESSING
        assert task.started_at is not None
        
        # Complete
        task.status = TaskStatus.COMPLETED
        task.completed_at = datetime.now(timezone.utc)
        task.progress = 100.0
        assert task.status == TaskStatus.COMPLETED
        assert task.completed_at is not None
        assert task.progress == 100.0
    
    def test_progress_tracking(self):
        """Test progress tracking fields."""
        task = Task(
            task_id="test-uuid-808",
            input_file_path="/tmp/audio.wav",
            model_type="mdx23c",
            config_path="/configs/mdx23c.yaml",
            instruments=["vocals"],
            file_size_bytes=1024000
        )
        
        # Update progress
        task.progress = 25.5
        task.current_stage = "Processing vocals"
        task.estimated_completion = datetime(2024, 1, 15, 10, 32, 0, tzinfo=timezone.utc)
        
        assert task.progress == 25.5
        assert task.current_stage == "Processing vocals"
        assert task.estimated_completion is not None
    
    def test_timestamps_default_to_none(self):
        """Test that optional timestamps default to None."""
        task = Task(
            task_id="test-uuid-909",
            input_file_path="/tmp/audio.wav",
            model_type="mdx23c",
            config_path="/configs/mdx23c.yaml",
            instruments=["vocals"],
            file_size_bytes=1024000
        )
        
        assert task.started_at is None
        assert task.completed_at is None
        assert task.estimated_completion is None
    
    def test_created_at_defaults_to_now(self):
        """Test that created_at defaults to current time."""
        before = datetime.now(timezone.utc)
        task = Task(
            task_id="test-uuid-1010",
            input_file_path="/tmp/audio.wav",
            model_type="mdx23c",
            config_path="/configs/mdx23c.yaml",
            instruments=["vocals"],
            file_size_bytes=1024000
        )
        after = datetime.now(timezone.utc)
        
        assert before <= task.created_at <= after
