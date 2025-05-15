import * as vscode from 'vscode';
import { WebSocketClient } from './websocket-client';
import * as fs from 'fs';
import * as path from 'path';

/**
 * Test WebSocket connection and functionality
 */
export async function testWebSocketConnection(): Promise<void> {
    console.log("Testing WebSocket connection...");
    
    const wsClient = new WebSocketClient();
    
    // Register test message handler
    wsClient.registerMessageHandler('test', (message) => {
        console.log("Received test message:", message);
    });
    
    // Attempt to connect
    const connected = await wsClient.connect();
    
    if (!connected) {
        console.error("Failed to connect to WebSocket server");
        return;
    }
    
    console.log("WebSocket connection established");
    
    // Send a test message
    const testMessage = {
        type: "test",
        data: {
            message: "This is a test message",
            timestamp: new Date().toISOString()
        }
    };
    
    const sent = wsClient.sendMessage(testMessage);
    
    if (sent) {
        console.log("Test message sent successfully");
    } else {
        console.log("Failed to send test message (may be queued for later)");
    }
    
    // Keep connection open for a short time to receive responses
    console.log("Waiting for responses...");
    await new Promise(resolve => setTimeout(resolve, 5000));
    
    // Clean up
    wsClient.dispose();
    console.log("WebSocket test complete");
}

// Function to add a command to test WebSocket
export function registerTestCommand(context: vscode.ExtensionContext) {
    const command = vscode.commands.registerCommand('agent-s3.testWebSocket', testWebSocketConnection);
    context.subscriptions.push(command);
}
