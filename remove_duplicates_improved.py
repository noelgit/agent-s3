#!/usr/bin/env python3
import os
import re
import subprocess

def find_and_remove_duplicates():
    """Find and remove Python files with numbers in their names."""
    # Use subprocess to get accurate listing with spaces in filenames
    result = subprocess.run(
        "find . -name '* [0-9].py' -o -name '* [0-9][0-9].py'",
        shell=True, 
        capture_output=True, 
        text=True
    )
    
    files = result.stdout.strip().split('\n')
    
    # Filter out empty strings
    files = [f for f in files if f]
    
    print(f"Found {len(files)} duplicate files.")
    
    for file_path in files:
        try:
            # Use subprocess to remove the file
            subprocess.run(["rm", "-f", file_path])
            print(f"Removed: {file_path}")
        except Exception as e:
            print(f"Error removing {file_path}: {e}")

if __name__ == "__main__":
    find_and_remove_duplicates()
