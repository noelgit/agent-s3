#!/usr/bin/env python3
"""
File Consolidation Script for Agent-S3 Project.
This script identifies duplicate files with '2' suffix variants,
merges any differences, and removes the duplicates.
"""

import os
import sys
import difflib
import shutil
from datetime import datetime
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('file_consolidation.log')
    ]
)
logger = logging.getLogger('file_consolidation')

def read_file(file_path):
    """Read a file's contents if it exists."""
    if not os.path.exists(file_path):
        logger.warning("File does not exist: %s", file_path)
        return None

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        logger.error("Error reading file %s: %s", file_path, str(e))
        return None

def write_file(file_path, content):
    """Write content to a file."""
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    except Exception as e:
        logger.error("Error writing to file %s: %s", file_path, str(e))
        return False

def backup_file(file_path):
    """Create a backup of a file."""
    if not os.path.exists(file_path):
        return False

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    backup_path = f"{file_path}.bak.{timestamp}"
    try:
        shutil.copy2(file_path, backup_path)
        print(f"Created backup: {backup_path}")
        return True
    except Exception as e:
        logger.error("Error creating backup of %s: %s", file_path, str(e))
        return False

def files_are_identical(content1, content2):
    """Check if two file contents are identical."""
    if content1 is None or content2 is None:
        return False
    return content1 == content2

def merge_file_contents(original_content, duplicate_content):
    """
    Merge the contents of two files, preferring the duplicate content
    when differences are found, as it's assumed to be newer.
    """
    if original_content is None and duplicate_content is None:
        return None
    elif original_content is None:
        return duplicate_content
    elif duplicate_content is None:
        return original_content

    # If files are identical, return either one
    if original_content == duplicate_content:
        return original_content

    # Split the content into lines for diffing
    original_lines = original_content.splitlines()
    duplicate_lines = duplicate_content.splitlines()

    # Use difflib to get a unified diff
    diff = list(difflib.unified_diff(original_lines, duplicate_lines, n=0))

    if not diff:
        return original_content

    # Log the differences found
    print("Differences found:\n" + "\n".join(diff[:20]) + ("..." if len(diff) > 20 else ""))

    # Since we're assuming the duplicate (with '2' suffix) is newer,
    # we'll use its content
    return duplicate_content

def consolidate_duplicate_files():
    """Consolidate duplicate files with '2' suffix variants."""
    # List of (duplicate, original) file pairs
    duplicates = [
        ('agent_s3/tools/coherence_validator 2.py', 'agent_s3/tools/coherence_validator.py'),
        ('agent_s3/tools/implementation_validator 2.py', 'agent_s3/tools/implementation_validator.py'),
        ('agent_s3/pre_planner_json_enforced 2.py', 'agent_s3/pre_planner_json_enforced.py'),
        ('system_tests/test_multi_step_workflow 2.py', 'system_tests/test_multi_step_workflow.py'),
        ('system_tests/test_context_aware_planning 2.py', 'system_tests/test_context_aware_planning.py'),
        ('agent_s3/tools/plan_validator 2.py', 'agent_s3/tools/plan_validator.py'),
        ('agent_s3/planner_json_enforced 2.py', 'agent_s3/planner_json_enforced.py'),
        ('agent_s3/test_generator 2.py', 'agent_s3/test_generator.py')
    ]

    consolidated_count = 0

    for duplicate, original in duplicates:
        print(f"Processing: {duplicate} -> {original}")

        # Read file contents
        duplicate_content = read_file(duplicate)
        original_content = read_file(original)

        # Skip if both files don't exist
        if duplicate_content is None and original_content is None:
            logger.warning("Both files don't exist: %s and %s", duplicate, original)
            continue

        # If only the duplicate exists, rename it to the original
        if original_content is None and duplicate_content is not None:
            print(f"Only duplicate exists, renaming to original: {duplicate} -> {original}")

            # Ensure directory exists for original
            os.makedirs(os.path.dirname(original), exist_ok=True)

            # Write duplicate content to original path
            if write_file(original, duplicate_content):
                os.remove(duplicate)
                consolidated_count += 1
            continue

        # If only the original exists, nothing to do
        if original_content is not None and duplicate_content is None:
            print("Only original exists, nothing to consolidate.")
            continue

        # If both exist, check if they're identical
        if files_are_identical(original_content, duplicate_content):
            print(f"Files are identical, removing duplicate: {duplicate}")
            os.remove(duplicate)
            consolidated_count += 1
            continue

        # Files differ, merge them
        print(f"Files differ, merging: {duplicate} -> {original}")

        # Create backup of original file
        if not backup_file(original):
            logger.error("Failed to backup original file: %s. Skipping merge.", original)
            continue

        # Merge and write content
        merged_content = merge_file_contents(original_content, duplicate_content)
        if write_file(original, merged_content):
            print(f"Successfully merged files. Removing duplicate: {duplicate}")
            os.remove(duplicate)
            consolidated_count += 1
        else:
            logger.error("Failed to write merged content to %s", original)

    print(f"Consolidation complete. Processed {consolidated_count} out of {len(duplicates)} duplicates.")
    return consolidated_count

if __name__ == "__main__":
    print("Starting file consolidation process")
    consolidated = consolidate_duplicate_files()
    print(f"Consolidation completed. Consolidated {consolidated} files.")
    sys.exit(0)
