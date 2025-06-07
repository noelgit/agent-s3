# Agent-S3 Remote Backend Setup Guide

This guide explains how to configure the Agent-S3 VS Code extension to work with remote backend instances, enabling distributed development workflows and remote server deployments.

## Overview

The Agent-S3 VS Code extension now supports both local and remote backend configurations:

- **Local Mode**: Commands are executed directly via the CLI on your local machine
- **Remote Mode**: Commands are sent to a remote Agent-S3 HTTP server via REST API
- **Automatic Fallback**: If remote connection fails, the extension automatically falls back to local CLI execution

## Configuration Priority

The extension uses the following priority order for configuration:

1. **VS Code Settings** (highest priority)
2. **Environment Variables**
3. **Local Configuration File** (`.agent_s3_http_connection.json`)
4. **Default Localhost** (lowest priority)

## VS Code Settings Configuration

Configure remote backend through VS Code settings:

1. Open VS Code Settings (`Cmd/Ctrl + ,`)
2. Search for "agent-s3"
3. Configure the following settings:

### Available Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `agent-s3.remoteHost` | string | `localhost` | Remote server hostname or IP |
| `agent-s3.remotePort` | number | `8081` | Remote server port |
| `agent-s3.authToken` | string | `""` | Authentication token for secure connections |
| `agent-s3.useTls` | boolean | `false` | Use HTTPS instead of HTTP |
| `agent-s3.httpTimeoutMs` | number | `10000` | Request timeout in milliseconds |

### Example VS Code Settings

```json
{
    "agent-s3.remoteHost": "my-agent-server.com",
    "agent-s3.remotePort": 8081,
    "agent-s3.authToken": "your-auth-token-here",
    "agent-s3.useTls": true,
    "agent-s3.httpTimeoutMs": 15000
}
```

## Environment Variables Configuration

Set environment variables for system-wide configuration:

```bash
export AGENT_S3_HOST=my-agent-server.com
export AGENT_S3_PORT=8081
export AGENT_S3_AUTH_TOKEN=your-auth-token-here
export AGENT_S3_USE_TLS=true
export AGENT_S3_HTTP_TIMEOUT_MS=15000
```

## Local Configuration File

Create `.agent_s3_http_connection.json` in your workspace root:

```json
{
    "type": "http",
    "host": "my-agent-server.com",
    "port": 8081,
    "base_url": "https://my-agent-server.com:8081",
    "auth_token": "your-auth-token-here",
    "use_tls": true
}
```

## Remote Server Setup

### 1. Install Agent-S3 on Remote Server

```bash
# Clone the repository
git clone https://github.com/your-org/agent-s3.git
cd agent-s3

# Install dependencies
pip install -r requirements.txt
pip install -e .
```

### 2. Start HTTP Server

```bash
# Start with default settings (localhost:8081)
python -m agent_s3.communication.http_server

# Start with custom host/port
python -m agent_s3.communication.http_server --host 0.0.0.0 --port 8081

# Start with authentication
python -m agent_s3.communication.http_server --auth-token your-secure-token-here
```

### 3. Configure Firewall (if needed)

Ensure the server port (default 8081) is accessible from your VS Code client:

```bash
# Example for Ubuntu/Debian
sudo ufw allow 8081

# Example for CentOS/RHEL
sudo firewall-cmd --permanent --add-port=8081/tcp
sudo firewall-cmd --reload
```

## Security Considerations

### 1. Authentication Tokens

Always use authentication tokens for production deployments:

```bash
# Generate a secure token
openssl rand -hex 32

# Use it in server startup
python -m agent_s3.communication.http_server --auth-token $(openssl rand -hex 32)
```

### 2. TLS/HTTPS

For production, use TLS encryption:

- Set `agent-s3.useTls: true` in VS Code settings
- Configure your server with proper SSL certificates
- Use a reverse proxy like nginx for SSL termination

### 3. Network Security

- Use VPN connections for remote access
- Limit server access to specific IP ranges
- Consider using SSH tunnels for additional security

## Commands and Usage

### Connection Management Commands

Access these commands via the Command Palette (`Cmd/Ctrl + Shift + P`):

- **Agent-S3: Show Connection Status** - Display current connection configuration
- **Agent-S3: Test Backend Connection** - Test connectivity to remote backend

### Chat Integration

All Agent-S3 commands executed through the chat interface will:

1. Try remote HTTP backend first
2. Fall back to local CLI if remote fails
3. Display output directly in the chat window
4. Show connection status and errors

### Example Workflow

1. Configure remote settings in VS Code
2. Test connection: `Cmd/Ctrl + Shift + P` → "Agent-S3: Test Backend Connection"
3. Open chat: `Cmd/Ctrl + Shift + P` → "Agent-S3: Open Chat Window"
4. Execute commands normally - they'll run on the remote server

## Troubleshooting

### Connection Issues

1. **Check Connection Status**:
   ```
   Cmd/Ctrl + Shift + P → "Agent-S3: Show Connection Status"
   ```

2. **Test Connection**:
   ```
   Cmd/Ctrl + Shift + P → "Agent-S3: Test Backend Connection"
   ```

3. **Check Server Logs**:
   ```bash
   # On remote server
   tail -f /path/to/agent-s3/server.log
   ```

### Common Problems

#### "Connection failed" errors
- Verify host/port settings
- Check firewall configuration
- Ensure server is running
- Verify authentication token

#### "Timeout" errors
- Increase `httpTimeoutMs` setting
- Check network latency
- Verify server performance

#### "Authentication failed" errors
- Verify auth token matches server configuration
- Check token format (no extra spaces/characters)

### Fallback Behavior

If remote connection fails, the extension automatically falls back to local CLI execution. Check the output for messages like:

```
HTTP failed, falling back to CLI: [error details]
```

This ensures commands continue working even with connectivity issues.

## Best Practices

### Development Workflow

1. **Local Development**: Use local mode for development and testing
2. **Team Collaboration**: Use shared remote servers for team projects
3. **Production**: Use dedicated remote servers with proper security

### Performance Optimization

1. **Reduce Timeout**: Lower `httpTimeoutMs` for faster fallback to CLI
2. **Use Local Cache**: Keep frequently accessed files locally
3. **Batch Commands**: Combine multiple operations when possible

### Security Best Practices

1. **Rotate Tokens**: Regularly update authentication tokens
2. **Monitor Access**: Log and monitor remote server access
3. **Use TLS**: Always use encryption for production deployments
4. **Limit Scope**: Restrict remote server access to necessary users/IPs

## API Reference

### HTTP Endpoints

The remote backend exposes the following endpoints:

- `GET /health` - Server health check
- `POST /command` - Execute Agent-S3 commands and return results immediately
  (the `/status` endpoint and asynchronous mode are deprecated)

### Request Format

```json
{
    "command": "/request add user authentication",
    "workspace_path": "/path/to/workspace"
}
```

### Response Format

```json
{
    "success": true,
    "result": "Command output here",
    "output": "Detailed output"
}
```

The server processes requests synchronously. Results are returned directly in
the response to `POST /command`, and the previous asynchronous job workflow is
deprecated.

## Contributing

To contribute to the remote backend functionality:

1. Check the connection management code in `src/config/connectionManager.ts`
2. Review HTTP client implementation in `src/http/httpClient.ts`
3. Test with both local and remote configurations
4. Update documentation for new features

## Support

For issues with remote backend setup:

1. Check the troubleshooting section above
2. Review server logs for error details
3. Test with local configuration first
4. Open an issue with connection details (excluding sensitive tokens)
