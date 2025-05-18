# Agent-S3 User Stories & Walkthroughs

This document outlines common user scenarios and provides step-by-step walkthroughs for interacting with Agent-S3, based on the actual implementation in the `agent_s3` Python package and the `vscode` extension.

Together with `README.md`, this file constitutes the canonical documentation for
Agent-S3. Refer to both documents for a complete understanding of the project.

## Story 1: Initializing Agent-S3 in a New Workspace

**Goal:** Set up Agent-S3 for the first time in a project workspace and authenticate with GitHub.

**Persona:** A developer starting to use Agent-S3 on their project.

**Walkthrough:**

1.  **Open Project:** The developer opens their project folder in VS Code.
2.  **Trigger Initialization:**
    *   **Via Command Palette:** The developer presses `Ctrl+Shift+P` (or `Cmd+Shift+P`), types `Agent-S3: Initialize workspace`, and selects the command.
    *   **Via CLI:** The developer opens a terminal and runs:
        ```bash
        python -m agent_s3.cli /init
        ```
3.  **VS Code Extension Action (`vscode/extension.ts`):**
    *   The `initializeWorkspace` function is triggered.
    *   It retrieves or creates the dedicated "Agent-S3" terminal using `getAgentTerminal`.
    *   It shows the terminal (`terminal.show()`).
    *   It sends the command `python -m agent_s3.cli /init` to the terminal (`terminal.sendText`).
    *   A notification "Initializing Agent-S3 workspace..." appears (`vscode.window.showInformationMessage`).
    *   A timeout is set to update the internal `isInitialized` flag after a delay (this is a simple check, the CLI process confirms actual success).
4.  **Backend CLI Action (`agent_s3/cli.py`):**
    *   The `main` function parses arguments and identifies the `/init` command.
    *   It calls `process_command`.
    *   `process_command` initializes the `Coordinator` (`agent_s3/coordinator.py`).
    *   It calls `coordinator.initialize_workspace()`.
5.  **Coordinator Initialization (`agent_s3/coordinator.py`):**
    *   The `initialize_workspace` method is executed.
    *   It loads configuration using `Config` (`agent_s3/config.py`), which reads environment variables and `llm.json`.
    *   It sets up essential directories and performs workspace validation checks:
        *   Checks for existence of README.md (core validation requirement)
        *   Creates required directories like .github if they don't exist
        *   Logs validation status and errors via EnhancedScratchpadManager
    *   It creates essential files if missing:
        *   Creates personas.md via `execute_personas_command()` if it doesn't exist
        *   Creates .github/copilot-instructions.md via `execute_guidelines_command()` if missing
        *   Creates llm.json with default LLM configuration if not present
    *   It detects the tech stack via `_detect_tech_stack()` which:
        *   Uses TechStackManager to analyze the codebase
        *   Identifies languages, frameworks, libraries and their versions
        *   Generates structured tech stack data with best practices
        *   Logs formatted tech stack information to scratchpad
6.  **GitHub Authentication Flow (`agent_s3/auth.py`, if needed):**
    *   If authentication is required and no valid token is found (checked via `check_github_auth`), `auth.authenticate_user()` is called by the `Coordinator`.
    *   `authenticate_user` determines the flow (OAuth App or GitHub App based on config).
    *   **OAuth App Flow:**
        *   Constructs a GitHub OAuth URL (`GITHUB_AUTH_URL`) with `GITHUB_CLIENT_ID`, scope, and a unique `state`.
        *   Starts a local HTTP server (`http.server.HTTPServer`) on `localhost:8000` with a `CallbackHandler`.
        *   Opens the user's web browser to the GitHub authorization URL (`webbrowser.open`).
        *   User logs into GitHub and authorizes the application.
        *   GitHub redirects the browser back to `http://localhost:8000/callback` with an authorization `code` and the `state`.
        *   The `CallbackHandler`'s `do_GET` method receives the request, validates the `state`.
        *   It exchanges the `code` for an access token by making a POST request to `GITHUB_TOKEN_URL` using `requests.post`, sending `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET`, `code`, and `redirect_uri`.
        *   The obtained access token is stored securely using `store_token` (e.g., in `~/.agent_s3/github_token.json`).
        *   The local server shuts down (`httpd.shutdown()`), and the browser might show a success message.
    *   **GitHub App Flow:** (Details depend on specific implementation, but generally involves JWT generation and installation access tokens).
