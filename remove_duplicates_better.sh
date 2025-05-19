#!/bin/bash
# Script to remove duplicate numbered files

# Find and remove all files with numbers in their names that are likely duplicates
find . -name "* [0-9].py" -o -name "* [0-9][0-9].py" | while read file; do
  rm -f "$file"
  echo "Removed: $file"
done

echo "Removed duplicate files."
