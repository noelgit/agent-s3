/**
 * WebSocket client for Agent-S3 that handles communication with the backend.
 * This provides real-time streaming of agent responses and progress updates.
 */

import * as vscode from 'vscode';
import * as fs from 'fs';
import * as path from 'path';
import * as WS from 'ws';

/**
 * Message types that can be received from the WebSocket server
 */
enum MessageType {
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
  
  // UI-specific messages
  NOTIFICATION = "notification",
  INTERACTIVE_DIFF = "interactive_diff",
  INTERACTIVE_APPROVAL = "interactive_approval",
  PROGRESS_INDICATOR = "progress_indicator",
  CHAT_MESSAGE = "chat_message",
  CODE_SNIPPET = "code_snippet",
  FILE_TREE = "file_tree",
  TASK_BREAKDOWN = "task_breakdown",
  THINKING_INDICATOR = "thinking_indicator"
}

/**
 * Connection states for the WebSocket client
 */
enum ConnectionState {
  DISCONNECTED,
  CONNECTING,
  CONNECTED,
  AUTHENTICATING,
  AUTHENTICATED,
  RECONNECTING,
  ERROR
}

/**
 * WebSocket client for Agent-S3 that manages the connection to the backend
 */
export class WebSocketClient implements vscode.Disposable {
  private socket: WS.WebSocket | null = null;
  private connectionState: ConnectionState = ConnectionState.DISCONNECTED;
  private reconnectAttempts = 0;
  private reconnectTimeout: NodeJS.Timeout | null = null;
  private heartbeatInterval: NodeJS.Timeout | null = null;
  private messageHandlers: Map<string, ((message: any) => void)[]> = new Map();
  private pendingMessages: any[] = [];
  private connectionConfig: { host: string; port: number; authToken: string } | null = null;
  private activeStreams: Map<string, { buffer: string }> = new Map();
  
  private readonly MAX_RECONNECT_ATTEMPTS = 5;
  private readonly RECONNECT_BASE_DELAY_MS = 1000;
  private readonly HEARTBEAT_INTERVAL_MS = 15000;
  
  /**
   * Create a new WebSocket client instance
   */
  constructor() {
    this.initializeMessageHandlers();
  }
  
  /**
   * Connect to the WebSocket server using configuration from the connection file
   */
  public async connect(): Promise<boolean> {
    // Avoid connecting if already connected or connecting
    if (
      this.connectionState === ConnectionState.CONNECTED ||
      this.connectionState === ConnectionState.CONNECTING ||
      this.connectionState === ConnectionState.AUTHENTICATING
    ) {
      return true;
    }
    
    try {
      // Set state to connecting
      this.connectionState = ConnectionState.CONNECTING;
      
      // Read connection configuration from the backend connection file
      const config = await this.readConnectionFile();
      if (!config) {
        console.error("Failed to read connection configuration");
        this.connectionState = ConnectionState.ERROR;
        return false;
      }
      
      this.connectionConfig = config;
      const { host, port, authToken } = config;
      
      // Create the WebSocket connection
      const url = `ws://${host}:${port}`;
      this.socket = new WS.WebSocket(url);
      
      // Set up event listeners (using Node.js ws library event pattern)
      if (this.socket) {
        this.socket.on('open', () => this.handleOpen(authToken));
        this.socket.on('message', (data) => {
          // Convert incoming data to string and create message event-like object
          const dataString = data.toString();
          const msgEvent = { data: dataString } as MessageEvent;
          this.handleMessage(msgEvent);
        });
        this.socket.on('close', () => this.handleClose());
        this.socket.on('error', (error) => {
          // Create event-like object to maintain compatibility
          const errorEvent = { type: 'error', target: this.socket } as Event;
          this.handleError(errorEvent);
        });
      }
      
      return true;
    } catch (error) {
      console.error("Error connecting to WebSocket server:", error);
      this.connectionState = ConnectionState.ERROR;
      return false;
    }
  }
  
  /**
   * Read the connection file to get WebSocket configuration
   */
  private async readConnectionFile(): Promise<{ host: string; port: number; authToken: string } | null> {
    try {
      // Find the connection file in the workspace
      const workspaceFolders = vscode.workspace.workspaceFolders;
      if (!workspaceFolders) {
        throw new Error("No workspace folder open");
      }
      
      const rootPath = workspaceFolders[0].uri.fsPath;
      const connectionFilePath = path.join(rootPath, '.agent_s3_ws_connection.json');
      
      // Check if the file exists
      if (!fs.existsSync(connectionFilePath)) {
        throw new Error(`Connection file not found: ${connectionFilePath}`);
      }
      
      // Read and parse the connection file
      const fileContent = fs.readFileSync(connectionFilePath, 'utf-8');
      const config = JSON.parse(fileContent);
      
      if (!config.host || !config.port || !config.auth_token) {
        throw new Error("Invalid connection file format");
      }
      
      return {
        host: config.host,
        port: config.port,
        authToken: config.auth_token
      };
    } catch (error) {
      console.error("Error reading connection file:", error);
      return null;
    }
  }
  