7.  **Organization Check (`agent_s3/auth.py`, if configured):**
    *   If `GITHUB_ORG` is set in the environment, `auth.verify_organization_membership()` is called after obtaining the token.
    *   It uses the token to make a request to the GitHub API (`/user/memberships/orgs`) via `requests.get`.
    *   It checks if the user is a member of any specified organization. If not, authentication fails, and an error is raised.
8.  **AI-Generated Guidelines (Optional, `agent_s3/coordinator.py`):**
    *   If enabled and `copilot-instructions.md` exists, `initialize_workspace` might call `_call_llm_api` (using the 'initializer' role LLM) to generate tech-stack-specific guidelines.
    *   It uses `PromptModerator` (`agent_s3/prompt_moderator.py`) to ask the user if they want to append these suggestions (`prompt_moderator.ask_binary_question`).
    *   If approved, it uses `FileTool` (`agent_s3/tools/file_tool.py`) to append the content (`file_tool.append_to_file`).
9.  **Initialization Complete:**
    *   The CLI prints a confirmation message.
    *   The `Coordinator` finishes.
    *   The VS Code extension's `isInitialized` flag (set via timeout earlier) allows subsequent commands.

**Outcome:** Agent-S3 is ready to use in the workspace. The user is authenticated with GitHub (if required), necessary configuration/guideline files are verified or created, and the tech stack is detected. Subsequent commands requiring GitHub access will use the stored token.

---

## Story 2: Making a Code Change Request

**Goal:** Request a code modification using various VS Code UI elements or the CLI.

**Persona:** A developer wanting to add a feature, fix a bug, or refactor code.

**Walkthrough:**

1.  **Trigger Command:**
    *   **VS Code Command Palette:** Press `Ctrl+Shift+P`, type `Agent-S3: Make change request`, select command.
    *   **VS Code Status Bar:** Click the `$(sparkle) Agent-S3` item.
    *   **VS Code Chat UI:** Open via `Agent-S3: Open Chat Window`, type request, press Send/Enter. (See Story 3 for Chat UI details).
    *   **CLI:** Open terminal, run `python -m agent_s3.cli "Your detailed change request here"`.
2.  **VS Code Extension Action (`vscode/extension.ts` - for UI triggers):**
    *   The `makeChangeRequest` function (or the status bar command handler, or the chat message handler `panel.webview.onDidReceiveMessage`) is called.
    *   It checks the `isInitialized` flag. If `false`, it prompts the user to initialize first (`vscode.window.showWarningMessage`, potentially calling `initializeWorkspace`).
    *   If triggered via Command Palette or Status Bar, it shows an input box (`vscode.window.showInputBox`) prompting "Enter your change request".
    *   It retrieves the dedicated "Agent-S3" terminal using `getAgentTerminal`.
    *   It shows the terminal (`terminal.show()`).
    *   It sends the developer's request (from input box or chat message) to the CLI, escaping quotes: `python -m agent_s3.cli "<user_request>"` (`terminal.sendText`).
    *   It shows an information notification: `Processing request: <user_request>` (`vscode.window.showInformationMessage`).
    *   It opens a `BackendConnection` to stream progress updates via WebSocket.
3.  **Backend CLI Action (`agent_s3/cli.py`):**
    *   The `main` function parses the command-line arguments, receiving the request text.
    *   It loads the configuration (`Config`).
    *   It initializes the `Coordinator` (`agent_s3/coordinator.py`).
    *   It performs an authentication check and initializes the `RouterAgent`.
    *   **Important:** It routes the request through an orchestrator that classifies the input:
        *   First calls the LLM with an orchestrator role to classify the request as planner, designer, tool_user, or general_qa.
        *   If classification confidence is below 0.7, it asks the user to clarify the intent.
        *   Based on classification, it routes to the appropriate method - most code change requests go to `coordinator.process_change_request`.
