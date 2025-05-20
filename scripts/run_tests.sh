#!/usr/bin/env bash
set -euo pipefail

# Install package in editable mode with dependencies
python -m pip install -e .
if [ -f requirements.txt ]; then
    python -m pip install -r requirements.txt
fi
# Ensure pytest and bcrypt are available
python -m pip install pytest bcrypt

# Run tests quietly
pytest -q
