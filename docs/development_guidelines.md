<!--
File: docs/development_guidelines.md
Description: Consolidated development guidelines for Agent-S3.
-->

# Development Guidelines

## Build and Test Commands

- Setup environment:
  ```bash
  python -m pip install -e . && pip install -r requirements.txt
  ```
- Install optional tokenizers (required for some tests):
  ```bash
  pip install '.[tokenizers]'  # provides tiktoken for accurate token counting
  ```
- Run tests: `pytest`
- If `tiktoken` is unavailable, unit tests under `tests/unit/context_management` mock the library to allow test execution.
- Run a single test: `pytest tests/path_to_test.py::TestClass::test_function`
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
- Always enforce fixed coding guidelines loaded from `.github/copilot-instructions.md`

## Critical Implementation Guidelines
- **Single Implementation:** maintain a single canonical implementation of each component
- **No Parallel Versions:** never create multiple versions of the same functionality
- **Modify in Place:** update existing code rather than introducing duplicates
- **Gradual Improvements:** prefer well‑tested incremental changes
- **Backward Compatibility:** use feature flags or optional parameters when necessary
- **Deprecation Warnings:** provide clear guidance when sunsetting old behavior

## Refactoring Guidelines
- Sunset old implementations in favor of improved versions
- Avoid maintaining parallel code paths
- Provide backward compatibility through the new implementation
- Update all affected code to use the new implementation directly
- Document migration steps when necessary

## Module Architecture Patterns
- Base modules provide core functionality (e.g., `planner.py`)
- Specialized modules extend base functionality with enforced schemas/validation (e.g., `pre_planner_json_enforced.py`)
- Maintain symmetrical relationships between related modules
- Specialized modules should import from their corresponding base module
- Avoid circular imports between modules of the same level

## Playwright Test Scripts

The repository includes Playwright tests that map to the user stories:

| User Story | Script File | Description |
|------------|-------------|-------------|
| **Story 1: Initializing Agent-S3 in a New Workspace** | [story1-initialize-workspace.spec.ts](../tests/playwright/specs/story1-initialize-workspace.spec.ts) | Tests initialization via command palette and CLI, including GitHub authentication |
| **Story 2: Making a Code Change Request** | [story2-code-change-request.spec.ts](../tests/playwright/specs/story2-code-change-request.spec.ts) | Tests making code change requests through multiple entry points |
| **Story 3: Interacting via the Chat UI** | [story3-chat-ui.spec.ts](../tests/playwright/specs/story3-chat-ui.spec.ts) | Tests chat window interactions and history persistence |
| **Story 4: Using Helper Commands** | [story4-helper-commands.spec.ts](../tests/playwright/specs/story4-helper-commands.spec.ts) | Tests helper commands like `/help` and `/explain` |

### Running the Tests

- Run all tests:
  ```bash
  npx playwright test
  ```
- Run a specific story:
  ```bash
  npx playwright test tests/playwright/specs/story1-initialize-workspace.spec.ts
  ```
- Run in headed mode:
  ```bash
  npx playwright test --headed
  ```

## Contributing Guidelines

### Setup for Contributors
- Install runtime and development dependencies:
  ```bash
  pip install -r requirements.txt
  pip install -r requirements-dev.txt
  ```

### Pre-commit Checklist
- Run `pytest` and confirm all tests pass
- Run `mypy agent_s3` for static type checking  
- Run `ruff check agent_s3` for linting
- Write commit messages according to the Conventional Commits specification

### Commit Message Format
Use [Conventional Commits](https://www.conventionalcommits.org/) with the format `<type>(<scope>): <description>`.
Keep the description concise and in the imperative mood.

Examples:
```
fix(security): sanitize header logs
docs(readme): clarify setup instructions
feat(planner): add JSON schema validation
refactor(auth): consolidate token validation
```
