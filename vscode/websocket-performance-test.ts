import * as vscode from "vscode";
import * as fs from "fs";
import * as path from "path";
import { WebSocketClient } from "./websocket-client";

/**
 * Performance test for WebSocket with large messages
 */
export class WebSocketPerformanceTest {
  private wsClient: WebSocketClient;
  private outputChannel: vscode.OutputChannel;

  constructor() {
    this.wsClient = new WebSocketClient();
    this.outputChannel = vscode.window.createOutputChannel(
      "WebSocket Performance Test",
    );
  }

  /**
   * Run the performance test for large messages
   */
  public async runPerformanceTest(): Promise<void> {
    this.outputChannel.clear();
    this.outputChannel.show();
    this.log("Starting WebSocket performance test...");

    // Connect to WebSocket server
    this.log("Connecting to WebSocket server...");
    const connected = await this.wsClient.connect();

    if (!connected) {
      this.log("ERROR: Failed to connect to WebSocket server");
      return;
    }

    this.log("Connected to WebSocket server");

    // Register a handler for large message responses
    this.wsClient.registerMessageHandler(
      "large_message_response",
      (message: any) => {
        this.log(
          `Received large message response: Size=${message.size} bytes, Time=${message.time}ms`,
        );
      },
    );

    // Generate test data of different sizes
    const testSizes = [10, 100, 1000, 10000, 100000, 1000000];

    for (const size of testSizes) {
      await this.testMessageSize(size);
      // Small delay between tests
      await new Promise((resolve) => setTimeout(resolve, 1000));
    }

    this.log("Performance test complete");
  }

  /**
   * Test sending a message of a specific size
   */
  private async testMessageSize(size: number): Promise<void> {
    this.log(`Testing message size: ${size} bytes`);

    // Generate test data
    const testData = this.generateTestData(size);

    // Measure send time
    const startTime = Date.now();

    // Send the test message
    const message = {
      type: "large_message_test",
      content: {
        size,
        data: testData,
      },
    };

    const sent = this.wsClient.sendMessage(message);

    if (!sent) {
      this.log(`ERROR: Failed to send ${size} byte message`);
      return;
    }

    const sendTime = Date.now() - startTime;
    this.log(`Sent ${size} byte message in ${sendTime}ms`);

    // Wait for response
    await new Promise((resolve) => setTimeout(resolve, 500));
  }

  /**
   * Generate test data of a specific size
   */
  private generateTestData(size: number): string {
    // Create a pattern that repeats to fill the required size
    const pattern =
      "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";
    let result = "";

    while (result.length < size) {
      result += pattern.substring(
        0,
        Math.min(pattern.length, size - result.length),
      );
    }

    return result;
  }

  /**
   * Log a message to the output channel
   */
  private log(message: string): void {
    const timestamp = new Date().toISOString();
    this.outputChannel.appendLine(`[${timestamp}] ${message}`);
  }

  /**
   * Dispose of resources
   */
  public dispose(): void {
    this.wsClient.dispose();
    this.outputChannel.dispose();
  }
}

/**
 * Register the performance test command
 */
export function registerPerformanceTestCommand(
  context: vscode.ExtensionContext,
): void {
  const performanceTest = new WebSocketPerformanceTest();

  const command = vscode.commands.registerCommand(
    "agent-s3.testWebSocketPerformance",
    () => {
      performanceTest.runPerformanceTest();
    },
  );

  context.subscriptions.push(command, performanceTest);
}
