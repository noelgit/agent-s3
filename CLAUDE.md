# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build/Test Commands
- Setup environment: `python -m pip install -e .`
- Run tests: `pytest`
- Run single test: `pytest tests/path_to_test.py::TestClass::test_function`
- Run the CLI: `python -m agent_s3.cli`
- Type checking: `mypy agent_s3/`
- Linting: `ruff check agent_s3/`

## Code Style Guidelines
- Use Python 3.10+ compatible code
- Use type hints for all function parameters and return values
- Follow PEP 8 style guidelines
- Organize imports: standard library first, then third-party, then local
- Naming: use snake_case for functions/variables, PascalCase for classes
- Document all modules and functions with docstrings
- Error handling: use try/except blocks with specific exceptions
- Use f-strings for string formatting
- Use absolute imports within the package
- Log all operations with proper timestamp and role labels
- Always enforce fixed coding guidelines loaded from .github/copilot-instructions.md