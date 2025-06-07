# Agent-S3

Agent-S3 is SparkSoft Solutions' own Engineer-in-the-Loop AI coding agent designed to empower engineers by emphasizing transparency, control, and strict adherence to guidelines. Recognizing that AI can and will make mistakes, Agent-S3 ensures that the engineer remains in control at every stage of the development process.

**Core Philosophy:**
- **Correctness over Speed**: Agent-S3 prioritizes correctness over convenience, implementing rigorous validation at every step
- **Engineer Control**: Every decision is reviewed and approved by the engineer before execution
- **Transparency First**: All planning, validation, and implementation steps are clearly visible to the user
- **Quality Assurance**: Multi-phase validation including semantic coherence checks, security reviews, and comprehensive testing strategies

This README and the companion `STORIES.md` file serve as the canonical project
documentation. Both documents provide authoritative information on setup,
workflows, and design decisions.

## Overview

Agent-S3 automates feature planning, code generation, and execution while maintaining a step-by-step approach to prioritize correctness over convenience. Key features include:

- **Consolidated Plan Workflow:** Engineers review and approve a consolidated plan that combines architecture reviews, tests, and implementation details. Each component is generated in separate phases and then merged, offering a comprehensive view of the proposed changes.
  - **Step 1: Architecture Review** – identify logical gaps, security issues, and optimizations.
  - **Step 2: Test Specification Refinement** – create detailed test requirements based on the review.
  - **Step 3: Test Implementation** – generate runnable unit, property-based, and acceptance tests.
  - **Step 4: Implementation Planning** – outline code changes addressing architecture findings and ensuring tests pass.
  - **Step 5: Semantic Validation** – verify coherence across architecture, tests, and implementation plan before consolidation.

- **Semantic Validation:** The system performs logical coherence validation between architecture, implementation plans, and tests, ensuring consistency and identifying potential issues before implementation.

- **Feature Group Processing:** Complex requests are decomposed into distinct single-concern features organized into feature groups that are processed individually, with comprehensive validation across architecture, implementation, and tests.

- **Interactive User Modification:** Engineers can modify plans with an intuitive "yes/no/modify" workflow, with automatic re-validation of modifications to ensure they don't introduce inconsistencies.

- **Checkpoint System:** The system maintains checkpoints and version tracking of plans through a dedicated checkpoint manager, providing traceability and history of planning decisions.

- **Complexity Management:** For complex tasks, the system provides an explicit warning and requires user confirmation, improving transparency and user control rather than automatic workflow switching.

- **Test Critic Integration:** The system analyzes test quality and coverage, providing warnings and suggestions for comprehensive testing strategies.

- **Multi-LLM Solution:** To prevent runaway costs, Agent-S3 implements a multi-LLM strategy, using state-of-the-art context and cache management to optimize token usage and response times.

- **VS Code Extension:** For a consistent user experience, Agent-S3 integrates with Visual Studio Code as its primary user interface, providing real-time feedback, progress tracking, and interactive prompts.

- **GitHub Integration:** Automatic creation of GitHub issues from approved plans and pull requests from completed implementations, providing seamless project management integration when a GitHub token is available.

Agent-S3 is not just a tool for automation; it is a partner in development that prioritizes transparency, correctness, and engineer control at every step.

## Key Objectives

Agent-S3 is built around several core objectives that guide its design and implementation:

### 1. **Maintain Engineering Excellence**
- **Security-First Development**: Implements OWASP Top 10 security standards, input validation, authentication/authorization, and secure coding practices
- **Performance Optimization**: Focuses on efficient algorithms (O(n) or better), proper database query optimization, memory management, and resource usage
- **Code Quality Standards**: Enforces SOLID principles, clean code practices, comprehensive documentation, and adherence to project-specific guidelines
- **Accessibility Compliance**: Ensures WCAG 2.1 Level AA compliance with semantic HTML, keyboard navigation, and assistive technology support

### 2. **Provide Comprehensive Validation**
- **Semantic Coherence**: Validates logical consistency between architecture, implementation plans, and tests
- **Multi-Phase Validation**: Implements pre-planning validation, JSON schema enforcement, and static plan checking
- **Cross-Component Verification**: Ensures traceability between system design elements, implementation steps, and test coverage
- **Security Review Integration**: Automated security validation for critical operations and data handling

