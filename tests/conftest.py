"""Shared test fixtures for v2-PureOS."""

import os
import sys

import pytest

# Ensure pureos is importable
try:
    from pureos.kernel import Kernel
except Exception:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
    from pureos.kernel import Kernel


@pytest.fixture
def kernel(tmp_path):
    """Create an initialized Kernel with a temporary backing store."""
    backing = tmp_path / "store.json"
    k = Kernel(config={"fs_backing": str(backing)})
    k.initialize()
    yield k
    k.shutdown()


@pytest.fixture
def shell(kernel):
    """Return the shell from an initialized kernel."""
    return kernel.shell


@pytest.fixture
def vfs(kernel):
    """Return the VirtualFS from an initialized kernel."""
    return kernel.fs


@pytest.fixture
def memory_driver(kernel):
    """Return the MemoryDriver from an initialized kernel."""
    return kernel.drivers.drivers["memory"]


@pytest.fixture
def scheduler(kernel):
    """Return the Scheduler from an initialized kernel."""
    return kernel.scheduler


@pytest.fixture
def small_memory_kernel(tmp_path):
    """Kernel with small memory (4MB RAM, 1MB swap) for OOM testing."""
    backing = tmp_path / "store.json"
    k = Kernel(
        config={
            "memory_total_kb": 4096,
            "memory_swap_kb": 1024,
            "fs_backing": str(backing),
        }
    )
    k.initialize()
    yield k
    k.shutdown()
