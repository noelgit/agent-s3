#!/bin/bash
# Cleanup script to remove duplicate files and leftover artifacts

echo "Starting repository cleanup..."

# Remove duplicate files with version numbers
echo "Removing duplicate files with version numbers..."

# Remove vscode duplicates
rm -f vscode/backend-connection\ 2.ts
rm -f vscode/backend-connection\ 3.ts

# Remove tools duplicates
rm -f agent_s3/tools/static_analyzer\ 2.py
rm -f agent_s3/tools/static_analyzer\ 3.py
rm -f agent_s3/tools/static_analyzer\ 4.py

# Remove crdownload files
rm -f agent_s3/tools/test_critic/core\ 2.crdownload
rm -f agent_s3/tools/test_critic/core\ 3.crdownload
rm -f agent_s3/tools/test_critic/core\ 4.crdownload

# Remove .hypothesis duplicates
find .hypothesis/constants -name "* 2" -type f -delete

# Remove leftover files
echo "Removing leftover files..."
rm -f agent_s3/config.py.rej

# Remove cleanup scripts with hard-coded paths
echo "Removing cleanup scripts with hard-coded paths..."
rm -f final_cleanup.sh

echo "Cleanup complete!"