### 3. **Enable Scalable Development Workflows**
- **Feature Group Processing**: Decomposes complex requests into manageable, single-concern features
- **Intelligent Context Management**: Uses semantic caching, token optimization, and framework-specific adaptations
- **Error Recovery Systems**: Implements pattern-based error detection, automated recovery strategies, and comprehensive logging
- **Multi-LLM Orchestration**: Optimizes costs and performance through strategic model selection and caching

### 4. **Support Modern Development Practices**
- **CI/CD Integration**: Seamless integration with GitHub for issue tracking, pull requests, and automated workflows
- **Test-Driven Development**: Comprehensive test planning including unit, property-based, and acceptance tests
- **Interactive Design Process**: Conversational feature decomposition with industry best practice recommendations
- **Real-Time Collaboration**: HTTP-based API for immediate feedback and progress tracking

## Dependencies and Installation

Agent-S3 is a multi-component system with dependencies across Python, Node.js, and TypeScript ecosystems. For comprehensive dependency information, see [`DEPENDENCIES.md`](DEPENDENCIES.md).

### Quick Setup

**Prerequisites:**
- Python 3.8+ 
- Node.js 16+
- npm or yarn

**Python Dependencies:**
```bash
# Core runtime dependencies
pip install -r requirements.txt

# Development and testing dependencies  
pip install -r requirements-dev.txt
```

**Node.js Dependencies:**
```bash
# Main project dependencies
npm install

# VSCode extension
cd vscode && npm install

# Webview UI
cd vscode/webview-ui && npm install
```

**Building:**
```bash
# Compile VSCode extension
cd vscode && npm run compile

# Build webview UI
cd vscode && npm run build-webview
```

**Validation:**
```bash
# Validate all dependencies are working
python validate_dependencies.py

# Quick dependency check
npm audit
pip check
```

## Core Features

**Python Backend (`agent_s3`):**
- Commands are sent via an HTTP server. The extension falls back to CLI when the server is unreachable.
- Advanced context management with:
  - Context registry with multiple providers that can be registered and queried
  - Tool/manager registry for coordinator components (`agent_s3.coordinator.registry`)
  - Framework-specific context adaptation for popular frameworks (React, Django, Flask, FastAPI, Express)
  - Smart token allocation based on role, content type, and task requirements
  - Dynamic token budget allocation with priority-based and task-adaptive strategies
  - Context checkpoint system for state saving/recovery with version control compatibility
- Context compression strategies (semantic summarization, key information extraction, reference-based) with comprehensive metadata for tracing and debugging
- Dynamic file relevance scoring using hybrid search and Git modification history (frequency/recency)
- Hierarchical summarization for large files
- Semantic clustering for better context organization
- Static Plan Checker for validating Pre-Planner outputs (see [STATIC_PLAN_CHECKER.md](STATIC_PLAN_CHECKER.md))
- Comprehensive error handling and recovery:
  - Error pattern detection, caching, similarity matching, and pruning based on frequency/recency
  - Type-specific error handlers for 12+ error categories (syntax, type, import, attribute, name, index, value, runtime, memory, permission, assertion, network, database)
  - Specialized context gathering based on error type (e.g., package info for imports, permissions for OS errors, network status)
  - Smart token budget allocation for error context
  - Recovery suggestions based on error patterns and type
  - Automated error recovery attempts for known patterns or common issues (e.g., installing missing packages via pip, fixing file permissions, running DB migrations)
- Consolidated Planning and Feature Group Processing:
  - Pre-planning phase with JSON format enforcement and static validation
  - Feature group decomposition with implementation plans, architecture reviews, and tests presented as a unified whole
  - Semantic validation for logical coherence between architecture, implementation, and tests
  - Interactive user modification with comprehensive re-validation
  - Structured modification format with COMPONENT, LOCATION, CHANGE_TYPE, and DESCRIPTION fields
  - Precise targeting of plan components for modification with enhanced LLM processing
  - Modification loop prevention to avoid endless cycles
  - Automatic plan file generation with unique IDs for traceability
