const WebSocket = require('ws');

const ws = new WebSocket('ws://localhost:8765');

ws.on('open', function open() {
  console.log('Connected to WebSocket server');
  
  // Send authentication
  ws.send(JSON.stringify({
    type: 'authentication',
    content: {
      token: 'test-token-123'
    }
  }));
});

ws.on('message', function message(data) {
  console.log('Received:', data.toString());
});

ws.on('close', function close() {
  console.log('Disconnected from WebSocket server');
});

ws.on('error', function error(err) {
  console.log('WebSocket error:', err);
});

// Keep connection alive for a few seconds
setTimeout(() => {
  console.log('Closing connection...');
  ws.close();
}, 5000);