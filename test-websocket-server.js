// Simple WebSocket server for testing the VS Code extension
const WebSocket = require('ws');
const fs = require('fs');
const path = require('path');

// Configuration
const PORT = 8080;
const AUTH_TOKEN = "test-token-1234";

// Create WebSocket server
const wss = new WebSocket.Server({ port: PORT });

// Store for client connections
let clients = new Map();

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
  console.log('Client connected');
  
  let clientId = null;
  let isAuthenticated = false;
  
  // Handle messages
  ws.on('message', (message) => {
    try {
      const data = JSON.parse(message);
      console.log('Received:', data);
      
      // Handle authentication
      if (data.type === 'authentication') {
        if (data.auth_token === AUTH_TOKEN) {
          isAuthenticated = true;
          clientId = `client-${Date.now()}`;
          clients.set(clientId, ws);
          
          console.log(`Client authenticated: ${clientId}`);
          
          // Send authentication success
          ws.send(JSON.stringify({
            type: 'authentication_result',
            success: true,
            client_id: clientId
          }));
          
          // Send a welcome message
          setTimeout(() => {
            if (ws.readyState === WebSocket.OPEN) {
              ws.send(JSON.stringify({
                type: 'notification',
                content: {
                  title: 'Welcome',
                  message: 'Connected to test server',
                  level: 'info'
                }
              }));
            }
          }, 1000);
        } else {
          console.log('Authentication failed');
          ws.send(JSON.stringify({
            type: 'authentication_result',
            success: false,
            error: 'Invalid authentication token'
          }));
          
          // Close connection after failing authentication
          ws.close();
        }
        return;
      }
      
      // Require authentication for other messages
      if (!isAuthenticated) {
        console.log('Unauthenticated message received, ignoring');
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
      
      // Handle test messages
      if (data.type === 'test') {
        console.log('Test message received:', data);
        
        // Echo back with additional info
        ws.send(JSON.stringify({
          type: 'test',
          content: {
            echo: data.data,
            server_time: new Date().toISOString(),
            message: 'Test message received successfully'
          }
        }));
        
        // Send a sample streaming message sequence
        sendSampleStream(ws);
        return;
      }

      // Handle file streaming request
      if (data.type === 'file_stream') {
        const filePath = path.join(__dirname, 'sample.txt');
        fs.stat(filePath, (err, stats) => {
          if (err) {
            ws.send(JSON.stringify({
              type: 'file_stream_error',
              error: 'File not found'
            }));
            return;
          }

          const stream = fs.createReadStream(filePath, { start: 0, end: stats.size - 1 });
          stream.on('data', chunk => {
            ws.send(JSON.stringify({
              type: 'file_stream_content',
              content: chunk.toString()
            }));
          });
          stream.on('end', () => {
            ws.send(JSON.stringify({
              type: 'file_stream_end'
            }));
          });
          stream.on('error', (streamErr) => {
            ws.send(JSON.stringify({
              type: 'file_stream_error',
              error: streamErr.message
            }));
          });
        });
        return;
      }
      
      // Handle other messages
      console.log(`Received message of type ${data.type}`);
    } catch (error) {
      console.error('Error processing message:', error);
    }
  });
  
  // Handle disconnection
  ws.on('close', () => {
    console.log(`Client disconnected${clientId ? ': ' + clientId : ''}`);
    if (clientId) {
      clients.delete(clientId);
    }
  });
  
  // Handle errors
  ws.on('error', (error) => {
    console.error('WebSocket error:', error);
    if (clientId) {
      clients.delete(clientId);
    }
  });
});

// Send a sample streaming message sequence
function sendSampleStream(ws) {
  const streamId = `stream-${Date.now()}`;
  
  // Stream start
  ws.send(JSON.stringify({
    type: 'stream_start',
    content: {
      stream_id: streamId,
      source: 'test-server',
      mime_type: 'text/plain'
    }
  }));
  
  // Stream content in chunks
  const message = "This is a test of the streaming functionality. The message is broken into multiple chunks to simulate real-time streaming of content from the server to the client.";
  const chunks = message.split(' ');
  
  let index = 0;
  const interval = setInterval(() => {
    if (index >= chunks.length || ws.readyState !== WebSocket.OPEN) {
      clearInterval(interval);
      
      // Send stream end if still connected
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({
          type: 'stream_end',
          content: {
            stream_id: streamId,
            status: 'completed'
          }
        }));
      }
      return;
    }
    
    // Send next chunk
    ws.send(JSON.stringify({
      type: 'stream_content',
      content: {
        stream_id: streamId,
        content: chunks[index] + ' '
      }
    }));
    
    index++;
  }, 200);
}

// Start the server
wss.on('listening', () => {
  console.log(`WebSocket server started on port ${PORT}`);
  createConnectionFile();
});

console.log('Starting WebSocket test server...');
