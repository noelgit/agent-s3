# Agent-S3 Playwright Test Script Registry

This document maintains a registry of all Playwright test scripts in the repository, mapping them to the user stories they cover.

## Test Script Coverage

| User Story | Script File | Description |
|------------|-------------|-------------|
| **Story 1: Initializing Agent-S3 in a New Workspace** | [story1-initialize-workspace.spec.ts](tests/playwright/specs/story1-initialize-workspace.spec.ts) | Tests initializing Agent-S3 via command palette and CLI, including GitHub authentication flow |
| **Story 2: Making a Code Change Request** | [story2-code-change-request.spec.ts](tests/playwright/specs/story2-code-change-request.spec.ts) | Tests making code change requests via command palette, status bar, and CLI, along with the full request workflow |
| **Story 3: Interacting via the Chat UI** | [story3-chat-ui.spec.ts](tests/playwright/specs/story3-chat-ui.spec.ts) | Tests opening the chat window, sending commands and change requests via chat, and chat history persistence |
| **Story 4: Using Helper Commands** | [story4-helper-commands.spec.ts](tests/playwright/specs/story4-helper-commands.spec.ts) | Tests helper commands like /help, /guidelines, and /explain via both command palette and CLI |

## Running the Tests

To run all tests:
```bash
npx playwright test
```

To run tests for a specific story:
```bash
npx playwright test tests/playwright/specs/story1-initialize-workspace.spec.ts
```

To run in headed mode (to see the browser UI):
```bash
npx playwright test --headed
```

## Test Infrastructure

- [playwright.config.ts](tests/playwright/playwright.config.ts): Configuration for Playwright tests
- [fixtures.ts](tests/playwright/fixtures.ts): Custom fixtures that simulate VS Code environment and provide utility functions

## Coverage Overview

The tests simulate user interactions with VS Code extension commands and the Agent-S3 agent through:

1. **Command Palette**: Tests opening VS Code's command palette and selecting Agent-S3 commands
2. **Status Bar**: Tests clicking the Agent-S3 status bar item
3. **Terminal**: Tests typing commands directly into the terminal
4. **Chat UI**: Tests interaction via the dedicated chat window

Each test validates both visual components (UI visibility) and program behavior (terminal output, progress updates).