# Agent-S3 Deployment Manual

## Overview

Agent-S3 is a comprehensive AI coding agent system consisting of multiple integrated components that work together to provide intelligent code generation, planning, and deployment capabilities. This manual provides step-by-step instructions for building, packaging, and deploying the complete system.

**Production-Ready**: This manual includes troubleshooting for common production startup issues, including HTTP server initialization and tech stack detection hanging problems that have been resolved in the current version.

## System Architecture

The Agent-S3 system consists of:

1. **Core Python Package** (`agent_s3/`) - Main AI agent backend with adaptive configuration
2. **VS Code Extension** (`vscode/`) - IDE integration
3. **Webview UI** (`vscode/webview-ui/`) - React-based frontend
4. **Deployment Manager** - Built-in application deployment capabilities
5. **Adaptive Configuration System** - Dynamic configuration optimization and management
6. **Context Management** - Intelligent context processing with embeddings and search

## Prerequisites

### Required Software
- **Python 3.10+** (Required for agent_s3 package and Pydantic v2 compatibility)
- **Node.js 16+** (Required for VS Code extension and webview UI)
- **npm or yarn** (Package management)
- **Git** (Version control)
- **Visual Studio Code** (For extension development/testing)

### Required Accounts/Services
- **GitHub Account** (For repository access and integration features)
- **LLM API Keys** (OpenAI, Anthropic, or other supported providers via OpenRouter)
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

# Validate Pydantic v2 compatibility
python -c "
import pydantic
print(f'Pydantic version: {pydantic.__version__}')
assert pydantic.__version__.startswith('2.'), 'Pydantic v2 required'
print('✅ Pydantic v2 validation passed')
"

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
# Start the system (should complete startup without hanging)
python -m agent_s3.cli

# Expected startup sequence:
# 1. Configuration loading
# 2. LLM model configuration loading  
# 3. Context management initialization
# 4. Tech stack detection (should complete in <5 seconds)
# 5. HTTP server startup on port 8081
# 6. "Agent-S3 server mode started" message

# If startup hangs at tech stack detection, see Section 8.4 troubleshooting

# Verify HTTP server is running
lsof -i :8081

# Test HTTP connectivity in another terminal
python -c "
import asyncio
import requests
import json

def test():
    try:
        response = requests.get('http://localhost:8081/health')
        if response.status_code == 200:
            print('✅ HTTP server connectivity successful')
        else:
            print(f'❌ HTTP server returned status {response.status_code}')
    except Exception as e:
        print(f'❌ HTTP test failed: {e}')

test()
"

