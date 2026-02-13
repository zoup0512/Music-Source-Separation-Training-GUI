# coding: utf-8
"""
Unit tests for WorkerPool class.

Tests worker pool functionality including:
- Initialization with GPU/CPU devices
- Task submission and execution
- Device assignment (round-robin)
- Worker crash recovery
- Graceful shutdown
- Active task tracking

Validates:
- Requirements 11.1: Multi-GPU task distribution
- Requirements 11.2: CPU-only sequential processing
- Requirements 11.3: Worker pool concurrency limit
- Requirements 11.4: Task queuing when workers busy
- Requirements 11.5: Worker crash recovery and graceful shutdown
"""

import pytest
import time
import threading
from concurrent.futures import Future
from api_server.workers.worker_pool import WorkerPool


class TestWorkerPoolInitialization:
    """Test worker pool initialization."""
    
    def test_init_with_single_gpu(self):
        """Test initialization with single GPU."""
        pool = WorkerPool(max_workers=2, device_ids=[0], force_cpu=False)
        
        assert pool.max_workers == 2
        assert pool.devices == ["cuda:0"]
        assert not pool.force_cpu
        assert not pool.is_shutdown()
        
        pool.shutdown()
    
    def test_init_with_multiple_gpus(self):
        """Test initialization with multiple GPUs."""
        pool = WorkerPool(max_workers=4, device_ids=[0, 1, 2], force_cpu=False)
        
        assert pool.max_workers == 4
        assert pool.devices == ["cuda:0", "cuda:1", "cuda:2"]
        assert not pool.force_cpu
        
        pool.shutdown()
    
    def test_init_with_cpu_only(self):
        """Test initialization with CPU-only mode."""
        pool = WorkerPool(max_workers=4, device_ids=[0, 1], force_cpu=True)
        
        # CPU-only mode should limit to 1 worker
        assert pool.max_workers == 1
        assert pool.devices == ["cpu"]
        assert pool.force_cpu
        
        pool.shutdown()


class TestDeviceAssignment:
    """Test device assignment logic."""
    
    def test_round_robin_single_device(self):
        """Test round-robin assignment with single device."""
        pool = WorkerPool(max_workers=2, device_ids=[0], force_cpu=False)
        
        # All tasks should get the same device
        device1 = pool._get_next_device()
        device2 = pool._get_next_device()
        device3 = pool._get_next_device()
        
        assert device1 == "cuda:0"
        assert device2 == "cuda:0"
        assert device3 == "cuda:0"
        
        pool.shutdown()
    
    def test_round_robin_multiple_devices(self):
        """Test round-robin assignment with multiple devices."""
        pool = WorkerPool(max_workers=4, device_ids=[0, 1, 2], force_cpu=False)
        
        # Should cycle through devices
        devices = [pool._get_next_device() for _ in range(6)]
        
        assert devices == [
            "cuda:0", "cuda:1", "cuda:2",
            "cuda:0", "cuda:1", "cuda:2"
        ]
        
        pool.shutdown()
    
    def test_cpu_device_assignment(self):
        """Test device assignment in CPU-only mode."""
        pool = WorkerPool(max_workers=1, device_ids=[], force_cpu=True)
        
        device1 = pool._get_next_device()
        device2 = pool._get_next_device()
        
        assert device1 == "cpu"
        assert device2 == "cpu"
        
        pool.shutdown()


