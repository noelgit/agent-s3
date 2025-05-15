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

## Critical Implementation Guidelines
- ALWAYS maintain a single canonical implementation of each component
- NEVER create multiple/parallel implementations of the same functionality
- When a feature needs updating or improvement, modify the existing implementation in place
- Code upgrades should NEVER result in multiple versions of the same component
- A request to update or improve code is NOT permission to create parallel implementations
- When enhancements are needed, improve the existing files directly
- Prefer gradual, well-tested changes to the canonical implementation
- If backward compatibility is needed, use feature flags or optional parameters
- Create shims or compatibility layers only when absolutely necessary and with explicit deprecation warnings

## Refactoring Guidelines
- When refactoring, always sunset old implementations in favor of improved versions
- Do not maintain parallel implementations of the same functionality
- Provide backward compatibility through the new implementation rather than keeping old code
- Add clear deprecation warnings to guide users toward the new implementation
- Update all affected code to use the new implementation directly
- Ensure backward compatibility by making new implementations handle legacy usage patterns
- Document the migration process in comments or docstrings

## Module Architecture Patterns
- Base modules provide core functionality (e.g., pre_planner.py, planner.py)
- Specialized modules extend base functionality with enforced schemas/validation (e.g., pre_planner_json_enforced.py, planner_json_enforced.py)
- Maintain symmetrical relationships between related modules (pre_planner <-> planner, pre_planner_json_enforced <-> planner_json_enforced)
- Core imports should follow this pattern:
  - Base modules can import from other base modules (e.g., planner.py can import from pre_planner.py)
  - Specialized modules should import from their corresponding base module
  - Avoid circular imports between similar level modules (don't create cycles)
- When using modules, import both the base and specialized versions for architectural consistency:
```python
from agent_s3.pre_planner import call_pre_planner  # Import base
from agent_s3.pre_planner_json_enforced import pre_planning_workflow  # Import canonical entry point
```

## Debugging System Architecture
- Chain of Thought (CoT) logging is implemented through EnhancedScratchpadManager
- Three-tier debugging strategy is implemented through DebuggingManager
- Error categorization and context collection is handled by ErrorContextManager
- Always run type checking and linting before committing changes
- See DEBUGGING.md for comprehensive details on the debugging system