# Test deployment manager
python -c "
from agent_s3.deployment_manager import DeploymentManager
dm = DeploymentManager()
print('✅ Deployment manager initialized successfully')
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
    "max_checkpoints": 10,
    "embedding": {
      "chunk_size": 1000,
      "chunk_overlap": 200
    },
    "search": {
      "bm25": {
        "k1": 1.2,
        "b": 0.75
      }
    },
    "summarization": {
      "threshold": 2000,
      "compression_ratio": 0.5
    },
    "importance_scoring": {
      "code_weight": 1.0,
      "comment_weight": 0.8,
      "metadata_weight": 0.7,
      "framework_weight": 0.9
    }
  },
  "adaptive_config": {
    "auto_adjust": true,
    "profile_repo_on_start": true,
    "metrics_collection": true,
    "optimization_interval": 3600
  },
  "http": {
    "host": "localhost",
    "port": 8081
  }
}
```

### 4.2 LLM Model Configuration

Configure models in `llm.json` (this is the canonical model configuration):

```json
[
  {
    "model": "google/gemini-2.0-flash-thinking-exp",
    "role": "planner",
    "context_window": 32768,
    "parameters": {
      "temperature": 0.15,
      "top_p": 0.90,
      "top_k": 64,
      "max_output_tokens": 4096
    },
    "pricing_per_million": { "input": 1.25, "output": 5.00 },
    "api": {
      "endpoint": "https://openrouter.ai/api/v1/chat/completions",
      "auth_header": "Authorization: Bearer $OPENROUTER_KEY"
    }
  },
  {
    "model": "google/gemini-2.0-flash-exp",
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

# LLM API Keys (OpenRouter recommended for multi-model access)
OPENROUTER_KEY=your_openrouter_api_key
OPENAI_KEY=your_openai_api_key
ANTHROPIC_API_KEY=your_anthropic_api_key

# GitHub Integration
GITHUB_TOKEN=your_github_token

# Database Configuration (optional)
DATABASE_URL=sqlite:///./agent_s3.db

# HTTP Configuration
HTTP_HOST=localhost
HTTP_PORT=8081

# Deployment Configuration
DEPLOYMENT_HOST=localhost
DEPLOYMENT_PORT=8000

# Adaptive Configuration
ADAPTIVE_CONFIG_REPO_PATH=.
ADAPTIVE_CONFIG_DIR=./.agent_s3/config
ADAPTIVE_METRICS_DIR=./.agent_s3/metrics

# Context Management
CONTEXT_WINDOW_PLANNER=16384
CONTEXT_WINDOW_GENERATOR=16384
TOP_K_RETRIEVAL=10
EVICTION_THRESHOLD=10000
VECTOR_STORE_PATH=.cache

# Performance Tuning
LLM_MAX_RETRIES=3
LLM_INITIAL_BACKOFF=1.0
LLM_BACKOFF_FACTOR=2.0
LLM_DEFAULT_TIMEOUT=60.0
QUERY_CACHE_TTL_SECONDS=3600
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
  "http": {
    "host": "0.0.0.0",
    "port": 8081
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

# Expose HTTP port
EXPOSE 8081

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
  -p 8081:8081 \
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
        - containerPort: 8081
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
  - port: 8081
    targetPort: 8081
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
import requests
from agent_s3.config import Config

def check_http():
    try:
        config = Config()
        config.load()
        host = config.config.get('http', {}).get('host', 'localhost')
        port = config.config.get('http', {}).get('port', 8081)
        
        response = requests.get(f"http://{host}:{port}/health")
        return response.status_code == 200
    except Exception as e:
        print(f"HTTP health check failed: {e}")
        return False
        return False

def check_deployment_manager():
    try:
        from agent_s3.deployment_manager import DeploymentManager
        dm = DeploymentManager()
        return True
    except Exception as e:
        print(f"Deployment manager check failed: {e}")
        return False

def check_adaptive_config():
    try:
        from agent_s3.tools.context_management.adaptive_config.adaptive_config_manager import AdaptiveConfigManager
        manager = AdaptiveConfigManager('.')
        current_config = manager.get_current_config()
        return True
    except Exception as e:
        print(f"Adaptive configuration check failed: {e}")
        return False

def check_pydantic_compatibility():
    try:
        import pydantic
        from agent_s3.config import ConfigModel
        
        # Verify Pydantic v2
        if not pydantic.__version__.startswith('2.'):
            print(f"Pydantic v1 detected ({pydantic.__version__}), v2 required")
            return False
            
        # Test model creation
        config = ConfigModel()
        config_dict = config.model_dump()
        return True
    except Exception as e:
        print(f"Pydantic compatibility check failed: {e}")
        return False

def check_llm_router():
    try:
        from agent_s3.router_agent import RouterAgent
        router = RouterAgent()
        return True
    except Exception as e:
        print(f"LLM router check failed: {e}")
        return False

if __name__ == "__main__":
    checks = [
        ("Pydantic Compatibility", check_pydantic_compatibility),
        ("HTTP Server", check_http),
        ("Deployment Manager", check_deployment_manager),
        ("Adaptive Configuration", check_adaptive_config),
        ("LLM Router", check_llm_router),
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

**Issue: HTTP connection fails**
```bash
# Check if port is open
netstat -tlnp | grep 8081

# Check if HTTP server is responding
curl -s http://localhost:8081/health

# Check firewall
sudo ufw status
sudo ufw allow 8081

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

**Issue: Pydantic v2 compatibility errors**
```bash
# Check Pydantic version
python -c "import pydantic; print(pydantic.__version__)"

# If v1 is installed, upgrade
pip install --upgrade "pydantic>=2.0.0"

# Verify configuration model validation
python -c "
from agent_s3.config import ConfigModel
config = ConfigModel()
print('✅ Configuration model validation passed')
"
```

**Issue: Adaptive configuration not initializing**
```bash
# Check adaptive config directories
ls -la .agent_s3/config/
ls -la .agent_s3/metrics/

# Create directories if missing
mkdir -p .agent_s3/config .agent_s3/metrics

# Check permissions
chmod 755 .agent_s3/config .agent_s3/metrics
```

**Issue: VS Code extension not loading**
```bash
# Check extension installation
code --list-extensions | grep agent-s3

# Check VS Code logs
code --log error
```

**Issue: LLM routing failures**
```bash
# Validate llm.json configuration
python -c "
import json
from agent_s3.router_agent import _validate_entry
with open('llm.json', 'r') as f:
    config = json.load(f)
for i, entry in enumerate(config):
    _validate_entry(entry, i)
print('✅ LLM configuration validation passed')
"
```

### 8.2 Performance Tuning

```bash
# HTTP server configuration is automatically optimized
# No special HTTP configuration needed for performance

# Optimize Python GC
export PYTHONOPTIMIZE=1

# Configure uvloop for better async performance
pip install uvloop

# Enable adaptive configuration optimization
export ADAPTIVE_CONFIG_AUTO_ADJUST=true
export ADAPTIVE_CONFIG_OPTIMIZATION_INTERVAL=3600

# Optimize context management
export CONTEXT_BACKGROUND_OPT_TARGET_TOKENS=16000
export QUERY_CACHE_TTL_SECONDS=7200

# Tune embedding settings for performance
export EMBEDDING_RETRY_COUNT=3
export EMBEDDING_TIMEOUT=30.0

# Configure LLM performance settings
export LLM_MAX_RETRIES=3
export LLM_DEFAULT_TIMEOUT=60.0
```

### 8.3 Debug Mode

```bash
# Enable debug logging
export AGENT_S3_LOG_LEVEL=DEBUG

# Enable adaptive configuration debugging
export ADAPTIVE_CONFIG_DEBUG=true

# Enable context management debugging
export CONTEXT_MANAGEMENT_DEBUG=true

# Enable LLM router debugging
export LLM_ROUTER_DEBUG=true

# Enable VS Code extension debugging
code --log trace --inspect-extensions=5858

# Test adaptive configuration system
python -c "
from agent_s3.tools.context_management.adaptive_config.adaptive_config_manager import AdaptiveConfigManager
from agent_s3.tools.context_management.adaptive_config.config_explainer import ConfigExplainer

# Test config manager
manager = AdaptiveConfigManager('.')
print('✅ Adaptive config manager initialized')

# Test config explainer
explainer = ConfigExplainer(manager)
report = explainer.generate_report()
print('✅ Configuration report generated')
print(f'Current version: {report.get(\"current_version\", \"unknown\")}')
"
```

### 8.4 Production Startup Issues

**Issue: Server hangs during startup at tech stack detection**
```bash
# Symptom: Server starts but hangs indefinitely during initialization
# Common causes: subprocess timeout in tech stack detection

# Check if the issue is in tech_stack_manager.py
python -c "
from agent_s3.tools.tech_stack_manager import TechStackManager
import sys
print(f'Using Python executable: {sys.executable}')
manager = TechStackManager('.')
print('Testing tech stack detection...')
result = manager.detect_tech_stack()
print(f'✅ Tech stack detection completed: {len(result.get(\"languages\", []))} languages detected')
"

# If the above hangs, the issue is subprocess timeout
# Verify the fix is in place:
grep -n "timeout=5" agent_s3/tools/tech_stack_manager.py
grep -n "sys.executable" agent_s3/tools/tech_stack_manager.py

# If missing, the subprocess call needs timeout and proper Python executable
```

**Issue: HTTP server fails with "address already in use" error**
```bash
# Symptom: OSError: [Errno 48] Address already in use
# Common cause: dual Coordinator instantiation in CLI

# Check for multiple Coordinator instances in CLI
grep -n "Coordinator(" agent_s3/cli/__init__.py

# Should only show ONE Coordinator instantiation, not two
# If you see multiple instantiations, this indicates the dual coordinator bug

# Kill any existing processes on port 8081
lsof -ti:8081 | xargs kill -9

# Verify the fix is in place by checking CLI structure
python -c "
# This should not create multiple Coordinator instances
from agent_s3.cli import main
print('✅ CLI imports successfully without dual instantiation')
"
```

**Issue: Server starts but HTTP connection immediately fails**
```bash
# Test HTTP connectivity
python -c "
import requests

def test():
    try:
        response = requests.get('http://localhost:8081/health')
        if response.status_code == 200:
            print('✅ HTTP connection successful')
        else:
            print(f'❌ HTTP returned status {response.status_code}')
    except Exception as e:
        print(f'❌ HTTP connection failed: {e}')

test()
"

# Check server logs for connection errors
python -m agent_s3.cli &
sleep 5
cat .agent_s3_http_connection.json
```

**Issue: Import errors during startup**
```bash
# Symptom: ModuleNotFoundError or ImportError during startup
# Solution: Install package in editable mode

# Reinstall in development mode
pip uninstall agent-s3 -y
pip install -e .

# Verify installation
python -c "
from agent_s3.config import Config
from agent_s3.coordinator import Coordinator
print('✅ Core imports successful')
"

# Test configuration loading
python -c "
from agent_s3.config import Config
config = Config()
config.load()
print('✅ Configuration loads successfully')
"
```

**Issue: Tech stack detection subprocess errors**
```bash
# Symptom: subprocess.TimeoutExpired or hanging Python version check
# This was fixed in production - verify the fix is present

# Check for proper subprocess handling
python -c "
import subprocess
import sys
try:
    result = subprocess.check_output([sys.executable, '--version'], 
                                   stderr=subprocess.STDOUT, 
                                   timeout=5)
    print(f'✅ Python version: {result.decode().strip()}')
except subprocess.TimeoutExpired:
    print('❌ Subprocess timeout - this should be handled gracefully')
except Exception as e:
    print(f'❌ Subprocess error: {e}')
"

# If subprocess calls hang, check tech_stack_manager.py for:
# 1. timeout=5 parameter
# 2. sys.executable instead of 'python'
# 3. Proper exception handling
```

## Phase 9: Adaptive Configuration Management

### 9.1 Understanding Adaptive Configuration

Agent-S3 v0.1.1 introduces an intelligent adaptive configuration system that automatically optimizes performance based on your project characteristics and usage patterns.

**Key Features:**
- **Automatic Optimization**: Adjusts configuration parameters based on performance metrics
- **Project Profiling**: Analyzes your codebase to determine optimal settings
- **Transparent Decisions**: Provides explanations for all configuration changes
- **Version Control**: Maintains history of configuration changes with rollback capability

### 9.2 Configuration Structure

The adaptive system manages several configuration domains:

```json
{
  "context_management": {
    "embedding": {
      "chunk_size": 1000,        // Text chunk size for embeddings
      "chunk_overlap": 200       // Overlap between chunks for continuity
    },
    "search": {
      "bm25": {
        "k1": 1.2,              // Term frequency saturation
        "b": 0.75               // Document length normalization
      }
    },
    "summarization": {
      "threshold": 2000,         // Token threshold for summarization
      "compression_ratio": 0.5   // Target compression ratio
    },
    "importance_scoring": {
      "code_weight": 1.0,        // Relative importance of code
      "comment_weight": 0.8,     // Relative importance of comments
      "metadata_weight": 0.7,    // Relative importance of metadata
      "framework_weight": 0.9    // Relative importance of framework code
    }
  }
}
```

### 9.3 Configuration Templates

The system includes optimized templates for different project types:

**Python Projects:**
```bash
# View available templates
python -c "
from agent_s3.tools.context_management.adaptive_config.config_templates import ConfigTemplateManager
manager = ConfigTemplateManager()
templates = manager.get_available_templates()
print('Available templates:', list(templates.keys()))
"

# Apply Python-optimized template
python -c "
from agent_s3.tools.context_management.adaptive_config.adaptive_config_manager import AdaptiveConfigManager
manager = AdaptiveConfigManager('.')
manager.apply_template('python')
print('✅ Python template applied')
"
```

**JavaScript/TypeScript Projects:**
```bash
python -c "
from agent_s3.tools.context_management.adaptive_config.adaptive_config_manager import AdaptiveConfigManager
manager = AdaptiveConfigManager('.')
manager.apply_template('javascript')
print('✅ JavaScript template applied')
"
```

### 9.4 Monitoring and Optimization

**View Current Configuration:**
```bash
python -c "
from agent_s3.tools.context_management.adaptive_config.config_explainer import ConfigExplainer
from agent_s3.tools.context_management.adaptive_config.adaptive_config_manager import AdaptiveConfigManager

manager = AdaptiveConfigManager('.')
explainer = ConfigExplainer(manager)

# Generate human-readable report
report = explainer.get_human_readable_report()
print(report)
"
```

**Check Optimization Status:**
```bash
python -c "
from agent_s3.tools.context_management.adaptive_config.adaptive_config_manager import AdaptiveConfigManager
manager = AdaptiveConfigManager('.')

if manager.check_optimization_needed():
    print('⚡ Optimization recommended')
    manager.optimize_configuration()
    print('✅ Configuration optimized')
else:
    print('✅ Configuration is optimal')
"
```

**View Configuration History:**
```bash
python -c "
from agent_s3.tools.context_management.adaptive_config.adaptive_config_manager import AdaptiveConfigManager
manager = AdaptiveConfigManager('.')

history = manager.get_config_history()
print(f'Configuration versions: {len(history)}')
for entry in history[-3:]:  # Show last 3 changes
    print(f'Version {entry[\"version\"]}: {entry[\"reason\"]} ({entry[\"timestamp\"]})')
"
```

### 9.5 Manual Configuration Override

**Temporarily Disable Adaptive Configuration:**
```bash
export ADAPTIVE_CONFIG_AUTO_ADJUST=false
```

**Reset to Default Configuration:**
```bash
python -c "
from agent_s3.tools.context_management.adaptive_config.adaptive_config_manager import AdaptiveConfigManager
manager = AdaptiveConfigManager('.')
manager.reset_to_default()
print('✅ Reset to default configuration')
"
```

**Rollback to Previous Version:**
```bash
python -c "
from agent_s3.tools.context_management.adaptive_config.adaptive_config_manager import AdaptiveConfigManager
manager = AdaptiveConfigManager('.')

# Get available versions
history = manager.get_config_history()
if len(history) > 1:
    previous_version = history[1]['version']
    manager.reset_to_version(previous_version)
    print(f'✅ Rolled back to version {previous_version}')
else:
    print('No previous version available')
"
```

## Phase 10: Security Considerations

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
sudo ufw allow from 127.0.0.1 to any port 8081
sudo ufw allow from 10.0.0.0/8 to any port 8081

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