- Complexity Management:
  - Explicit complexity assessment with numerical scoring
- User confirmation required for complex tasks
- Clear options to proceed, modify request, or cancel
- Removal of automatic workflow switching in favor of user control
  - Final confirmation after reviewing pre-planning results when tasks are
    flagged as complex
- Design-to-Implementation Pipeline:
  - Conversational feature decomposition and architecture planning via `/design` command
  - Industry best practice analysis and recommendations during design
  - Automatic extraction and organization of single-concern features into hierarchical tasks
  - Structured design document generation (`design.txt`)
  - Tracking implementation progress in `implementation_progress.json`
  - Sequential implementation of tasks with the `/continue` command
  - Automatic test execution after each implementation step
- CLI interface (`agent_s3.cli`) with commands: `/init`, `/help`, `/config`, `/reload-llm-config`, `/explain`, `/request`, `/terminal`, `/design`, `/design-auto`, `/guidelines`, `/continue`, `/tasks`, `/clear`, `/db`, `/test`, `/debug`. Supports multi-line heredoc input (`<<MARKER ... MARKER`) for `/cli file` and `/cli bash`.
- GitHub authentication via OAuth App and GitHub App flows (`agent_s3.auth`)
- Centralized configuration loading from `llm.json`, environment variables, and `.env` (`agent_s3.config`)
- Dynamic LLM routing by arbitrary roles defined in `llm.json`, with circuit breaker, fallback logic, and metrics tracking (`agent_s3.router_agent`)
- Resilient LLM calls with retry, exponential backoff, and fallback strategies (`agent_s3.llm_utils.call_llm_with_retry`)
- Multi-phase task orchestration: pre-planning, feature group processing, code generation, execution/testing, and optional PR creation in `agent_s3.coordinator`
- Iterative code generation & refinement (`agent_s3.code_generator`) with automated linting, testing, and diff-based user approvals
- `generate_code` returns a mapping of file paths to code strings, using `None` when a file fails to generate
- Retrieval-Augmented Generation (RAG) context: embedding-based search (`agent_s3.tools.embedding_client`) and hierarchical summarization (`agent_s3.tools.memory_manager`)
- Tech stack detection with versioning and best practice identification (`agent_s3.tools.tech_stack_manager`)
- Secure file operations (`FileTool`), sandboxed shell execution (`BashTool`, `TerminalExecutor`), and database interactions (`DatabaseTool`)
- `BashTool.run_command` returns `(exit_code, output)` for consistent error handling
- Database Tool Features (`DatabaseTool`):
  - Query execution with SQLAlchemy (primary) and BashTool (fallback)
  - Parameterized queries (SQLAlchemy) and basic parameter substitution (BashTool)
  - Schema information retrieval (`get_schema_info`) using SQLAlchemy Inspector or fallback queries
  - Query plan explanation (`explain_query`)
  - Database connection testing (`test_connection`)
  - SQL script execution (`execute_script`)
  - Explicit transaction control (`begin_transaction`, `commit_transaction`, `rollback_transaction`)
  - Security validation against dangerous commands and potential injection patterns
  - Improved CLI output parsing for various DB types (CSV, TSV)
  - Automatic test database configuration for database-dependent tests
  - Schema metadata capture for PR descriptions and documentation
- Git operations and GitHub API integration (issues, PRs, repo metadata) via `agent_s3.tools.git_tool`
- Code analysis, diff computation, and lint/test tooling via `agent_s3.tools.code_analysis_tool` and `agent_s3.tools.error_context_manager`
- Comprehensive debugging system with Chain of Thought integration:
  - Three-tier debugging strategy (quick fix, full debugging, strategic restart)
  - Enhanced scratchpad with structured CoT logging (`agent_s3.enhanced_scratchpad_manager`)
  - Specialized error categorization and handling for 12+ error types (`agent_s3.debugging_manager`)
  - Context-aware error resolution with historical reasoning extraction
  - Requests engineer guidance if automated debugging fails after repeated attempts
  - See [docs/debugging_and_error_handling.md](docs/debugging_and_error_handling.md) for details
