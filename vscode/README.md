<!--
NOTE: The top-level README.md in the repository contains the latest features and documentation for Agent-S3. Please refer to ../../README.md for the most up-to-date information.
-->
# Agent-S3 VS Code Extension

This extension integrates Agent-S3, a state-of-the-art AI coding agent, directly into VS Code.

## Features

- **Dual-LLM Orchestration**: Utilizes DeepSeek Reasoner for planning and Gemini 2.5 Pro for code generation
- **Transparent Planning Process**: View and approve the AI's plan before execution
- **GitHub Issue Tracking**: Automatically creates GitHub issues for change requests
- **Fixed Coding Guidelines**: Enforces consistent coding standards
- **Iterative Development**: Automatically refines implementations based on test results

## Requirements

- Python 3.10+
- GitHub account (for authentication)
- GitHub OAuth credentials (for API access)

The extension also requires a token encryption key to store your GitHub token securely:
```bash
AGENT_S3_ENCRYPTION_KEY="$(python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"
```

## Installation

1. Install the Agent-S3 Python package:
   ```
   pip install agent-s3
   ```

2. Install this VS Code extension

3. Set up GitHub OAuth credentials as environment variables:
   ```
   GITHUB_CLIENT_ID=your_client_id
   GITHUB_CLIENT_SECRET=your_client_secret
   ```

### Configuration

The extension uses TLS (`wss`) for WebSocket connections by default. You may
override this by setting `agent-s3.websocketProtocol` to `ws` if TLS must be
disabled (not recommended).

When the backend starts, it writes connection information to a file named
`.agent_s3_ws_connection.json` in the root of your workspace. The extension
reads this file to determine the WebSocket host, port, and authentication token.
The file is removed automatically when the backend shuts down and is created
with `0600` permissions on POSIX systems.

## Usage

1. Run "Agent-S3: Initialize workspace" from the command palette (Ctrl+Shift+P) to set up your workspace and authenticate with GitHub

2. Make a change request:
   - Click the Agent-S3 status bar item, or
   - Run "Agent-S3: Make change request" from the command palette

3. Review and approve the plan when prompted

4. Agent-S3 will:
   - Create a GitHub issue to track the changes
   - Generate and apply code changes
   - Run tests to verify the implementation
   - Automatically refine the implementation if needed

## Commands

- **Agent-S3: Initialize workspace** - Set up Agent-S3 in your current workspace
- **Agent-S3: Show help** - Display help information
- **Agent-S3: Show coding guidelines** - Display the current coding guidelines
- **Agent-S3: Make change request** - Submit a change request to Agent-S3
- **Agent-S3: Run automated design** - Generate a design with automatic approvals

## Status Tracking

Agent-S3 provides real-time status updates in the VS Code interface as it works through each phase:
1. Planning
2. Plan approval
3. GitHub issue creation
4. Code generation and implementation
5. Testing and refinement

## Logs

Detailed logs are available in your workspace:
- `scratchpad.txt` - Detailed internal chain-of-thought log
- `progress_log.jsonl` - Structured progress updates
- `development_status.json` - Overall development status tracking

## Chat History Persistence

The extension stores chat history in your workspace to retain conversations
across sessions. The `CHAT_HISTORY_KEY` constant (`"agent-s3.chatHistory"`) is
used as the lookup key when loading or saving messages in `context.workspaceState`.
When you open the chat window, previous messages are loaded from this key and
new entries are persisted back to it when the window closes. Clearing this key
will remove all saved chat history for the workspace.

## Feedback and Contributions

Please submit issues and feature requests through GitHub.