class TestTaskSubmission:
    """Test task submission and execution."""
    
    def test_submit_simple_task(self):
        """Test submitting a simple task."""
        pool = WorkerPool(max_workers=2, device_ids=[0], force_cpu=False)
        
        executed = threading.Event()
        received_device = []
        
        def task_fn(device):
            received_device.append(device)
            executed.set()
        
        future = pool.submit_task("task1", task_fn)
        
        assert isinstance(future, Future)
        executed.wait(timeout=2.0)
        assert executed.is_set()
        assert received_device == ["cuda:0"]
        
        pool.shutdown()
    
    def test_submit_multiple_tasks(self):
        """Test submitting multiple tasks."""
        pool = WorkerPool(max_workers=2, device_ids=[0, 1], force_cpu=False)
        
        completed_tasks = []
        lock = threading.Lock()
        
        def task_fn(device):
            time.sleep(0.1)  # Simulate work
            with lock:
                completed_tasks.append(device)
        
        # Submit 4 tasks
        futures = []
        for i in range(4):
            future = pool.submit_task(f"task{i}", task_fn)
            futures.append(future)
        
        # Wait for all tasks to complete
        for future in futures:
            future.result(timeout=5.0)
        
        # Should have 4 completed tasks
        assert len(completed_tasks) == 4
        
        # Should use both devices (round-robin)
        assert "cuda:0" in completed_tasks
        assert "cuda:1" in completed_tasks
        
        pool.shutdown()
    
    def test_task_queuing_when_workers_busy(self):
        """Test that tasks are queued when all workers are busy."""
        pool = WorkerPool(max_workers=2, device_ids=[0], force_cpu=False)
        
        start_event = threading.Event()
        completed_count = [0]
        lock = threading.Lock()
        
        def task_fn(device):
            # Wait for signal to start
            start_event.wait()
            time.sleep(0.1)
            with lock:
                completed_count[0] += 1
        
        # Submit 4 tasks (more than max_workers)
        futures = []
        for i in range(4):
            future = pool.submit_task(f"task{i}", task_fn)
            futures.append(future)
        
        # At this point, tasks should be queued
        time.sleep(0.1)
        
        # Signal tasks to start
        start_event.set()
        
        # Wait for all tasks to complete
        for future in futures:
            future.result(timeout=5.0)
        
        assert completed_count[0] == 4
        
        pool.shutdown()


class TestActiveTaskTracking:
    """Test active task tracking."""
    
    def test_get_active_count(self):
        """Test getting active task count."""
        pool = WorkerPool(max_workers=2, device_ids=[0], force_cpu=False)
        
        assert pool.get_active_count() == 0
        
        start_event = threading.Event()
        
        def task_fn(device):
            start_event.wait()
        
        # Submit 2 tasks
        future1 = pool.submit_task("task1", task_fn)
        future2 = pool.submit_task("task2", task_fn)
        
        # Wait a bit for tasks to start
        time.sleep(0.1)
        
        # Should have 2 active tasks
        assert pool.get_active_count() == 2
        
        # Signal tasks to complete
        start_event.set()
        future1.result(timeout=2.0)
        future2.result(timeout=2.0)
        
        # Should have 0 active tasks
        time.sleep(0.1)
        assert pool.get_active_count() == 0
        
        pool.shutdown()
    
    def test_get_active_task_ids(self):
        """Test getting active task IDs."""
        pool = WorkerPool(max_workers=2, device_ids=[0], force_cpu=False)
        
        start_event = threading.Event()
        
        def task_fn(device):
            start_event.wait()
        
        # Submit tasks
        future1 = pool.submit_task("task1", task_fn)
        future2 = pool.submit_task("task2", task_fn)
        
        time.sleep(0.1)
        
        active_ids = pool.get_active_task_ids()
        assert "task1" in active_ids
        assert "task2" in active_ids
        
        start_event.set()
        future1.result(timeout=2.0)
        future2.result(timeout=2.0)
        
        pool.shutdown()
    
    def test_is_task_active(self):
        """Test checking if task is active."""
        pool = WorkerPool(max_workers=2, device_ids=[0], force_cpu=False)
        
        start_event = threading.Event()
        
        def task_fn(device):
            start_event.wait()
        
        future = pool.submit_task("task1", task_fn)
        
        time.sleep(0.1)
        assert pool.is_task_active("task1")
        assert not pool.is_task_active("task2")
        
        start_event.set()
        future.result(timeout=2.0)
        
        time.sleep(0.1)
        assert not pool.is_task_active("task1")
        
        pool.shutdown()


class TestWorkerCrashRecovery:
    """Test worker crash recovery."""
    
    def test_task_exception_does_not_crash_worker(self):
        """Test that task exceptions don't crash the worker."""
        pool = WorkerPool(max_workers=2, device_ids=[0], force_cpu=False)
        
        def failing_task(device):
            raise ValueError("Task failed!")
        
        def successful_task(device):
            return "success"
        
        # Submit failing task
        future1 = pool.submit_task("task1", failing_task)
        
        # Wait for it to complete (with exception)
        try:
            future1.result(timeout=2.0)
        except ValueError:
            pass  # Expected
        
        # Submit successful task - should work despite previous failure
        future2 = pool.submit_task("task2", successful_task)
        result = future2.result(timeout=2.0)
        
        assert result == "success"
        
        pool.shutdown()
    
    def test_multiple_task_failures(self):
        """Test multiple task failures don't affect worker pool."""
        pool = WorkerPool(max_workers=2, device_ids=[0], force_cpu=False)
        
        def failing_task(device):
            raise RuntimeError("Task failed!")
        
        # Submit multiple failing tasks
        futures = []
        for i in range(5):
            future = pool.submit_task(f"task{i}", failing_task)
            futures.append(future)
        
        # Wait for all to complete
        time.sleep(0.5)
        
        # Pool should still be functional
        assert not pool.is_shutdown()
        assert pool.get_active_count() == 0
        
        pool.shutdown()