  /**
   * Handle the WebSocket open event
   */
  private handleOpen(authToken: string) {
    console.log("WebSocket connection established");
    this.connectionState = ConnectionState.AUTHENTICATING;
    
    // Send authentication message
    this.sendMessage({
      type: "authentication",
      auth_token: authToken
    });
    
    // Set up heartbeat interval
    this.startHeartbeat();
  }
  
  /**
   * Handle incoming WebSocket messages
   */
  private handleMessage(event: MessageEvent | Buffer | ArrayBuffer | Buffer[]) {
    try {
      // Convert data to string if it's not already
      let dataString: string;
      if (event instanceof MessageEvent) {
        dataString = event.data.toString();
      } else if (Buffer.isBuffer(event) || Array.isArray(event)) {
        dataString = event.toString();
      } else if (event instanceof ArrayBuffer) {
        dataString = Buffer.from(event).toString();
      } else {
        // Handle the case where event is already a string-like object
        dataString = String(event);
      }
      
      let messageData: any = JSON.parse(dataString);

      if (messageData.encoding === 'gzip' && messageData.payload) {
        try {
          const buffer = Buffer.from(messageData.payload, 'base64');
          const decompressed = require('zlib').gunzipSync(buffer).toString('utf-8');
          messageData = JSON.parse(decompressed);
        } catch (err) {
          console.error('Failed to decompress message:', err);
          return;
        }
      }

      const message = messageData;
      const type = message.type;
      
      // Handle authentication response
      if (type === "authentication_result") {
        this.handleAuthResult(message);
        return;
      }
      
      // Handle heartbeat response
      if (type === "heartbeat_response" || type === "server_heartbeat") {
        // Reset heartbeat monitoring
        return;
      }
      
      // Handle other message types
      if (type) {
        const handlers = this.messageHandlers.get(type);
        
        if (handlers && handlers.length > 0) {
          // Call all registered handlers for this message type
          handlers.forEach(handler => {
            try {
              handler(message);
            } catch (error) {
              console.error(`Error in message handler for ${type}:`, error);
            }
          });
        } else {
          console.warn(`No handlers registered for message type: ${type}`);
        }
      } else {
        console.warn(`Unknown message type: ${type}`);
      }
    } catch (error) {
      console.error("Error parsing WebSocket message:", error);
    }
  }
  