- Comprehensive test framework:
  - TestCritic for analyzing test quality and coverage (`agent_s3.tools.test_critic`)
  - TestFrameworks for framework-agnostic test generation (`agent_s3.tools.test_frameworks`)
  - Integrated test coverage enforcement within feature group processing
  - Comprehensive test validation including unit, property-based, and acceptance tests
  - Test quality metrics including coverage ratio
  - Warning system for uncovered critical files and missing test types
- Progress tracking in `progress_log.jsonl` (`agent_s3.progress_tracker`) and detailed chain-of-thought logs via enhanced scratchpad management (`agent_s3.enhanced_scratchpad_manager`)
- Interactive user prompts, plan reviews, patch diffs, and explanations via `agent_s3.prompt_moderator`
- Workspace initialization (`/init`): Validates workspace (checks for `README.md`), creates default `.github/copilot-instructions.md` and `llm.json` if missing
- Task State Management & Resumption (`TaskStateManager`):
  - Saves task state snapshots for each phase (Planning, PromptApproval, IssueCreation, CodeGeneration, Execution, PRCreation) to disk
  - Allows resuming interrupted tasks from the last saved state via `/continue` or automatically on startup
  - Supports granular resumption within Execution and PRCreation phases using sub-states (e.g., resuming after applying some changes but before running tests)
  - Tracks module scaffolding events in `development_status.json`
- Advanced semantic caching for LLM calls:
  - TTL-based expiration, vector similarity search, and prefix-aware eviction
  - Atomic disk persistence under `.cache/semantic_cache/`
  - Metrics: hits, misses, semantic_hits (via `get_cache_stats()`)
  - Asynchronous cache storage to avoid blocking LLM calls
  - vLLM KV cache reuse for improved inference performance
  - Hybrid caching strategy combining semantic hits with tensor prefix reuse
  - Automatic tensor size tracking and hit counting for performance metrics

## Validated LLM Summarization System

Agent-S3 now uses a validated LLM-based summarization system for all code and context summarization. This system:
- Uses language- and task-specific prompt generation
- Validates summaries for faithfulness, detail preservation, and structural coherence
- Refines summaries that do not meet quality thresholds
- Caches validated summaries for efficiency
- Includes a benchmark and evaluation tool for summary quality

See `docs/summarization.md` for details.

**VS Code Extension (`vscode`):**
- Command Palette integration: Initialize workspace, Make change request, Show help, Show config, Reload LLM config, Explain last LLM interaction, Open Chat Window
- Status bar item (`$(sparkle) Agent-S3`) to start change requests
- Dedicated terminal panel for backend interactions
  - Real-time status updates via HTTP API; progress is written to `progress_log.jsonl`
  - Command results are returned directly from `POST /command`; no `/status` polling
- Connection information is stored in `.agent_s3_http_connection.json` at the root
  of your workspace
- Optional Copilot-style chat UI for input; terminal shows actual outputs
- WebView panels for structured information display:
  - Code change plan reviews
  - Diff visualization
  - Design documentation

## Streaming UI

Agent-S3 features a real-time UI for chat and progress updates, powered by an HTTP-based architecture. See [docs/streaming_ui_implementation.md](docs/streaming_ui_implementation.md) for implementation details:

- **HTTP Client/Server:** The backend and VS Code extension communicate via HTTP REST API, supporting command processing and status updates.
- **Streaming Chat UI:** The `ChatView` React component in the extension displays real-time agent responses, partial message rendering, and thinking indicators.
  - **Backend Integration:** The extension reads `progress_log.jsonl` for progress details and receives command results directly from `POST /command`. Streaming updates will be added after Issue #2.
- **Robust Error Handling:** Includes reconnection logic, buffering, and error logging for reliable user experience.
- **Extensible Protocol:** The message protocol supports future UI features like syntax highlighting, progress bars, and operation cancellation.

This architecture enables a Copilot-like, interactive experience with immediate feedback and smooth agent interaction.

## Prerequisites

- Python 3.10+ installed
- VS Code 1.60+ for extension features
- Git installed
- Required packages: `sqlalchemy` with optional adapters
  - `psycopg2-binary` for PostgreSQL
  - `pymysql` for MySQL
- GitHub account and relevant tokens or app credentials

## Tree-sitter Grammar Setup