class TestGracefulShutdown:
    """Test graceful shutdown."""
    
    def test_shutdown_with_no_active_tasks(self):
        """Test shutdown with no active tasks."""
        pool = WorkerPool(max_workers=2, device_ids=[0], force_cpu=False)
        
        pool.shutdown(wait=True)
        
        assert pool.is_shutdown()
    
    def test_shutdown_waits_for_active_tasks(self):
        """Test that shutdown waits for active tasks to complete."""
        pool = WorkerPool(max_workers=2, device_ids=[0], force_cpu=False)
        
        completed = []
        lock = threading.Lock()
        
        def task_fn(device):
            time.sleep(0.3)
            with lock:
                completed.append(True)
        
        # Submit tasks
        pool.submit_task("task1", task_fn)
        pool.submit_task("task2", task_fn)
        
        time.sleep(0.1)
        
        # Shutdown and wait
        pool.shutdown(wait=True)
        
        # Tasks should have completed
        assert len(completed) == 2
        assert pool.is_shutdown()
    
    def test_shutdown_without_wait(self):
        """Test shutdown without waiting for tasks."""
        pool = WorkerPool(max_workers=2, device_ids=[0], force_cpu=False)
        
        def task_fn(device):
            time.sleep(1.0)
        
        pool.submit_task("task1", task_fn)
        
        time.sleep(0.1)
        
        # Shutdown without waiting
        pool.shutdown(wait=False)
        
        assert pool.is_shutdown()
    
    def test_submit_after_shutdown_raises_error(self):
        """Test that submitting tasks after shutdown raises error."""
        pool = WorkerPool(max_workers=2, device_ids=[0], force_cpu=False)
        
        pool.shutdown()
        
        def task_fn(device):
            pass
        
        with pytest.raises(RuntimeError, match="shut down"):
            pool.submit_task("task1", task_fn)
    
    def test_context_manager(self):
        """Test using worker pool as context manager."""
        completed = []
        
        with WorkerPool(max_workers=2, device_ids=[0], force_cpu=False) as pool:
            def task_fn(device):
                time.sleep(0.1)
                completed.append(True)
            
            pool.submit_task("task1", task_fn)
            pool.submit_task("task2", task_fn)
        
        # Should have shut down and waited for tasks
        assert len(completed) == 2


class TestCPUOnlyMode:
    """Test CPU-only mode behavior."""
    
    def test_cpu_only_limits_to_one_worker(self):
        """Test that CPU-only mode limits to 1 worker."""
        pool = WorkerPool(max_workers=4, device_ids=[0, 1], force_cpu=True)
        
        assert pool.max_workers == 1
        assert pool.devices == ["cpu"]
        
        pool.shutdown()
    
    def test_cpu_only_sequential_processing(self):
        """Test that CPU-only mode processes tasks sequentially."""
        pool = WorkerPool(max_workers=4, device_ids=[0], force_cpu=True)
        
        execution_times = []
        lock = threading.Lock()
        
        def task_fn(device):
            start = time.time()
            time.sleep(0.1)
            end = time.time()
            with lock:
                execution_times.append((start, end, device))
        
        # Submit 3 tasks
        futures = []
        for i in range(3):
            future = pool.submit_task(f"task{i}", task_fn)
            futures.append(future)
        
        # Wait for all to complete
        for future in futures:
            future.result(timeout=5.0)
        
        # All should use CPU device
        for _, _, device in execution_times:
            assert device == "cpu"
        
        # Tasks should be mostly sequential (allowing for small overlap)
        # Sort by start time
        execution_times.sort(key=lambda x: x[0])
        
        # Check that each task starts after the previous one mostly completes
        for i in range(len(execution_times) - 1):
            current_end = execution_times[i][1]
            next_start = execution_times[i + 1][0]
            # Allow small overlap due to thread scheduling
            assert next_start >= current_end - 0.05
        
        pool.shutdown()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
