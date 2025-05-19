#!/usr/bin/env python3
import os
import re
import sys

def find_duplicate_files():
    """Find files with numbers in their names that are likely duplicates."""
    duplicates = []
    for root, dirs, files in os.walk('.'):
        for file in files:
            if re.search(r' \d+\.py$', file):
                duplicates.append(os.path.join(root, file))
    return duplicates

def remove_files(files):
    """Remove the specified files."""
    for file in files:
        try:
            os.remove(file)
            print(f"Removed: {file}")
        except Exception as e:
            print(f"Error removing {file}: {e}")

if __name__ == "__main__":
    duplicate_files = find_duplicate_files()
    print(f"Found {len(duplicate_files)} duplicate files.")
    if duplicate_files:
        remove_files(duplicate_files)
        print("Duplicate files removed.")
    else:
        print("No duplicate files found.")
