"""
Unit tests for DatabaseManager.

Tests CRUD operations, status transitions, and cleanup functionality.

Validates:
- Requirements 2.2, 2.3, 2.4: Task status management
- Requirements 3.1: Task retrieval
- Requirements 5.1, 5.2, 5.3: Task cleanup
"""

import pytest
import tempfile
import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from api_server.core.database import DatabaseManager
from api_server.models.task import Task, TaskStatus


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    # Cleanup
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture
def db_manager(temp_db):
    """Create a DatabaseManager instance with temporary database."""
    manager = DatabaseManager(temp_db)
    yield manager
    manager.close()


@pytest.fixture
def sample_task():
    """Create a sample task for testing."""
    return Task(
        task_id=str(uuid4()),
        input_file_path="/tmp/test.wav",
        model_type="mdx23c",
        config_path="/configs/mdx23c.yaml",
        instruments=["vocals", "instrumental"],
        file_size_bytes=1024000,
        use_tta=False,
        extract_instrumental=False,
        output_format="wav",
        pcm_type="PCM_24"
    )


class TestDatabaseManagerInitialization:
    """Test database initialization and schema creation."""
    
    def test_database_initialization(self, temp_db):
        """Test that database is initialized with correct schema."""
        manager = DatabaseManager(temp_db)
        assert os.path.exists(temp_db)
        manager.close()
    
    def test_multiple_initialization_safe(self, temp_db):
        """Test that multiple initializations don't cause errors."""
        manager1 = DatabaseManager(temp_db)
        manager1.close()
        
        # Second initialization should work fine
        manager2 = DatabaseManager(temp_db)
        manager2.close()


class TestTaskCreation:
    """Test task creation operations."""
    
    def test_create_task(self, db_manager, sample_task):
        """Test creating a new task."""
        created_task = db_manager.create_task(sample_task)
        
        assert created_task.task_id == sample_task.task_id
        assert created_task.status == TaskStatus.PENDING
        assert created_task.model_type == "mdx23c"
        assert created_task.get_instruments() == ["vocals", "instrumental"]
    
    def test_create_task_with_custom_status(self, db_manager):
        """Test creating a task with custom initial status."""
        task = Task(
            task_id=str(uuid4()),
            input_file_path="/tmp/test.wav",
            model_type="mdx23c",
            config_path="/configs/mdx23c.yaml",
            instruments=["vocals"],
            file_size_bytes=1024000,
            status=TaskStatus.PROCESSING
        )
        
        created_task = db_manager.create_task(task)
        assert created_task.status == TaskStatus.PROCESSING
    
    def test_create_task_with_all_parameters(self, db_manager):
        """Test creating a task with all optional parameters."""
        task = Task(
            task_id=str(uuid4()),
            input_file_path="/tmp/test.flac",
            model_type="htdemucs",
            config_path="/configs/htdemucs.yaml",
            instruments=["vocals", "drums", "bass", "other"],
            file_size_bytes=5000000,
            use_tta=True,
            extract_instrumental=True,
            output_format="flac",
            pcm_type="PCM_16"
        )
        
        created_task = db_manager.create_task(task)
        assert created_task.get_use_tta() is True
        assert created_task.get_extract_instrumental() is True
        assert created_task.output_format == "flac"
        assert created_task.pcm_type == "PCM_16"


class TestTaskRetrieval:
    """Test task retrieval operations."""
    
    def test_get_task_existing(self, db_manager, sample_task):
        """Test retrieving an existing task."""
        db_manager.create_task(sample_task)
        
        retrieved_task = db_manager.get_task(sample_task.task_id)
        assert retrieved_task is not None
        assert retrieved_task.task_id == sample_task.task_id
        assert retrieved_task.model_type == sample_task.model_type
    
    def test_get_task_nonexistent(self, db_manager):
        """Test retrieving a non-existent task returns None."""
        task = db_manager.get_task("nonexistent-id")
        assert task is None
    
    def test_get_task_after_update(self, db_manager, sample_task):
        """Test that retrieved task reflects updates."""
        db_manager.create_task(sample_task)
        db_manager.update_task_status(
            sample_task.task_id,
            TaskStatus.PROCESSING,
            progress=50.0
        )
        
        retrieved_task = db_manager.get_task(sample_task.task_id)
        assert retrieved_task.status == TaskStatus.PROCESSING
        assert retrieved_task.progress == 50.0


