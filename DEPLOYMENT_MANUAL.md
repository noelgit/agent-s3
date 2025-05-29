# Agent-S3 Deployment Manual

## Overview

Agent-S3 is a comprehensive AI coding agent system consisting of multiple integrated components that work together to provide intelligent code generation, planning, and deployment capabilities. This manual provides step-by-step instructions for building, packaging, and deploying the complete system.

## System Architecture

The Agent-S3 system consists of:

1. **Core Python Package** (`agent_s3/`) - Main AI agent backend
2. **VS Code Extension** (`vscode/`) - IDE integration
3. **Webview UI** (`vscode/webview-ui/`) - React-based frontend
4. **Deployment Manager** - Built-in application deployment capabilities

## Prerequisites

### Required Software
- **Python 3.10+** (Required for agent_s3 package)
- **Node.js 16+** (Required for VS Code extension and webview UI)
- **npm or yarn** (Package management)
- **Git** (Version control)
- **Visual Studio Code** (For extension development/testing)

### Required Accounts/Services
- **GitHub Account** (For repository access and integration features)
- **LLM API Keys** (OpenAI, Anthropic, or other supported providers)
- **Package Registry Access** (PyPI for Python, VS Code Marketplace for extension)

## Phase 1: Development Environment Setup

### 1.1 Clone and Verify Repository

```bash
# Clone the repository
git clone https://github.com/agent-s3/agent-s3.git
cd agent-s3

# Verify directory structure
ls -la
```

Expected structure:
```
agent_s3/           # Core Python package
vscode/             # VS Code extension
docs/               # Documentation
tests/              # Test suites
requirements.txt    # Python dependencies
pyproject.toml      # Python package configuration
package.json        # Node.js dependencies
```

### 1.2 Python Environment Setup

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
# venv\Scripts\activate

# Upgrade pip
pip install --upgrade pip

# Install development dependencies
pip install -r requirements.txt

# Install build tools
pip install build twine

# Install package in development mode
pip install -e .
```

### 1.3 Node.js Environment Setup

```bash
# Install main project dependencies
npm install

# Install VS Code extension dependencies
cd vscode
npm install

# Install VS Code Extension CLI (vsce) globally
npm install -g @vscode/vsce

# Install webview UI dependencies
cd webview-ui
npm install
cd ../..
```

### 1.4 Verify Installation

```bash
# Validate Python dependencies
python validate_dependencies.py

# Check for any missing dependencies
pip check

# Verify Node.js dependencies  
npm audit
cd vscode && npm audit && cd ..
cd vscode/webview-ui && npm audit && cd ../..
```

## Phase 2: Building Components

### 2.1 Build Python Package

```bash
# Clean previous builds
rm -rf build/ dist/ *.egg-info/

# Build source distribution and wheel
python -m build

# Verify build artifacts
ls -la dist/
```

Expected output:
```
agent_s3-0.1.1-py3-none-any.whl
agent_s3-0.1.1.tar.gz
```

### 2.2 Build VS Code Extension

```bash
cd vscode

# Clean previous builds
rm -rf out/ *.vsix

# Compile TypeScript
npm run compile

# Build webview UI (may take several minutes)
npm run build-webview || echo "Build may fail due to dependency conflicts - check logs"

# Package extension (may take several minutes)
vsce package --allow-missing-repository

# Verify extension package
ls -la *.vsix
cd ..
```

Expected output:
```
agent-s3-0.1.0.vsix (approximately 1.1MB)
```

**Performance Note**: The `.vscodeignore` file excludes development files, reducing package size from ~212MB to ~1MB and significantly speeding up the packaging process.

**Note**: Webview-UI Node.js Compatibility Fix Required:
If you encounter `ERR_OSSL_EVP_UNSUPPORTED` errors with Node.js 18+:

1. Add to `vscode/webview-ui/package.json` scripts:
   ```json
   "build": "NODE_OPTIONS=--openssl-legacy-provider react-scripts build"
   ```

2. Downgrade marked.js in `vscode/webview-ui/package.json`:
   ```json
   "marked": "^4.3.0"
   ```

3. Add to `vscode/webview-ui/.env`:
   ```
   SKIP_PREFLIGHT_CHECK=true
   NODE_OPTIONS=--openssl-legacy-provider
   ```

These fixes resolve OpenSSL 3.0 compatibility issues with older webpack versions.

### 2.3 Build Webview UI (Standalone)

```bash
cd vscode/webview-ui

