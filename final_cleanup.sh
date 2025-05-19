#!/bin/bash
# Final cleanup script to remove all duplicates

cd /Users/noelpatron/Documents/GitHub/agent-s3

# Remove files with spaces and numbers in their name (3+)
find . -name "* 3.py" -o -name "* 4.py" -o -name "* 5.py" -o -name "* 6.py" -o -name "* 7.py" -o -name "* 8.py" -o -name "* 9.py" | while read file; do
  # Remove the file
  rm -f "$file"
  echo "Removed: $file"
done

# Stage all changes
git add -A

# Commit changes
git commit -m "Remove remaining duplicate files with numbered suffixes"
