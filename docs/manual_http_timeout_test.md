<!--
File: docs/manual_http_timeout_test.md
Description: Manual steps to verify HTTP timeout handling in the VS Code extension.
-->
# Manual Test for HTTP Timeout

This guide verifies that long-running HTTP commands do not cause the extension to fall back to the CLI.

1. Launch the Agent-S3 backend so that `.agent_s3_http_connection.json` is created with the HTTP server address.
2. Set the environment variable `AGENT_S3_HTTP_TIMEOUT=1000` to force a short timeout.
3. In VS Code, execute a command expected to run longer than one second, for example:
   - Open the command palette and run **Agent-S3: Make change request**.
   - Provide a complex request that will take additional processing time.
4. Observe that the extension displays a processing message instead of spawning the CLI.
5. Once the backend finishes, the terminal output should show the result without a secondary CLI process.
