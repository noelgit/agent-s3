// Simple WebSocket server for testing on port 8765
const WebSocket = require("ws");
const fs = require("fs");
const path = require("path");

// Configuration
const PORT = 8765;
const AUTH_TOKEN = "test-token-8765";

console.log("Starting WebSocket server on port 8765...");

// Create WebSocket server
const wss = new WebSocket.Server({ port: PORT });

// Create connection file
const createConnectionFile = () => {
  const config = {
    host: "localhost",
    port: PORT,
    auth_token: AUTH_TOKEN,
    protocol: "ws",
  };

  const filePath = path.join(process.cwd(), ".agent_s3_ws_connection.json");
  fs.writeFileSync(filePath, JSON.stringify(config, null, 2));
  console.log(`Created connection file at: ${filePath}`);
};

// Handle connections
wss.on("connection", (ws) => {
  console.log("[SERVER] Client connected");
  let isAuthenticated = false;

  // Handle messages
  ws.on("message", (message) => {
    try {
      const data = JSON.parse(message.toString());
      console.log("[SERVER] Received:", data);

      // Handle authentication
      if (data.type === "authentication") {
        if (data.auth_token === AUTH_TOKEN) {
          isAuthenticated = true;
          console.log("[SERVER] Client authenticated");

          // Send authentication successful response
          ws.send(
            JSON.stringify({
              type: "authentication_result",
              success: true,
              message: "Authentication successful",
            }),
          );
        } else {
          console.log("[SERVER] Authentication failed");
          ws.send(
            JSON.stringify({
              type: "authentication_result",
              success: false,
              message: "Invalid authentication token",
            }),
          );
          ws.close();
        }
      } else if (!isAuthenticated) {
        console.log("[SERVER] Unauthenticated message rejected");
        ws.send(
          JSON.stringify({
            type: "error",
            message: "Not authenticated",
          }),
        );
      } else {
        // Echo back the message for testing
        console.log("[SERVER] Echoing message");
        ws.send(JSON.stringify({
          type: "echo",
          original: data,
          timestamp: new Date().toISOString()
        }));
      }
    } catch (err) {
      console.error("[SERVER] Error processing message:", err);
    }
  });

  // Handle disconnection
  ws.on("close", () => {
    console.log("[SERVER] Client disconnected");
  });

  // Handle errors
  ws.on("error", (error) => {
    console.error("[SERVER] WebSocket error:", error);
  });
});

// Handle server events
wss.on("listening", () => {
  console.log(`[SERVER] WebSocket server started on port ${PORT}`);
  createConnectionFile();
});

wss.on("error", (error) => {
  console.error("[SERVER] Server error:", error);
});

// Handle process termination
process.on('SIGINT', () => {
  console.log('\n[SERVER] Shutting down gracefully...');
  wss.close(() => {
    console.log('[SERVER] Server closed');
    process.exit(0);
  });
});

console.log(`[SERVER] Starting WebSocket test server on port ${PORT}...`);
