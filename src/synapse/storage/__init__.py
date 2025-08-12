"""
Synapse MCP Storage System

This package contains the core storage components for Synapse MCP:
- paths: Cross-platform storage path management using platformdirs
- initializer: Storage initialization and first-run setup logic
- file_manager: JSON file storage and management with locking and backup support

The storage system follows cross-platform best practices and uses standard
directory structures appropriate for each operating system.
"""

from synapse.storage.paths import StoragePaths, storage_paths
from synapse.storage.initializer import StorageInitializer, initialize_synapse_storage
from synapse.storage.file_manager import FileManager, StorageStats, BackupInfo

__all__ = [
    "StoragePaths",
    "storage_paths", 
    "StorageInitializer",
    "initialize_synapse_storage",
    "FileManager",
    "StorageStats",
    "BackupInfo"
]