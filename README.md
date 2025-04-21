# Agent-S3

State-of-the-art AI coding agent integrated with VS Code and GitHub. Agent-S3 assists developers by planning code changes, generating code, tracking progress via GitHub issues, and integrating seamlessly into the VS Code environment.

## Core Features

**Python Backend (`agent_s3`):**

*   **CLI Interface:** Provides `agent_s3.cli` for commands (`/init`, `/help`, `/guidelines`) and processing change requests.
*   **GitHub Authentication:** Supports user authentication via GitHub OAuth and GitHub App integration for secure API access and organization checks (`agent_s3.auth`).
*   **Configuration Management:** Loads settings from environment variables (`GITHUB_*`, `OPENROUTER_KEY`, etc.) and configuration files (`llm.json`) (`agent_s3.config`).
*   **Task Orchestration:** `Coordinator` manages the end-to-end workflow: planning, code generation, tool execution, and progress tracking (`agent_s3.coordinator`).
*   **LLM Routing:** `RouterAgent` intelligently selects appropriate Language Models (LLMs) for different tasks based on `llm.json` configuration (`agent_s3.router_agent`). Includes circuit breaking and dynamic config reloading.
*   **Planning & Code Generation:** Dedicated modules for planning change requests (`agent_s3.planner`) and generating code using LLMs (`agent_s3.code_generator`) with fallback mechanisms.
*   **Extensible Tool System:** Includes tools for:
    *   Secure file operations (`FileTool`) with path validation and restrictions.
    *   Secure shell command execution (`BashTool`, `TerminalExecutor`) with sandboxing and denylists.
    *   Git operations and GitHub API interaction (issues, PRs, repo info, rate limiting) (`GitTool`).
    *   Code analysis, linting, and embedding-based search (`CodeAnalysisTool`, `EmbeddingClient` using FAISS).
    *   Technology stack detection (`TechStackManager`).
    *   Context/memory management (`MemoryManager`) with hierarchical summarization.
    *   Database interactions (`DatabaseTool`).
*   **Progress & Logging:** Tracks workflow status in `progress_log.json` (`ProgressTracker`) and detailed internal logs in `scratchpad.txt` (`ScratchpadManager`).
*   **Prompt Moderation:** Interactive approval steps for plans and actions (`agent_s3.prompt_moderator`).

**VS Code Extension (`vscode`):**

*   **Command Palette Integration:** Registers commands like `Agent-S3: Initialize workspace`, `Agent-S3: Make change request`, `Agent-S3: Show help`, `Agent-S3: Open Chat Window`.
*   **CLI Bridge:** Executes Python backend commands (`agent_s3.cli`) within a dedicated VS Code terminal.
*   **Workspace Initialization:** Command (`/init`) to set up Agent-S3 within the current VS Code workspace.
*   **Status Bar Item:** Provides quick access (`$(sparkle) Agent-S3`) to make change requests.
*   **Real-time Progress Monitoring:** Monitors `progress_log.json` to display live status updates and notifications in the VS Code UI.
*   **Chat UI:** Offers a dedicated WebviewPanel for a Copilot-style chat experience, interacting with the backend CLI (uses `postMessage` for communication).

## Tech Stack

*   **Backend:** Python (>=3.10)
*   **Frontend (VS Code Ext):** TypeScript
*   **Key Python Libraries:**
    *   `requests`: HTTP requests for APIs.
    *   `PyGithub`: GitHub API interactions.
    *   `PyJWT`: JWT generation for GitHub Apps.
    *   `faiss-cpu`: Vector similarity search for RAG.
    *   `openai`: Interacting with OpenAI/OpenRouter compatible APIs.
    *   `tiktoken`: Token counting for LLMs.
    *   `toml`: Parsing `pyproject.toml`.
    *   `flake8`, `ruff`, `mypy`, `radon`: Code quality and analysis.
    *   `pytest`: Testing framework.
*   **Key VS Code Ext Libraries:**
    *   `@types/vscode`: VS Code API typings.
    *   `eslint`, `@typescript-eslint/parser`, `@typescript-eslint/eslint-plugin`: Linting.
*   **Tools:** Git, Docker (implied for potential containerization), GitHub Actions (detected).

## Prerequisites

*   Python 3.10 or higher.
*   Git installed.
*   A GitHub account.
*   VS Code (version ^1.60.0 or higher).
*   API keys/credentials for GitHub and desired LLM providers (e.g., OpenRouter).

## Installation

1.  **Clone the repository (optional, for development):**
    ```bash
    git clone https://github.com/agent-s3/agent-s3.git
    cd agent-s3
    ```