4.  **Coordinator Workflow (`agent_s3/coordinator.py` - `run_task` method):**
    *   **Phase 0: Pre-Planning Assessment:**
        *   Updates progress: `{"phase": "pre_planning", "status": "started"}`.
        *   Uses `pre_planner_json_enforced.pre_planning_workflow` to analyze the request and generate structured feature groups.
        *   Validates the pre-planner output with Static Plan Checker (`plan_validator.validate_pre_plan`).
        *   Saves a checkpoint of the pre-planning data for version tracking.
        *   Checks for task complexity (either `is_complex` flag or complexity_score > 7).
        *   If complex, presents warning to user with explicit confirmation options (yes/modify/no).
    *   **Pre-Planning Review:**
        *   Presents pre-planning results to user for review.
        *   User can accept (yes), reject (no), or modify the pre-planning results.
        *   If user chooses to modify, system calls `_regenerate_pre_planning_with_modifications` to update pre-planning with user feedback.
        *   Saves modification checkpoint and continues when user approves.
    *   **Feature Group Processing:**
        *   Updates progress: `{"phase": "feature_group_processing", "status": "started"}`.
        *   Calls `feature_group_processor.process_pre_planning_output` to process each feature group.
        *   For each feature group:
            *   Generates architecture review for the feature group
            *   Creates implementation plan based on architecture review and feature group
            *   Generates tests for the implementation plan
            *   Runs test critic to analyze test quality and coverage
            *   Performs cross-phase validation across architecture, implementation, and tests
            *   Creates consolidated plan that combines all components
            *   Performs semantic validation for logical coherence
            *   Presents the consolidated plan to the user for review
        *   User can accept (yes), reject (no), or modify the consolidated plan.
        *   If user chooses to modify, applies modifications to architecture review and performs comprehensive re-validation.
        *   Automatically saves plan file with unique ID for reference.
    *   **Code Generation and Refinement:**
        *   Multiple attempts may be made (configured via `max_attempts`, default 3).
        *   For each attempt:
            *   Updates progress: `{"phase": "generation", "status": "started", "attempt": attempt}`.
            *   Calls `code_generator.generate_code(request_text, plan)` to create code changes.
            *   Applies changes using `_apply_changes_and_manage_dependencies`.
            *   Runs validation via `_run_validation_phase()` which includes:
                *   Linting with tools like flake8
                *   Type checking with mypy
                *   Running tests with test_runner_tool
                *   Verifying test coverage with TestCritic
            *   If validation fails, collects error context and refines the plan.
            *   If validation passes, breaks the loop.
    *   **Finalization:**
        *   If changes were successfully made and validated, calls `_finalize_task(changes)` which:
            *   Commits changes with a descriptive message
            *   Pushes the branch if configured to do so
            *   Creates a pull request if configured
            *   Includes database schema metadata in PR descriptions when database changes are involved
        *   Clears the task state and reports completion.
5.  **VS Code Monitoring (`vscode/extension.ts`):**
    *   Progress updates stream through `BackendConnection` via WebSocket, eliminating the file watcher.
    *   Updates the status bar with current phase and status.
    *   When a final state is reached, shows a notification with result summary.
    *   If a PR was created, includes the PR URL in the notification.

**Outcome:** The requested code change is evaluated for complexity, broken down into feature groups, and each group is reviewed by the user with a comprehensive view of implementation, architecture, and tests. After approval, the system generates and validates code, ensuring high-quality changes that meet requirements. The process includes multiple validation phases, automatic re-validation after modifications, and comprehensive coverage testing to deliver robust implementations.

---

## Story 3: Interacting via the Chat UI

**Goal:** Use the dedicated chat window in VS Code to make requests and interact with Agent-S3.

**Persona:** A developer preferring a conversational interface.

**Walkthrough:**

1.  **Open Chat Window:** The developer runs `Agent-S3: Open Chat Window` from the Command Palette.
2.  **VS Code Extension Action (`vscode/extension.ts`):**
    *   The `openChatWindow` function creates a `WebviewPanel`.
    *   It generates a `nonce` for Content Security Policy (CSP).
    *   It loads previous message history from `extensionContext.workspaceState.get('agent-s3.chatHistory', [])`.
    *   It sets the webview's HTML content using `getWebviewContent(nonce)`. This function generates the HTML structure, CSS for styling (respecting VS Code themes), and the client-side JavaScript. CSP is configured via `<meta>` tag. ARIA roles (`role="log"`, `aria-live="polite"`) are included for accessibility.
    *   It sets up a message listener (`panel.webview.onDidReceiveMessage`) to handle messages sent *from* the webview JavaScript to the extension.
    *   It registers a disposal handler (`panel.onDidDispose`) to save the final chat history when the panel is closed.
3.  **Webview Loads:**
    *   The chat panel appears in VS Code (typically beside the editor).
    *   The webview's JavaScript initializes.
    *   It acquires the VS Code API bridge using `acquireVsCodeApi()`.
    *   It sends a 'ready' message to the extension: `vscode.postMessage({ command: 'ready' })`.
