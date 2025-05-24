/**
 * Backend connection manager for Agent-S3 that integrates the WebSocket client
 * with the VS Code extension.
 */

import * as vscode from "vscode";
import { WebSocketClient } from "./websocket-client";
import { InteractiveWebviewManager } from "./webview-ui-loader";
import { ChatMessage } from "./types/message";
import * as fs from "fs";
import * as path from "path";

/**
 * Manages the connection to the Agent-S3 backend, integrating terminal and WebSocket communication
 */
export class BackendConnection implements vscode.Disposable {
  private webSocketClient: WebSocketClient;
  private interactiveWebviewManager: InteractiveWebviewManager | undefined;
  private activeStreams: Map<string, StreamingContent> = new Map();
  private readonly CHAT_HISTORY_KEY = "agent-s3.chatHistory";
  private readonly chatHistoryEmitter = new vscode.EventEmitter<ChatMessage>();
  private outputChannel: vscode.OutputChannel;
  private offlineQueue: any[] = [];
  private workspaceState: vscode.Memento | undefined;
  private progressInterval: NodeJS.Timeout | undefined;

  /**
   * Event fired whenever a chat message is persisted
   */
  public readonly onChatHistory = this.chatHistoryEmitter.event;

  /**
   * Create a new backend connection
   */
  constructor(workspaceState?: vscode.Memento) {
    this.workspaceState = workspaceState;
    // Create WebSocket client
    this.webSocketClient = new WebSocketClient();

    // Create output channel for messages
    this.outputChannel = vscode.window.createOutputChannel("Agent-S3");

    // Set up WebSocket message handlers
    this.setupMessageHandlers();

    if (this.workspaceState) {
      this.offlineQueue = this.workspaceState.get("agent-s3.offlineQueue", []);
    }
  }

  /**
   * Set the interactive webview manager to receive messages
   */
  public setInteractiveWebviewManager(
    manager: InteractiveWebviewManager,
  ): void {
    this.interactiveWebviewManager = manager;
  }

  /**
   * Connect to the backend
   */
  public async connect(): Promise<boolean> {
    const connected = await this.webSocketClient.connect();
    if (connected) {
      this.flushOfflineQueue();
      this.monitorProgress();
    }
    return connected;
  }

  /**
   * Check if connected to the backend
   */
  public isConnected(): boolean {
    return this.webSocketClient.isConnected();
  }

  /**
   * Send a message to the backend
   */
  public sendMessage(message: any): boolean {
    const sent = this.webSocketClient.sendMessage(message);
    if (!sent) {
      this.offlineQueue.push(message);
      this.persistOfflineQueue();
    }
    return sent;
  }

  /**
   * Set up WebSocket message handlers
   */
  private setupMessageHandlers(): void {
    // Set up handlers for streaming content
    this.webSocketClient.registerMessageHandler(
      "thinking",
      this.handleThinking.bind(this),
    );
    this.webSocketClient.registerMessageHandler(
      "stream_start",
      this.handleStreamStart.bind(this),
    );
    this.webSocketClient.registerMessageHandler(
      "stream_content",
      this.handleStreamContent.bind(this),
    );
    this.webSocketClient.registerMessageHandler(
      "stream_end",
      this.handleStreamEnd.bind(this),
    );
    this.webSocketClient.registerMessageHandler(
      "stream_interactive",
      this.handleStreamInteractive.bind(this),
    );

    // Set up handlers for interactive components
    this.webSocketClient.registerMessageHandler(
      "interactive_approval",
      this.handleInteractiveApproval.bind(this),
    );
    this.webSocketClient.registerMessageHandler(
      "interactive_diff",
      this.handleInteractiveDiff.bind(this),
    );
    this.webSocketClient.registerMessageHandler(
      "progress_indicator",
      this.handleProgressIndicator.bind(this),
    );

    // Set up handlers for other message types
    this.webSocketClient.registerMessageHandler(
      "terminal_output",
      this.handleTerminalOutput.bind(this),
    );
    this.webSocketClient.registerMessageHandler(
      "notification",
      this.handleNotification.bind(this),
    );
  }

  /**
   * Process a message received from the backend
   * This is the original method that will be patched in extension.ts
   */
  public processMessage(message: any): void {
    // The original implementation does nothing - it will be patched
    console.log("Default processMessage called, this should be overridden");
  }

