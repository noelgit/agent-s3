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
    
    // Send /help command to test coordinator integration
    const commandMessage = {
        type: "command",
        content: {
            command: "/help",
            args: "",
            request_id: `test-help-${Date.now()}`
        }
    };
    
    console.log('Sending command:', commandMessage);
    ws.send(JSON.stringify(commandMessage));
    
    // Keep connection alive for a longer time to see responses
    setTimeout(() => {
        console.log('Closing connection...');
        ws.close();
    }, 20000);
});

ws.on('message', function message(data) {
    try {
        const parsed = JSON.parse(data.toString());
        console.log('Received message type:', parsed.type);
        if (parsed.type === 'command_result') {
            console.log('COMMAND RESULT:', JSON.stringify(parsed, null, 2));
            console.log('Result text:', parsed.content.result);
            ws.close(); // Close after getting result
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