2.  **Install Python dependencies:**
    *   From PyPI (recommended for users):
        ```bash
        pip install agent-s3
        ```
    *   From source (for development):
        ```bash
        pip install -r requirements.txt
        # or for editable install
        pip install -e .
        ```
3.  **Install the VS Code Extension:**
    *   Open the `vscode` directory in VS Code.
    *   Press `F5` to run the extension in a new Extension Development Host window, OR
    *   Build the extension (`vsce package`) and install the `.vsix` file manually.

## Configuration

Agent-S3 relies on environment variables for sensitive keys and configuration:

*   **GitHub Authentication:**
    *   **OAuth App:** Set `GITHUB_CLIENT_ID` and `GITHUB_CLIENT_SECRET` for user authentication flow.
    *   **GitHub App:** Set `GITHUB_APP_ID` and `GITHUB_PRIVATE_KEY` (file path or content) for application-level API access.
    *   `GITHUB_ORG`: (Optional) Comma-separated list of allowed GitHub organizations.
*   **LLM Provider:**
    *   `OPENROUTER_KEY`: API key for OpenRouter (or configure specific keys in `llm.json`).
*   **Development:**
    *   `DEV_GITHUB_TOKEN`: (Optional) A personal access token for development purposes.
    *   `DEV_MODE`: Set to `true` to enable development features.
*   **Security:**
    *   `DENYLIST_COMMANDS`: Comma-separated list of shell commands to block (defaults to `rm,shutdown,reboot`).
    *   `COMMAND_TIMEOUT`: Timeout for shell commands in seconds (defaults to `30.0`).

Configuration for LLM models (endpoints, roles, parameters) is managed in `llm.json`.

## Usage

**1. Initialize Workspace (First Time):**

*   **VS Code:** Open the Command Palette (`Ctrl+Shift+P` or `Cmd+Shift+P`) and run `Agent-S3: Initialize workspace`. This runs `python -m agent_s3.cli /init`.
*   **CLI:**
    ```bash
    python -m agent_s3.cli /init
    ```
    Follow the prompts to authenticate with GitHub if required.

**2. Make a Change Request:**

*   **VS Code:**
    *   Click the `$(sparkle) Agent-S3` status bar item.
    *   OR: Run `Agent-S3: Make change request` from the Command Palette.
    *   Enter your request in the input box.
*   **CLI:**
    ```bash
    python -m agent_s3.cli "Your detailed change request here"
    ```
*   **Chat UI (VS Code):**
    *   Run `Agent-S3: Open Chat Window` from the Command Palette.
    *   Type your request in the chat input and press Enter or click Send.

**3. Review and Approve:**

*   Agent-S3 will present a plan in the terminal (or chat UI).
*   You may be prompted to approve the plan and the creation of a GitHub issue using `PromptModerator`.

**4. Monitor Progress:**

*   **VS Code:** Progress notifications will appear. Check the dedicated "Agent-S3" terminal for detailed output.
*   **Logs:** Check `scratchpad.txt` (detailed thoughts) and `progress_log.json` (structured status).

**Other Commands:**

*   `Agent-S3: Show help` / `python -m agent_s3.cli /help`: Display help.
*   `Agent-S3: Show coding guidelines` / `python -m agent_s3.cli /guidelines`: Show loaded guidelines.
*   `python -m agent_s3.cli /reload-llm-config`: Reload `llm.json` dynamically.

## Testing

The project uses `pytest` for testing.

1.  Ensure development dependencies are installed (`pip install -r requirements.txt` or `pip install -e .[test]`).
2.  Run tests from the root directory:
    ```bash
    pytest
    ```
3.  Run specific tests:
    ```bash
    pytest tests/test_planner.py::TestPlanner::test_some_function
    ```
4.  Run type checking:
    ```bash
    mypy agent_s3/
    ```
5.  Run linting:
    ```bash
    ruff check agent_s3/
    ```

## Contributing

Contributions are welcome!

*   **Bug Reports & Feature Requests:** Please submit issues via the [GitHub Issue Tracker](https://github.com/agent-s3/agent-s3/issues).
*   **Code Style:** Follow PEP 8 guidelines. Use `ruff` for formatting/linting and `mypy` for type checking (configurations are in `pyproject.toml`).
*   **Pull Requests:** Please ensure tests pass (`pytest`) and linting/type checks are clean before submitting a PR.

## License

This project is licensed under the MIT License. See the `LICENSE` file (if present) or `pyproject.toml` for details.