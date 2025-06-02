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
    console.log('VS Code test - Connected to WebSocket server');
    
    // Simulate the exact message that VS Code should send for /help
    const chatCommand = {
        type: "command",
        content: {
            command: "/help",
            args: "",
            request_id: `chat-${Date.now()}`
        }
    };
    
    console.log('Sending VS Code chat command:', JSON.stringify(chatCommand, null, 2));
    ws.send(JSON.stringify(chatCommand));
});

ws.on('message', function message(data) {
    try {
        const parsed = JSON.parse(data.toString());
        console.log('Received message type:', parsed.type);
        
        if (parsed.type === 'command_result') {
            console.log('✅ COMMAND RESULT RECEIVED:');
            console.log('Command:', parsed.content.command);
            console.log('Success:', parsed.content.success);
            console.log('Result length:', parsed.content.result.length);
            console.log('First 200 chars:', parsed.content.result.substring(0, 200));
            ws.close();
        } else if (parsed.type === 'connection_established') {
            console.log('✅ Connection established');
        } else {
            console.log('Other message:', parsed.type);
        }
    } catch (error) {
        console.log('Raw data:', data.toString());
    }
});

ws.on('error', function error(err) {
    console.error('❌ WebSocket error:', err);
});

ws.on('close', function close() {
    console.log('Connection closed');
    process.exit(0);
});

// Timeout after 15 seconds
setTimeout(() => {
    console.log('❌ Test timed out - no command result received');
    ws.close();
    process.exit(1);
}, 15000);