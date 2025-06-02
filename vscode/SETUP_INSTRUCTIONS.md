# Agent-S3 VS Code Extension Setup Instructions

## Quick Setup

### 1. Start the HTTP Server

```bash
# Navigate to the agent-s3 repository
cd /path/to/agent-s3

# Start the HTTP server
python -m agent_s3.cli
```

Expected output:
```
Agent-S3 server mode started. HTTP server running at http://localhost:8081
Available endpoints: GET /health, GET /help, POST /command
Press Ctrl+C to stop.
```

### 2. Install VS Code Extension

1. Open VS Code in the agent-s3 workspace
2. Press `Ctrl+Shift+P` to open command palette
3. Run "Extensions: Install from VSIX..."
4. Select `vscode/agent-s3-0.1.0.vsix`

### 3. Test the Extension

1. Press `Ctrl+Shift+P`
2. Run "Agent-S3: Show help"
3. Verify help content appears in a new document

## Architecture

### HTTP Communication

The system now uses a simple HTTP-based architecture:

1. **Backend**: Python HTTP server on port 8081
2. **Frontend**: VS Code extension using fetch API
3. **Fallback**: Direct CLI command execution

### Communication Flow

1. User triggers command in VS Code
2. Extension attempts HTTP request to localhost:8081
3. If HTTP fails, extension falls back to CLI execution
4. Results displayed in VS Code document

## Commands Available

All original commands are preserved:

- `Agent-S3: Show help` - Display help information
- `Agent-S3: Initialize workspace` - Initialize workspace
- `Agent-S3: Make change request` - Submit change request
- `Agent-S3: Run automated design` - Run design process
- `Agent-S3: Open Chat Window` - Open interactive chat
- `Agent-S3: Open Interactive View` - Open interactive view

## Troubleshooting

### HTTP Connection Issue

**Symptom**: Commands show "Agent-S3 HTTP Server: Not running. Using CLI mode."

**Solution**: 
```bash
# Check if server is running
curl http://localhost:8081/health

# If not running, start it
python -m agent_s3.cli

# Verify it starts successfully and shows:
# "HTTP server started on http://localhost:8081"
```

### Port Already in Use

**Symptom**: `OSError: [Errno 48] Address already in use`

**Solution**:
```bash
# Find process using port 8081
lsof -i :8081

# Kill the process
kill <PID>

# Restart server
python -m agent_s3.cli
```

### Extension Not Loading

**Symptom**: Commands not appearing in command palette

**Solution**:
1. Check VS Code Developer Console (Help > Toggle Developer Tools)
2. Look for extension activation messages
3. Verify extension is enabled in Extensions view
4. Reload VS Code window if needed

## Implementation Details

### HTTP Endpoints

- `GET /health` - Returns `{"status": "ok"}`
- `GET /help` - Returns help text
- `POST /command` - Accepts `{"command": "/help"}` and returns results

### Extension Behavior

1. **HTTP First**: Always tries HTTP communication first
2. **CLI Fallback**: Falls back to spawning CLI commands if HTTP fails
3. **Result Display**: Shows command output in new VS Code document
4. **Error Handling**: Graceful error messages for failures

### File Changes

**Modified Files:**
- `agent_s3/cli/__init__.py` - Updated to start HTTP server
- `agent_s3/coordinator/__init__.py` - Updated communication layer
- `vscode/extension.ts` - Rewritten for HTTP communication

**New Files:**
- `agent_s3/communication/http_server.py` - HTTP server implementation

**Removed Files:**
- All WebSocket-related files and dependencies

## Testing

### Manual Testing

```bash
# Test HTTP endpoints directly
curl http://localhost:8081/health
curl http://localhost:8081/help
curl -X POST -H "Content-Type: application/json" \
  -d '{"command":"/help"}' http://localhost:8081/command

# Test CLI fallback
python -m agent_s3.cli /help
```

### VS Code Testing

1. Open command palette (`Ctrl+Shift+P`)
2. Run each Agent-S3 command
3. Verify results appear in new documents
4. Check VS Code Developer Console for any errors

## Migration Benefits

- **Simplified Architecture**: No WebSocket connection management
- **Better Reliability**: HTTP is stateless and more robust
- **Easier Debugging**: Standard HTTP tools work for testing
- **Graceful Fallback**: CLI commands always work as backup
- **Reduced Complexity**: Fewer moving parts and dependencies