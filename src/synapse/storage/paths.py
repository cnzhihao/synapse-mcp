"""
Cross-platform storage path management system for Synapse MCP.

This module provides a centralized way to manage storage paths across different
operating systems using the platformdirs library. It ensures that user data,
configuration files, and cache are stored in appropriate system directories.

Storage Location Standards:
- macOS/Linux: ~/.local/share/synapse-mcp/ (data), ~/.config/synapse-mcp/ (config)
- Windows: %APPDATA%\\synapse\\synapse-mcp\\ (data and config)
"""

from pathlib import Path
from typing import Dict, Optional
import platformdirs


class StoragePaths:
    """
    Cross-platform storage path management for Synapse MCP.
    
    This class handles all storage path operations using platformdirs to ensure
    proper directory placement on different operating systems. It provides methods
    to get various storage directories and creates them if they don't exist.
    
    The class follows the XDG Base Directory Specification on Unix-like systems
    and Windows-specific conventions on Windows.
    """
    
    def __init__(self, app_name: str = "synapse-mcp", app_author: str = "synapse"):
        """
        Initialize the StoragePaths manager.
        
        Args:
            app_name: Application name used for directory naming
            app_author: Application author/organization name
        """
        self.app_name = app_name
        self.app_author = app_author
        
        # Initialize platformdirs paths
        self._data_dir = platformdirs.user_data_dir(
            appname=self.app_name, 
            appauthor=self.app_author
        )
        self._config_dir = platformdirs.user_config_dir(
            appname=self.app_name, 
            appauthor=self.app_author
        )
        self._cache_dir = platformdirs.user_cache_dir(
            appname=self.app_name, 
            appauthor=self.app_author
        )
    
    def get_data_dir(self) -> Path:
        """
        Get the main user data directory for storing conversations and solutions.
        
        This is where all persistent user data will be stored, including
        conversation records, extracted solutions, and search indexes.
        
        Returns:
            Path: User data directory path
            
        Examples:
            - macOS: /Users/username/.local/share/synapse-mcp/
            - Linux: /home/username/.local/share/synapse-mcp/
            - Windows: C:\\Users\\username\\AppData\\Roaming\\synapse\\synapse-mcp\\
        """
        return Path(self._data_dir)
    
    def get_config_dir(self) -> Path:
        """
        Get the configuration directory for storing settings and preferences.
        
        This directory stores configuration files, user preferences, and
        application settings that shouldn't be mixed with user data.
        
        Returns:
            Path: Configuration directory path
            
        Examples:
            - macOS: /Users/username/.config/synapse-mcp/
            - Linux: /home/username/.config/synapse-mcp/
            - Windows: C:\\Users\\username\\AppData\\Roaming\\synapse\\synapse-mcp\\ (same as data)
        """
        return Path(self._config_dir)
    
    def get_cache_dir(self) -> Path:
        """
        Get the cache directory for temporary and cached data.
        
        This directory stores temporary files, search caches, and other data
        that can be safely deleted without losing user information.
        
        Returns:
            Path: Cache directory path
            
        Examples:
            - macOS: /Users/username/Library/Caches/synapse-mcp/
            - Linux: /home/username/.cache/synapse-mcp/
            - Windows: C:\\Users\\username\\AppData\\Local\\synapse\\synapse-mcp\\Cache\\
        """
        return Path(self._cache_dir)
    
    def get_conversations_dir(self) -> Path:
        """
        Get the directory for storing conversation records.
        
        This directory contains subdirectories organized by year and month
        (YYYY/MM/) to efficiently organize conversation files.
        
        Returns:
            Path: Conversations storage directory
            
        Structure:
            conversations/
            ├── 2024/
            │   ├── 01/
            │   │   ├── conv_20240115_001.json
            │   │   └── conv_20240115_002.json
            │   └── 02/
            └── 2023/
        """
        return self.get_data_dir() / "conversations"
    
    def get_solutions_dir(self) -> Path:
        """
        Get the directory for storing extracted solutions and patterns.
        
        This directory contains reusable code snippets, solutions, and
        patterns extracted from conversations.
        
        Returns:
            Path: Solutions storage directory
        """
        return self.get_data_dir() / "solutions"
    
    def get_indexes_dir(self) -> Path:
        """
        Get the directory for storing search indexes and metadata.
        
        This directory contains keyword indexes, tag indexes, and other
        metadata files used for efficient searching.
        
        Returns:
            Path: Search indexes directory
            
        Structure:
            indexes/
            ├── keyword_index.json
            ├── tag_index.json
            └── metadata.json
        """
        return self.get_data_dir() / "indexes"
    
    def get_logs_dir(self) -> Path:
        """
        Get the directory for storing application logs.
        
        Returns:
            Path: Logs directory path
        """
        return self.get_data_dir() / "logs"
    
    def get_backups_dir(self) -> Path:
        """
        Get the directory for storing data backups.
        
        Returns:
            Path: Backups directory path
        """
        return self.get_data_dir() / "backups"
    
    def get_all_directories(self) -> Dict[str, Path]:
        """
        Get all storage directories as a dictionary.
        
        This method returns all available directory paths in a structured
        format, useful for initialization and display purposes.
        
        Returns:
            Dict[str, Path]: Dictionary mapping directory names to paths
        """
        return {
            "data": self.get_data_dir(),
            "config": self.get_config_dir(),
            "cache": self.get_cache_dir(),
            "conversations": self.get_conversations_dir(),
            "solutions": self.get_solutions_dir(),
            "indexes": self.get_indexes_dir(),
            "logs": self.get_logs_dir(),
            "backups": self.get_backups_dir()
        }
    
    def get_storage_info(self) -> Dict[str, str]:
        """
        Get human-readable storage location information.
        
        This method provides formatted string representations of storage
        paths, useful for display to users and logging.
        
        Returns:
            Dict[str, str]: Dictionary with formatted path information
        """
        dirs = self.get_all_directories()
        return {
            name: str(path) for name, path in dirs.items()
        }
    
    def create_directory(self, path: Path, exist_ok: bool = True) -> bool:
        """
        Create a directory with proper error handling.
        
        Args:
            path: Directory path to create
            exist_ok: Don't raise error if directory already exists
            
        Returns:
            bool: True if directory was created or already exists, False on error
        """
        try:
            path.mkdir(parents=True, exist_ok=exist_ok)
            return True
        except (OSError, PermissionError) as e:
            # Log error but don't raise - let caller handle gracefully
            print(f"Warning: Failed to create directory {path}: {e}")
            return False
    
    def validate_permissions(self, path: Path) -> bool:
        """
        Check if we have read/write permissions for a directory.
        
        Args:
            path: Directory path to check
            
        Returns:
            bool: True if we have read/write permissions
        """
        try:
            # Try to create directory if it doesn't exist
            if not path.exists():
                path.mkdir(parents=True, exist_ok=True)
            
            # Test write permission by creating and removing a test file
            test_file = path / ".permission_test"
            test_file.touch()
            test_file.unlink()
            
            return True
        except (OSError, PermissionError):
            return False


# Global instance for easy access throughout the application
storage_paths = StoragePaths()