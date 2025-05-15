// Simple WebSocket server for testing the VS Code extension WebSocket integration
const WebSocket = require('ws');
const fs = require('fs');
const path = require('path');

// Configuration
const PORT = 8080;
const AUTH_TOKEN = "test-token-1234";

console.log('Starting WebSocket test server...');

// Create WebSocket server
const wss = new WebSocket.Server({ port: PORT });

// Create connection file
const createConnectionFile = () => {
  const config = {
    host: 'localhost',
    port: PORT,
    auth_token: AUTH_TOKEN
  };
  
  const filePath = path.join(process.cwd(), '.agent_s3_ws_connection.json');
  fs.writeFileSync(filePath, JSON.stringify(config, null, 2));
  
  console.log(`Created connection file at: ${filePath}`);
};

// Handle connections
wss.on('connection', (ws) => {
  console.log('[SERVER] Client connected');
  let isAuthenticated = false;
  
  // Handle messages
  ws.on('message', (message) => {
    try {
      const data = JSON.parse(message.toString());
      console.log('[SERVER] Received:', data);
      
      // Handle authentication
      if (data.type === 'authentication') {
        if (data.auth_token === AUTH_TOKEN) {
          isAuthenticated = true;
          console.log('[SERVER] Client authenticated');
          
          // Send authentication success
          ws.send(JSON.stringify({
            type: 'authentication_result',
            success: true
          }));
          
          // Send a test notification
          setTimeout(() => {
            ws.send(JSON.stringify({
              type: 'notification',
              content: {
                title: 'Connection Successful',
                message: 'WebSocket connection established successfully!',
                level: 'info'
              }
            }));
          }, 1000);
        } else {
          console.log('[SERVER] Authentication failed');
          ws.send(JSON.stringify({
            type: 'authentication_result',
            success: false,
            error: 'Invalid authentication token'
          }));
        }
        return;
      }
      
      // Require authentication for other messages
      if (!isAuthenticated) {
        console.log('[SERVER] Unauthenticated message received, ignoring');
        return;
      }
      
      // Handle heartbeat
      if (data.type === 'heartbeat') {
        ws.send(JSON.stringify({
          type: 'heartbeat_response',
          timestamp: new Date().toISOString()
        }));
        return;
      }
      
      // Handle large message performance tests
      if (data.type === 'large_message_test') {
        const receivedSize = data.content?.size || 0;
        const receivedData = data.content?.data || '';
        
        console.log(`[SERVER] Received large message test: ${receivedSize} bytes`);
        
        // Send response without echoing the full data
        ws.send(JSON.stringify({
          type: 'large_message_response',
          size: receivedSize,
          actualSize: receivedData.length,
          time: new Date().getTime(),
          timestamp: new Date().toISOString()
        }));
        return;
      }
      
      // Echo back any other test messages
      ws.send(JSON.stringify({
        type: 'echo',
        content: data,
        timestamp: new Date().toISOString()
      }));
    } catch (error) {
      console.error('[SERVER] Error processing message:', error);
    }
  });
  
  // Handle disconnection
  ws.on('close', () => {
    console.log('[SERVER] Client disconnected');
  });
  
  // Handle errors
  ws.on('error', (error) => {
    console.error('[SERVER] WebSocket error:', error);
  });
});

// Start the server
wss.on('listening', () => {
  console.log(`[SERVER] WebSocket server started on port ${PORT}`);
  createConnectionFile();
});

console.log('[SERVER] Waiting for connections...');
