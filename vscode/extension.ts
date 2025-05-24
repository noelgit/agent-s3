import * as vscode from "vscode";
import * as path from "path";
import { InteractiveWebviewManager } from "./webview-ui-loader";
import { BackendConnection } from "./backend-connection";
import { initializeWebSocketTester } from "./websocket-tester";
import { registerPerformanceTestCommand } from "./websocket-performance-test";
import { quote } from "./shellQuote";
import { ChatHistoryEntry } from "./types/message";

/**
 * Extension activation point
 */
export function activate(context: vscode.ExtensionContext) {
  console.log("Activating Agent-S3 extension");

  // Create interactive webview manager
  const interactiveWebviewManager = new InteractiveWebviewManager(
    context.extensionUri,
  );

  // Create backend connection
  const backendConnection = new BackendConnection(context.workspaceState);
  backendConnection.setInteractiveWebviewManager(interactiveWebviewManager);

  // Try to connect to the backend
  backendConnection.connect().then((connected) => {
    if (connected) {
      console.log("Connected to Agent-S3 backend");
    } else {
      console.log("Not connected to Agent-S3 backend yet");
    }
  });

  // Register commands
  context.subscriptions.push(
    vscode.commands.registerCommand("agent-s3.init", initializeWorkspace),
    vscode.commands.registerCommand("agent-s3.help", showHelp),
    vscode.commands.registerCommand("agent-s3.guidelines", showGuidelines),
    vscode.commands.registerCommand("agent-s3.request", makeChangeRequest),
    vscode.commands.registerCommand("agent-s3.openChatWindow", openChatWindow),
    vscode.commands.registerCommand(
      "agent-s3.openInteractiveView",
      openInteractiveView,
    ),
  );

  // Create status bar item to trigger change requests or open chat
  const statusBarItem = vscode.window.createStatusBarItem(
    vscode.StatusBarAlignment.Left,
    100,
  );
  statusBarItem.text = "$(sparkle) Agent-S3";
  statusBarItem.command = "agent-s3.request";
  statusBarItem.tooltip = "Start a change request";
  statusBarItem.show();
  context.subscriptions.push(statusBarItem);

  // Initialize the WebSocket tester
  const wsocketTester = initializeWebSocketTester(context);

  // Register WebSocket performance test
  registerPerformanceTestCommand(context);

  // Register the backend connection for disposal
  context.subscriptions.push(backendConnection);

  /**
   * Open the interactive components view.
   */
  function openInteractiveView() {
    // Create or show the interactive webview panel
    const panel = interactiveWebviewManager.createOrShowPanel();

    // Set up message handler for the interactive webview
    interactiveWebviewManager.setMessageHandler((message: any) => {
      console.log("Received message from interactive webview:", message);

      // Handle messages from the interactive components
      if (message.type) {
        switch (message.type) {
          case "APPROVAL_RESPONSE":
            // Forward response to backend
            backendConnection.sendMessage({
              type: "interactive_response",
              response_type: "approval",
              request_id: message.content.request_id,
              selected_option: message.content.selected_option,
            });
            break;

          case "DIFF_RESPONSE":
            // Forward response to backend
            backendConnection.sendMessage({
              type: "interactive_response",
              response_type: "diff",
              action: message.content.action,
              files: message.content.files,
              file: message.content.file,
            });
            break;

          case "PROGRESS_RESPONSE":
            // Forward response to backend
            backendConnection.sendMessage({
              type: "interactive_response",
              response_type: "progress",
              action: message.content.action,
            });
            break;

          case "webview-ready":
            // Send any pending interactive components
            // This could be fetched from a cache or state
            console.log("Interactive webview is ready");
            break;
        }
      }
    });
  }

  /**
   * Initialize workspace for Agent-S3
   */
  function initializeWorkspace() {
    // Get the Agent-S3 terminal
    const terminal = getAgentTerminal();

    // Show the terminal
    terminal.show();

    // Send initialization command
    terminal.sendText("python -m agent_s3.cli /init");

    // Show notification
    vscode.window.showInformationMessage("Initializing Agent-S3 workspace...");
  }

  /**
   * Show help information
   */
  function showHelp() {
    // Get the Agent-S3 terminal
    const terminal = getAgentTerminal();

    // Show the terminal
    terminal.show();

    // Send help command
    terminal.sendText("python -m agent_s3.cli /help");
  }

  /**
   * Show coding guidelines
   */
  function showGuidelines() {
    // Get the Agent-S3 terminal
    const terminal = getAgentTerminal();

    // Show the terminal
    terminal.show();

    // Send guidelines command
    terminal.sendText("python -m agent_s3.cli /guidelines");
  }

  /**
   * Make a change request
   */
  async function makeChangeRequest() {
    // Show input box for request
    const request = await vscode.window.showInputBox({
      placeHolder: "Enter your change request",
      prompt: "Describe the code changes you want Agent-S3 to make",
    });

    if (request) {
      // Get the Agent-S3 terminal
      const terminal = getAgentTerminal();

      // Show the terminal
      terminal.show();

      // Quote the request to prevent shell injection
      const safeRequest = quote([request]);

      // Send the request to the CLI
      terminal.sendText(`python -m agent_s3.cli ${safeRequest}`);

      // Show notification
      vscode.window.showInformationMessage(`Processing request: ${request}`);
    }
  }

  /**
   * Open the chat window
   */
  function openChatWindow() {
    // Create or show the shared interactive webview panel
    const panel = interactiveWebviewManager.createOrShowPanel();

    // Load persisted chat history from workspace state
    const rawHistory: any[] = context.workspaceState.get(
      "agent-s3.chatHistory",
      [],
    );

    const messageHistory: ChatHistoryEntry[] = rawHistory.map((msg) => ({
      ...msg,
      timestamp:
        msg.timestamp && typeof msg.timestamp === "string"
          ? new Date(msg.timestamp)
          : msg.timestamp instanceof Date
          ? msg.timestamp
          : new Date(),
    }));

    const historyListener = backendConnection.onDidPersistChatMessage((entry: ChatHistoryEntry) => {
      messageHistory.push(entry);
    });

    // Save history when the panel is disposed
    panel.onDidDispose(() => {
      const serializedHistory = messageHistory.map((msg) => ({
        ...msg,
        timestamp:
          msg.timestamp instanceof Date
            ? msg.timestamp.toISOString()
            : msg.timestamp,
      }));
      context.workspaceState.update(
        "agent-s3.chatHistory",
        serializedHistory,
      );
      historyListener.dispose();
    });

    // Set up message handler for chat and interactive messages
    interactiveWebviewManager.setMessageHandler((message: any) => {
      console.log("Received message from chat webview:", message);

      if (!message.type) {
        return;
      }

      switch (message.type) {
        case "webview-ready":
          const initial = messageHistory.slice(-20);
          interactiveWebviewManager.postMessage({
            type: "LOAD_HISTORY",
            history: initial,
            has_more: messageHistory.length > initial.length,
          });
          break;

        case "REQUEST_MORE_HISTORY":
          const alreadySent = message.already || 0;
          const more = messageHistory.slice(
            Math.max(0, messageHistory.length - alreadySent - 20),
            messageHistory.length - alreadySent,
          );
          interactiveWebviewManager.postMessage({
            type: "LOAD_HISTORY",
            history: more,
            has_more: messageHistory.length > alreadySent + more.length,
          });
          break;

        case "send":
          if (!message.text) {
            break;
          }

          // Record the user message in history
          messageHistory.push({
            id: `user-${Date.now()}`,
            type: "user",
            content: message.text,
            timestamp: new Date().toISOString(),
            isComplete: true,
          });

          // Persist updated history
          const serializedHistory = messageHistory.map((msg) => ({
            ...msg,
            timestamp:
              msg.timestamp instanceof Date
                ? msg.timestamp.toISOString()
                : msg.timestamp,
          }));
          context.workspaceState.update(
            "agent-s3.chatHistory",
            serializedHistory,
          );

          // Forward the message to the backend for processing
          backendConnection.sendMessage({
            type: "user_input",
            content: { text: message.text },
          });
          break;

        case "APPROVAL_RESPONSE":
          backendConnection.sendMessage({
            type: "interactive_response",
            response_type: "approval",
            request_id: message.content.request_id,
            selected_option: message.content.selected_option,
          });
          break;

        case "DIFF_RESPONSE":
          backendConnection.sendMessage({
            type: "interactive_response",
            response_type: "diff",
            action: message.content.action,
            files: message.content.files,
            file: message.content.file,
          });
          break;

        case "PROGRESS_RESPONSE":
          backendConnection.sendMessage({
            type: "interactive_response",
            response_type: "progress",
            action: message.content.action,
          });
          break;

        case "interactive_component":
          backendConnection.sendMessage({
            type: "interactive_component",
            component: message.component,
          });
          break;
      }
    });
  }

  /**
   * Get or create the Agent-S3 terminal
   */
  function getAgentTerminal(): vscode.Terminal {
    // Try to find existing terminal
    const existingTerminal = vscode.window.terminals.find(
      (t) => t.name === "Agent-S3",
    );

    if (existingTerminal) {
      return existingTerminal;
    }

    // Create a new terminal
    return vscode.window.createTerminal("Agent-S3");
  }
}
