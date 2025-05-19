#!/bin/bash
# Script to remove duplicate numbered files and apply patches

# Find and remove all files with numbers in their names that are likely duplicates
find . -name "* [0-9].py" -o -name "* [0-9][0-9].py" | xargs rm -v

# Find and remove similar duplicate files in system_tests
find ./system_tests -name "*[0-9].py" | xargs rm -v

# Apply the patches
git apply fixed_patch.patch
git apply user_patch.patch

# Check if there were any conflicts
if [ $? -ne 0 ]; then
    echo "Error: There were conflicts when applying patches"
    exit 1
fi

# Stage all changes
git add .

# Commit the changes
git commit -m "Remove unused duplicate files and apply patches"

echo "Done! Duplicates removed and patches applied."
