const WebSocket = require('ws');
const fs = require('fs');

// Simple connection test with better error handling
console.log('Testing WebSocket connection with authentication...');

// Function to test connection with retries
async function testConnection(retries = 5) {
  for (let i = 0; i < retries; i++) {
    try {
      console.log(`\n--- Attempt ${i + 1}/${retries} ---`);
      
      // Check if connection file exists
      if (!fs.existsSync('.agent_s3_ws_connection.json')) {
        console.log('Connection file not found. Server may not be ready yet.');
        await new Promise(resolve => setTimeout(resolve, 2000));
        continue;
      }
      
      // Read connection config
      const config = JSON.parse(fs.readFileSync('.agent_s3_ws_connection.json', 'utf8'));
      console.log('Found connection config:', {
        host: config.host,
        port: config.port,
        pid: config.pid,
        timestamp: new Date(config.timestamp * 1000).toISOString()
      });
      
      // Test the connection
      const result = await new Promise((resolve, reject) => {
        const timeout = setTimeout(() => {
          reject(new Error('Connection timeout'));
        }, 5000);
        
        const ws = new WebSocket(`ws://127.0.0.1:${config.port}`);
        
        ws.on('open', () => {
          console.log('✅ Connected to WebSocket server');
          
          // Send authentication message
          const authMessage = {
            type: "authenticate",
            content: {
              token: config.auth_token
            }
          };
          
          console.log('📤 Sending authentication message...');
          ws.send(JSON.stringify(authMessage));
        });
        
        ws.on('message', (data) => {
          try {
            const message = JSON.parse(data.toString());
            console.log('📥 Received message:', JSON.stringify(message, null, 2));
            
            if (message.type === 'authentication_result') {
              clearTimeout(timeout);
              if (message.content && message.content.success) {
                console.log('🎉 Authentication successful!');
                resolve({ success: true, message: 'Authentication successful' });
              } else {
                resolve({ success: false, message: 'Authentication failed', error: message.content });
              }
              ws.close();
            }
          } catch (error) {
            console.error('Error parsing message:', error);
            resolve({ success: false, message: 'Message parsing error', error: error.message });
          }
        });
        
        ws.on('error', (error) => {
          clearTimeout(timeout);
          console.error('❌ WebSocket error:', error.message);
          resolve({ success: false, message: 'WebSocket error', error: error.message });
        });
        
        ws.on('close', (code, reason) => {
          clearTimeout(timeout);
          console.log(`🔌 Connection closed: ${code} ${reason || ''}`);
          if (!resolved) {
            resolve({ success: false, message: 'Connection closed unexpectedly', code });
          }
        });
        
        let resolved = false;
        const originalResolve = resolve;
        resolve = (result) => {
          if (!resolved) {
            resolved = true;
            originalResolve(result);
          }
        };
      });
      
      if (result.success) {
        console.log('\n🌟 CONNECTION TEST SUCCESSFUL! 🌟');
        return result;
      } else {
        console.log('❌ Connection failed:', result.message);
        if (result.error) {
          console.log('Error details:', result.error);
        }
      }
      
    } catch (error) {
      console.error(`Attempt ${i + 1} failed:`, error.message);
    }
    
    if (i < retries - 1) {
      console.log('Waiting 3 seconds before retry...');
      await new Promise(resolve => setTimeout(resolve, 3000));
    }
  }
  
  console.log('\n❌ All connection attempts failed');
  return { success: false, message: 'All retries failed' };
}

// Run the test
testConnection().then(() => {
  process.exit(0);
}).catch((error) => {
  console.error('Test failed:', error);
  process.exit(1);
});