class TestTaskStatusUpdates:
    """Test task status update operations."""
    
    def test_update_status_to_processing(self, db_manager, sample_task):
        """Test updating task status to PROCESSING sets started_at."""
        db_manager.create_task(sample_task)
        
        success = db_manager.update_task_status(
            sample_task.task_id,
            TaskStatus.PROCESSING,
            progress=10.0,
            current_stage="Loading model"
        )
        
        assert success is True
        
        task = db_manager.get_task(sample_task.task_id)
        assert task.status == TaskStatus.PROCESSING
        assert task.started_at is not None
        assert task.progress == 10.0
        assert task.current_stage == "Loading model"
    
    def test_update_status_to_completed(self, db_manager, sample_task):
        """Test updating task status to COMPLETED sets completed_at."""
        db_manager.create_task(sample_task)
        
        output_files = {"vocals": "/output/vocals.wav", "instrumental": "/output/instrumental.wav"}
        success = db_manager.update_task_status(
            sample_task.task_id,
            TaskStatus.COMPLETED,
            progress=100.0,
            output_files=output_files,
            processing_time_seconds=45.5
        )
        
        assert success is True
        
        task = db_manager.get_task(sample_task.task_id)
        assert task.status == TaskStatus.COMPLETED
        assert task.completed_at is not None
        assert task.progress == 100.0
        assert task.get_output_files() == output_files
        assert task.processing_time_seconds == 45.5
    
    def test_update_status_to_failed(self, db_manager, sample_task):
        """Test updating task status to FAILED sets error message."""
        db_manager.create_task(sample_task)
        
        success = db_manager.update_task_status(
            sample_task.task_id,
            TaskStatus.FAILED,
            error_message="Model loading failed"
        )
        
        assert success is True
        
        task = db_manager.get_task(sample_task.task_id)
        assert task.status == TaskStatus.FAILED
        assert task.completed_at is not None
        assert task.error_message == "Model loading failed"
    
    def test_update_status_nonexistent_task(self, db_manager):
        """Test updating status of non-existent task returns False."""
        success = db_manager.update_task_status(
            "nonexistent-id",
            TaskStatus.PROCESSING
        )
        assert success is False
    
    def test_update_status_multiple_times(self, db_manager, sample_task):
        """Test updating task status through multiple transitions."""
        db_manager.create_task(sample_task)
        
        # PENDING -> PROCESSING
        db_manager.update_task_status(sample_task.task_id, TaskStatus.PROCESSING, progress=0.0)
        task = db_manager.get_task(sample_task.task_id)
        assert task.status == TaskStatus.PROCESSING
        assert task.started_at is not None
        
        # PROCESSING -> PROCESSING (progress update)
        db_manager.update_task_status(sample_task.task_id, TaskStatus.PROCESSING, progress=50.0)
        task = db_manager.get_task(sample_task.task_id)
        assert task.progress == 50.0
        
        # PROCESSING -> COMPLETED
        db_manager.update_task_status(sample_task.task_id, TaskStatus.COMPLETED, progress=100.0)
        task = db_manager.get_task(sample_task.task_id)
        assert task.status == TaskStatus.COMPLETED
        assert task.completed_at is not None


class TestTaskListing:
    """Test task listing operations."""
    
    def test_list_all_tasks(self, db_manager):
        """Test listing all tasks."""
        # Create multiple tasks
        for i in range(3):
            task = Task(
                task_id=str(uuid4()),
                input_file_path=f"/tmp/test{i}.wav",
                model_type="mdx23c",
                config_path="/configs/mdx23c.yaml",
                instruments=["vocals"],
                file_size_bytes=1024000
            )
            db_manager.create_task(task)
        
        tasks = db_manager.list_tasks()
        assert len(tasks) == 3
    
    def test_list_tasks_by_status(self, db_manager):
        """Test listing tasks filtered by status."""
        # Create tasks with different statuses
        task1 = Task(
            task_id=str(uuid4()),
            input_file_path="/tmp/test1.wav",
            model_type="mdx23c",
            config_path="/configs/mdx23c.yaml",
            instruments=["vocals"],
            file_size_bytes=1024000
        )
        db_manager.create_task(task1)
        
        task2 = Task(
            task_id=str(uuid4()),
            input_file_path="/tmp/test2.wav",
            model_type="mdx23c",
            config_path="/configs/mdx23c.yaml",
            instruments=["vocals"],
            file_size_bytes=1024000
        )
        db_manager.create_task(task2)
        db_manager.update_task_status(task2.task_id, TaskStatus.PROCESSING)
        
        # List only pending tasks
        pending_tasks = db_manager.list_tasks(status=TaskStatus.PENDING)
        assert len(pending_tasks) == 1
        assert pending_tasks[0].task_id == task1.task_id
        
        # List only processing tasks
        processing_tasks = db_manager.list_tasks(status=TaskStatus.PROCESSING)
        assert len(processing_tasks) == 1
        assert processing_tasks[0].task_id == task2.task_id
    
    def test_list_tasks_with_limit(self, db_manager):
        """Test listing tasks with limit."""
        # Create 5 tasks
        for i in range(5):
            task = Task(
                task_id=str(uuid4()),
                input_file_path=f"/tmp/test{i}.wav",
                model_type="mdx23c",
                config_path="/configs/mdx23c.yaml",
                instruments=["vocals"],
                file_size_bytes=1024000
            )
            db_manager.create_task(task)
        
        tasks = db_manager.list_tasks(limit=3)
        assert len(tasks) == 3
    
    def test_list_tasks_with_offset(self, db_manager):
        """Test listing tasks with offset."""
        # Create 5 tasks
        task_ids = []
        for i in range(5):
            task = Task(
                task_id=str(uuid4()),
                input_file_path=f"/tmp/test{i}.wav",
                model_type="mdx23c",
                config_path="/configs/mdx23c.yaml",
                instruments=["vocals"],
                file_size_bytes=1024000
            )
            db_manager.create_task(task)
            task_ids.append(task.task_id)
        
        # Get tasks with offset
        tasks = db_manager.list_tasks(offset=2, limit=2)
        assert len(tasks) == 2


