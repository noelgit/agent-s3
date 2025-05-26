#!/usr/bin/env python3
"""
Agent-S3 Repository Cleanup Tool
Consolidated script to handle all repository cleanup operations.

This replaces multiple individual cleanup scripts with a unified tool.
"""
import argparse
import logging
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Set

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class RepositoryCleanup:
    """Handles all repository cleanup operations."""
    
    def __init__(self, repo_root: Path, dry_run: bool = False, force: bool = False):
        self.repo_root = repo_root
        self.dry_run = dry_run
        self.force = force
        self.files_to_remove: List[Path] = []
        self.dirs_to_remove: List[Path] = []
    
    def find_duplicate_files(self) -> List[Path]:
        """Find files that appear to be duplicates (with numbers or 'copy' in name)."""
        duplicate_patterns = [
            r'.*\s+\d+\.[^.]+$',  # file 2.txt, script 3.py
            r'.*\s+copy.*\.[^.]+$',  # file copy.txt
            r'.*\(\d+\)\.[^.]+$',  # file(2).txt
            r'.*\.bak$',  # backup files
            r'.*\.backup$',  # backup files
            r'.*\.orig$',  # original files
            r'.*\.old$',  # old files
            r'.*~$',  # editor backups
        ]
        
        duplicates = []
        for pattern in duplicate_patterns:
            regex = re.compile(pattern, re.IGNORECASE)
            for file_path in self.repo_root.rglob('*'):
                if file_path.is_file() and not self._is_in_git_dir(file_path):
                    if regex.match(file_path.name):
                        duplicates.append(file_path)
        
        return duplicates
    
    def find_backup_directories(self) -> List[Path]:
        """Find backup directories."""
        backup_dirs = []
        backup_names = ['backups', 'backup', '.backup', 'old', 'archive']
        
        for backup_name in backup_names:
            for path in self.repo_root.rglob(backup_name):
                if path.is_dir() and not self._is_in_git_dir(path):
                    backup_dirs.append(path)
        
        return backup_dirs
    
    def find_temp_files(self) -> List[Path]:
        """Find temporary files and build artifacts."""
        temp_patterns = [
            '**/*.pyc',
            '**/*.pyo',
            '**/__pycache__',
            '**/.pytest_cache',
            '**/*.tmp',
            '**/*.temp',
            '**/.DS_Store',
            '**/*.crdownload',
            '**/*.part',
        ]
        
        temp_files = []
        for pattern in temp_patterns:
            for file_path in self.repo_root.glob(pattern):
                if not self._is_in_git_dir(file_path):
                    temp_files.append(file_path)
        
        return temp_files
    
    def find_log_files(self) -> List[Path]:
        """Find old log files."""
        log_files = []
        for file_path in self.repo_root.rglob('*.log'):
            if not self._is_in_git_dir(file_path):
                # Keep recent logs (less than 7 days old)
                if file_path.stat().st_mtime < (Path().stat().st_mtime - 604800):
                    log_files.append(file_path)
        
        return log_files
    
    def _is_in_git_dir(self, path: Path) -> bool:
        """Check if path is within .git directory."""
        return '.git' in path.parts
    
    def _confirm_deletion(self, items: List[Path], item_type: str) -> bool:
        """Ask user to confirm deletion."""
        if self.force or self.dry_run:
            return True
        
        if not items:
            return False
        
        print(f"\nFound {len(items)} {item_type} to remove:")
        for item in items[:10]:  # Show first 10
            print(f"  {item.relative_to(self.repo_root)}")
        
        if len(items) > 10:
            print(f"  ... and {len(items) - 10} more")
        
        try:
            response = input(f"\nRemove these {item_type}? (y/N): ").strip().lower()
            return response in ['y', 'yes']
        except (EOFError, KeyboardInterrupt):
            print("\nOperation cancelled")
            return False
    
    def remove_items(self, items: List[Path], item_type: str):
        """Remove files or directories."""
        if not items:
            logger.info(f"No {item_type} found to remove")
            return
        
        if not self._confirm_deletion(items, item_type):
            logger.info(f"Skipping removal of {item_type}")
            return
        
        removed_count = 0
        for item in items:
            try:
                if self.dry_run:
                    logger.info(f"[DRY RUN] Would remove: {item.relative_to(self.repo_root)}")
                else:
                    if item.is_dir():
                        shutil.rmtree(item)
                    else:
                        item.unlink()
                    logger.info(f"Removed: {item.relative_to(self.repo_root)}")
                removed_count += 1
            except Exception as e:
                logger.error(f"Failed to remove {item}: {e}")
        
        logger.info(f"Removed {removed_count} {item_type}")
    
    def clean_python_cache(self):
        """Clean Python cache files and directories."""
        logger.info("Cleaning Python cache files...")
        
        # Find __pycache__ directories
        pycache_dirs = list(self.repo_root.rglob('__pycache__'))
        self.remove_items(pycache_dirs, "__pycache__ directories")
        
        # Find .pyc files
        pyc_files = list(self.repo_root.rglob('*.pyc'))
        self.remove_items(pyc_files, ".pyc files")
    
    def clean_node_modules(self):
        """Clean node_modules directories (but keep package files)."""
        logger.info("Checking for node_modules directories...")
        
        node_modules_dirs = []
        for path in self.repo_root.rglob('node_modules'):
            if path.is_dir() and not self._is_in_git_dir(path):
                # Check if there's a package.json nearby
                parent_has_package_json = any(
                    (path.parent / name).exists() 
                    for name in ['package.json', 'package-lock.json']
                )
                if not parent_has_package_json:
                    node_modules_dirs.append(path)
        
        if node_modules_dirs:
            logger.info("Found orphaned node_modules directories")
            self.remove_items(node_modules_dirs, "orphaned node_modules directories")
    
    def fix_permissions(self):
        """Fix file permissions."""
        logger.info("Fixing file permissions...")
        
        if self.dry_run:
            logger.info("[DRY RUN] Would fix file permissions")
            return
        
        # Make shell scripts executable
        for script in self.repo_root.rglob('*.sh'):
            if not self._is_in_git_dir(script):
                script.chmod(0o755)
                logger.info(f"Made executable: {script.relative_to(self.repo_root)}")
    
    def run_full_cleanup(self):
        """Run all cleanup operations."""
        logger.info(f"Starting full cleanup of repository: {self.repo_root}")
        
        # Find all items to clean
        duplicate_files = self.find_duplicate_files()
        backup_dirs = self.find_backup_directories()
        temp_files = self.find_temp_files()
        old_logs = self.find_log_files()
        
        # Clean items
        self.remove_items(duplicate_files, "duplicate files")
        self.remove_items(backup_dirs, "backup directories")
        self.remove_items(temp_files, "temporary files")
        self.remove_items(old_logs, "old log files")
        
        # Clean Python and Node artifacts
        self.clean_python_cache()
        self.clean_node_modules()
        
        # Fix permissions
        self.fix_permissions()
        
        logger.info("Repository cleanup completed!")


