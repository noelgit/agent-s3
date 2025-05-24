#!/usr/bin/env python3
"""
A script to delete duplicate files where duplicates are identified as
files with a number before the file extension.
For example: file1.txt, script2.py, refinement_manager 3.py

Usage:
  python delete_file_duplicates.py           # Interactive mode with confirmation
  python delete_file_duplicates.py --force   # Delete without confirmation
  python delete_file_duplicates.py --dry-run # Show files that would be deleted
  python delete_file_duplicates.py --help    # Show help message
"""
import os
import re
import argparse
from pathlib import Path


def is_duplicate_file(file_path):
    """
    Check if a file has a number before the extension, making it a likely duplicate.
    
    Args:
        file_path (Path): The path to the file to check
        
    Returns:
        bool: True if the file has a number before the extension, False otherwise
    """
    # Extract the filename
    filename = file_path.name
    
    # Check if the filename has a number before the extension
    # This pattern matches filenames that have a number immediately before the extension
    # For example: file1.txt, document2.docx, script3.py
    pattern = r'^(.+?)(\d+)(\..+)$'
    
    # This pattern matches filenames with spaces and numbers before extension
    # For example: "refinement_manager 3.py"
    pattern2 = r'^(.+?)\s+(\d+)(\..+)$'
    
    return bool(re.match(pattern, filename) or re.match(pattern2, filename))


def find_duplicate_files(directory, exclude_dirs=None):
    """
    Find all files in the directory that have a number before the extension.
    
    Args:
        directory (str): The root directory to search in
        exclude_dirs (list): List of directory names to exclude (case-insensitive)
        
    Returns:
        list: A list of Path objects for files that have a number before the extension
    """
    if exclude_dirs is None:
        exclude_dirs = ['node_modules', '__pycache__', '.git', '.mypy_cache', 'venv']
    
    duplicate_files = []
    root_path = Path(directory)
    
    for file_path in root_path.glob('**/*'):
        # Skip if it's a directory
        if file_path.is_dir():
            continue
        
        # Skip if the file is in an excluded directory
        if any(ex_dir.lower() in str(file_path).lower() for ex_dir in exclude_dirs):
            continue
            
        if is_duplicate_file(file_path):
            duplicate_files.append(file_path)
            
    return duplicate_files


def delete_files(file_list, dry_run=False):
    """
    Delete the specified files.
    
    Args:
        file_list (list): A list of Path objects for files to delete
        dry_run (bool): If True, don't actually delete files, just print what would be done
        
    Returns:
        int: Number of files deleted
    """
    count = 0
    for file_path in file_list:
        try:
            if dry_run:
                print(f"Would delete: {file_path}")
            else:
                os.remove(file_path)
                print(f"Deleted: {file_path}")
            count += 1
        except Exception as e:
            print(f"Error deleting {file_path}: {str(e)}")
    
    return count


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Delete duplicate files with numbers before extensions')
    parser.add_argument('--force', action='store_true', help='Delete files without confirmation')
    parser.add_argument('--dry-run', action='store_true', help='Show files that would be deleted without deleting')
    args = parser.parse_args()
    
    # Get the root directory (agent-s3)
    root_dir = Path(__file__).parent
    
    # Find duplicate files
    print("Searching for duplicate files...")
    duplicate_files = find_duplicate_files(root_dir)
    
    if not duplicate_files:
        print("No duplicate files found.")
        return
    
    # First run in dry-run mode to show what will be deleted
    print("\nFound the following duplicate files:")
    for file_path in duplicate_files:
        print(f"  {file_path}")
    
    # If dry-run mode is enabled, exit after showing files
    if args.dry_run:
        print("\nDry run completed. No files were deleted.")
        return
    
    # Ask for confirmation before deleting
    if args.force:
        confirm = 'y'
    else:
        confirm = input("\nDelete these files? (y/n): ").strip().lower()
    
    if confirm == 'y':
        num_deleted = delete_files(duplicate_files)
        print(f"\nDeleted {num_deleted} duplicate files.")
    else:
        print("\nOperation cancelled. No files were deleted.")


if __name__ == "__main__":
    main()
