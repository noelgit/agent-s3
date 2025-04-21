# Agent-S3 User Stories & Walkthroughs

This document outlines common user scenarios and provides step-by-step walkthroughs for interacting with Agent-S3, based on the actual implementation in the `agent_s3` Python package and the `vscode` extension.

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
3.  **VS Code Extension Action:** The `initializeWorkspace` function in `vscode/extension.ts` is triggered. It opens the dedicated "Agent-S3" terminal (creating it if it doesn't exist using `getAgentTerminal`) and sends the `python -m agent_s3.cli /init` command. A notification "Initializing Agent-S3 workspace..." appears.
4.  **Backend CLI Action:** `agent_s3/cli.py` receives the `/init` command. The `process_command` function handles it.
5.  **Authentication Check:** The `/init` process (likely within the `Coordinator` or triggered by it) checks if a valid GitHub token exists (e.g., via `os.getenv("GITHUB_TOKEN")` or a stored token file like `~/.agent_s3/github_token.json`).
6.  **GitHub OAuth Flow (if needed):**
    *   If no valid token is found, `agent_s3/auth.py`'s `authenticate_user` function is called.
    *   It constructs a GitHub OAuth URL (`GITHUB_AUTH_URL`) with the `GITHUB_CLIENT_ID`, scope, and a unique `state` parameter.
    *   It starts a local HTTP server (`http.server`) on `localhost:8000` to listen for the callback.
    *   It opens the user's web browser to the GitHub authorization URL.
    *   The user logs into GitHub and authorizes the application.
    *   GitHub redirects the browser back to `http://localhost:8000/callback` with an authorization `code` and the `state`.
    *   The local server handler (`CallbackHandler` in `auth.py`) receives the request, validates the `state`, and exchanges the `code` for an access token by making a POST request to `GITHUB_TOKEN_URL` with the `GITHUB_CLIENT_ID` and `GITHUB_CLIENT_SECRET`.
    *   The obtained access token is stored securely (e.g., in `~/.agent_s3/github_token.json`).
    *   The local server shuts down, and the browser might show a success message.
7.  **Organization Check (if configured):** If `GITHUB_ORG` is set, `auth.py` uses the obtained token to verify the user's membership in the specified organization(s) via the GitHub API (`/user/memberships/orgs`). If the user is not a member, authentication fails.
8.  **Initialization Complete:** The CLI confirms successful initialization. The VS Code extension sets an internal flag (`isInitialized = true`) after a short delay. Necessary configuration files (like `.github/copilot-instructions.md` if part of the init process) might be created or verified.

**Outcome:** Agent-S3 is ready to use in the workspace. The user is authenticated with GitHub, and subsequent commands requiring GitHub access will use the stored token.

---

## Story 2: Making a Code Change Request via VS Code Command

**Goal:** Request a code modification using the VS Code command palette.

**Persona:** A developer wanting to add a feature or fix a bug.

**Walkthrough:**

1.  **Trigger Command:** The developer presses `Ctrl+Shift+P` (or `Cmd+Shift+P`), types `Agent-S3: Make change request`, and selects the command. Alternatively, they click the `$(sparkle) Agent-S3` item in the status bar.
2.  **Input Prompt:** VS Code shows an input box (`vscode.window.showInputBox`) prompting "Enter your change request".
3.  **Enter Request:** The developer types their request (e.g., "Add a function to calculate the factorial of a number in utils.py") and presses Enter.
4.  **VS Code Extension Action:** The `makeChangeRequest` function in `vscode/extension.ts` is called.
    *   It checks if the workspace is initialized (`isInitialized` flag). If not, it prompts the user to initialize first.
    *   It retrieves the dedicated "Agent-S3" terminal using `getAgentTerminal`.
    *   It shows the terminal (`terminal.show()`).
    *   It sends the developer's request to the CLI, escaping any quotes: `python -m agent_s3.cli "<user_request>"`.
    *   It shows an information notification: `Processing request: <user_request>`.
    *   It starts monitoring the `progress_log.json` file for updates using `monitorProgress`.
5.  **Backend CLI Action:** `agent_s3/cli.py` receives the request as a command-line argument.
    *   The `main` function parses the arguments.
    *   It loads the configuration (`Config`).
    *   It initializes the `Coordinator`.
    *   It checks for authentication (calling `authenticate_user` if needed, as in Story 1).
    *   It calls `coordinator.process_change_request(prompt)`.
6.  **Coordinator Workflow:** The `Coordinator` (`agent_s3/coordinator.py`) executes its phases:
    *   **Planning:** Uses the `RouterAgent` to select a planning LLM (based on `llm.json`). Calls the `Planner` (`agent_s3/planner.py`) to generate a step-by-step plan based on the request and project context (potentially using RAG via `EmbeddingClient` and `MemoryManager`). Logs progress to `progress_log.json`.
    *   **Plan Approval:** Uses `PromptModerator` (`agent_s3/prompt_moderator.py`) to display the plan in the terminal and ask the user for approval (`y/n`).
    *   **GitHub Issue Creation (Optional):** If approved and configured, uses `GitTool` (`agent_s3/tools/git_tool.py`) to create a GitHub issue based on the plan. Logs progress.
    *   **Execution:** Iterates through the plan steps. For code generation steps:
        *   Uses `RouterAgent` to select a code generation LLM.
        *   Calls `CodeGenerator` (`agent_s3/code_generator.py`) to generate code/diffs.
        *   Uses `PromptModerator` to show diffs and ask for approval.
        *   Uses `FileTool` (`agent_s3/tools/file_tool.py`) to apply approved changes.
        *   Uses `CodeAnalysisTool` (`agent_s3/tools/code_analysis_tool.py`) or `BashTool` (`agent_s3/tools/bash_tool.py`) to run linters/tests.
        *   If errors occur, potentially enters a refinement loop, feeding errors back to the planner/generator. Logs progress.
    *   **PR Creation (Optional):** If configured, uses `GitTool` to commit changes, push a branch, and create a Pull Request. Logs progress.
7.  **VS Code Monitoring:** The `monitorProgress` function in `vscode/extension.ts` periodically reads `progress_log.json`.
    *   It parses new entries.
    *   It updates the status bar item (`updateProgressStatus`) with the current phase/status.
    *   It shows relevant notifications (e.g., "Agent-S3 created pull request: <url>", "Agent-S3 encountered an issue...").
    *   It stops monitoring when a final state (completed, failed, rejected, PR created) is reached or after a timeout.

**Outcome:** The requested code change is planned, potentially tracked in a GitHub issue, implemented (with user approvals), and possibly submitted as a PR. The developer sees progress updates in VS Code.

---

## Story 3: Interacting via the Chat UI

**Goal:** Use the dedicated chat window in VS Code to make requests and interact with Agent-S3.

**Persona:** A developer preferring a conversational interface.

**Walkthrough:**

1.  **Open Chat Window:** The developer runs `Agent-S3: Open Chat Window` from the Command Palette.
2.  **VS Code Extension Action:** The `openChatWindow` function in `vscode/extension.ts` creates a `WebviewPanel`.
    *   It sets up the HTML content using `getWebviewContent`, including CSS for styling and JavaScript for interaction (using a `nonce` for CSP).
    *   It loads previous message history from `extensionContext.workspaceState`.
    *   It sets up a message listener (`panel.webview.onDidReceiveMessage`) to handle messages sent *from* the webview JS.
3.  **Webview Loads:** The chat panel appears. The webview's JavaScript (`acquireVsCodeApi`, event listeners) initializes. It requests and displays the loaded history.
4.  **User Sends Message:** The developer types a request (e.g., "/help" or "Refactor the login function") into the textarea (`#msg`) and clicks Send or presses Enter.
5.  **Webview JavaScript Action:**
    *   The `sendMessage` function in the webview JS captures the text.
    *   It adds the user's message to the UI (`addMessageToUI`).
    *   It sends the message to the VS Code extension using `vscode.postMessage({ command: 'send', text: <user_text> })`.
    *   It might show a temporary typing indicator.
6.  **VS Code Extension Receives Message:** The `panel.webview.onDidReceiveMessage` listener in `extension.ts` receives the message.
    *   It adds the user message to the persistent `messageHistory`.
    *   It gets the "Agent-S3" terminal (`getAgentTerminal`).
    *   It sends the user's text to the CLI: `python -m agent_s3.cli "<user_text>"`.
7.  **Backend Processing:** The CLI (`agent_s3/cli.py`) processes the command or request as described in Story 1 (for `/` commands) or Story 2 (for change requests). All output, including plans, prompts for approval, and results, appears in the "Agent-S3" terminal.
8.  **Chat UI Feedback (Simulated/Limited):**
    *   The current implementation in `vscode/extension.ts` *simulates* an agent response in the chat UI after a delay (`setTimeout`).
    *   **Note:** It does *not* currently parse the actual output from the terminal to display the agent's real responses directly in the chat bubbles. The user needs to monitor the "Agent-S3" terminal for the actual interaction and results. The chat UI primarily serves as an input mechanism.

**Outcome:** The user can initiate Agent-S3 commands and requests via the chat interface. The actual interaction and detailed output occur in the associated "Agent-S3" terminal. The chat history is saved within the VS Code workspace state.

---

## Story 4: Using Helper Commands

**Goal:** Get help or view coding guidelines using specific commands.

**Persona:** A developer needing information about Agent-S3 or project standards.

**Walkthrough (using `/help`):**

1.  **Trigger Command:**
    *   **VS Code:** Run `Agent-S3: Show help` from the Command Palette.
    *   **CLI:** Run `python -m agent_s3.cli /help` in the terminal.
    *   **Chat UI:** Type `/help` and send.
2.  **VS Code Extension Action (if applicable):** The `showHelp` function (or `openChatWindow` message handler) gets the terminal and sends `python -m agent_s3.cli /help`.
3.  **Backend CLI Action:** `agent_s3/cli.py` receives the `/help` command.
    *   `process_command` identifies it as a special command.
    *   It calls a function (e.g., `display_help` or a coordinator method) to print help information to standard output.
4.  **Output:** The help text is displayed directly in the "Agent-S3" terminal where the command was executed.

**Walkthrough (using `/guidelines`):**

1.  **Trigger Command:**
    *   **VS Code:** Run `Agent-S3: Show coding guidelines` from the Command Palette.
    *   **CLI:** Run `python -m agent_s3.cli /guidelines` in the terminal.
    *   **Chat UI:** Type `/guidelines` and send.
2.  **VS Code Extension Action (if applicable):** The `showGuidelines` function (or `openChatWindow` message handler) gets the terminal and sends `python -m agent_s3.cli /guidelines`.
3.  **Backend CLI Action:** `agent_s3/cli.py` receives the `/guidelines` command.
    *   `process_command` identifies it.
    *   It likely calls a method on the `Coordinator` or `Config` object.
    *   `agent_s3/config.py`'s `load` method reads guidelines (e.g., from `.github/copilot-instructions.md`).
    *   The relevant function prints the loaded guidelines content to standard output.
4.  **Output:** The coding guidelines are displayed in the "Agent-S3" terminal.

**Outcome:** The user receives the requested information directly in the terminal associated with Agent-S3.