  /**
   * Handle thinking indicator messages
   */
  private handleThinking(message: any): void {
    const source = message.content?.source || "agent";
    const streamId = message.content?.stream_id;

    if (!streamId) {
      return;
    }

    // Show thinking indicator in UI
    if (this.interactiveWebviewManager) {
      this.interactiveWebviewManager.postMessage({
        type: "THINKING_INDICATOR",
        content: {
          source: source,
          stream_id: streamId,
        },
      });
    }

    // Log to output channel
    this.outputChannel.appendLine(`[${source}] Thinking...`);
  }

  /**
   * Handle stream start messages
   */
  private handleStreamStart(message: any): void {
    const streamId = message.content?.stream_id;
    const source = message.content?.source || "agent";

    if (!streamId) {
      return;
    }

    // Initialize stream tracking
    this.activeStreams.set(streamId, {
      content: "",
      source: source,
      startTime: new Date(),
    });

    // Notify UI that streaming is starting
    if (this.interactiveWebviewManager) {
      this.interactiveWebviewManager.postMessage({
        type: "STREAM_START",
        content: {
          stream_id: streamId,
          source: source,
        },
      });
    }
  }

  /**
   * Handle stream content messages
   */
  private handleStreamContent(message: any): void {
    const streamId = message.content?.stream_id;
    const content = message.content?.content || "";

    if (!streamId) {
      return;
    }

    // Update stream content
    const stream = this.activeStreams.get(streamId);
    if (!stream) {
      // Initialize if this is the first content we're seeing
      this.activeStreams.set(streamId, {
        content: content,
        source: "unknown",
        startTime: new Date(),
      });
      return;
    }

    // Append content
    stream.content += content;

    // Send content to UI for incremental update
    if (this.interactiveWebviewManager) {
      this.interactiveWebviewManager.postMessage({
        type: "STREAM_CONTENT",
        content: {
          stream_id: streamId,
          content: content,
        },
      });
    }

    // Show in output channel
    this.outputChannel.append(content);
  }

  /**
   * Handle stream end messages
   */
  private handleStreamEnd(message: any): void {
    const streamId = message.content?.stream_id;

    if (!streamId) {
      return;
    }

    // Get the final content
    const stream = this.activeStreams.get(streamId);
    if (!stream) {
      return;
    }

    // Notify UI that streaming has ended
    if (this.interactiveWebviewManager) {
      this.interactiveWebviewManager.postMessage({
        type: "STREAM_END",
        content: {
          stream_id: streamId,
          final_content: stream.content,
        },
      });
    }

    // Persist the completed agent message
    this.persistChatMessage({
      id: streamId,
      type: "agent",
      content: stream.content,
      timestamp: new Date(),
      isComplete: true,
    });

    // Log completion
    this.outputChannel.appendLine(""); // Ensure we end with a newline

    // Cleanup
    this.activeStreams.delete(streamId);
  }

  /**
   * Handle interactive component messages within a stream
   */
  private handleStreamInteractive(message: any): void {
    if (this.interactiveWebviewManager) {
      this.interactiveWebviewManager.postMessage({
        type: "STREAM_INTERACTIVE",
        content: message.content,
      });
    }
  }

  /**
   * Handle terminal output messages
   */
  private handleTerminalOutput(message: any): void {
    const content = message.content?.text || "";
    const category = message.content?.category || "output";

    // Show in output channel
    if (category === "error") {
      this.outputChannel.appendLine(`[ERROR] ${content}`);
    } else {
      this.outputChannel.appendLine(content);
    }

    // Forward to webview if available
    if (this.interactiveWebviewManager) {
      this.interactiveWebviewManager.postMessage({
        type: "TERMINAL_OUTPUT",
        content: {
          text: content,
          category: category,
        },
      });
    }
  }

  /**
   * Handle notification messages
   */
  private handleNotification(message: any): void {
    const title = message.content?.title || "Agent-S3";
    const text = message.content?.text || "";
    const level = message.content?.level || "info";

    // Show VS Code notification based on level
    switch (level) {
      case "error":
        vscode.window.showErrorMessage(`${title}: ${text}`);
        break;
      case "warning":
        vscode.window.showWarningMessage(`${title}: ${text}`);
        break;
      case "info":
      default:
        vscode.window.showInformationMessage(`${title}: ${text}`);
        break;
    }

    // Log to output channel
    this.outputChannel.appendLine(`[${level.toUpperCase()}] ${title}: ${text}`);
  }

