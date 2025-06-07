<!--
File: docs/manual_http_timeout_test.md
Description: Manual steps to verify HTTP timeout handling in the VS Code extension.
-->
# Manual Test for HTTP Timeout

This guide verifies that the extension gracefully falls back to the CLI when an HTTP request exceeds the configured timeout.

1. Launch the Agent-S3 backend so that `.agent_s3_http_connection.json` is created with the HTTP server address.
2. Set the environment variable `AGENT_S3_HTTP_TIMEOUT=1000` to force a short timeout.
3. In VS Code, execute a command expected to run longer than one second, for example:
   - Open the command palette and run **Agent-S3: Make change request**.
   - Provide a complex request that will take additional processing time.
4. Run the request. The extension sends an HTTP `POST /command` request.
5. Because the timeout is short, the HTTP request fails and the extension automatically falls back to the CLI.
6. The command output appears in the terminal once the CLI run completes; the server does not expose a `/status` endpoint.
7. Commands run synchronously with direct responses from the server.
