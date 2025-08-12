"""
Synapse MCP Storage System

This package contains the core storage components for Synapse MCP:
- paths: Cross-platform storage path management using platformdirs
- initializer: Storage initialization and first-run setup logic
- file_manager: JSON file storage and management (to be implemented)

The storage system follows cross-platform best practices and uses standard
directory structures appropriate for each operating system.
"""

from .paths import StoragePaths, storage_paths
from .initializer import StorageInitializer, initialize_synapse_storage

__all__ = [
    "StoragePaths",
    "storage_paths", 
    "StorageInitializer",
    "initialize_synapse_storage"
]