4.  **Extension Sends History:**
    *   The `panel.webview.onDidReceiveMessage` listener in `extension.ts` receives the 'ready' message.
    *   It sends the loaded `messageHistory` back to the webview: `panel.webview.postMessage({ command: 'loadHistory', history: messageHistory })`.
5.  **Webview Renders History:**
    *   The `window.addEventListener('message', ...)` listener in the webview JS receives the 'loadHistory' message.
    *   It iterates through the history array and calls `addMessageToUI(message)` for each message to render them in the `#messages` div. `addMessageToUI` creates DOM elements for the message bubble, content, and timestamp, applying appropriate CSS classes (`user`, `agent`, `system`).
6.  **User Sends Message:**
    *   The developer types a request (e.g., "/help" or "Refactor the login function") into the textarea (`#msg`) and clicks the Send button (`#send`) or presses Enter (handler in webview JS `input.addEventListener('keydown', ...)`).
7.  **Webview JavaScript Action (`getWebviewContent` script):**
    *   The `sendMessage` function is called.
    *   It gets the text from the input (`input.value`).
    *   It calls `addMessageToUI` to immediately display the user's message in the chat window.
    *   It clears the input field (`input.value = ''`).
    *   It sends the message content to the VS Code extension: `vscode.postMessage({ command: 'send', text: <user_text> })`.
    *   It might show a temporary typing indicator (`showTypingIndicator`).
8.  **VS Code Extension Receives Message (`vscode/extension.ts`):**
    *   The `panel.webview.onDidReceiveMessage` listener receives the message with `command: 'send'`.
    *   It creates a message object `{ type: 'user', content: msg.text, timestamp: ... }`.
    *   It appends this message to the `messageHistory` array (potentially trimming old messages).
    *   It saves the updated `messageHistory` to workspace state: `extensionContext.workspaceState.update('agent-s3.chatHistory', messageHistory)`.
    *   It gets the "Agent-S3" terminal (`getAgentTerminal`).
    *   It shows the terminal (`term.show(true)`).
    *   It sends the user's text to the CLI, escaping quotes: `term.sendText(\`python -m agent_s3.cli "${safe_text}"\`)`.
9.  **Backend Processing:**
    *   The CLI (`agent_s3/cli.py`) receives and processes the command or request exactly as described in Story 1 (for `/` commands like `/init`, `/help`, `/guidelines`) or Story 2 (for change requests).
    *   **Crucially, all interactive output from the backend (plans, persona debates, approval prompts, diffs, results) appears in the "Agent-S3" terminal, NOT directly in the chat UI bubbles.**
10. **Chat UI Feedback (Simulated/Limited):**
    *   The current webview JS in `getWebviewContent` includes a `setTimeout` within `sendMessage` that *simulates* an agent response after a delay (calling `removeTypingIndicator` and `addMessageToUI` with placeholder content).
    *   **Note:** This is **not** connected to the actual backend output. The chat UI primarily serves as a convenient input method and history viewer. The user **must** monitor the "Agent-S3" terminal for the real interaction flow and agent output.

**Outcome:** The user can initiate Agent-S3 commands and requests via the chat interface, and the conversation history is saved. However, the actual detailed interaction (planning, approvals, code diffs, results) occurs in the associated "Agent-S3" terminal, which the user needs to monitor.

---

## Story 4: Using Helper Commands

**Goal:** Get help information or view loaded coding guidelines using specific commands.

**Persona:** A developer needing information about Agent-S3 commands or project standards.

**Walkthrough (using `/help`):**

1.  **Trigger Command:**
    *   **VS Code Command Palette:** Run `Agent-S3: Show help`.
    *   **CLI:** Run `python -m agent_s3.cli /help` in the terminal.
    *   **Chat UI:** Type `/help` and send (See Story 3).
2.  **VS Code Extension Action (`vscode/extension.ts`, if applicable):**
    *   The `showHelp` function (or the chat message handler) is called.
    *   It gets the terminal (`getAgentTerminal`).
    *   It shows the terminal (`terminal.show()`).
    *   It sends the command `python -m agent_s3.cli /help` to the terminal (`terminal.sendText`).
3.  **Backend CLI Action (`agent_s3/cli.py`):**
    *   `main` parses arguments and identifies `/help`.
    *   `process_command` handles it.
    *   It likely calls a dedicated function like `display_help()` (implementation details may vary) which prints pre-defined help text to standard output.
