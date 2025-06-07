#!/bin/bash

# Agent-S3 Remote Backend Implementation - Verification Script
# This script helps verify the remote backend functionality is working correctly

echo "🔍 Agent-S3 Remote Backend Verification"
echo "========================================"

# Check if we're in the correct directory
if [ ! -f "package.json" ]; then
    echo "❌ Error: Run this script from the vscode directory"
    exit 1
fi

echo "✅ Running from vscode directory"

# Check if required files exist
echo ""
echo "📁 Checking required files..."

required_files=(
    "src/config/connectionManager.ts"
    "src/http/httpClient.ts"
    "REMOTE_BACKEND_SETUP.md"
    "IMPLEMENTATION_SUMMARY.md"
)

for file in "${required_files[@]}"; do
    if [ -f "$file" ]; then
        echo "✅ $file exists"
    else
        echo "❌ $file missing"
    fi
done

# Check package.json for new settings
echo ""
echo "⚙️  Checking VS Code settings in package.json..."

if grep -q "remoteHost" package.json; then
    echo "✅ remoteHost setting found"
else
    echo "❌ remoteHost setting missing"
fi

if grep -q "authToken" package.json; then
    echo "✅ authToken setting found"
else
    echo "❌ authToken setting missing"
fi

if grep -q "testConnection" package.json; then
    echo "✅ testConnection command found"
else
    echo "❌ testConnection command missing"
fi

# Try to compile
echo ""
echo "🔨 Testing compilation..."
if npm run compile; then
    echo "✅ Extension compiles successfully"
else
    echo "❌ Compilation failed"
    exit 1
fi

# Check if out directory was created
if [ -d "out" ]; then
    echo "✅ Output directory created"
    
    if [ -f "out/extension.js" ]; then
        echo "✅ Main extension file compiled"
    else
        echo "❌ Main extension file missing"
    fi
    
    if [ -f "out/src/config/connectionManager.js" ]; then
        echo "✅ ConnectionManager compiled"
    else
        echo "❌ ConnectionManager missing"
    fi
    
    if [ -f "out/src/http/httpClient.js" ]; then
        echo "✅ HttpClient compiled"
    else
        echo "❌ HttpClient missing"
    fi
else
    echo "❌ Output directory not created"
fi

echo ""
echo "🧪 Manual Testing Recommendations:"
echo "=================================="
echo "1. Open VS Code in this workspace"
echo "2. Press F5 to launch Extension Development Host"
echo "3. In the new window, open Command Palette (Cmd+Shift+P)"
echo "4. Try these commands:"
echo "   - 'Agent-S3: Show Connection Status'"
echo "   - 'Agent-S3: Test Backend Connection'"
echo "   - 'Agent-S3: Open Chat Window'"
echo "5. In chat, try commands like '/help' or '/config'"
echo ""
echo "🌐 Remote Backend Testing:"
echo "========================="
echo "1. Start a remote server:"
echo "   python -m agent_s3.communication.http_server --host 0.0.0.0 --port 8081"
echo "2. Configure VS Code settings:"
echo "   - agent-s3.remoteHost: 'localhost'"
echo "   - agent-s3.remotePort: 8081"
echo "3. Test connection using the commands above"
echo ""
echo "✅ Verification script completed!"
echo "📖 See REMOTE_BACKEND_SETUP.md for detailed setup instructions"
echo "📋 See IMPLEMENTATION_SUMMARY.md for implementation details"