  /**
   * Handle interactive approval messages
   */
  private handleInteractiveApproval(message: any): void {
    // Show the interactive panel if not already visible
    if (this.interactiveWebviewManager) {
      const panel = this.interactiveWebviewManager.createOrShowPanel();

      // Forward the message to the webview
      this.interactiveWebviewManager.postMessage({
        type: "INTERACTIVE_APPROVAL",
        content: message.content,
      });
    }
  }

  /**
   * Handle interactive diff messages
   */
  private handleInteractiveDiff(message: any): void {
    // Show the interactive panel if not already visible
    if (this.interactiveWebviewManager) {
      const panel = this.interactiveWebviewManager.createOrShowPanel();

      // Forward the message to the webview
      this.interactiveWebviewManager.postMessage({
        type: "INTERACTIVE_DIFF",
        content: message.content,
      });
    }
  }

  /**
   * Handle progress indicator messages
   */
  private handleProgressIndicator(message: any): void {
    // Show the interactive panel if not already visible
    if (this.interactiveWebviewManager) {
      // Ensure the interactive panel is visible
      this.interactiveWebviewManager.createOrShowPanel();

      // Forward the message to the webview
      this.interactiveWebviewManager.postMessage({
        type: "PROGRESS_INDICATOR",
        content: message.content,
      });
    }
  }

  /**
   * Persist offline queue to workspace state
   */
  private persistOfflineQueue(): void {
    if (this.workspaceState) {
      this.workspaceState.update("agent-s3.offlineQueue", this.offlineQueue);
    }
  }

  /**
   * Persist a chat message to workspace state
   */
  private persistChatMessage(message: ChatMessage): void {
    if (!this.workspaceState) {
      return;
    }

    const history = this.workspaceState.get<ChatMessage[]>(
      this.CHAT_HISTORY_KEY,
      [],
    );
    history.push(message);
    this.workspaceState.update(this.CHAT_HISTORY_KEY, history);

    // Notify listeners that a new message was persisted
    this.chatHistoryEmitter.fire(message);
  }

  /**
   * Flush queued messages when reconnected
   */
  private flushOfflineQueue(): void {
    if (!this.offlineQueue.length) {
      return;
    }

    const queue = [...this.offlineQueue];
    this.offlineQueue = [];
    queue.forEach((msg) => this.sendMessage(msg));
    this.persistOfflineQueue();
  }

  /**
   * Monitor progress updates written to progress_log.jsonl
   */
  private monitorProgress(): void {
    if (this.progressInterval) {
      return;
    }

    const folders = vscode.workspace.workspaceFolders;
    if (!folders || !folders.length) {
      return;
    }

    const progressPath = path.join(folders[0].uri.fsPath, "progress_log.jsonl");
    let position = 0;
    this.progressInterval = setInterval(() => {
      fs.stat(
        progressPath,
        (err: NodeJS.ErrnoException | null, stats: fs.Stats) => {
          if (err) {
            this.outputChannel.appendLine(
              `Error reading progress log: ${err.message}`,
            );
            return;
          }

          if (stats.size <= position) {
            return;
          }

          const stream = fs.createReadStream(progressPath, {
            start: position,
            end: stats.size - 1,
          });

          let buffer = "";
          stream.on("data", (chunk: Buffer) => {
            buffer += chunk.toString();
          });

          stream.on("error", (streamErr: Error) => {
            this.outputChannel.appendLine(
              `Progress stream error: ${streamErr.message}`,
            );
          });

          stream.on("end", () => {
            position = stats.size;
            const lines = buffer.split(/\r?\n/).filter((l) => l);
            for (const line of lines) {
              try {
                const entry = JSON.parse(line);
                if (this.interactiveWebviewManager) {
                  this.interactiveWebviewManager.postMessage({
                    type: "PROGRESS_ENTRY",
                    content: entry,
                  });
                }
              } catch (e) {
                this.outputChannel.appendLine(
                  `Progress parse error: ${(e as Error).message}`,
                );
              }
            }
          });
        },
      );
    }, 2000);
  }

  /**
   * Stop monitoring progress updates
   */
  private stopMonitoringProgress(): void {
    if (this.progressInterval) {
      clearInterval(this.progressInterval);
      this.progressInterval = undefined;
    }
  }

  /**
   * Dispose of resources
   */
  public dispose(): void {
    // Stop the progress timer before releasing the rest of the resources
    this.stopMonitoringProgress();
    this.webSocketClient.dispose();
    this.outputChannel.dispose();
  }
}

/**
 * Interface for tracking streaming content
 */
interface StreamingContent {
  content: string;
  source: string;
  startTime: Date;
}
