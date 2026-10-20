import os
import sys

import pytest
from prometheus_client import REGISTRY


@pytest.fixture(autouse=True)
def _cleanup_prometheus_registry():
    """Unregister collectors created during a test (ModuleManager counters)."""
    yield
    for collector in list(REGISTRY._collector_to_names):
        REGISTRY.unregister(collector)


@pytest.fixture(autouse=True)
def _cleanup_module_imports():
    """Undo sys.path / sys.modules changes made while loading directory modules."""
    original_path = list(sys.path)
    original_modules = set(sys.modules)
    yield
    inserted = [p for p in sys.path if p not in original_path]
    sys.path[:] = original_path
    # Drop sibling modules imported from an inserted module directory.
    for name in set(sys.modules) - original_modules:
        module = sys.modules[name]
        module_file = getattr(module, "__file__", None) or ""
        if any(module_file.startswith(os.path.join(entry, "")) for entry in inserted):
            del sys.modules[name]
    # Drop the synthetic packages registered for directory modules.
    for name in [n for n in sys.modules if n == "bot_modules" or n.startswith("bot_modules.")]:
        del sys.modules[name]
