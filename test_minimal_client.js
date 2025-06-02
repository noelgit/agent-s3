#!/usr/bin/env node
/**
 * Test client for minimal WebSocket server
 */

const WebSocket = require('ws');

async function testMinimalConnection() {
    console.log('🧪 Testing connection to minimal WebSocket server...\n');
    
    const addresses = [
        'ws://localhost:8765',
        'ws://127.0.0.1:8765',
        'ws://[::1]:8765'  // IPv6
    ];
    
    for (const addr of addresses) {
        console.log(`Testing ${addr}...`);
        
        try {
            const ws = new WebSocket(addr);
            
            await new Promise((resolve, reject) => {
                const timeout = setTimeout(() => {
                    ws.close();
                    reject(new Error('Connection timeout'));
                }, 5000);
                
                ws.on('open', () => {
                    clearTimeout(timeout);
                    console.log(`✅ Connected to ${addr}`);
                    
                    // Send test message
                    const testMsg = {
                        type: 'test',
                        content: { message: 'Hello from client!' }
                    };
                    ws.send(JSON.stringify(testMsg));
                    console.log('📤 Sent test message');
                });
                
                ws.on('message', (data) => {
                    const message = JSON.parse(data.toString());
                    console.log('📥 Received:', message);
                    ws.close();
                    resolve();
                });
                
                ws.on('error', (error) => {
                    clearTimeout(timeout);
                    reject(error);
                });
                
                ws.on('close', () => {
                    resolve();
                });
            });
            
            console.log(`✅ SUCCESS: ${addr} works!\n`);
            break;  // Stop on first success
            
        } catch (error) {
            console.log(`❌ FAILED: ${addr} - ${error.message}\n`);
        }
    }
}

testMinimalConnection();