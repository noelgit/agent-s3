// Simple WebSocket server for testing the VS Code extension WebSocket integration
const WebSocket = require("ws");
const fs = require("fs");
const path = require("path");

// Configuration
const PORT = 8080;
const AUTH_TOKEN = "test-token-1234";

console.log("Starting WebSocket test server...");

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
        ws.send(message.toString());
      }
    } catch (err) {
      console.error("[SERVER] Error processing message:", err);
    }
  });

  // Handle disconnection
  ws.on("close", () => {
    console.log("[SERVER] Client disconnected");
  });
});

// Create the connection file on startup
createConnectionFile();

console.log(`WebSocket test server running on port ${PORT}`);
