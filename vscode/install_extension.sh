#!/bin/bash

# Script to properly install the Agent-S3 VS Code extension

echo "🔧 Installing Agent-S3 VS Code Extension..."

# Get the path to the VSIX file
VSIX_PATH="$(pwd)/agent-s3-working.vsix"

if [ ! -f "$VSIX_PATH" ]; then
    echo "❌ VSIX file not found: $VSIX_PATH"
    echo "Please run this script from the vscode directory"
    exit 1
fi

echo "📦 Found VSIX file: $VSIX_PATH"

# First, uninstall any existing version
echo "🗑️  Uninstalling existing Agent-S3 extension..."
code --uninstall-extension sparksoft-solutions.agent-s3 2>/dev/null || echo "No existing extension found"

# Wait a moment for the uninstall to complete
sleep 2

# Install the new version
echo "📥 Installing new Agent-S3 extension..."
code --install-extension "$VSIX_PATH" --force

if [ $? -eq 0 ]; then
    echo "✅ Agent-S3 extension installed successfully!"
    echo ""
    echo "📋 Next steps:"
    echo "1. Restart VS Code (completely close and reopen)"
    echo "2. Look for the Agent-S3 icon in the left sidebar"
    echo "3. Open a workspace/folder in VS Code"
    echo "4. The extension should now appear properly"
    echo ""
    echo "🐛 If you still don't see the icon:"
    echo "   - Check Extensions panel (Ctrl+Shift+X / Cmd+Shift+X)"
    echo "   - Search for 'Agent-S3'"
    echo "   - Make sure it's enabled"
    echo "   - Try reloading the window (Ctrl+Shift+P -> 'Developer: Reload Window')"
else
    echo "❌ Installation failed. Please check VS Code output panel for errors."
    exit 1
fi