  /**
   * Handle WebSocket close event
   */
  private handleClose() {
    console.log("WebSocket connection closed");
    
    // Clear heartbeat interval
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval);
      this.heartbeatInterval = null;
    }
    
    // Update connection state
    if (
      this.connectionState !== ConnectionState.DISCONNECTED &&
      this.connectionState !== ConnectionState.ERROR
    ) {
      this.connectionState = ConnectionState.DISCONNECTED;
      
      // Attempt to reconnect if previously connected successfully
      this.scheduleReconnect();
    }
  }
  
  /**
   * Handle WebSocket error event
   */
  private handleError(error: Event | Error | any) {
    console.error("WebSocket error:", error);
    this.connectionState = ConnectionState.ERROR;
  }
  
  /**
   * Handle authentication result
   */
  private handleAuthResult(message: any) {
    const success = message.success === true;
    
    if (success) {
      console.log("Authentication successful");
      this.connectionState = ConnectionState.AUTHENTICATED;
      this.reconnectAttempts = 0;
      
      // Send any pending messages
      this.sendPendingMessages();
    } else {
      console.error("Authentication failed:", message.error || "Unknown error");
      this.connectionState = ConnectionState.ERROR;
    }
  }
  
  /**
   * Start the heartbeat interval
   */
  private startHeartbeat() {
    // Clear any existing interval
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval);
    }
    
    // Set up new heartbeat interval
    this.heartbeatInterval = setInterval(() => {
      if (this.isConnected()) {
        this.sendMessage({
          type: "heartbeat",
          timestamp: new Date().toISOString()
        });
      }
    }, this.HEARTBEAT_INTERVAL_MS);
  }
  
  /**
   * Schedule a reconnection attempt with exponential backoff
   */
  private scheduleReconnect() {
    // Clear any existing reconnect timeout
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }
    
    // Check if max reconnect attempts reached
    if (this.reconnectAttempts >= this.MAX_RECONNECT_ATTEMPTS) {
      console.error("Maximum reconnect attempts reached");
      this.connectionState = ConnectionState.ERROR;
      return;
    }
    
    // Calculate backoff delay with exponential increase
    const delay = this.RECONNECT_BASE_DELAY_MS * Math.pow(2, this.reconnectAttempts);
    console.log(`Scheduling reconnect attempt ${this.reconnectAttempts + 1} in ${delay}ms`);
    
    // Schedule reconnect
    this.connectionState = ConnectionState.RECONNECTING;
    this.reconnectTimeout = setTimeout(() => {
      this.reconnectAttempts++;
      this.connect();
    }, delay);
  }
  
  /**
   * Send a message to the WebSocket server
   */
  public sendMessage(message: any): boolean {
    // If not connected, queue the message for later
    if (!this.isConnected()) {
      this.pendingMessages.push(message);
      
      // Try to connect if disconnected
      if (this.connectionState === ConnectionState.DISCONNECTED) {
        this.connect();
      }
      
      return false;
    }
    
    // Send the message
    try {
      if (this.socket) {
        const jsonString = JSON.stringify(message);
        this.socket.send(jsonString, (error) => {
          if (error) {
            console.error("Error sending WebSocket message:", error);
            this.pendingMessages.push(message);
          } else {
            console.log("Message sent successfully");
          }
        });
        return true;
      }
    } catch (error) {
      console.error("Error sending WebSocket message:", error);
      this.pendingMessages.push(message);
    }
    
    return false;
  }
  
  /**
   * Send any pending messages
   */
  private sendPendingMessages() {
    if (this.pendingMessages.length === 0 || !this.isConnected()) {
      return;
    }
    
    console.log(`Sending ${this.pendingMessages.length} pending messages`);
    
    // Send all pending messages
    const messagesToSend = [...this.pendingMessages];
    this.pendingMessages = [];
    
    messagesToSend.forEach(message => {
      this.sendMessage(message);
    });
  }
  
  /**
   * Check if the WebSocket is connected and authenticated
   */
  public isConnected(): boolean {
    return (
      this.socket !== null &&
      this.socket.readyState === WS.WebSocket.OPEN &&
      this.connectionState === ConnectionState.AUTHENTICATED
    );
  }
  
  /**
   * Initialize message handlers for different message types
   */
  private initializeMessageHandlers() {
    // Set up handlers for streaming messages
    this.registerMessageHandler("thinking", this.handleThinking.bind(this));
    this.registerMessageHandler("stream_start", this.handleStreamStart.bind(this));
    this.registerMessageHandler("stream_content", this.handleStreamContent.bind(this));
    this.registerMessageHandler("stream_end", this.handleStreamEnd.bind(this));
    this.registerMessageHandler("stream_interactive", this.handleStreamInteractive.bind(this));
    
    // Default handlers for other message types 
    // (can be overridden or extended by external registrations)
  }
  
  /**
   * Register a message handler for a specific message type
   */
  public registerMessageHandler(type: string, handler: (message: any) => void) {
    if (!this.messageHandlers.has(type)) {
      this.messageHandlers.set(type, []);
    }
    
    this.messageHandlers.get(type)?.push(handler);
  }
  
  /**
   * Handle thinking indicator messages
   */
  private handleThinking(message: any) {
    // This is just a placeholder - actual handling will be implemented
    // when we integrate with the UI
    console.log("Agent thinking:", message.content?.source || "unknown source");
  }
  
  /**
   * Handle stream start messages
   */
  private handleStreamStart(message: any) {
    const streamId = message.content?.stream_id;
    if (!streamId) {
      console.warn("Received stream start without stream ID");
      return;
    }
    
    // Initialize buffer for this stream
    this.activeStreams.set(streamId, { buffer: "" });
    console.log(`Stream started: ${streamId} from ${message.content?.source || "unknown"}`);
  }
  
  /**
   * Handle stream content messages
   */
  private handleStreamContent(message: any) {
    const streamId = message.content?.stream_id;
    const content = message.content?.content || "";
    
    if (!streamId) {
      console.warn("Received stream content without stream ID");
      return;
    }
    
    // Get the stream buffer
    const stream = this.activeStreams.get(streamId);
    if (!stream) {
      console.warn(`Received content for unknown stream: ${streamId}`);
      this.activeStreams.set(streamId, { buffer: content });
      return;
    }
    
    // Append content to buffer
    stream.buffer += content;
  }
  
  /**
   * Handle stream end messages
   */
  private handleStreamEnd(message: any) {
    const streamId = message.content?.stream_id;
    
    if (!streamId) {
      console.warn("Received stream end without stream ID");
      return;
    }
    
    // Get the final stream content
    const stream = this.activeStreams.get(streamId);
    if (!stream) {
      console.warn(`Received end for unknown stream: ${streamId}`);
      return;
    }
    
    // Process the complete stream content
    console.log(`Stream ended: ${streamId}, content length: ${stream.buffer.length}`);
    
    // Clean up
    this.activeStreams.delete(streamId);
  }

  /**
   * Handle interactive component messages
   */
  private handleStreamInteractive(message: any) {
    const streamId = message.content?.stream_id;
    const component = message.content?.component;
    if (!streamId || !component) {
      console.warn('Invalid interactive message');
      return;
    }

    const stream = this.activeStreams.get(streamId);
    if (!stream) {
      this.activeStreams.set(streamId, { buffer: '' });
    }
    // forward to registered handlers
    const handlers = this.messageHandlers.get('stream_interactive');
    if (handlers) {
      handlers.forEach(h => h(message));
    }
  }
  
  /**
   * Clean up resources
   */
  public dispose() {
    // Clear intervals and timeouts
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval);
      this.heartbeatInterval = null;
    }
    
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }
    
    // Close WebSocket
    if (this.socket) {
      try {
        this.socket.close();
      } catch (error) {
        console.error("Error closing WebSocket:", error);
      }
      this.socket = null;
    }
    
    this.connectionState = ConnectionState.DISCONNECTED;
  }
}