class TestTaskCleanup:
    """Test task cleanup operations."""
    
    def test_cleanup_old_completed_tasks(self, db_manager):
        """Test cleanup of old completed tasks."""
        # Create an old completed task
        old_task = Task(
            task_id=str(uuid4()),
            input_file_path="/tmp/old.wav",
            model_type="mdx23c",
            config_path="/configs/mdx23c.yaml",
            instruments=["vocals"],
            file_size_bytes=1024000
        )
        db_manager.create_task(old_task)
        db_manager.update_task_status(old_task.task_id, TaskStatus.COMPLETED)
        
        # Manually set completed_at to old date
        task = db_manager.get_task(old_task.task_id)
        from api_server.core.database import DatabaseManager
        session = db_manager._get_session()
        db_task = session.query(Task).filter(Task.task_id == old_task.task_id).first()
        db_task.completed_at = datetime.now(timezone.utc) - timedelta(days=10)
        session.commit()
        session.close()
        
        # Run cleanup with 7 day retention
        deleted_count = db_manager.cleanup_old_tasks(metadata_retention_days=7)
        
        assert deleted_count == 1
        assert db_manager.get_task(old_task.task_id) is None
    
    def test_cleanup_old_failed_tasks(self, db_manager):
        """Test cleanup of old failed tasks."""
        # Create an old failed task
        old_task = Task(
            task_id=str(uuid4()),
            input_file_path="/tmp/old.wav",
            model_type="mdx23c",
            config_path="/configs/mdx23c.yaml",
            instruments=["vocals"],
            file_size_bytes=1024000
        )
        db_manager.create_task(old_task)
        db_manager.update_task_status(old_task.task_id, TaskStatus.FAILED, error_message="Test error")
        
        # Manually set completed_at to old date
        session = db_manager._get_session()
        db_task = session.query(Task).filter(Task.task_id == old_task.task_id).first()
        db_task.completed_at = datetime.now(timezone.utc) - timedelta(days=10)
        session.commit()
        session.close()
        
        # Run cleanup with 7 day retention
        deleted_count = db_manager.cleanup_old_tasks(metadata_retention_days=7)
        
        assert deleted_count == 1
        assert db_manager.get_task(old_task.task_id) is None
    
    def test_cleanup_preserves_recent_tasks(self, db_manager):
        """Test that cleanup preserves recent tasks."""
        # Create a recent completed task
        recent_task = Task(
            task_id=str(uuid4()),
            input_file_path="/tmp/recent.wav",
            model_type="mdx23c",
            config_path="/configs/mdx23c.yaml",
            instruments=["vocals"],
            file_size_bytes=1024000
        )
        db_manager.create_task(recent_task)
        db_manager.update_task_status(recent_task.task_id, TaskStatus.COMPLETED)
        
        # Run cleanup
        deleted_count = db_manager.cleanup_old_tasks(
            completed_retention_hours=24,
            metadata_retention_days=7
        )
        
        assert deleted_count == 0
        assert db_manager.get_task(recent_task.task_id) is not None
    
    def test_cleanup_preserves_pending_tasks(self, db_manager):
        """Test that cleanup preserves pending and processing tasks."""
        # Create pending and processing tasks
        pending_task = Task(
            task_id=str(uuid4()),
            input_file_path="/tmp/pending.wav",
            model_type="mdx23c",
            config_path="/configs/mdx23c.yaml",
            instruments=["vocals"],
            file_size_bytes=1024000
        )
        db_manager.create_task(pending_task)
        
        processing_task = Task(
            task_id=str(uuid4()),
            input_file_path="/tmp/processing.wav",
            model_type="mdx23c",
            config_path="/configs/mdx23c.yaml",
            instruments=["vocals"],
            file_size_bytes=1024000
        )
        db_manager.create_task(processing_task)
        db_manager.update_task_status(processing_task.task_id, TaskStatus.PROCESSING)
        
        # Run cleanup
        deleted_count = db_manager.cleanup_old_tasks(metadata_retention_days=0)
        
        # Pending and processing tasks should not be deleted
        assert deleted_count == 0
        assert db_manager.get_task(pending_task.task_id) is not None
        assert db_manager.get_task(processing_task.task_id) is not None


