#!/bin/bash
# cleanup_duplicates.sh - Script to remove backup files from both local and remote repositories

echo "Starting cleanup of backup files..."

# Change to the repository root directory
cd "$(dirname "$0")"

# 1. Remove the entire backups directory
echo "Removing the backups directory..."
if [ -d "backups" ]; then
  echo "Removing backups directory"
  rm -rf backups
else
  echo "Backups directory not found, skipping..."
fi

# 2. Remove all .bak files recursively
echo "Removing any .bak files..."
find . -type f -name "*.bak*" | grep -v ".git" > /tmp/bak_files_to_remove.txt

# Remove .bak files found
echo "Removing any remaining .bak files..."
while read -r file; do
  if [ -f "$file" ]; then
    echo "Removing $file"
    rm -f "$file"
  else
    echo "File $file not found, skipping..."
  fi
done < /tmp/bak_files_to_remove.txt

# Add all changes to git
echo "Adding changes to git..."
git add -A

# Commit changes
echo "Committing changes..."
git commit -m "Remove duplicate and backup files"

# Push changes to remote main branch
echo "Pushing changes to remote main branch..."
git push origin main

echo "Cleanup complete!"
echo "Files removed locally and from remote main branch."