# Clean previous builds
rm -rf build/

# Build production bundle
npm run build

# Verify build
ls -la build/
cd ../..
```

## Phase 3: Testing and Validation

### 3.1 Python Package Testing

```bash
# Install test dependencies if not already installed
pip install pytest

# Ensure package is installed in development mode
pip install -e .

# Run unit tests (some import issues may occur with full test suite)
python -m pytest tests/ -v

# Alternative: Run individual test files to avoid collection conflicts
python -m pytest tests/test_config_pydantic.py -v
python -m pytest tests/test_code_generator.py -v
python -m pytest tests/test_file_tool_paths.py -v

# Run specific test suites
python -m pytest tests/test_deployment_manager.py -v
python -m pytest tests/test_coordinator_*.py -v

# Run integration tests
python -m pytest system_tests/ -v

# Check code coverage
python -m pytest --cov=agent_s3 tests/
```

### 3.2 VS Code Extension Testing

```bash
cd vscode

# Run TypeScript compilation check
npm run typecheck

# Run linting
npm run lint

# Fix linting issues if any
npm run lint:fix

# Test extension loading
code --install-extension agent-s3-0.1.0.vsix
cd ..
```

### 3.3 End-to-End Testing

```bash
# Start the system
python -m agent_s3.cli

# In another terminal, test WebSocket connectivity
cd vscode
npm run test-websocket

# Test deployment manager
python -c "
from agent_s3.deployment_manager import DeploymentManager
dm = DeploymentManager()
print('Deployment manager initialized successfully')
"
```

## Phase 4: Configuration Management

### 4.1 Environment Configuration

Create a production configuration file `config.json`:

```json
{
  "max_attempts": 3,
  "task_state_directory": "./task_snapshots",
  "sandbox_environment": false,
  "host_os_type": "linux",
  "context_management": {
    "optimization_interval": 60,
    "compression_threshold": 1000,
    "checkpoint_interval": 300,
    "max_checkpoints": 10
  },
  "websocket": {
    "host": "localhost",
    "port": 8765,
    "max_message_size": 65536
  }
}
```

### 4.2 LLM Model Configuration

Configure models in `llm.json` (this is the canonical model configuration):

```json
[
  {
    "model": "google/gemini-2.5-pro-preview-03-25",
    "role": "planner",
    "context_window": 1048576,
    "parameters": {
      "temperature": 0.15,
      "top_p": 0.90,
      "top_k": 64,
      "max_output_tokens": 4096
    },
    "pricing_per_million": { "input": 1.25, "output": 10.00 },
    "api": {
      "endpoint": "https://openrouter.ai/api/v1/chat/completions",
      "auth_header": "Authorization: Bearer $OPENROUTER_KEY"
    }
  },
  {
    "model": "google/gemini-2.5-flash-preview",
    "role": "generator",
    "context_window": 1048576,
    "parameters": {
      "temperature": 0.10,
      "top_p": 0.90,
      "top_k": 64,
      "max_output_tokens": 4096
    },
    "pricing_per_million": { "input": 0.15, "output": 0.60 },
    "api": {
      "endpoint": "https://openrouter.ai/api/v1/chat/completions",
      "auth_header": "Authorization: Bearer $OPENROUTER_KEY"
    }
  }
]
```

**Available Roles**: `pre_planner`, `analyzer`, `test_critic`, `initializer`, `planner`, `generator`, `debugger`, `designer`, `orchestrator`, `tool_user`, `explainer`, `file_finder`, `guideline_expert`, `general_qa`, `embedder`, `summarizer`, `context_distiller`

### 4.3 Environment Variables

Create a `.env` template:

```bash
# Core configuration
AGENT_S3_CONFIG_PATH=./config.json
AGENT_S3_LOG_LEVEL=INFO

