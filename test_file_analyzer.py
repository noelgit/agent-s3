#!/usr/bin/env python3
"""
Test File Analyzer for Agent-S3 Project.
This script identifies and cleans up test files:
1. Removes duplicate test files with a "2" suffix
2. Identifies test files with syntax errors that need fixing
3. Identifies test files that are not being used
"""

import os
import sys
import subprocess
import re
from pathlib import Path
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('test_cleanup.log')
    ]
)
logger = logging.getLogger('test_cleanup')

def find_test_files():
    """Find all test files in the project."""
    test_files = []
    
    # Search for test files in standard test directories
    for root_dir in ['tests', 'agent_s3/tests', 'system_tests']:
        if not os.path.exists(root_dir):
            continue
            
        for root, _, files in os.walk(root_dir):
            for file in files:
                if file.startswith('test_') and file.endswith('.py'):
                    test_files.append(os.path.join(root, file))
    
    return test_files

def check_syntax(file_path):
    """Check if a Python file has syntax errors."""
    result = subprocess.run(
        ['python', '-m', 'py_compile', file_path],
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True
    )
    
    if result.returncode != 0:
        return False, result.stderr
    return True, None

def find_duplicate_test_files():
    """Find duplicate test files with '2' suffix."""
    duplicates = []
    
    # Find all files with " 2" in their name
    for root, _, files in os.walk('.'):
        for file in files:
            if ' 2' in file and file.endswith('.py'):
                duplicates.append(os.path.join(root, file))
    
    return duplicates

def move_to_legacy_folder(file_path):
    """Move a file to a legacy folder."""
    legacy_dir = os.path.join(os.path.dirname(file_path), 'legacy')
    os.makedirs(legacy_dir, exist_ok=True)
    
    target_path = os.path.join(legacy_dir, os.path.basename(file_path))
    os.rename(file_path, target_path)
    logger.info(f"Moved {file_path} to {target_path}")

def main():
    """Main function."""
    logger.info("Starting test file analysis")
    
    # Find all test files
    test_files = find_test_files()
    logger.info(f"Found {len(test_files)} test files")
    
    # Check for syntax errors
    files_with_syntax_errors = []
    for file in test_files:
        syntax_valid, error = check_syntax(file)
        if not syntax_valid:
            files_with_syntax_errors.append((file, error))
    
    if files_with_syntax_errors:
        logger.warning(f"Found {len(files_with_syntax_errors)} files with syntax errors:")
        for file, error in files_with_syntax_errors:
            logger.warning(f"{file}: {error}")
    
    # Find duplicate test files
    duplicates = find_duplicate_test_files()
    if duplicates:
        logger.info(f"Found {len(duplicates)} duplicate test files:")
        for dupe in duplicates:
            logger.info(f"  {dupe}")
        
        # Option to move duplicates to legacy folder
        response = input("Do you want to move these duplicate files to a legacy folder? (y/n): ")
        if response.lower() == 'y':
            for dupe in duplicates:
                move_to_legacy_folder(dupe)
    
    # Provide summary
    logger.info("Test file analysis complete")
    if files_with_syntax_errors:
        logger.info(f"{len(files_with_syntax_errors)} files have syntax errors and need to be fixed.")
    if duplicates:
        logger.info(f"{len(duplicates)} duplicate files found.")

if __name__ == "__main__":
    main()
