#!/usr/bin/env node
/**
 * Test IPv4 vs IPv6 connection issues
 */

const WebSocket = require('ws');

async function testConnections() {
    console.log('Testing different connection addresses...\n');
    
    const addresses = [
        'ws://localhost:8765',      // May resolve to IPv6
        'ws://127.0.0.1:8765',     // Explicit IPv4
        'ws://0.0.0.0:8765'        // Broadcast address
    ];
    
    for (const addr of addresses) {
        console.log(`Testing ${addr}...`);
        
        try {
            const ws = new WebSocket(addr);
            
            await new Promise((resolve, reject) => {
                const timeout = setTimeout(() => {
                    ws.close();
                    reject(new Error('Connection timeout'));
                }, 3000);
                
                ws.on('open', () => {
                    clearTimeout(timeout);
                    console.log(`✅ SUCCESS: Connected to ${addr}`);
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
        } catch (error) {
            console.log(`❌ FAILED: ${addr} - ${error.message}`);
        }
    }
}

testConnections();