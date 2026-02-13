"""
Database manager for the API server.

This module provides the DatabaseManager class for handling all database
operations including task CRUD operations, status updates, and cleanup.

Validates:
- Requirements 2.2: Task status updates
- Requirements 2.3: Task completion tracking
- Requirements 2.4: Task failure tracking
- Requirements 3.1: Task status retrieval
- Requirements 5.1: Completed task cleanup
- Requirements 5.2: Task metadata cleanup
- Requirements 5.3: Failed task cleanup
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, List
from sqlalchemy import create_engine, and_, or_
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError
import logging

from api_server.models.task import Base, Task, TaskStatus


logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Database manager for task persistence and retrieval.
    
    Handles all database operations including:
    - Task creation and retrieval
    - Status updates and progress tracking
    - Cleanup of old tasks and metadata
    - Database initialization and migrations
    
    Validates:
    - Requirements 2.2, 2.3, 2.4: Task status management
    - Requirements 3.1: Task retrieval
    - Requirements 5.1, 5.2, 5.3: Task cleanup
    """
    
    def __init__(self, database_path: str):
        """
        Initialize database manager with connection to SQLite database.
        
        Args:
            database_path: Path to SQLite database file
        """
        self.database_path = database_path
        self.engine = create_engine(
            f"sqlite:///{database_path}",
            echo=False,
            connect_args={"check_same_thread": False}
        )
        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine
        )
        
        # Initialize database schema
        self._initialize_database()
        
        logger.info(f"DatabaseManager initialized with database: {database_path}")
    
    def _initialize_database(self) -> None:
        """
        Initialize database schema by creating all tables.
        
        Creates tables if they don't exist. Safe to call multiple times.
        """
        try:
            Base.metadata.create_all(bind=self.engine)
            logger.info("Database schema initialized successfully")
        except SQLAlchemyError as e:
            logger.error(f"Failed to initialize database schema: {e}")
            raise
    
    def _get_session(self) -> Session:
        """
        Get a new database session.
        
        Returns:
            SQLAlchemy session
        """
        return self.SessionLocal()
    
    def create_task(self, task: Task) -> Task:
        """
        Create a new task in the database.
        
        Args:
            task: Task object to persist
            
        Returns:
            The created task
            
        Raises:
            SQLAlchemyError: If database operation fails
        """
        session = self._get_session()
        try:
            session.add(task)
            session.commit()
            session.refresh(task)
            logger.info(f"Created task: {task.task_id}")
            return task
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Failed to create task {task.task_id}: {e}")
            raise
        finally:
            session.close()
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """
        Retrieve a task by its ID.
        
        Args:
            task_id: Unique task identifier
            
        Returns:
            Task object if found, None otherwise
        """
        session = self._get_session()
        try:
            task = session.query(Task).filter(Task.task_id == task_id).first()
            if task:
                # Detach from session to avoid lazy loading issues
                session.expunge(task)
            return task
        except SQLAlchemyError as e:
            logger.error(f"Failed to retrieve task {task_id}: {e}")
            return None
        finally:
            session.close()
    
    def update_task_status(
        self,
        task_id: str,
        status: TaskStatus,
        progress: Optional[float] = None,
        current_stage: Optional[str] = None,
        error_message: Optional[str] = None,
        output_files: Optional[dict] = None,
        processing_time_seconds: Optional[float] = None
    ) -> bool:
        """
        Update task status and related fields.
        
        Args:
            task_id: Unique task identifier
            status: New task status
            progress: Progress percentage (0.0 to 100.0)
            current_stage: Current processing stage description
            error_message: Error message if task failed
            output_files: Dictionary of output files if completed
            processing_time_seconds: Total processing time
            
        Returns:
            True if update successful, False otherwise
            
        Validates:
        - Requirements 2.2: Status updates to "processing"
        - Requirements 2.3: Status updates to "completed"
        - Requirements 2.4: Status updates to "failed"
        """
        session = self._get_session()
        try:
            task = session.query(Task).filter(Task.task_id == task_id).first()
            if not task:
                logger.warning(f"Task {task_id} not found for status update")
                return False
            
            # Update status
            task.status = status
            
            # Update timestamps based on status
            now = datetime.now(timezone.utc)
            if status == TaskStatus.PROCESSING and task.started_at is None:
                task.started_at = now
            elif status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
                if task.completed_at is None:
                    task.completed_at = now
            
            # Update optional fields
            if progress is not None:
                task.progress = progress
            if current_stage is not None:
                task.current_stage = current_stage
            if error_message is not None:
                task.error_message = error_message
            if output_files is not None:
                task.set_output_files(output_files)
            if processing_time_seconds is not None:
                task.processing_time_seconds = processing_time_seconds
            
            session.commit()
            logger.info(f"Updated task {task_id} status to {status.value}")
            return True
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Failed to update task {task_id} status: {e}")
            return False
        finally:
            session.close()
    
    def list_tasks(
        self,
        status: Optional[TaskStatus] = None,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[Task]:
        """
        List tasks with optional filtering.
        
        Args:
            status: Filter by task status (optional)
            limit: Maximum number of tasks to return (optional)
            offset: Number of tasks to skip (default: 0)
            
        Returns:
            List of Task objects
        """
        session = self._get_session()
        try:
            query = session.query(Task)
            
            if status is not None:
                query = query.filter(Task.status == status)
            
            query = query.order_by(Task.created_at.desc())
            
            if offset > 0:
                query = query.offset(offset)
            if limit is not None:
                query = query.limit(limit)
            
            tasks = query.all()
            
            # Detach from session
            for task in tasks:
                session.expunge(task)
            
            return tasks
        except SQLAlchemyError as e:
            logger.error(f"Failed to list tasks: {e}")
            return []
        finally:
            session.close()
    
    def cleanup_old_tasks(
        self,
        completed_retention_hours: int = 24,
        failed_retention_hours: int = 24,
        metadata_retention_days: int = 7
    ) -> int:
        """
        Clean up old tasks and their metadata.
        
        Removes tasks based on retention policies:
        - Completed tasks older than completed_retention_hours
        - Failed tasks older than failed_retention_hours
        - All task metadata older than metadata_retention_days
        
        Args:
            completed_retention_hours: Hours to retain completed tasks
            failed_retention_hours: Hours to retain failed tasks
            metadata_retention_days: Days to retain task metadata
            
        Returns:
            Number of tasks deleted
            
        Validates:
        - Requirements 5.1: Completed task cleanup
        - Requirements 5.2: Task metadata cleanup
        - Requirements 5.3: Failed task cleanup
        """
        session = self._get_session()
        deleted_count = 0
        
        try:
            now = datetime.now(timezone.utc)
            
            # Calculate cutoff times
            completed_cutoff = now - timedelta(hours=completed_retention_hours)
            failed_cutoff = now - timedelta(hours=failed_retention_hours)
            metadata_cutoff = now - timedelta(days=metadata_retention_days)
            
            # Find tasks to delete based on metadata retention (oldest policy)
            tasks_to_delete = session.query(Task).filter(
                or_(
                    # Completed tasks older than metadata retention
                    and_(
                        Task.status == TaskStatus.COMPLETED,
                        Task.completed_at < metadata_cutoff
                    ),
                    # Failed tasks older than metadata retention
                    and_(
                        Task.status == TaskStatus.FAILED,
                        Task.completed_at < metadata_cutoff
                    ),
                    # Cancelled tasks older than metadata retention
                    and_(
                        Task.status == TaskStatus.CANCELLED,
                        Task.completed_at < metadata_cutoff
                    )
                )
            ).all()
            
            # Delete tasks
            for task in tasks_to_delete:
                session.delete(task)
                deleted_count += 1
                logger.debug(f"Deleted task {task.task_id} (status: {task.status.value})")
            
            session.commit()
            
            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} old tasks")
            
            return deleted_count
            
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Failed to cleanup old tasks: {e}")
            return 0
        finally:
            session.close()
    
    def get_incomplete_tasks(self) -> List[Task]:
        """
        Get all tasks that are pending or processing.
        
        Used for resuming tasks after server restart.
        
        Returns:
            List of incomplete Task objects
            
        Validates:
        - Requirements 5.4: Task resumption on restart
        """
        session = self._get_session()
        try:
            tasks = session.query(Task).filter(
                or_(
                    Task.status == TaskStatus.PENDING,
                    Task.status == TaskStatus.PROCESSING
                )
            ).order_by(Task.created_at.asc()).all()
            
            # Detach from session
            for task in tasks:
                session.expunge(task)
            
            logger.info(f"Found {len(tasks)} incomplete tasks")
            return tasks
        except SQLAlchemyError as e:
            logger.error(f"Failed to retrieve incomplete tasks: {e}")
            return []
        finally:
            session.close()
    
    def delete_task(self, task_id: str) -> bool:
        """
        Delete a task from the database.
        
        Args:
            task_id: Unique task identifier
            
        Returns:
            True if deletion successful, False otherwise
        """
        session = self._get_session()
        try:
            task = session.query(Task).filter(Task.task_id == task_id).first()
            if not task:
                logger.warning(f"Task {task_id} not found for deletion")
                return False
            
            session.delete(task)
            session.commit()
            logger.info(f"Deleted task: {task_id}")
            return True
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Failed to delete task {task_id}: {e}")
            return False
        finally:
            session.close()
    
    def get_task_count(self, status: Optional[TaskStatus] = None) -> int:
        """
        Get count of tasks, optionally filtered by status.
        
        Args:
            status: Filter by task status (optional)
            
        Returns:
            Number of tasks matching criteria
        """
        session = self._get_session()
        try:
            query = session.query(Task)
            if status is not None:
                query = query.filter(Task.status == status)
            count = query.count()
            return count
        except SQLAlchemyError as e:
            logger.error(f"Failed to count tasks: {e}")
            return 0
        finally:
            session.close()
    
    def close(self) -> None:
        """
        Close database connections and cleanup resources.
        """
        try:
            self.engine.dispose()
            logger.info("Database connections closed")
        except Exception as e:
            logger.error(f"Error closing database connections: {e}")
