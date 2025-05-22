#!/usr/bin/env bash
# Script to consolidate duplicate files and update both local and remote main branches

set -e  # Exit on error

echo "=== Starting duplicate file cleanup process ==="

# Create backups directory if it doesn't exist
mkdir -p backups

# Make scripts executable
chmod +x consolidate_files.py

# Run the consolidation script
echo "=== Running file consolidation script ==="
python3 ./consolidate_files.py

# Add the consolidated files to git
echo "=== Adding changes to git ==="
git add .

# Commit the changes
echo "=== Committing changes ==="
git commit -m "Fix: Consolidated duplicate files to improve codebase consistency"

# Update local main branch
echo "=== Updating local main branch ==="
git checkout main
git merge --no-ff HEAD@{1} -m "Merge: Consolidated duplicate files"

# Push to remote
echo "=== Pushing changes to remote ==="
git push origin main

echo "=== File consolidation complete and branches updated ==="