class TestIncompleteTaskRetrieval:
    """Test retrieval of incomplete tasks for resumption."""
    
    def test_get_incomplete_tasks(self, db_manager):
        """Test retrieving incomplete tasks."""
        # Create tasks with various statuses
        pending_task = Task(
            task_id=str(uuid4()),
            input_file_path="/tmp/pending.wav",
            model_type="mdx23c",
            config_path="/configs/mdx23c.yaml",
            instruments=["vocals"],
            file_size_bytes=1024000
        )
        db_manager.create_task(pending_task)
        
        processing_task = Task(
            task_id=str(uuid4()),
            input_file_path="/tmp/processing.wav",
            model_type="mdx23c",
            config_path="/configs/mdx23c.yaml",
            instruments=["vocals"],
            file_size_bytes=1024000
        )
        db_manager.create_task(processing_task)
        db_manager.update_task_status(processing_task.task_id, TaskStatus.PROCESSING)
        
        completed_task = Task(
            task_id=str(uuid4()),
            input_file_path="/tmp/completed.wav",
            model_type="mdx23c",
            config_path="/configs/mdx23c.yaml",
            instruments=["vocals"],
            file_size_bytes=1024000
        )
        db_manager.create_task(completed_task)
        db_manager.update_task_status(completed_task.task_id, TaskStatus.COMPLETED)
        
        # Get incomplete tasks
        incomplete_tasks = db_manager.get_incomplete_tasks()
        
        assert len(incomplete_tasks) == 2
        task_ids = [t.task_id for t in incomplete_tasks]
        assert pending_task.task_id in task_ids
        assert processing_task.task_id in task_ids
        assert completed_task.task_id not in task_ids


class TestTaskDeletion:
    """Test task deletion operations."""
    
    def test_delete_existing_task(self, db_manager, sample_task):
        """Test deleting an existing task."""
        db_manager.create_task(sample_task)
        
        success = db_manager.delete_task(sample_task.task_id)
        assert success is True
        assert db_manager.get_task(sample_task.task_id) is None
    
    def test_delete_nonexistent_task(self, db_manager):
        """Test deleting a non-existent task returns False."""
        success = db_manager.delete_task("nonexistent-id")
        assert success is False


class TestTaskCounting:
    """Test task counting operations."""
    
    def test_get_task_count_all(self, db_manager):
        """Test counting all tasks."""
        # Create multiple tasks
        for i in range(5):
            task = Task(
                task_id=str(uuid4()),
                input_file_path=f"/tmp/test{i}.wav",
                model_type="mdx23c",
                config_path="/configs/mdx23c.yaml",
                instruments=["vocals"],
                file_size_bytes=1024000
            )
            db_manager.create_task(task)
        
        count = db_manager.get_task_count()
        assert count == 5
    
    def test_get_task_count_by_status(self, db_manager):
        """Test counting tasks by status."""
        # Create tasks with different statuses
        for i in range(3):
            task = Task(
                task_id=str(uuid4()),
                input_file_path=f"/tmp/pending{i}.wav",
                model_type="mdx23c",
                config_path="/configs/mdx23c.yaml",
                instruments=["vocals"],
                file_size_bytes=1024000
            )
            db_manager.create_task(task)
        
        for i in range(2):
            task = Task(
                task_id=str(uuid4()),
                input_file_path=f"/tmp/completed{i}.wav",
                model_type="mdx23c",
                config_path="/configs/mdx23c.yaml",
                instruments=["vocals"],
                file_size_bytes=1024000
            )
            db_manager.create_task(task)
            db_manager.update_task_status(task.task_id, TaskStatus.COMPLETED)
        
        pending_count = db_manager.get_task_count(status=TaskStatus.PENDING)
        completed_count = db_manager.get_task_count(status=TaskStatus.COMPLETED)
        
        assert pending_count == 3
        assert completed_count == 2
