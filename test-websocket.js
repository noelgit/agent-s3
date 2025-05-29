// test-websocket.js
const WebSocket = require('ws');

const ws = new WebSocket('ws://127.0.0.1:8765'); // Changed localhost to 127.0.0.1

ws.on('open', function open() {
  console.log('Connected to WebSocket server');
  ws.send(JSON.stringify({ type: 'test', payload: 'Hello Server!' }));
});

ws.on('message', function incoming(data) {
  console.log('Received: %s', data);
  ws.close();
});

ws.on('error', function error(err) {
  console.error('WebSocket error:', err.message);
});

ws.on('close', function close() {
  console.log('Disconnected from WebSocket server');
});
