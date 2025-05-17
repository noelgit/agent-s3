#!/bin/bash

# Read the list of files from the output of git ls-files -ci --exclude-standard
git ls-files -ci --exclude-standard | while read file; do
  echo "Removing $file from Git tracking (but keeping the local file)"
  git rm --cached "$file"
done