4.  **Output:** The help text is displayed directly in the "Agent-S3" terminal where the command was executed.

**Walkthrough (using `/config`):**

1.  **Trigger Command:**
    *   **VS Code Command Palette:** Run `Agent-S3: Show current configuration`.
    *   **CLI:** Run `python -m agent_s3.cli /config` in the terminal.
    *   **Chat UI:** Type `/config` and send (See Story 3).
2.  **Backend CLI Action (`agent_s3/cli.py`):**
    *   `main` parses arguments and identifies `/config`.
    *   `process_command` handles it and prints "Current configuration:".
    *   It iterates over `coordinator.config.config` and prints each key/value pair, masking sensitive values for `openrouter_key`, `github_token`, and `api_key`.
3.  **Output:** The current configuration settings are displayed in the "Agent-S3" terminal, with sensitive values masked.

**Walkthrough (using `/explain`):**

1.  **Trigger Command:**
    *   **CLI:** Run `python -m agent_s3.cli /explain` in the terminal.
    *   **Chat UI:** Type `/explain` and send (See Story 3).
2.  **Backend CLI Action (`agent_s3/cli.py`):**
    *   `main` parses arguments and identifies `/explain`.
    *   `process_command` handles it and prints "Explaining the last LLM interaction with context...".
    *   It initializes the `Coordinator`.
    *   It gathers context via `coordinator._gather_context()` to provide tech stack and code snippets for better explanation context.
    *   It calls `coordinator.explain_last_llm_interaction(context)`, passing in the gathered context.
3.  **Explanation Content (Enhanced with Tech Stack and Code Context):**
    *   The `role` (model identifier used, e.g., "gemini-2.5-pro" or "mistral-7b-instruct") is shown.
    *   The `status` of the interaction (e.g., "success", "error", "fallback_success") is shown.
    *   The `timestamp` of when the interaction occurred is displayed.
    *   A truncated version of the `prompt` sent to the LLM is displayed, including code context that was provided.
    *   A truncated version of the `response` received from the LLM is displayed.
    *   If relevant, tech stack information is shown to clarify what technologies were considered.
    *   If the interaction failed, the error message is displayed along with debugging suggestions.
4.  **Implementation Details:**
    *   The enhanced scratchpad manager (`EnhancedScratchpadManager`) captures detailed LLM interaction logs.
    *   The system has a circuit breaker pattern implemented in `RouterAgent`, which can trigger fallbacks to alternative models if a primary model fails.
    *   The explanation includes information about any token estimation and potential truncation that may have occurred.
    *   The system can show confidence scores for classifications if they were part of the LLM call.
    *   In the case of orchestrator calls, information about the routing decision is also included.
5.  **Output:** The formatted explanation of the last LLM interaction including tech context is displayed in the "Agent-S3" terminal, providing a comprehensive view of how the LLM made its decision.

**Walkthrough (using `/reload-llm-config`):**

1.  **Trigger Command:**
    *   **CLI:** Run `python -m agent_s3.cli /reload-llm-config` in the terminal.
    *   **Chat UI:** Type `/reload-llm-config` and send (See Story 3).
2.  **Backend CLI Action (`agent_s3/cli.py`):**
    *   `main` parses arguments and identifies `/reload-llm-config`.
    *   `process_command` handles it.
    *   It attempts to import `RouterAgent` (`agent_s3/router_agent.py`).
    *   It creates an instance of `RouterAgent`.
    *   It calls `router.reload_config()`.
3.  **Router Agent Action (`agent_s3/router_agent.py`):**
    *   The `reload_config` method calls the internal `_load_llm_config()` function.
    *   `_load_llm_config()` re-reads and parses `llm.json`.
    *   It validates the structure of each entry.
    *   It rebuilds the internal `_models_by_role` dictionary.
    *   `reload_config` then clears the circuit breaker state (`_failure_counts`, `_last_failure_time`).
4.  **Output:** The CLI prints "LLM configuration reloaded successfully." or an error message if reloading failed (e.g., file not found, JSON invalid).

**Outcome:** The `RouterAgent`'s model configuration is updated based on the current `llm.json` without restarting the application. Circuit breaker states are reset.

---

## Story 5: Processing a Full Change Request (`/request`)

**Goal:** Process a full change request with planning, code generation, and execution.

