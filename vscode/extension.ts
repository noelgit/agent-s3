import * as vscode from "vscode";
import { InteractiveWebviewManager } from "./webview-ui-loader";
import { BackendConnection } from "./backend-connection";
import { initializeWebSocketTester } from "./websocket-tester";
import { registerPerformanceTestCommand } from "./websocket-performance-test";
import { quote } from "./shellQuote";
import { ChatHistoryEntry } from "./types/message";
import { CHAT_HISTORY_KEY } from "./constants";
import { Agent3ChatProvider, Agent3HistoryProvider } from "./tree-providers";

/**
 * Extension activation point
 */
export function activate(context: vscode.ExtensionContext): void {
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

  // Create and register tree data providers
  const chatProvider = new Agent3ChatProvider(context);
  const historyProvider = new Agent3HistoryProvider(context);
  
  vscode.window.registerTreeDataProvider("agent-s3-chat", chatProvider);
  vscode.window.registerTreeDataProvider("agent-s3-history", historyProvider);

  // Register commands
  context.subscriptions.push(
    vscode.commands.registerCommand("agent-s3.init", initializeWorkspace),
    vscode.commands.registerCommand("agent-s3.help", showHelp),
    vscode.commands.registerCommand("agent-s3.guidelines", showGuidelines),
    vscode.commands.registerCommand("agent-s3.request", makeChangeRequest),
    vscode.commands.registerCommand("agent-s3.designAuto", runAutomatedDesign),
    vscode.commands.registerCommand("agent-s3.openChatWindow", openChatWindow),
    vscode.commands.registerCommand(
      "agent-s3.openInteractiveView",
      openInteractiveView,
    ),
    vscode.commands.registerCommand("agent-s3.showChatEntry", showChatEntry),
    vscode.commands.registerCommand("agent-s3.refreshChat", () => chatProvider.refresh()),
    vscode.commands.registerCommand("agent-s3.refreshHistory", () => historyProvider.refresh()),
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
  initializeWebSocketTester(context);

  // Register WebSocket performance test
  registerPerformanceTestCommand(context);

  // Register the backend connection for disposal
  context.subscriptions.push(backendConnection);

  /**
   * Open the interactive components view.
   */
  function openInteractiveView() {
    // Create or show the interactive webview panel
    interactiveWebviewManager.createOrShowPanel();

    // Set up message handler for the interactive webview
    interactiveWebviewManager.setMessageHandler((message: {type: string; content: any}) => {
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
    // Send command through WebSocket if connected
    if (backendConnection.isConnected()) {
      backendConnection.sendMessage({
        type: "command",
        content: {
          command: "/init",
          args: "",
          request_id: `init-${Date.now()}`
        }
      });
      vscode.window.showInformationMessage("Initializing Agent-S3 workspace...");
    } else {
      // Fallback to terminal
      const terminal = getAgentTerminal();
      terminal.show();
      terminal.sendText("python -m agent_s3.cli /init");
      vscode.window.showInformationMessage("Initializing Agent-S3 workspace... (fallback mode)");
    }
  }

  /**
   * Show help information
   */
  function showHelp() {
    // Send command through WebSocket if connected
    if (backendConnection.isConnected()) {
      backendConnection.sendMessage({
        type: "command",
        content: {
          command: "/help",
          args: "",
          request_id: `help-${Date.now()}`
        }
      });
    } else {
      // Fallback to terminal
      const terminal = getAgentTerminal();
      terminal.show();
      terminal.sendText("python -m agent_s3.cli /help");
    }
  }

  /**
   * Show coding guidelines
   */
  function showGuidelines() {
    // Send command through WebSocket if connected
    if (backendConnection.isConnected()) {
      backendConnection.sendMessage({
        type: "command",
        content: {
          command: "/guidelines",
          args: "",
          request_id: `guidelines-${Date.now()}`
        }
      });
    } else {
      // Fallback to terminal
      const terminal = getAgentTerminal();
      terminal.show();
      terminal.sendText("python -m agent_s3.cli /guidelines");
    }
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
      // Send command through WebSocket if connected
      if (backendConnection.isConnected()) {
        backendConnection.sendMessage({
          type: "command",
          content: {
            command: request,
            args: "",
            request_id: `request-${Date.now()}`
          }
        });
        vscode.window.showInformationMessage(`Processing request: ${request}`);
      } else {
        // Fallback to terminal
        const terminal = getAgentTerminal();
        terminal.show();
        const safeRequest = quote([request]);
        terminal.sendText(`python -m agent_s3.cli ${safeRequest}`);
        vscode.window.showInformationMessage(`Processing request: ${request} (fallback mode)`);
      }
    }
  }

  /**
   * Run automated design workflow
   */
  async function runAutomatedDesign() {
    const objective = await vscode.window.showInputBox({
      placeHolder: "Enter your design objective",
      prompt: "Describe the system you want Agent-S3 to design automatically",
    });

    if (objective) {
      const terminal = getAgentTerminal();
      terminal.show();
      const safeObjective = quote([objective]);
      terminal.sendText(`python -m agent_s3.cli /design-auto ${safeObjective}`);
      vscode.window.showInformationMessage(
        `Running automated design: ${objective}`,
      );
    }
  }

  /**
   * Open the chat window
   */
  function openChatWindow() {
    // Create or show the shared interactive webview panel
    const panel = interactiveWebviewManager.createOrShowPanel();

    // Load persisted chat history from workspace state
    const rawHistory: ChatHistoryEntry[] = context.workspaceState.get(
      CHAT_HISTORY_KEY,
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
        CHAT_HISTORY_KEY,
        serializedHistory,
      );
      historyListener.dispose();
    });

    // Set up message handler for chat and interactive messages
    interactiveWebviewManager.setMessageHandler((message: {type: string; [key: string]: any}) => {
      console.log("Received message from chat webview:", message);

      if (!message.type) {
        return;
      }

      switch (message.type) {
        case "webview-ready": {
          const initial = messageHistory.slice(-20);
          interactiveWebviewManager.postMessage({
            type: "LOAD_HISTORY",
            history: initial,
            has_more: messageHistory.length > initial.length,
          });
          break;
        }

        case "REQUEST_MORE_HISTORY": {
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
        }

        case "send": {
          if (!message.text) {
            break;
          }

          // Check if this is a command (starts with /)
          if (message.text.startsWith('/')) {
            // Parse command and args
            const parts = message.text.trim().split(' ');
            const command = parts[0];
            const args = parts.slice(1).join(' ');
            
            // Send as command message
            backendConnection.sendMessage({
              type: "command",
              content: {
                command: command,
                args: args,
                request_id: `chat-${Date.now()}`
              }
            });
          } else {
            // Regular user input - send as user_input message
            backendConnection.sendMessage({
              type: "user_input",
              content: { text: message.text },
            });
          }

          // Record the user message in history regardless of type
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
            CHAT_HISTORY_KEY,
            serializedHistory,
          );
          break;
        }

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
      (t: vscode.Terminal) => t.name === "Agent-S3",
    );

    if (existingTerminal) {
      return existingTerminal;
    }

    // Create a new terminal
    return vscode.window.createTerminal("Agent-S3");
  }

  /**
   * Show chat entry details
   */
  function showChatEntry(entry: ChatHistoryEntry): void {
    const timestamp = new Date(entry.timestamp).toLocaleString();
    
    vscode.window.showInformationMessage(
      `Chat Entry from ${entry.type} (${timestamp}):\n\n${entry.content}`,
      { modal: false },
      "Open Chat Window"
    ).then((selection: string | undefined) => {
      if (selection === "Open Chat Window") {
        vscode.commands.executeCommand("agent-s3.openChatWindow");
      }
    });
  }
}
