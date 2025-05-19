#!/bin/bash
# Script to remove duplicate numbered files

# Find and remove all files with numbers in their names that are likely duplicates
find . -name "* [0-9].py" | xargs rm -f
find . -name "* [0-9][0-9].py" | xargs rm -f

# Find and remove similar duplicate files in system_tests 
find ./system_tests -name "*[0-9].py" -not -path "*/[^0-9]*[0-9].py" | xargs rm -f

# Echo the results
echo "Removed duplicate files."
