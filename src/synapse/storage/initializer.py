"""
Storage initialization and setup system for Synapse MCP.

This module handles the first-run initialization of the storage system,
including creating directory structures, generating default configuration
files, and validating storage permissions.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import sys
import os

from synapse.storage.paths import StoragePaths


class StorageInitializer:
    """
    Handles initialization and setup of the Synapse storage system.
    
    This class manages:
    - First-run directory structure creation
    - Default configuration file generation
    - Storage location validation and display
    - Permission checking and troubleshooting
    """
    
    def __init__(self, storage_paths: StoragePaths):
        """
        Initialize the storage initializer.
        
        Args:
            storage_paths: StoragePaths instance for path management
        """
        self.storage_paths = storage_paths
        self.initialization_marker = storage_paths.get_config_dir() / ".initialized"
    
    def is_initialized(self) -> bool:
        """
        Check if Synapse has been initialized before.
        
        Returns:
            bool: True if initialization has been completed previously
        """
        return self.initialization_marker.exists()
    
    def initialize_storage(self, force: bool = False, show_info: bool = True) -> Tuple[bool, List[str]]:
        """
        Initialize the complete storage system.
        
        This method:
        1. Creates all necessary directories
        2. Generates default configuration files
        3. Validates permissions
        4. Creates initialization marker
        5. Shows storage location information
        
        Args:
            force: Force re-initialization even if already initialized
            show_info: Display initialization information to user
            
        Returns:
            Tuple[bool, List[str]]: (success, list of messages/errors)
        """
        messages = []
        
        # Check if already initialized
        if self.is_initialized() and not force:
            messages.append("Synapse storage is already initialized.")
            if show_info:
                self._display_storage_info(messages)
            return True, messages
        
        try:
            # Create all directories
            success = self._create_directory_structure(messages)
            if not success:
                return False, messages
            
            # Generate default configuration
            self._create_default_configuration(messages)
            
            # Create index files if they don't exist
            self._create_default_indexes(messages)
            
            # Validate permissions
            self._validate_storage_permissions(messages)
            
            # Create initialization marker
            self._create_initialization_marker()
            
            # Display information
            if show_info:
                self._display_storage_info(messages)
                messages.append("✅ Synapse storage initialized successfully!")
            
            return True, messages
            
        except Exception as e:
            error_msg = f"Failed to initialize storage: {e}"
            messages.append(error_msg)
            return False, messages
    
    def _create_directory_structure(self, messages: List[str]) -> bool:
        """
        Create all necessary directories for Synapse storage.
        
        Args:
            messages: List to append status messages to
            
        Returns:
            bool: True if all directories were created successfully
        """
        directories = self.storage_paths.get_all_directories()
        success = True
        
        for name, path in directories.items():
            if self.storage_paths.create_directory(path):
                messages.append(f"📁 Created {name} directory: {path}")
            else:
                messages.append(f"❌ Failed to create {name} directory: {path}")
                success = False
        
        return success
    
    def _create_default_configuration(self, messages: List[str]) -> None:
        """
        Create default configuration files.
        
        Args:
            messages: List to append status messages to
        """
        config_dir = self.storage_paths.get_config_dir()
        
        # Main configuration file
        config_file = config_dir / "config.json"
        if not config_file.exists():
            default_config = {
                "version": "1.0.0",
                "storage": {
                    "max_conversation_size_kb": 500,
                    "max_conversations": 10000,
                    "auto_backup": True,
                    "backup_interval_days": 7
                },
                "search": {
                    "max_results": 50,
                    "relevance_threshold": 0.1,
                    "enable_fuzzy_matching": True
                },
                "indexing": {
                    "auto_index": True,
                    "index_update_interval_minutes": 30
                },
                "extraction": {
                    "auto_extract_solutions": True,
                    "min_reusability_score": 0.3,
                    "supported_languages": ["python", "javascript", "typescript", "java", "cpp", "go", "rust"]
                },
                "ui": {
                    "show_debug_info": False,
                    "max_snippet_length": 200
                }
            }
            
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, indent=2, ensure_ascii=False)
            
            messages.append(f"⚙️  Created default configuration: {config_file}")
        
        # Logging configuration
        log_config_file = config_dir / "logging.json"
        if not log_config_file.exists():
            log_config = {
                "version": 1,
                "disable_existing_loggers": False,
                "formatters": {
                    "standard": {
                        "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
                    }
                },
                "handlers": {
                    "file": {
                        "level": "INFO",
                        "class": "logging.handlers.RotatingFileHandler",
                        "formatter": "standard",
                        "filename": str(self.storage_paths.get_logs_dir() / "synapse.log"),
                        "maxBytes": 10485760,
                        "backupCount": 5
                    },
                    "console": {
                        "level": "WARNING",
                        "class": "logging.StreamHandler",
                        "formatter": "standard",
                        "stream": "ext://sys.stderr"
                    }
                },
                "loggers": {
                    "synapse": {
                        "level": "INFO",
                        "handlers": ["file", "console"],
                        "propagate": False
                    }
                },
                "root": {
                    "level": "INFO",
                    "handlers": ["file"]
                }
            }
            
            with open(log_config_file, 'w', encoding='utf-8') as f:
                json.dump(log_config, f, indent=2)
            
            messages.append(f"📝 Created logging configuration: {log_config_file}")
    
    def _create_default_indexes(self, messages: List[str]) -> None:
        """
        Create default index files if they don't exist.
        
        Args:
            messages: List to append status messages to
        """
        indexes_dir = self.storage_paths.get_indexes_dir()
        
        # Keyword index
        keyword_index_file = indexes_dir / "keyword_index.json"
        if not keyword_index_file.exists():
            default_keyword_index = {
                "version": "1.0",
                "created_at": datetime.now().isoformat(),
                "last_updated": datetime.now().isoformat(),
                "total_entries": 0,
                "keywords": {}
            }
            
            with open(keyword_index_file, 'w', encoding='utf-8') as f:
                json.dump(default_keyword_index, f, indent=2)
            
            messages.append(f"🔍 Created keyword index: {keyword_index_file}")
        
        # Tag index
        tag_index_file = indexes_dir / "tag_index.json"
        if not tag_index_file.exists():
            default_tag_index = {
                "version": "1.0",
                "created_at": datetime.now().isoformat(),
                "last_updated": datetime.now().isoformat(),
                "total_tags": 0,
                "tags": {}
            }
            
            with open(tag_index_file, 'w', encoding='utf-8') as f:
                json.dump(default_tag_index, f, indent=2)
            
            messages.append(f"🏷️  Created tag index: {tag_index_file}")
        
        # Metadata file
        metadata_file = indexes_dir / "metadata.json"
        if not metadata_file.exists():
            metadata = {
                "version": "1.0",
                "created_at": datetime.now().isoformat(),
                "last_maintenance": datetime.now().isoformat(),
                "statistics": {
                    "total_conversations": 0,
                    "total_solutions": 0,
                    "total_storage_bytes": 0
                },
                "health": {
                    "last_health_check": datetime.now().isoformat(),
                    "status": "healthy"
                }
            }
            
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2)
            
            messages.append(f"📊 Created metadata file: {metadata_file}")
    
    def _validate_storage_permissions(self, messages: List[str]) -> None:
        """
        Validate that we have proper permissions for all storage directories.
        
        Args:
            messages: List to append status messages to
        """
        directories = self.storage_paths.get_all_directories()
        
        for name, path in directories.items():
            if self.storage_paths.validate_permissions(path):
                messages.append(f"✅ {name} directory permissions OK")
            else:
                messages.append(f"⚠️  Warning: Limited permissions for {name} directory: {path}")
    
    def _create_initialization_marker(self) -> None:
        """Create a marker file to indicate successful initialization."""
        marker_data = {
            "initialized_at": datetime.now().isoformat(),
            "version": "1.0.0",
            "platform": sys.platform,
            "python_version": sys.version,
            "storage_paths": self.storage_paths.get_storage_info()
        }
        
        with open(self.initialization_marker, 'w', encoding='utf-8') as f:
            json.dump(marker_data, f, indent=2)
    
    def _display_storage_info(self, messages: List[str]) -> None:
        """
        Display storage location information to the user.
        
        Args:
            messages: List to append display messages to
        """
        messages.append("\n" + "=" * 60)
        messages.append("📂 Synapse MCP Storage Locations")
        messages.append("=" * 60)
        
        storage_info = self.storage_paths.get_storage_info()
        
        # Primary storage locations
        messages.append(f"📊 Data Directory:   {storage_info['data']}")
        messages.append(f"⚙️  Config Directory: {storage_info['config']}")
        messages.append(f"🗃️  Cache Directory:  {storage_info['cache']}")
        
        messages.append("\n" + "-" * 40)
        messages.append("📁 Data Subdirectories:")
        messages.append("-" * 40)
        
        # Data subdirectories
        messages.append(f"💬 Conversations: {storage_info['conversations']}")
        messages.append(f"💡 Solutions:     {storage_info['solutions']}")
        messages.append(f"🔍 Indexes:       {storage_info['indexes']}")
        messages.append(f"📝 Logs:          {storage_info['logs']}")
        messages.append(f"💾 Backups:       {storage_info['backups']}")
        
        messages.append("\n" + "=" * 60)
    
    def get_storage_status(self) -> Dict[str, any]:
        """
        Get comprehensive storage status information.
        
        Returns:
            Dict with storage status details
        """
        directories = self.storage_paths.get_all_directories()
        status = {
            "initialized": self.is_initialized(),
            "storage_paths": self.storage_paths.get_storage_info(),
            "directory_status": {},
            "permissions_ok": True,
            "total_size_bytes": 0
        }
        
        for name, path in directories.items():
            dir_info = {
                "exists": path.exists(),
                "writable": self.storage_paths.validate_permissions(path) if path.exists() else False,
                "size_bytes": 0
            }
            
            # Calculate directory size if it exists
            if path.exists():
                try:
                    dir_info["size_bytes"] = sum(
                        f.stat().st_size for f in path.rglob('*') if f.is_file()
                    )
                    status["total_size_bytes"] += dir_info["size_bytes"]
                except (OSError, PermissionError):
                    dir_info["size_bytes"] = -1  # Error calculating size
            
            if not dir_info["writable"]:
                status["permissions_ok"] = False
            
            status["directory_status"][name] = dir_info
        
        return status
    
    def cleanup_storage(self, confirm: bool = False) -> Tuple[bool, List[str]]:
        """
        Clean up storage (for development/testing purposes).
        
        Args:
            confirm: Must be True to actually perform cleanup
            
        Returns:
            Tuple[bool, List[str]]: (success, messages)
        """
        messages = []
        
        if not confirm:
            messages.append("⚠️  Cleanup not performed - confirmation required")
            messages.append("Use confirm=True to actually delete storage data")
            return False, messages
        
        try:
            import shutil
            
            # Remove data directory
            data_dir = self.storage_paths.get_data_dir()
            if data_dir.exists():
                shutil.rmtree(data_dir)
                messages.append(f"🗑️  Removed data directory: {data_dir}")
            
            # Remove config directory
            config_dir = self.storage_paths.get_config_dir()
            if config_dir.exists():
                shutil.rmtree(config_dir)
                messages.append(f"🗑️  Removed config directory: {config_dir}")
            
            # Remove cache directory
            cache_dir = self.storage_paths.get_cache_dir()
            if cache_dir.exists():
                shutil.rmtree(cache_dir)
                messages.append(f"🗑️  Removed cache directory: {cache_dir}")
            
            messages.append("✅ Storage cleanup completed")
            return True, messages
            
        except Exception as e:
            messages.append(f"❌ Failed to cleanup storage: {e}")
            return False, messages


# Convenience function for easy initialization
def initialize_synapse_storage(force: bool = False, show_info: bool = True) -> Tuple[bool, List[str]]:
    """
    Convenience function to initialize Synapse storage.
    
    Args:
        force: Force re-initialization
        show_info: Display initialization information
        
    Returns:
        Tuple[bool, List[str]]: (success, messages)
    """
    storage_paths = StoragePaths()
    initializer = StorageInitializer(storage_paths)
    return initializer.initialize_storage(force=force, show_info=show_info)