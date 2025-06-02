#!/usr/bin/env node
const WebSocket = require('ws');
const fs = require('fs');

async function testConnection() {
    try {
        // Read connection config
        const config = JSON.parse(fs.readFileSync('.agent_s3_ws_connection.json', 'utf8'));
        console.log('📡 Connection config:', config);
        
        const ws = new WebSocket(`ws://${config.host}:${config.port}`);
        
        return new Promise((resolve, reject) => {
            const timeout = setTimeout(() => {
                reject(new Error('Connection timeout'));
            }, 10000);
            
            ws.on('open', () => {
                console.log('✅ Connected to WebSocket server');
                
                // Authenticate
                ws.send(JSON.stringify({
                    type: "auth",
                    content: { token: config.auth_token }
                }));
            });
            
            ws.on('message', (data) => {
                const message = JSON.parse(data.toString());
                console.log('📨 Received:', message.type);
                
                if (message.type === 'connection_established') {
                    console.log('🔐 Authentication successful');
                    
                    // Test /help command
                    ws.send(JSON.stringify({
                        type: "command",
                        content: {
                            command: "/help",
                            args: "",
                            request_id: `test-${Date.now()}`
                        }
                    }));
                } else if (message.type === 'command_result') {
                    console.log('🎯 Command result received:');
                    console.log(message.content.result);
                    clearTimeout(timeout);
                    ws.close();
                    resolve(true);
                }
            });
            
            ws.on('error', (error) => {
                clearTimeout(timeout);
                reject(error);
            });
            
            ws.on('close', () => {
                console.log('🔌 Connection closed');
            });
        });
    } catch (error) {
        console.error('❌ Test failed:', error.message);
        return false;
    }
}

testConnection()
    .then(() => {
        console.log('\n🎉 Connection test PASSED!');
        process.exit(0);
    })
    .catch((error) => {
        console.error('\n💥 Connection test FAILED:', error.message);
        process.exit(1);
    });
