#!/usr/bin/env node
/**
 * Debug VS Code WebSocket connection issues
 */

const WebSocket = require('ws');
const fs = require('fs');

async function debugConnection() {
    console.log('🔍 Debugging VS Code WebSocket Connection Issues');
    console.log('================================================');
    
    // 1. Check connection file
    console.log('\n1. Connection File Check:');
    try {
        const connectionFile = '/Users/noelpatron/Documents/GitHub/agent-s3/.agent_s3_ws_connection.json';
        const config = JSON.parse(fs.readFileSync(connectionFile, 'utf-8'));
        console.log('✅ Connection file found:', config);
        
        const protocol = config.protocol || 'ws';
        const url = `${protocol}://${config.host}:${config.port}`;
        console.log('🔗 Connection URL:', url);
        
        // 2. Test WebSocket connection
        console.log('\n2. WebSocket Connection Test:');
        const ws = new WebSocket(url);
        
        let connected = false;
        let authenticated = false;
        
        ws.on('open', () => {
            console.log('✅ WebSocket connected successfully');
            connected = true;
            
            // Send auth message
            const authMsg = {
                type: 'authenticate',
                content: { token: config.auth_token }
            };
            console.log('📤 Sending auth message:', authMsg);
            ws.send(JSON.stringify(authMsg));
        });
        
        ws.on('message', (data) => {
            const message = JSON.parse(data.toString());
            console.log('📥 Received message:', message);
            
            if (message.type === 'authentication_result' && message.content.success) {
                console.log('✅ Authentication successful');
                authenticated = true;
                
                // Send /help command
                const helpCmd = {
                    type: 'command',
                    content: {
                        command: '/help',
                        args: '',
                        request_id: 'debug-help-test'
                    }
                };
                console.log('📤 Sending /help command:', helpCmd);
                ws.send(JSON.stringify(helpCmd));
            }
            
            if (message.type === 'command_result') {
                console.log('✅ Command result received successfully');
                console.log('📄 Help text preview:', message.content.result.substring(0, 100) + '...');
                ws.close();
            }
        });
        
        ws.on('error', (error) => {
            console.log('❌ WebSocket error:', error.message);
        });
        
        ws.on('close', () => {
            console.log('🔌 WebSocket connection closed');
            
            // 3. Summary
            console.log('\n3. Connection Summary:');
            console.log('Connected:', connected ? '✅' : '❌');
            console.log('Authenticated:', authenticated ? '✅' : '❌');
            
            if (connected && authenticated) {
                console.log('\n🎉 SUCCESS: WebSocket connection working perfectly!');
                console.log('💡 If VS Code extension still fails, the issue is likely:');
                console.log('   - Extension not installed properly');
                console.log('   - Wrong extension version being used');
                console.log('   - VS Code cache issues');
                console.log('   - Extension configuration problems');
            } else {
                console.log('\n❌ FAILURE: WebSocket connection issues detected');
            }
        });
        
    } catch (error) {
        console.log('❌ Error:', error.message);
    }
}

debugConnection();