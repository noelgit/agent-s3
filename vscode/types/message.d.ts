/**
 * Type definitions for WebSocket messages in Agent-S3
 */

/**
 * Message types that can be received from the WebSocket server
 */
export enum MessageType {
  // General message types
  TERMINAL_OUTPUT = "terminal_output",
  APPROVAL_REQUEST = "approval_request",
  DIFF_DISPLAY = "diff_display",
  LOG_OUTPUT = "log_output",
  PROGRESS_UPDATE = "progress_update",
  USER_RESPONSE = "user_response",
  ERROR_NOTIFICATION = "error_notification",

  // Connection management
  CONNECTION_ESTABLISHED = "connection_established",
  AUTHENTICATION_RESULT = "authentication_result",
  HEARTBEAT = "heartbeat",
  HEARTBEAT_RESPONSE = "heartbeat_response",
  SERVER_HEARTBEAT = "server_heartbeat",
  RECONNECT = "reconnect",
  RECONNECTION_RESULT = "reconnection_result",

  // Streaming message types
  THINKING = "thinking",
  STREAM_START = "stream_start",
  STREAM_CONTENT = "stream_content",
  STREAM_END = "stream_end",
  STREAM_INTERACTIVE = "stream_interactive",

  // UI-specific messages
  NOTIFICATION = "notification",
  INTERACTIVE_DIFF = "interactive_diff",
  INTERACTIVE_APPROVAL = "interactive_approval",
  PROGRESS_INDICATOR = "progress_indicator",
  CHAT_MESSAGE = "chat_message",
  CODE_SNIPPET = "code_snippet",
  FILE_TREE = "file_tree",
  TASK_BREAKDOWN = "task_breakdown",
  THINKING_INDICATOR = "thinking_indicator",
}

/**
 * Connection states for the WebSocket client
 */
export enum ConnectionState {
  DISCONNECTED = "disconnected",
  CONNECTING = "connecting",
  CONNECTED = "connected",
  AUTHENTICATING = "authenticating",
  AUTHENTICATED = "authenticated",
  RECONNECTING = "reconnecting",
  ERROR = "error",
}

/**
 * Base message interface
 */
export interface Message {
  type: string;
  content?: any;
  session_id?: string;
  timestamp?: string;
  id?: string;
}

/**
 * Terminal output message
 */
export interface TerminalOutputMessage extends Message {
  type: MessageType.TERMINAL_OUTPUT;
  content: {
    text: string;
    category: string;
  };
}

/**
 * Thinking indicator message
 */
export interface ThinkingMessage extends Message {
  type: MessageType.THINKING;
  content: {
    stream_id: string;
    source: string;
  };
}

/**
 * Stream start message
 */
export interface StreamStartMessage extends Message {
  type: MessageType.STREAM_START;
  content: {
    stream_id: string;
    source: string;
  };
}

/**
 * Stream content message
 */
export interface StreamContentMessage extends Message {
  type: MessageType.STREAM_CONTENT;
  content: {
    stream_id: string;
    content: string;
  };
}

/**
 * Stream end message
 */
export interface StreamEndMessage extends Message {
  type: MessageType.STREAM_END;
  content: {
    stream_id: string;
  };
}

export interface StreamInteractiveMessage extends Message {
  type: MessageType.STREAM_INTERACTIVE;
  content: {
    stream_id: string;
    component: {
      type: "button" | "input";
      id: string;
      label?: string;
      action?: string;
      placeholder?: string;
    };
  };
}

/**
 * Notification message
 */
export interface NotificationMessage extends Message {
  type: MessageType.NOTIFICATION;
  content: {
    title: string;
    text: string;
    level: "info" | "warning" | "error";
  };
}

/**
 * Progress indicator message
 */
export interface ProgressIndicatorMessage extends Message {
  type: MessageType.PROGRESS_INDICATOR;
  content: {
    title: string;
    percentage: number;
    steps?: Array<{
      name: string;
      status: "pending" | "in-progress" | "completed" | "failed";
      details?: string;
    }>;
    estimated_time_remaining?: number;
  };
}

/**
 * Interactive approval message
 */
export interface ApprovalRequestMessage extends Message {
  type: MessageType.INTERACTIVE_APPROVAL;
  content: {
    title: string;
    description: string;
    options: Array<{
      id: string;
      label: string;
      description?: string;
    }>;
    request_id: string;
    timeout?: number;
  };
}

/**
 * Interactive diff message
 */
export interface DiffDisplayMessage extends Message {
  type: MessageType.INTERACTIVE_DIFF;
  content: {
    files: Array<{
      file_path: string;
      diff: string;
      stats?: {
        insertions: number;
        deletions: number;
      };
    }>;
    summary: string;
  };
}

/**
 * Interface for streaming content tracking
 */
export interface StreamingContent {
  content: string;
  source: string;
  startTime: Date;
}

/**
 * Chat message interface
 */
export interface ChatMessage {
  id: string;
  type: "user" | "agent" | "system";
  content: string;
  timestamp: Date;
  isComplete: boolean;
}

/**
 * Stream state interface
 */
export interface StreamState {
  id: string;
  content: string;
  source: string;
  isThinking: boolean;
}

/**
 * WebView message data
 */
export interface MessageData {
  type: string;
  content: any;
  id?: string;
}