**Persona:** A developer wanting to implement a feature or make code changes.

**Walkthrough:**

1.  **Trigger Command:**
    *   **CLI:** Run `python -m agent_s3.cli /request "Your detailed feature request here"`.
    *   **Chat UI:** Type `/request Add user profile page` and send (See Story 3).
2.  **Backend CLI Action (`agent_s3/cli.py`):**
    *   `main` parses arguments and identifies the command starting with `/request`.
    *   It extracts the request text following the command.
    *   It calls `process_command`.
    *   `process_command` initializes the `Coordinator`.
    *   It calls `coordinator.process_change_request(request_text)`, which is effectively mapped to `run_task` in the actual implementation.
3.  **Coordinator Action (`agent_s3/coordinator.py` - `run_task` method):**
    *   **Phase 0: Pre-Planning Assessment**
        *   Updates progress: `{"phase": "pre_planning", "status": "started"}`.
        *   Calls `pre_planner_json_enforced.pre_planning_workflow` to analyze the request with enforced JSON output.
        *   Validates output with Static Plan Checker
        *   Saves a checkpoint of the pre-planning data.
        *   Checks if task is complex and requires explicit user confirmation.
        *   If complex, presents warning to user with options to proceed, modify, or cancel.
    *   **Feature Group Processing**
        *   Updates progress: `{"phase": "feature_group_processing", "status": "started"}`.
        *   Calls `feature_group_processor.process_pre_planning_output(pre_plan_data, request_text)`.
        *   For each feature group:
            *   Generates architecture review, implementation plan, and tests.
            *   Creates a consolidated plan combining all three components.
            *   Performs semantic validation for logical coherence.
            *   Presents consolidated plan to user for review.
            *   User chooses to accept, modify, or reject the plan.
            *   If modified, performs comprehensive re-validation.
            *   Saves plan file with unique ID for reference.
    *   **Code Generation and Refinement Loop**
        *   Multiple attempts may be made (configured via `max_attempts`, default 3).
        *   For each attempt:
            *   Updates progress: `{"phase": "generation", "status": "started", "attempt": attempt}`.
            *   Calls `code_generator.generate_code(request_text, plan)` to create code changes.
            *   If generation fails, aborts with error message.
            *   Applies changes using `_apply_changes_and_manage_dependencies(changes)`.
            *   Runs validation via `_run_validation_phase()` which includes linting, type checking, and running tests.
            *   If validation fails, collects error context and refines the plan for the next attempt.
            *   If validation passes, breaks the loop.
    *   **Finalization**
        *   If changes were successfully made and validated, calls `_finalize_task(changes)`.
        *   This may involve committing changes, pushing to a branch, and creating a pull request.
        *   For database changes, includes schema metadata in PR descriptions.

**Outcome:** The developer gets a complete end-to-end implementation of their requested feature or code change, with interactive review of consolidated plans (implementation, architecture, tests) before code generation. The process involves automatic validation and multiple refinement attempts if needed, ensuring high-quality code that meets requirements.

---

## Story 6: Executing Direct CLI Commands (`/cli`)

**Goal:** Execute specific file modifications or shell commands directly, bypassing the LLM planning and generation phases.

**Persona:** A developer needing to perform a precise, known operation quickly or interact directly with the file system or shell within the agent's environment.

**Walkthrough:**

1.  **Trigger Command:**
    *   **CLI (Bash):** `python -m agent_s3.cli /cli bash "git status"`
    *   **CLI (File Write):** `python -m agent_s3.cli /cli file ./new_file.txt "Hello World"`
    *   **CLI (Multi-line Bash):**
        ```bash
        python -m agent_s3.cli /cli bash "echo 'Start';\nls -l" <<EOF
        echo 'Middle Line 1'
        echo 'Middle Line 2'
        EOF
        ```
    *   **CLI (Multi-line File):**
        ```bash
        python -m agent_s3.cli /cli file ./multi.sh <<MARKER
        #!/bin/bash
        echo "This is a multi-line script."
        MARKER
        ```
    *   **Chat UI:** `/cli bash ls -la` or `/cli file notes.txt "Initial note."` (See Story 3).
2.  **Backend CLI Action (`agent_s3/cli.py`):**
    *   `main` parses arguments and identifies the command starting with `/cli`.
    *   `process_command` determines the type (`file` or `bash`) and extracts the arguments.
    *   If multi-line input syntax (`<<MARKER`) is detected, it calls `_process_multiline_cli` to read lines from standard input until the marker is found, constructing the full command arguments.
    *   It initializes the `Coordinator`.
    *   It calls `coordinator.execute_cli_command(command_type, command_args)`.
