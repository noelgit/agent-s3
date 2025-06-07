<!--
File: docs/debugging_and_error_handling.md
Description: Combined guide for debugging strategies and error handling.
-->

# Debugging and Error Handling

## Comprehensive Debugging System with Chain of Thought Integration

Agent-S3's debugging system combines a three-tier debugging strategy with Chain of Thought (CoT) integration for more effective error resolution.

### Overview

The debugging system leverages historical reasoning, specialized error handling, and a structured approach that escalates from quick fixes to comprehensive debugging to strategic restarts when necessary.

### Key Components

#### Enhanced Scratchpad Manager
The `EnhancedScratchpadManager` provides:
- **Structured Chain of Thought Logging**
- **Session Management** with log rotation and encryption
- **CoT Extraction** utilities
- **Advanced Filtering** by role, level, section, and tags
- **Metadata Tracking** for each log entry
- **LLM Interaction Recording**

#### Debugging Manager
Implements a three-tier strategy:
1. **Generator Quick Fix** for simple issues
2. **Full Debugging** when quick fixes fail
3. **Strategic Restart** as a last resort

The manager categorizes errors and allocates token budgets for relevant context.

### Integration with Testing
- Automatically debugs test failures
- Captures test context for more effective debugging
- Provides specialized handling for assertion errors
- Works with the TestCritic to improve test quality

### Configuration
Key configuration options include:
- Max attempts per tier
- CoT storage settings
- Log rotation policies
- Error pattern matching thresholds
- Provide an `encryption_key` when `scratchpad_enable_encryption` is enabled. Generate it with `Fernet.generate_key()` and rotate it periodically.

## Error Handling

Agent-S3 implements comprehensive error handling with pattern detection and specialized recovery strategies.

### Error Types
1. **Syntax Errors** – pattern detection and recovery suggestions
2. **Type Errors** – variable type validation and conversion
3. **Import Errors** – dependency checks and path validation
4. **Attribute Errors** – object initialization verification
5. **Name Errors** – scope analysis and typo detection
6. **Index Errors** – bounds checking and key validation
7. **Value Errors** – input validation and range checking
8. **Runtime Errors** – capturing stack traces and relevant context
9. **Memory Errors** – memory usage monitoring and cleanup suggestions
10. **Permission Errors** – file and network permission checks
11. **Assertion Errors** – integration with the testing framework
12. **Network Errors** – retry logic with backoff and connectivity checks

### Workflow
When an error occurs, the system:
1. Classifies the error type
2. Gathers relevant context and historical reasoning
3. Suggests potential fixes or automated recovery steps
4. Tracks whether the suggestion resolves the issue

### Configuration
Error handling can be tuned via:
- Token budget allocation
- Pattern retention period
- Similarity threshold for pattern matching
- Context gathering depth per error type

## Terminal Hanging Issue Resolution

### Problem
The VS Code extension previously hung indefinitely when executing certain CLI
commands. Simple commands triggered the entire Coordinator startup, no timeout
mechanism was in place, and failed processes were not cleaned up properly.

### Implemented Fix
- Added lightweight handlers for `/help` and `/config` so they bypass full
  initialization.
- Updated the CLI main entry point to detect these commands early and exit with
  proper status codes.
- Introduced a 30‑second timeout in the VS Code extension with graceful process
  cleanup and user feedback.
- Verified that the Coordinator shuts down correctly, cleaning up background
  threads and HTTP resources.

### Verification Commands
```bash
python -m agent_s3.cli /help
python -m agent_s3.cli /config
python -m agent_s3.cli "list files in current directory"
```

## Manual HTTP Timeout Test

This procedure verifies that the extension falls back to the CLI when an HTTP
request exceeds the configured timeout.

1. Start the Agent-S3 backend so `.agent_s3_http_connection.json` contains the
   server address.
2. Set `AGENT_S3_HTTP_TIMEOUT=1000` to force a short timeout.
3. In VS Code, run a command expected to take more than one second, such as
   **Agent-S3: Make change request** with a complex prompt.
4. The extension sends an HTTP `POST /command` request which fails due to the
   short timeout and automatically falls back to the CLI.
5. Command output appears in the terminal once the CLI run completes.

