const WebSocket = require('ws');
const fs = require('fs');

console.log('Starting WebSocket test...');

// Read the connection config
try {
  const config = JSON.parse(fs.readFileSync('.agent_s3_ws_connection.json', 'utf8'));
  console.log('Connection config:', config);
  testConnection(config);
} catch (error) {
  console.error('Failed to read config:', error);
  process.exit(1);
}

function testConnection(config) {

  // Create WebSocket connection
  const url = `ws://127.0.0.1:${config.port}`;
  console.log('Connecting to:', url);
  const ws = new WebSocket(url);

ws.on('open', function open() {
  console.log('Connected to WebSocket server');
  
  // Send authentication message
  const authMessage = {
    type: "authenticate",
    content: {
      token: config.auth_token
    }
  };
  
  console.log('Sending auth message:', JSON.stringify(authMessage));
  ws.send(JSON.stringify(authMessage));
});

ws.on('message', function message(data) {
  try {
    const parsed = JSON.parse(data.toString());
    console.log('Received message:', JSON.stringify(parsed, null, 2));
    
    // If authentication was successful, test sending a message
    if (parsed.type === 'authentication_result' && parsed.content && parsed.content.success) {
      console.log('Authentication successful! Sending test message...');
      
      setTimeout(() => {
        const testMessage = {
          type: "user_input",
          content: {
            text: "Hello from test client!"
          }
        };
        console.log('Sending test message:', JSON.stringify(testMessage));
        ws.send(JSON.stringify(testMessage));
      }, 1000);
    }
  } catch (error) {
    console.error('Error parsing message:', error);
    console.log('Raw message:', data.toString());
  }
});

ws.on('error', function error(err) {
  console.error('WebSocket error:', err);
});

ws.on('close', function close() {
  console.log('WebSocket connection closed');
});

  // Keep the process running for a bit
  setTimeout(() => {
    console.log('Closing connection...');
    ws.close();
    process.exit(0);
  }, 10000);
}