3.  **Coordinator Action (`agent_s3/coordinator.py` - `execute_cli_command` method):**
    *   Logs the start of the CLI execution.
    *   Updates progress: `{"phase": "cli_execution", "status": "started"}`.
    *   Checks if a first-time usage warning for `/cli` needs to be shown (`cli_warning` log file check) and displays it via `PromptModerator.ask_binary_question` if needed.
    *   Based on `command_type`:
        *   **If 'file':** Calls `_execute_cli_file_command(command_args)`.
            *   Parses path and content.
            *   Checks for potentially dangerous paths (`_is_dangerous_file_operation`) and asks for confirmation via `PromptModerator.ask_binary_question` if needed.
            *   Uses `FileTool.write_file` to perform the operation.
            *   Returns success status and message.
        *   **If 'bash':** Calls `_execute_cli_bash_command(command_args)`.
            *   Checks for potentially dangerous command patterns (`_is_dangerous_bash_operation`) and asks for confirmation via `PromptModerator.ask_binary_question` if needed.
            *   Uses `BashTool.run_command` (which respects sandboxing config) to execute the command.
            *   Returns success status and command output/error.
    *   Updates progress based on the success/failure result: `{"phase": "cli_execution", "status": "completed/failed", "error": ...}`.
    *   Notifies the user of the outcome (success message with result, or failure message with error) via `PromptModerator.notify_user`.

**Outcome:** The specified file operation or bash command is executed directly. The user sees a warning for potentially dangerous operations and must confirm. The result (output or error) is displayed in the terminal. This bypasses all LLM interaction for planning or code generation.

---

## Story 7: Viewing and Resuming Interrupted Tasks

**Goal:** Resume a previously interrupted or incomplete Agent-S3 workflow.

**Persona:** A developer who closed VS Code or the terminal before a task completed, or who wants to continue a previously started request.

**Walkthrough:**

1. **Trigger:**
   * On CLI startup, or when initializing the `Coordinator`, Agent-S3 checks for an existing `development_status.json` file.
   * Alternatively, the user can manually list tasks via `/tasks` command or attempt to resume via `/continue` command.
2. **Backend Action (`agent_s3/coordinator.py` and `agent_s3/task_resumer.py`):**
   * The `check_for_interrupted_tasks` method in `TaskResumer` reads the last entry in `development_status.json`.
   * If the last status is not `completed` and the phase is not `initialization`, it prints a message about the interrupted task, including the phase, timestamp, and original request.
   * The user is prompted: "Do you want to attempt resuming this task? (yes/no):"
   * If the user answers `yes`, the task state is loaded from the task snapshot directory:
     * Task ID, description, phase, plan, and other context is restored
     * For execution phase tasks, completed steps are tracked to avoid redoing work
     * The system positions itself at the appropriate restart point
3. **Resume Options:**
   * **Pre-Planning Phase:** If interrupted during pre-planning, the system restarts with any saved pre-planning data, preserving complexity assessment.
   * **Feature Group Processing Phase:** If interrupted during feature group processing, the system restores any already processed feature groups and continues with the next unprocessed group.
   * **Code Generation Phase:** If interrupted during code generation, the system restores the validated plan and continues with code generation, potentially skipping to a specific attempt number.
   * **Execution Phase:** If interrupted during execution, the system can resume after applying certain changes but before running tests, or after specific validation steps.
   * **PR Creation Phase:** If interrupted before creating a PR, the system can resume by creating the PR with previously committed changes.
4. **State Management (`agent_s3/task_state_manager.py`):**
   * The `TaskStateManager` loads the appropriate task snapshot from disk
   * Snapshots contain phase-specific data needed to resume each particular phase
   * Snapshots include metadata such as timestamp, task ID, phase, and status
   * For database operations, any schema changes made before interruption are preserved in the snapshots
5. **Execution:**
   * The task continues from the resumed state, with all context and progress preserved
   * Any necessary re-validation is performed automatically to ensure consistency
   * The system generates appropriate log entries to track the resumption

**Outcome:** The developer successfully resumes an interrupted task without having to start over from the beginning. All context, progress, and state information is preserved, saving time and maintaining consistency across the workflow.