# LLM API Keys
OPENAI_API_KEY=your_openai_api_key
ANTHROPIC_API_KEY=your_anthropic_api_key

# GitHub Integration
GITHUB_TOKEN=your_github_token

# Database Configuration (optional)
DATABASE_URL=sqlite:///./agent_s3.db

# WebSocket Configuration
WEBSOCKET_HOST=localhost
WEBSOCKET_PORT=8765
WEBSOCKET_MAX_MESSAGE_SIZE=65536

# Deployment Configuration
DEPLOYMENT_HOST=localhost
DEPLOYMENT_PORT=8000
```

### 4.4 Security Configuration

```bash
# Generate secure secret key
python -c "
import secrets
import string
key = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(32))
print(f'SECRET_KEY={key}')
" >> .env

# Set proper file permissions
chmod 600 .env
```

## Phase 5: Distribution Preparation

### 5.1 Python Package Distribution

```bash
# Upload to Test PyPI (recommended first)
python -m twine upload --repository testpypi dist/*

# Test installation from Test PyPI
pip install --index-url https://test.pypi.org/simple/ agent-s3

# Upload to PyPI (production)
python -m twine upload dist/*
```

### 5.2 VS Code Extension Distribution

```bash
cd vscode

# Publish to VS Code Marketplace
npx vsce publish

# Or upload manually to https://marketplace.visualstudio.com/manage
# Upload the agent-s3-0.1.0.vsix file

cd ..
```

### 5.3 Create Release Package

```bash
# Create distribution directory
mkdir -p dist/release

# Copy built artifacts
cp dist/agent_s3-*.whl dist/release/
cp dist/agent_s3-*.tar.gz dist/release/
cp vscode/agent-s3-*.vsix dist/release/

# Copy configuration templates
cp config.json dist/release/config.template.json
cp .env dist/release/.env.template

# Create installation script
cat > dist/release/install.sh << 'EOF'
#!/bin/bash
set -e

echo "Installing Agent-S3..."

# Install Python package
pip install agent_s3-*.whl

# Install VS Code extension
code --install-extension agent-s3-*.vsix

echo "Installation complete!"
echo "Configure your .env file and run 'agent-s3' to start."
EOF

chmod +x dist/release/install.sh

# Create release archive
cd dist/release
tar -czf ../agent-s3-v0.1.1-release.tar.gz *
cd ../..
```

## Phase 6: Production Deployment Options

### 6.1 Local Installation

```bash
# Extract release package
tar -xzf agent-s3-v0.1.1-release.tar.gz
cd agent-s3-v0.1.1-release

# Run installation script
./install.sh

# Configure environment
cp .env.template .env
cp config.template.json config.json

# Edit configuration files with your settings
nano .env
nano config.json
```

### 6.2 Server Deployment

```bash
# Create deployment user
sudo useradd -m -s /bin/bash agent-s3
sudo su - agent-s3

# Install Python and dependencies
sudo apt update
sudo apt install python3.10 python3.10-venv python3-pip nodejs npm

# Create application directory
mkdir -p /opt/agent-s3
cd /opt/agent-s3

# Install Agent-S3
pip install agent-s3

# Create configuration
cat > config.json << 'EOF'
{
  "sandbox_environment": true,
  "host_os_type": "linux",
  "websocket": {
    "host": "0.0.0.0",
    "port": 8765
  }
}
EOF

# Create systemd service
sudo tee /etc/systemd/system/agent-s3.service << 'EOF'
[Unit]
Description=Agent-S3 AI Coding Agent
After=network.target

[Service]
Type=simple
User=agent-s3
WorkingDirectory=/opt/agent-s3
Environment=PATH=/opt/agent-s3/.local/bin:/usr/bin:/bin
ExecStart=/opt/agent-s3/.local/bin/agent-s3
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Enable and start service
sudo systemctl enable agent-s3
sudo systemctl start agent-s3
```

### 6.3 Docker Deployment

Create `Dockerfile`:

```dockerfile
FROM python:3.10-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

# Create app user
RUN useradd -m -s /bin/bash agent-s3
USER agent-s3
WORKDIR /home/agent-s3

# Install Agent-S3
COPY dist/agent_s3-*.whl .
RUN pip install --user agent_s3-*.whl

# Copy configuration
COPY config.json .env ./

# Expose WebSocket port
EXPOSE 8765

# Start Agent-S3
CMD ["/home/agent-s3/.local/bin/agent-s3"]
```

Build and run:

```bash
# Build image
docker build -t agent-s3:latest .

# Run container
docker run -d \
  --name agent-s3 \
  -p 8765:8765 \
  -v $(pwd)/data:/home/agent-s3/data \
  agent-s3:latest
```

### 6.4 Kubernetes Deployment

Create `k8s-deployment.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: agent-s3
spec:
  replicas: 1
  selector:
    matchLabels:
      app: agent-s3
  template:
    metadata:
      labels:
        app: agent-s3
    spec:
      containers:
      - name: agent-s3
        image: agent-s3:latest
        ports:
        - containerPort: 8765
        env:
        - name: AGENT_S3_CONFIG_PATH
          value: "/config/config.json"
        volumeMounts:
        - name: config
          mountPath: /config
        - name: data
          mountPath: /home/agent-s3/data
      volumes:
      - name: config
        configMap:
          name: agent-s3-config
      - name: data
        persistentVolumeClaim:
          claimName: agent-s3-data

---
apiVersion: v1
kind: Service
metadata:
  name: agent-s3-service
spec:
  selector:
    app: agent-s3
  ports:
  - port: 8765
    targetPort: 8765
  type: LoadBalancer
```

Deploy:

```bash
# Create config map
kubectl create configmap agent-s3-config --from-file=config.json

# Create PVC for data
kubectl apply -f - << 'EOF'
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: agent-s3-data
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 10Gi
EOF

# Deploy application
kubectl apply -f k8s-deployment.yaml
```

## Phase 7: Monitoring and Maintenance

### 7.1 Health Checks

Create health check script `health_check.py`:

```python
#!/usr/bin/env python3
import requests
import sys
import websocket
from agent_s3.config import Config

def check_websocket():
    try:
        config = Config()
        config.load()
        host = config.config.get('websocket', {}).get('host', 'localhost')
        port = config.config.get('websocket', {}).get('port', 8765)
        
        ws = websocket.create_connection(f"ws://{host}:{port}")
        ws.send('{"type": "health_check"}')
        response = ws.recv()
        ws.close()
        return True
    except Exception as e:
        print(f"WebSocket health check failed: {e}")
        return False

def check_deployment_manager():
    try:
        from agent_s3.deployment_manager import DeploymentManager
        dm = DeploymentManager()
        return True
    except Exception as e:
        print(f"Deployment manager check failed: {e}")
        return False

if __name__ == "__main__":
    checks = [
        ("WebSocket", check_websocket),
        ("Deployment Manager", check_deployment_manager),
    ]
    
    failed = 0
    for name, check in checks:
        if check():
            print(f"✅ {name}: OK")
        else:
            print(f"❌ {name}: FAILED")
            failed += 1
    
    sys.exit(failed)
```

### 7.2 Log Management

```bash
# Configure log rotation
sudo tee /etc/logrotate.d/agent-s3 << 'EOF'
/opt/agent-s3/logs/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    copytruncate
}
EOF
```

### 7.3 Backup Strategy

Create backup script `backup.sh`:

```bash
#!/bin/bash
BACKUP_DIR="/opt/backups/agent-s3"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Backup configuration
tar -czf "$BACKUP_DIR/config_$TIMESTAMP.tar.gz" \
    /opt/agent-s3/config.json \
    /opt/agent-s3/.env

# Backup data
tar -czf "$BACKUP_DIR/data_$TIMESTAMP.tar.gz" \
    /opt/agent-s3/data/ \
    /opt/agent-s3/task_snapshots/ \
    /opt/agent-s3/logs/

# Cleanup old backups (keep 30 days)
find "$BACKUP_DIR" -name "*.tar.gz" -mtime +30 -delete

echo "Backup completed: $TIMESTAMP"
```

### 7.4 Update Procedure

Create update script `update.sh`:

```bash
#!/bin/bash
set -e

echo "Updating Agent-S3..."

# Stop service
sudo systemctl stop agent-s3

# Backup current installation
./backup.sh

# Update Python package
pip install --upgrade agent-s3

# Update VS Code extension (if applicable)
if command -v code &> /dev/null; then
    code --install-extension agent-s3-latest.vsix
fi

# Restart service
sudo systemctl start agent-s3

# Verify health
python health_check.py

echo "Update completed successfully!"
```

## Phase 8: Troubleshooting

### 8.1 Common Issues

**Issue: WebSocket connection fails**
```bash
# Check if port is open
netstat -tlnp | grep 8765

# Check firewall
sudo ufw status
sudo ufw allow 8765

# Check logs
journalctl -u agent-s3 -f
```

**Issue: Python dependencies conflict**
```bash
# Create fresh virtual environment
python -m venv fresh_venv
source fresh_venv/bin/activate
pip install agent-s3
```

**Issue: VS Code extension not loading**
```bash
# Check extension installation
code --list-extensions | grep agent-s3

# Check VS Code logs
code --log error
```

### 8.2 Performance Tuning

```bash
# Increase WebSocket message size limit
export WEBSOCKET_MAX_MESSAGE_SIZE=131072

# Optimize Python GC
export PYTHONOPTIMIZE=1

# Configure uvloop for better async performance
pip install uvloop
```

### 8.3 Debug Mode

```bash
# Enable debug logging
export AGENT_S3_LOG_LEVEL=DEBUG

# Enable VS Code extension debugging
code --log trace --inspect-extensions=5858
```

## Phase 9: Security Considerations

### 9.1 API Key Management

```bash
# Use environment variables for API keys
export OPENAI_API_KEY="$(cat /etc/agent-s3/openai_key)"

# Set proper permissions
sudo chmod 600 /etc/agent-s3/openai_key
sudo chown agent-s3:agent-s3 /etc/agent-s3/openai_key
```

### 9.2 Network Security

```bash
# Configure firewall
sudo ufw allow from 127.0.0.1 to any port 8765
sudo ufw allow from 10.0.0.0/8 to any port 8765

# Use reverse proxy for external access
# (Configure nginx/apache with SSL)
```

### 9.3 Sandboxing

```bash
# Enable Docker-based sandboxing
docker run --rm -it \
  --security-opt no-new-privileges \
  --cap-drop ALL \
  --network none \
  agent-s3:latest
```

## Conclusion

This deployment manual provides comprehensive instructions for deploying Agent-S3 in various environments, from development to production. Follow the phases sequentially, adapting the configurations to your specific requirements.

For additional support:
- Check the [GitHub Issues](https://github.com/agent-s3/agent-s3/issues)
- Review the [documentation](https://github.com/agent-s3/agent-s3/docs)
- Contact the development team

Remember to:
- Keep your API keys secure
- Regularly backup your configuration and data
- Monitor system health and performance
- Keep the system updated with latest releases
