import * as vscode from "vscode";
import { WebSocketClient } from "./websocket-client";

/**
 * WebSocket connection tester for development and testing
 */
export class WebSocketTester {
  private wsClient: WebSocketClient;
  private statusBarItem: vscode.StatusBarItem;

  constructor() {
    this.wsClient = new WebSocketClient();

    // Create status bar item for connection status
    this.statusBarItem = vscode.window.createStatusBarItem(
      vscode.StatusBarAlignment.Right,
      100,
    );
    this.statusBarItem.text = "$(plug) WS: Disconnected";
    this.statusBarItem.tooltip = "WebSocket connection status";
    this.statusBarItem.command = "agent-s3.testWebSocket";
    this.statusBarItem.show();

    // Register message handlers
    this.registerHandlers();
  }

  /**
   * Register message handlers for the WebSocket client
   */
  private registerHandlers() {
    // Register for notifications
    this.wsClient.registerMessageHandler("notification", (message: any) => {
      const { title, message: msg, level } = message.content || {};
      if (title && msg) {
        const notificationFn =
          level === "error"
            ? vscode.window.showErrorMessage
            : level === "warning"
              ? vscode.window.showWarningMessage
              : vscode.window.showInformationMessage;

        notificationFn(`${title}: ${msg}`);
      }
    });

    // Register for echo messages
    this.wsClient.registerMessageHandler("echo", (message: any) => {
      console.log("Echo received:", message);
      vscode.window.showInformationMessage(
        `WebSocket message echo received: ${JSON.stringify(message.content).substring(0, 50)}...`,
      );
    });
  }

  /**
   * Test the WebSocket connection
   */
  public async testConnection(): Promise<void> {
    try {
      this.statusBarItem.text = "$(sync~spin) WS: Connecting...";

      // Attempt to connect
      const connected = await this.wsClient.connect();

      if (!connected) {
        this.statusBarItem.text = "$(error) WS: Connection Failed";
        vscode.window.showErrorMessage("Failed to connect to WebSocket server");
        return;
      }

      // Update status bar
      this.statusBarItem.text = "$(pass) WS: Connected";
      vscode.window.showInformationMessage("Connected to WebSocket server");

      // Send a test message
      const testMessage = {
        type: "test",
        data: {
          message: "Hello from VS Code extension!",
          timestamp: new Date().toISOString(),
        },
      };

      const sent = this.wsClient.sendMessage(testMessage);

      if (sent) {
        vscode.window.showInformationMessage("Test message sent");
      } else {
        vscode.window.showWarningMessage(
          "Test message queued for sending later",
        );
      }
    } catch (error) {
      this.statusBarItem.text = "$(error) WS: Error";
      vscode.window.showErrorMessage(
        `Error testing WebSocket connection: ${error}`,
      );
      console.error("Error testing WebSocket connection:", error);
    }
  }

  /**
   * Dispose of resources
   */
  public dispose(): void {
    this.statusBarItem.dispose();
    this.wsClient.dispose();
  }
}

/**
 * Initialize the WebSocket tester and register commands
 */
export function initializeWebSocketTester(
  context: vscode.ExtensionContext,
): WebSocketTester {
  const tester = new WebSocketTester();

  // Register command
  const command = vscode.commands.registerCommand(
    "agent-s3.testWebSocket",
    () => {
      tester.testConnection();
    },
  );

  context.subscriptions.push(command, tester);

  return tester;
}
