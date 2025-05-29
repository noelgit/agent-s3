#!/usr/bin/env node
/**
 * Standalone WebSocket test script for Agent-S3
 * This script tests WebSocket connectivity without VS Code dependencies
 */

const WebSocket = require('ws');
const fs = require('fs');
const path = require('path');

// Configuration
const CONFIG_FILE = '.agent_s3_ws_connection.json';
const DEFAULT_CONFIG = {
  host: 'localhost',
  port: 8765,
  protocol: 'ws',
  auth_token: 'test-token'
};

/**
 * Load WebSocket configuration
 */
function loadConfig() {
  const configPath = path.join(process.cwd(), CONFIG_FILE);
  
  if (fs.existsSync(configPath)) {
    try {
      const config = JSON.parse(fs.readFileSync(configPath, 'utf8'));
      console.log(`✅ Loaded config from ${configPath}`);
      return config;
    } catch (error) {
      console.warn(`⚠️  Failed to parse config file: ${error.message}`);
    }
  } else {
    console.log(`ℹ️  Config file not found at ${configPath}, using defaults`);
  }
  
  return DEFAULT_CONFIG;
}

/**
 * Test WebSocket connection
 */
async function testWebSocketConnection() {
  console.log('🚀 Starting WebSocket connection test...\n');
  
  const config = loadConfig();
  const url = `${config.protocol}://${config.host}:${config.port}`;
  
  console.log(`📡 Connecting to: ${url}`);
  
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(url);
    let connected = false;
    let authenticated = false;
    
    // Set connection timeout
    const timeout = setTimeout(() => {
      if (!connected) {
        console.error('❌ Connection timeout');
        ws.terminate();
        reject(new Error('Connection timeout'));
      }
    }, 10000);
    
    ws.on('open', () => {
      connected = true;
      clearTimeout(timeout);
      console.log('✅ WebSocket connection established');
      
      // Send authentication message if token is available
      if (config.auth_token) {
        console.log('🔐 Sending authentication...');
        ws.send(JSON.stringify({
          type: 'authentication',
          auth_token: config.auth_token
        }));
      } else {
        console.log('ℹ️  No auth token configured, skipping authentication');
        // Send a test message directly
        sendTestMessage(ws);
      }
    });
    
    ws.on('message', (data) => {
      try {
        const message = JSON.parse(data.toString());
        console.log('📨 Received message:', JSON.stringify(message, null, 2));
        
        // Handle authentication result
        if (message.type === 'authentication_result') {
          if (message.success) {
            authenticated = true;
            console.log('✅ Authentication successful');
            sendTestMessage(ws);
          } else {
            console.error('❌ Authentication failed:', message.error);
            ws.close();
            reject(new Error('Authentication failed'));
          }
        }
        
        // Handle test response
        if (message.type === 'test_response') {
          console.log('✅ Test message responded successfully');
          setTimeout(() => {
            ws.close();
            resolve(true);
          }, 1000);
        }
        
        // Handle heartbeat
        if (message.type === 'heartbeat') {
          console.log('💓 Received heartbeat, sending response');
          ws.send(JSON.stringify({
            type: 'heartbeat_response',
            timestamp: new Date().toISOString()
          }));
        }
        
      } catch (error) {
        console.warn('⚠️  Failed to parse message:', error.message);
        console.log('Raw message:', data.toString());
      }
    });
    
    ws.on('error', (error) => {
      console.error('❌ WebSocket error:', error.message);
      reject(error);
    });
    
    ws.on('close', (code, reason) => {
      console.log(`🔌 Connection closed. Code: ${code}, Reason: ${reason || 'No reason provided'}`);
      if (connected && (authenticated || !config.auth_token)) {
        resolve(true);
      } else {
        reject(new Error('Connection closed unexpectedly'));
      }
    });
    
    function sendTestMessage(websocket) {
      console.log('📤 Sending test message...');
      const testMessage = {
        type: 'test',
        data: {
          message: 'This is a test message from VS Code extension test',
          timestamp: new Date().toISOString(),
          test_id: Math.random().toString(36).substr(2, 9)
        }
      };
      
      websocket.send(JSON.stringify(testMessage));
      
      // If no response in 5 seconds, consider test complete
      setTimeout(() => {
        if (websocket.readyState === WebSocket.OPEN) {
          console.log('ℹ️  No test response received, but connection is working');
          websocket.close();
          resolve(true);
        }
      }, 5000);
    }
  });
}

/**
 * Main test function
 */
async function main() {
  try {
    await testWebSocketConnection();
    console.log('\n🎉 WebSocket test completed successfully!');
    process.exit(0);
  } catch (error) {
    console.error('\n💥 WebSocket test failed:', error.message);
    console.log('\nTroubleshooting tips:');
    console.log('1. Make sure the Agent-S3 WebSocket server is running');
    console.log('2. Check the connection configuration in .agent_s3_ws_connection.json');
    console.log('3. Verify firewall settings and port availability');
    console.log('4. Try running: python -m agent_s3.cli to start the server');
    process.exit(1);
  }
}

// Run the test if this script is executed directly
if (require.main === module) {
  main();
}

module.exports = { testWebSocketConnection, loadConfig };
