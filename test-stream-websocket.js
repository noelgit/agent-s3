const WebSocket = require('ws');

// Read connection info
const fs = require('fs');
const connectionFile = '.agent_s3_ws_connection.json';
let connection;

try {
    connection = JSON.parse(fs.readFileSync(connectionFile, 'utf8'));
    console.log('Connection info:', connection);
} catch (error) {
    console.error('Failed to read connection file:', error.message);
    process.exit(1);
}

const ws = new WebSocket(`ws://127.0.0.1:${connection.port}`);

ws.on('open', function open() {
    console.log('Connected to WebSocket server');
    
    // Send a user input message which should trigger a response
    const userMessage = {
        type: "user_input",
        content: {
            text: "Hello, can you help me with something?"
        }
    };
    
    console.log('Sending user input:', userMessage);
    ws.send(JSON.stringify(userMessage));
    
    // Keep connection alive for a longer time to see responses
    setTimeout(() => {
        console.log('Closing connection...');
        ws.close();
    }, 15000);
});

ws.on('message', function message(data) {
    try {
        const parsed = JSON.parse(data.toString());
        console.log('Received message type:', parsed.type);
        if (parsed.type === 'stream_content' || parsed.type === 'stream_start' || parsed.type === 'stream_end') {
            console.log('Stream message:', JSON.stringify(parsed, null, 2));
        } else {
            console.log('Other message:', JSON.stringify(parsed, null, 2));
        }
    } catch (error) {
        console.log('Received raw data:', data.toString());
    }
});

ws.on('error', function error(err) {
    console.error('WebSocket error:', err);
});

ws.on('close', function close() {
    console.log('WebSocket connection closed');
});