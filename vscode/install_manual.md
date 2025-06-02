# Manual Installation Guide for Agent-S3 VS Code Extension

Since the VS Code CLI (`code` command) is not available in your terminal, you need to install the extension manually through VS Code's interface.

## Step-by-Step Installation

### 1. **Install the Extension**
1. Open VS Code
2. Press `Cmd+Shift+P` to open the Command Palette
3. Type: `Extensions: Install from VSIX...`
4. Press Enter
5. Navigate to: `/Users/noelpatron/Documents/GitHub/agent-s3/vscode/`
6. Select: `agent-s3-fixed.vsix`
7. Click "Install"

### 2. **Restart VS Code Completely**
- **Important**: Close VS Code completely (`Cmd+Q`)
- Reopen VS Code
- This ensures the extension is properly loaded

### 3. **Open a Workspace**
- Open a folder/workspace in VS Code
- The extension only activates when a workspace is open

### 4. **Start the Backend Server**
```bash
cd /Users/noelpatron/Documents/GitHub/agent-s3
python -m agent_s3.cli
```

### 5. **Verify Installation**
You should now see:
- ✅ Agent-S3 icon in the left sidebar
- ✅ Commands available in Command Palette (`Cmd+Shift+P`):
  - `Agent-S3: Initialize workspace`
  - `Agent-S3: Make change request`
  - `Agent-S3: Open Chat Window`
  - `Agent-S3: Open Interactive View`
  - `Agent-S3: Show help`
  - etc.

### 6. **If Commands Still Show "Not Found"**

#### Check Developer Console:
1. `Help → Toggle Developer Tools → Console`
2. Look for red error messages about "agent-s3"
3. Look for the message: "Activating Agent-S3 extension"

#### Force Reload:
1. `Cmd+Shift+P → "Developer: Reload Window"`

#### Check Extension Status:
1. Go to Extensions panel (`Cmd+Shift+X`)
2. Search for "Agent-S3"
3. Make sure it shows as "Enabled"
4. If disabled, click "Enable"

## Troubleshooting

### Extension Not Showing Up
- Make sure you selected the correct VSIX file
- Try uninstalling first: Extensions panel → Agent-S3 → Uninstall
- Restart VS Code and reinstall

### Commands Not Working
- Check that a workspace/folder is open
- Check Developer Console for errors
- Try reloading the window

### HTTP Connection Issues
- Make sure the backend server is running on port 8081
- Check that the HTTP server responds: `curl http://localhost:8081/health`
- Extension will automatically fall back to CLI commands if HTTP server is unavailable

## File Locations
- **VSIX file**: `/Users/noelpatron/Documents/GitHub/agent-s3/vscode/agent-s3-fixed.vsix`
- **HTTP server**: Available at `http://localhost:8081` when backend is running

The extension is properly compiled and should work once installed correctly!