def main():
    parser = argparse.ArgumentParser(description="Agent-S3 Repository Cleanup Tool")
    parser.add_argument('--dry-run', action='store_true', help="Show what would be done without making changes")
    parser.add_argument('--force', action='store_true', help="Skip confirmation prompts")
    parser.add_argument('--duplicates-only', action='store_true', help="Only remove duplicate files")
    parser.add_argument('--python-only', action='store_true', help="Only clean Python cache files")
    parser.add_argument('--temp-only', action='store_true', help="Only remove temporary files")
    
    args = parser.parse_args()
    
    # Find repository root
    current = Path.cwd()
    repo_root = current
    while repo_root != repo_root.parent:
        if (repo_root / '.git').exists():
            break
        repo_root = repo_root.parent
    else:
        logger.error("Not in a git repository")
        sys.exit(1)
    
    cleaner = RepositoryCleanup(repo_root, dry_run=args.dry_run, force=args.force)
    
    if args.duplicates_only:
        duplicates = cleaner.find_duplicate_files()
        cleaner.remove_items(duplicates, "duplicate files")
    elif args.python_only:
        cleaner.clean_python_cache()
    elif args.temp_only:
        temp_files = cleaner.find_temp_files()
        cleaner.remove_items(temp_files, "temporary files")
    else:
        cleaner.run_full_cleanup()


if __name__ == '__main__':
    main()