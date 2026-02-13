# coding: utf-8
"""
Worker Pool for concurrent task processing.

This module provides the WorkerPool class for managing concurrent execution
of separation tasks using a thread pool. It handles GPU/CPU device assignment,
worker crash recovery, and graceful shutdown.

Validates:
- Requirements 11.1: Multi-GPU task distribution
- Requirements 11.2: CPU-only sequential processing
- Requirements 11.3: Worker pool concurrency limit
- Requirements 11.4: Task queuing when workers busy
- Requirements 11.5: Worker crash recovery and graceful shutdown
"""

import logging
import threading
from concurrent.futures import ThreadPoolExecutor, Future
from typing import List, Optional, Callable, Dict
from queue import Queue


logger = logging.getLogger(__name__)


class WorkerPool:
    """
    Worker pool for concurrent task processing.
    
    Manages concurrent execution of separation tasks using ThreadPoolExecutor.
    Handles device assignment (GPU/CPU), worker crash recovery, and graceful
    shutdown.
    
    Key features:
    - Thread-based concurrency with configurable worker count
    - GPU/CPU device assignment with round-robin distribution
    - Worker crash isolation (failed tasks don't crash other workers)
    - Graceful shutdown with task completion wait
    - FIFO task queuing
    
    Validates:
    - Requirements 11.1: Multi-GPU task distribution
    - Requirements 11.2: CPU-only sequential processing
    - Requirements 11.3: Worker pool concurrency limit
    - Requirements 11.4: Task queuing when workers busy
    - Requirements 11.5: Worker crash recovery and graceful shutdown
    """
    
    def __init__(
        self,
        max_workers: int,
        device_ids: List[int],
        force_cpu: bool = False
    ):
        """
        Initialize worker pool with specified concurrency.
        
        Args:
            max_workers: Maximum number of concurrent workers
            device_ids: List of GPU device IDs to use (e.g., [0, 1] for cuda:0 and cuda:1)
            force_cpu: If True, use CPU only regardless of device_ids
        
        Validates:
        - Requirements 11.1: Multi-GPU device assignment
        - Requirements 11.2: CPU-only mode
        - Requirements 11.3: Worker count configuration
        """
        self.max_workers = max_workers
        self.force_cpu = force_cpu
        
        # Configure devices
        if force_cpu:
            self.devices = ["cpu"]
            # For CPU-only, limit to 1 worker to prevent memory exhaustion
            self.max_workers = 1
            logger.info("Worker pool initialized in CPU-only mode with 1 worker")
        else:
            # Use GPU devices
            self.devices = [f"cuda:{device_id}" for device_id in device_ids]
            logger.info(f"Worker pool initialized with {max_workers} workers across devices: {self.devices}")
        
        # Initialize thread pool
        self._executor = ThreadPoolExecutor(
            max_workers=self.max_workers,
            thread_name_prefix="worker"
        )
        
        # Track active tasks
        self._active_tasks: Dict[str, Future] = {}
        self._active_tasks_lock = threading.Lock()
        
        # Device assignment (round-robin)
        self._device_index = 0
        self._device_lock = threading.Lock()
        
        # Shutdown flag
        self._shutdown = False
        self._shutdown_lock = threading.Lock()
        
        logger.info(f"WorkerPool initialized with {self.max_workers} workers")
    
    def _get_next_device(self) -> str:
        """
        Get next device for task assignment using round-robin.
        
        Returns:
            Device string (e.g., "cpu", "cuda:0", "cuda:1")
        
        Validates:
        - Requirements 11.1: Multi-GPU task distribution
        """
        with self._device_lock:
            device = self.devices[self._device_index]
            self._device_index = (self._device_index + 1) % len(self.devices)
            return device
    
    def submit_task(
        self,
        task_id: str,
        task_fn: Callable[[str], None],
    ) -> Future:
        """
        Submit a task for asynchronous processing.
        
        The task function will be executed on a worker thread with an assigned
        device. If all workers are busy, the task will be queued until a worker
        becomes available.
        
        Args:
            task_id: Unique task identifier
            task_fn: Function to execute, takes device string as argument
        
        Returns:
            Future object representing the task execution
        
        Raises:
            RuntimeError: If worker pool has been shut down
        
        Validates:
        - Requirements 11.3: Worker pool concurrency limit
        - Requirements 11.4: Task queuing when workers busy
        """
        with self._shutdown_lock:
            if self._shutdown:
                raise RuntimeError("Worker pool has been shut down")
        
        # Get device for this task
        device = self._get_next_device()
        
        # Create wrapper function that handles device assignment and error recovery
        def task_wrapper():
            try:
                logger.info(f"Task {task_id} starting on device {device}")
                result = task_fn(device)
                logger.info(f"Task {task_id} completed successfully")
                return result
            except Exception as e:
                # Worker crash recovery: log error but don't crash the worker
                logger.error(f"Task {task_id} failed with error: {e}", exc_info=True)
                # The task_fn should handle updating task status to failed
                raise  # Re-raise so the future captures the exception
            finally:
                # Remove from active tasks
                with self._active_tasks_lock:
                    if task_id in self._active_tasks:
                        del self._active_tasks[task_id]
        
        # Submit to executor
        future = self._executor.submit(task_wrapper)
        
        # Track active task
        with self._active_tasks_lock:
            self._active_tasks[task_id] = future
        
        logger.debug(f"Task {task_id} submitted to worker pool (device: {device})")
        return future
    
    def get_active_count(self) -> int:
        """
        Return number of currently executing tasks.
        
        Returns:
            Number of active tasks
        
        Validates:
        - Requirements 11.3: Worker pool concurrency tracking
        """
        with self._active_tasks_lock:
            return len(self._active_tasks)
    
    def get_active_task_ids(self) -> List[str]:
        """
        Return list of currently executing task IDs.
        
        Returns:
            List of active task IDs
        """
        with self._active_tasks_lock:
            return list(self._active_tasks.keys())
    
    def is_task_active(self, task_id: str) -> bool:
        """
        Check if a task is currently active.
        
        Args:
            task_id: Task identifier to check
        
        Returns:
            True if task is active, False otherwise
        """
        with self._active_tasks_lock:
            return task_id in self._active_tasks
    
    def cancel_task(self, task_id: str) -> bool:
        """
        Attempt to cancel a task.
        
        Note: Cancellation may not succeed if the task is already running.
        
        Args:
            task_id: Task identifier to cancel
        
        Returns:
            True if cancellation succeeded, False otherwise
        """
        with self._active_tasks_lock:
            if task_id in self._active_tasks:
                future = self._active_tasks[task_id]
                cancelled = future.cancel()
                if cancelled:
                    del self._active_tasks[task_id]
                    logger.info(f"Task {task_id} cancelled successfully")
                else:
                    logger.warning(f"Task {task_id} could not be cancelled (already running)")
                return cancelled
        
        logger.warning(f"Task {task_id} not found in active tasks")
        return False
    
    def shutdown(self, wait: bool = True, timeout: Optional[float] = None) -> None:
        """
        Gracefully shutdown worker pool.
        
        Stops accepting new tasks and optionally waits for active tasks to complete.
        
        Args:
            wait: If True, wait for active tasks to complete before returning
            timeout: Maximum time to wait for tasks to complete (seconds)
        
        Validates:
        - Requirements 11.5: Graceful shutdown
        """
        with self._shutdown_lock:
            if self._shutdown:
                logger.warning("Worker pool already shut down")
                return
            
            self._shutdown = True
        
        logger.info(f"Shutting down worker pool (wait={wait}, timeout={timeout})")
        
        # Get count of active tasks before shutdown
        active_count = self.get_active_count()
        if active_count > 0:
            logger.info(f"Waiting for {active_count} active tasks to complete")
        
        # Shutdown executor
        self._executor.shutdown(wait=wait)
        
        logger.info("Worker pool shut down complete")
    
    def is_shutdown(self) -> bool:
        """
        Check if worker pool has been shut down.
        
        Returns:
            True if shut down, False otherwise
        """
        with self._shutdown_lock:
            return self._shutdown
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.shutdown(wait=True)
        return False