Agent-S3 uses [tree-sitter](https://tree-sitter.github.io/tree-sitter/) for code parsing in supported languages. This setup is required for all developers and CI environments running Agent-S3 with JS/PHP parsing support.

### Supported Languages
- JavaScript
- TypeScript
- PHP
- Python

### Required Packages

```bash
# Install the core tree-sitter library (minimum version 0.22.0)
pip install --upgrade tree-sitter>=0.22.0

# Install language-specific packages
pip install tree-sitter-python tree-sitter-javascript tree-sitter-php tree-sitter-typescript
```

### Implementation Approach

Agent-S3 uses the direct capsule-based API for each language parser:

```python
# JavaScript Parser
from tree_sitter import Language, Parser
import tree_sitter_javascript

js_grammar = Language(tree_sitter_javascript.language())
parser = Parser()
parser.set_language(js_grammar)

# PHP Parser
import tree_sitter_php
php_grammar = Language(tree_sitter_php.language())
parser = Parser()
parser.set_language(php_grammar)

# TypeScript Parser
import tree_sitter_typescript
ts_grammar = Language(tree_sitter_typescript.language_typescript())
parser = Parser()
parser.set_language(ts_grammar)

# Python Parser
import tree_sitter_python
python_grammar = Language(tree_sitter_python.language())
parser = Parser()
parser.set_language(python_grammar)
```

### Testing

To verify the parser implementations are working correctly:

```zsh
pytest tests/tools/parsing/ --maxfail=3 --disable-warnings -q
```

---

**Troubleshooting:**
- If you see `AttributeError: type object 'tree_sitter.Language' has no attribute 'build_library'`, ensure you are using the latest `tree_sitter` Python package.
- If you see `OSError: ... .so: file too short`, ensure the build step completed successfully and the grammar repos are not empty.

---

**Security Note:**
- Only use official tree-sitter grammars or review third-party grammars for malicious code before building.

## Installation

1. **Python package:**
   ```bash
   pip install agent-s3
   ```

   For development from source, Agent-S3 uses PEP 621 metadata defined in
   `pyproject.toml`:
   ```bash
   pip install -e .
   pip install -r requirements.txt
   # Install development tools for linting, type checking and tests
   pip install -r requirements-dev.txt
   ```
2. **VS Code Extension:**
   - Open the `vscode` folder in VS Code
   - Press `F5` to launch the extension in Extension Development Host, or
   - Build and install the `.vsix` via `vsce package`/`Extensions: Install from VSIX...`
   - Run `npm install` in the `vscode` directory before executing `npm run lint` or `npx tsc`

## Configuration

- Create or adjust `llm.json` for model roles and endpoints
- Set environment variables or include in a `.env`:
  - **GitHub OAuth:** `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET`
  - **GitHub App:** `GITHUB_APP_ID`, `GITHUB_PRIVATE_KEY`
  - `GITHUB_ORG` (optional membership filter)
  - **GitHub Token:** `GITHUB_TOKEN` (enables automatic issue and PR creation when present)
  - `OPENROUTER_KEY` (or other LLM keys such as `OPENAI_KEY`)
  - **Token Encryption:** `AGENT_S3_ENCRYPTION_KEY` (required for GitHub token storage; the CLI fails to save tokens when unset)
  - **Scratchpad Encryption:** set `encryption_key` when `scratchpad_enable_encryption` is true. Generate the key with `Fernet.generate_key()` and provide it via `AGENT_S3_ENCRYPTION_KEY` or your config file.
  - `CLI_COMMAND_MAX_SIZE` (optional, defaults to `10000` characters)
    limits the length of `/cli` commands
  - `ALLOW_INTERACTIVE_CLARIFICATION` (optional, defaults to `True`)
    enables clarifying questions during pre-planning
  - `MAX_CLARIFICATION_ROUNDS` (optional, defaults to `3`) limits pre-planning clarification exchanges
  - `MAX_PREPLANNING_ATTEMPTS` (optional, defaults to `2`) sets the maximum number of retries when generating pre-planning data
  - `pre_planning_mode` selects `off`, `json`, or `enforced_json` workflow. See `docs/pre_planning_workflow.md` for details.
  - HTTP server settings for request/response handling
  - `AGENT_S3_HTTP_TIMEOUT` (optional, defaults to `5000`) timeout in milliseconds before the VS Code extension falls back to CLI mode (see `docs/manual_http_timeout_test.md` for a verification procedure)
  - `AGENT_S3_AUTH_TOKEN` (optional) require `Authorization: Bearer <token>` on HTTP requests; may also be set in `config.json` under `http.auth_token`
  - `TEST_WS_TOKEN` (optional, defaults to `"replace-me"`)
    authentication token for `simple-test-server.js`
  - `MAX_DESIGN_PATTERNS` (optional, defaults to `3`)
    limits how many architectural patterns a system design may use to keep
    the architecture consistent


### Encryption Key Management

Generate a key using:

```bash
python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
```

Store the value in `AGENT_S3_ENCRYPTION_KEY` or your config file. To rotate the key, generate a new value, update the configuration, and restart Agent-S3. Decrypt existing logs with the previous key before archival or re-encryption.

## Coding Guidelines

Agent-S3 can apply project‑specific coding instructions you provide in a `copilot-instructions.md` file at the repository root (under `.github/` by default). During code generation and analysis, the assistant:

- Loads and respects all instructions defined in this file
- Applies your Core Development Criteria (security, performance, code quality, accessibility) and any additional guidelines you specify
- Ignores or safely handles any instruction that would conflict with system safety policies or cause unsafe operations

Place your coding rules, best practices, and user stories in `copilot-instructions.md` to guide Agent-S3's output.

## Usage

### CLI
```bash
# Initialize workspace (creates missing config files)
python -m agent_s3.cli /init

# Show help
python -m agent_s3.cli /help

# Show current config
python -m agent_s3.cli /config

# Reload LLM config from llm.json
python -m agent_s3.cli /reload-llm-config

# Explain last LLM interaction details
python -m agent_s3.cli /explain

# Generate a development plan only
python -m agent_s3.cli /plan "Add login feature"

# Generate plan and execute request
python -m agent_s3.cli /request "Your feature request"

# Start a design conversation
python -m agent_s3.cli /design "Design a scalable e-commerce system"

# Run auto-approved design
python -m agent_s3.cli /design-auto "Design a scalable e-commerce system"

# Execute bash command bypassing LLM
python -m agent_s3.cli /cli bash "echo Hello"
# Simplified bash execution
python -m agent_s3.cli /cli "ls -la"

# Execute a terminal command directly
python -m agent_s3.cli /terminal "ls -la"

# Edit file bypassing LLM
python -m agent_s3.cli /cli file path/to/file.txt "new content"

# Multi-line bash command with heredoc syntax
python -m agent_s3.cli /cli bash <<EOT
echo "Line 1"
echo "Line 2"
EOT

# Multi-line file content with heredoc syntax
python -m agent_s3.cli /cli file path/to/script.sh <<EOF
#!/bin/bash
echo "Hello from script"
EOF


# Create default copilot-instructions.md
python -m agent_s3.cli /guidelines

# List active tasks that can be resumed
python -m agent_s3.cli /tasks

# Resume a specific task
python -m agent_s3.cli /continue <task_id>

# Attempt to resume the last interrupted task
python -m agent_s3.cli /continue

# Run tests
python -m agent_s3.cli /test

# Debug the last failing test
python -m agent_s3.cli /debug

# Process a full change request (plan, generate, execute)
python -m agent_s3.cli "Implement user authentication using JWT"

# Database operations
python -m agent_s3.cli /db list
python -m agent_s3.cli /db schema
python -m agent_s3.cli /db query <db_name> "SELECT * FROM users"

# Deploy using a design file
python -m agent_s3.cli /deploy design.txt

# Clear state for a task
python -m agent_s3.cli /clear <task_id>
```
### VS Code
- **Initialize:** `Agent-S3: Initialize workspace`
- **Make change:** `Agent-S3: Make change request` or click status bar
- **Show help, config, reload, explain:** corresponding commands in palette
- **Chat UI:** `Agent-S3: Open Chat Window` (input only; follow terminal prompts)

## Development

Install the development requirements first:

```bash
pip install -r requirements-dev.txt
```

- **Tests:** `pytest`
- **Type Checking:** `mypy agent_s3`
- **Linting:** `ruff check agent_s3`
- **Test HTTP server:** Available at `http://localhost:8081`

## Contributing

Contributions welcome! Please:
- Ensure tests pass and lint/type checks are clean
- Follow PEP 8 and the core criteria in `.github/copilot-instructions.md`
- Review [docs/development_guidelines.md](docs/development_guidelines.md) for additional coding rules
- Use [Conventional Commits](CONTRIBUTING.md#commit-messages) for commit messages

## License

MIT License. See `LICENSE` or `pyproject.toml` for details.

## Additional Documentation

Detailed development and testing guidance can be found in
[docs/development_guidelines.md](docs/development_guidelines.md). Information on
debugging and error handling resides in
[docs/debugging_and_error_handling.md](docs/debugging_and_error_handling.md).

## Static Plan Checker

The Static Plan Checker is a critical validation component that ensures Pre-Planner outputs are structurally sound and logically consistent before they reach the Planner phase. This validation happens in milliseconds with zero token consumption.

### Key Benefits
- **Fast & Token-Free**: All checks run in milliseconds without consuming any LLM tokens
- **Early Error Detection**: Catches structural and logical issues before they reach expensive LLM phases
- **CI Integration**: Generates JUnit XML reports for CI/CD pipeline integration
- **GitHub Annotations**: Creates annotation-compatible output for PR reviews

### Validation Checks
The Static Plan Checker performs several deterministic checks:

| Check category          | Purpose                                                                                                |
| ----------------------- | ------------------------------------------------------------------------------------------------------ |
| **Schema & types**      | Ensures all objects match the JSON schema (arrays, enums, required keys) with proper types             |
| **Identifier hygiene**  | Verifies IDs are unique and function names follow naming conventions and aren't reserved keywords      |
| **Path validity**       | Confirms file paths refer to existing files or are clearly marked as new files to be created           |
| **Token budget**        | Checks that feature token estimates don't exceed complexity-based budgets                              |
| **Duplicate symbols**   | Ensures no function/route/environment key is defined in multiple features                              |
| **Reserved prefixes**   | Validates environment variables follow conventions (uppercase) and don't override system variables      |
| **Stub/test coherence** | Confirms every stub function has corresponding test coverage                                           |
| **Complexity sanity**   | Verifies complexity levels correlate logically with token estimates                                    |
| **Test-Risk alignment** | Validates tests include required types, keywords, and libraries based on risk assessment characteristics |

### Integration
The Static Plan Checker is integrated into the workflow between the Pre-Planner and Planner phases:

```
Pre‑Planner ──> Static Plan Checker ──> Planner
                 ▲
   fail-fast:    └─ fix or retry
```

When validation fails, the Pre-Planner may be retried or a human can intervene to fix issues before proceeding to the Planner phase.

### Implementation Details
- Uses standard Python libraries (`jsonschema`, regex, `glob`) for maximum portability
- Optionally produces JUnit XML output for CI/CD integration
- Can be extended with additional custom validation rules
- Error messages include enough context to identify and fix issues

### Test Coverage vs. Risk Assessment
The Static Plan Checker includes an enhanced validation of test coverage against risk assessment through the `validate_test_coverage_against_risk` function in `phase_validator.py`. This validation ensures that:

1. **Critical Files Coverage**: All files marked as "critical" in the risk assessment have associated tests
2. **High-Risk Areas Coverage**: All high-risk areas identified in the risk assessment have adequate test coverage
3. **Test Types Alignment**: Required test types match the risk profile (e.g., property-based for edge cases, acceptance tests for component interactions)
4. **Risk-Specific Test Characteristics**: Tests meet the specific characteristics required by the risk assessment:
   - **Required Test Types**: Verifies that all required test types (e.g., security, performance) are included
   - **Required Keywords**: Ensures test names, descriptions, or code contain required keywords (e.g., "injection", "unauthorized", "benchmark")
   - **Suggested Libraries**: Checks that the suggested testing libraries are used in the appropriate tests

The validation provides detailed reporting on missing test characteristics, enabling developers to pinpoint exactly which risk mitigation strategies are not adequately covered by tests.
