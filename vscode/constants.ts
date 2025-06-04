// constants.ts
// Centralized constants for the VS Code extension.

/**
 * Workspace state key for storing chat history.
 */
export const CHAT_HISTORY_KEY = "agent-s3.chatHistory";

/**
 * Default HTTP timeout for requests to the Agent-S3 backend.
 */
export const DEFAULT_HTTP_TIMEOUT_MS = 5000;

/**
 * VS Code configuration key used to override the HTTP timeout.
 */
export const HTTP_TIMEOUT_SETTING = "agent-s3.httpTimeoutMs";
