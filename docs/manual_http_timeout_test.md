<!--
File: docs/manual_http_timeout_test.md
Description: Manual steps to verify HTTP timeout handling in the VS Code extension.
-->
# Manual Test for HTTP Timeout

This guide verifies that long-running HTTP commands are processed asynchronously without falling back to the CLI.

1. Launch the Agent-S3 backend so that `.agent_s3_http_connection.json` is created with the HTTP server address.
2. Set the environment variable `AGENT_S3_HTTP_TIMEOUT=1000` to force a short timeout.
3. In VS Code, execute a command expected to run longer than one second, for example:
   - Open the command palette and run **Agent-S3: Make change request**.
   - Provide a complex request that will take additional processing time.
4. Observe that the `/command` endpoint immediately returns a JSON object containing a `job_id`.
5. The VS Code extension polls `GET /status/<job_id>` until the backend finishes processing.
6. Once the job completes, the terminal output updates with the final result and no secondary CLI process is spawned.
