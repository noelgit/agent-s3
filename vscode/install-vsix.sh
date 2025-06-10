#!/bin/bash

# Install Agent-S3 VS Code Extension from VSIX
# This script will install the packaged extension

echo "🔧 Installing Agent-S3 VS Code Extension..."

# Check if VS Code command line tools are available
if ! command -v code &> /dev/null; then
    echo "❌ VS Code command line tools not found."
    echo "   Please install VS Code and enable 'code' command in PATH"
    echo "   (VS Code > Command Palette > 'Shell Command: Install code command in PATH')"
    exit 1
fi

# Check if VSIX file exists
VSIX_FILE="agent-s3-0.1.0.vsix"
if [ ! -f "$VSIX_FILE" ]; then
    echo "❌ VSIX file not found: $VSIX_FILE"
    echo "   Please run 'vsce package' first to create the VSIX file"
    exit 1
fi

# Uninstall any existing version first
echo "🗑️  Removing any existing Agent-S3 extension..."
code --uninstall-extension agent-s3 2>/dev/null || true

# Install the new version
echo "📦 Installing Agent-S3 extension from VSIX..."
code --install-extension "$VSIX_FILE"

if [ $? -eq 0 ]; then
    echo "✅ Agent-S3 VS Code Extension installed successfully!"
    echo ""
    echo "🎉 Installation Complete!"
    echo ""
    echo "📋 Next Steps:"
    echo "   1. Restart VS Code to activate the extension"
    echo "   2. Open your workspace folder in VS Code"
    echo "   3. Use Ctrl+Shift+P and search for 'Agent-S3' commands"
    echo "   4. Try 'Agent-S3: Show help' to test the installation"
    echo ""
    echo "💡 Available Commands:"
    echo "   • Agent-S3: Show help"
    echo "   • Agent-S3: Initialize workspace" 
    echo "   • Agent-S3: Make change request"
    echo "   • Agent-S3: Open Chat Window"
    echo "   • Agent-S3: Run automated design"
else
    echo "❌ Installation failed!"
    echo "   Please check VS Code output for error details"
    exit 1
fi
