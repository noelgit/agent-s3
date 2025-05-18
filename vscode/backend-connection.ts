/**
 * Backend connection manager for Agent-S3 that integrates the WebSocket client 
 * with the VS Code extension.
 */

import * as vscode from 'vscode';
import * as fs from 'fs';
import * as path from 'path';
import { WebSocketClient } from './websocket-client';
import { InteractiveWebviewManager } from './webview-ui-loader';

/**
 * Manages the connection to the Agent-S3 backend, integrating terminal and WebSocket communication
 */
export class BackendConnection implements vscode.Disposable {
  private webSocketClient: WebSocketClient;
  private interactiveWebviewManager: InteractiveWebviewManager | undefined;
  private activeStreams: Map<string, StreamingContent> = new Map();
  private outputChannel: vscode.OutputChannel;
  private progressPollingInterval: NodeJS.Timeout | null = null;
  private progressFilePosition = 0;
  
  /**
   * Create a new backend connection
   */
  constructor() {
    // Create WebSocket client
    this.webSocketClient = new WebSocketClient();

    // Monitor connection state to toggle progress polling
    this.webSocketClient.registerConnectionListener((connected) => {
      if (connected) {
        this.stopMonitoringProgress();
      } else {
        this.monitorProgress();
      }
    });
    
    // Create output channel for messages
    this.outputChannel = vscode.window.createOutputChannel("Agent-S3");
    
    // Set up WebSocket message handlers
    this.setupMessageHandlers();
  }
  
  /**
   * Set the interactive webview manager to receive messages
   */
  public setInteractiveWebviewManager(manager: InteractiveWebviewManager): void {
    this.interactiveWebviewManager = manager;
  }
  
  /**
   * Connect to the backend
   */
  public async connect(): Promise<boolean> {
    const result = await this.webSocketClient.connect();
    if (!result) {
      this.monitorProgress();
    }
    return result;
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
    return this.webSocketClient.sendMessage(message);
  }
  
  /**
   * Set up WebSocket message handlers
   */
  private setupMessageHandlers(): void {
    // Set up handlers for streaming content
    this.webSocketClient.registerMessageHandler('thinking', this.handleThinking.bind(this));
    this.webSocketClient.registerMessageHandler('stream_start', this.handleStreamStart.bind(this));
    this.webSocketClient.registerMessageHandler('stream_content', this.handleStreamContent.bind(this));
    this.webSocketClient.registerMessageHandler('stream_end', this.handleStreamEnd.bind(this));
    
    // Set up handlers for interactive components
    this.webSocketClient.registerMessageHandler('interactive_approval', this.handleInteractiveApproval.bind(this));
    this.webSocketClient.registerMessageHandler('interactive_diff', this.handleInteractiveDiff.bind(this));
    this.webSocketClient.registerMessageHandler('progress_indicator', this.handleProgressIndicator.bind(this));
    
    // Set up handlers for other message types
    this.webSocketClient.registerMessageHandler('terminal_output', this.handleTerminalOutput.bind(this));
    this.webSocketClient.registerMessageHandler('notification', this.handleNotification.bind(this));
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
        type: 'THINKING_INDICATOR',
        content: {
          source: source,
          stream_id: streamId
        }
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
      content: '',
      source: source,
      startTime: new Date()
    });
    
    // Notify UI that streaming is starting
    if (this.interactiveWebviewManager) {
      this.interactiveWebviewManager.postMessage({
        type: 'STREAM_START',
        content: {
          stream_id: streamId,
          source: source
        }
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
        source: 'unknown',
        startTime: new Date()
      });
      return;
    }
    
    // Append content
    stream.content += content;
    
    // Send content to UI for incremental update
    if (this.interactiveWebviewManager) {
      this.interactiveWebviewManager.postMessage({
        type: 'STREAM_CONTENT',
        content: {
          stream_id: streamId,
          content: content
        }
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
        type: 'STREAM_END',
        content: {
          stream_id: streamId,
          final_content: stream.content
        }
      });
    }
    
    // Log completion
    this.outputChannel.appendLine(''); // Ensure we end with a newline
    
    // Cleanup
    this.activeStreams.delete(streamId);
  }
  
  /**
   * Handle terminal output messages
   */
  private handleTerminalOutput(message: any): void {
    const content = message.content?.text || '';
    const category = message.content?.category || 'output';
    
    // Show in output channel
    if (category === 'error') {
      this.outputChannel.appendLine(`[ERROR] ${content}`);
    } else {
      this.outputChannel.appendLine(content);
    }
    
    // Forward to webview if available
    if (this.interactiveWebviewManager) {
      this.interactiveWebviewManager.postMessage({
        type: 'TERMINAL_OUTPUT',
        content: {
          text: content,
          category: category
        }
      });
    }
  }
  
  /**
   * Handle notification messages
   */
  private handleNotification(message: any): void {
    const title = message.content?.title || 'Agent-S3';
    const text = message.content?.text || '';
    const level = message.content?.level || 'info';
    
    // Show VS Code notification based on level
    switch (level) {
      case 'error':
        vscode.window.showErrorMessage(`${title}: ${text}`);
        break;
      case 'warning':
        vscode.window.showWarningMessage(`${title}: ${text}`);
        break;
      case 'info':
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
        type: 'INTERACTIVE_APPROVAL',
        content: message.content
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
        type: 'INTERACTIVE_DIFF',
        content: message.content
      });
    }
  }
  
  /**
   * Handle progress indicator messages
   */
  private handleProgressIndicator(message: any): void {
    // Show the interactive panel if not already visible
    if (this.interactiveWebviewManager) {
      this.interactiveWebviewManager.createOrShowPanel();
      // Forward the message to the webview
      this.interactiveWebviewManager.postMessage({
        type: 'PROGRESS_INDICATOR',
        content: message.content
      });
    }
  }

  /**
   * Start polling progress_log.jsonl for updates when WebSocket is unavailable
   */
  private monitorProgress(): void {
    if (this.progressPollingInterval) {
      return;
    }

    const workspaceFolders = vscode.workspace.workspaceFolders;
    if (!workspaceFolders || workspaceFolders.length === 0) {
      return;
    }

    const progressFile = path.join(
      workspaceFolders[0].uri.fsPath,
      'progress_log.jsonl'
    );

    this.progressPollingInterval = setInterval(() => {
      fs.stat(progressFile, (err, stats) => {
        if (err || !stats.isFile()) {
          return;
        }

        if (stats.size <= this.progressFilePosition) {
          return;
        }

        const stream = fs.createReadStream(progressFile, {
          start: this.progressFilePosition,
          encoding: 'utf-8'
        });

        let data = '';
        stream.on('data', chunk => {
          data += chunk;
        });

        stream.on('error', (error) => {
          console.error('Error reading progress file:', error);
        });

        stream.on('end', () => {
          this.progressFilePosition = stats.size;
          const lines = data.split(/\n/).filter(l => l.trim() !== '');
          lines.forEach(line => {
            try {
              const entry = JSON.parse(line);
              this.handleProgressIndicator({ content: entry });
            } catch (e) {
              console.error('Failed to parse progress log entry', e);
            }
          });
        });
      });
    }, 2000);
  }

  /**
   * Stop progress file polling
   */
  private stopMonitoringProgress(): void {
    if (this.progressPollingInterval) {
      clearInterval(this.progressPollingInterval);
      this.progressPollingInterval = null;
    }
  }
  
  /**
   * Dispose of resources
   */
  public dispose(): void {
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
