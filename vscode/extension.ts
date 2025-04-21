/**
 * Agent-S3 VS Code Extension
 * 
 * Integrates the Agent-S3 Python CLI with VS Code.
 */

import * as vscode from 'vscode';
import * as cp from 'child_process';
import * as path from 'path';
import * as fs from 'fs';

// Terminal for Agent-S3 output
let agentTerminal: vscode.Terminal | undefined;

// Track if Agent-S3 is initialized
let isInitialized = false;

// Store extension context for use in commands outside activate
let extensionContext: vscode.ExtensionContext;

/**
 * Activate the extension.
 */
export function activate(context: vscode.ExtensionContext) {
  // Save context for later use
  extensionContext = context;
  console.log('Agent-S3 extension is now active');

  // Register commands
  const initCommand = vscode.commands.registerCommand('agent-s3.init', initializeWorkspace);
  const helpCommand = vscode.commands.registerCommand('agent-s3.help', showHelp);
  const guidelinesCommand = vscode.commands.registerCommand('agent-s3.guidelines', showGuidelines);
  const requestCommand = vscode.commands.registerCommand('agent-s3.request', makeChangeRequest);
  const openChatCommand = vscode.commands.registerCommand('agent-s3.openChatWindow', openChatWindow);

  // Add commands to context subscriptions
  context.subscriptions.push(initCommand, helpCommand, guidelinesCommand, requestCommand, openChatCommand);

  // Create status bar item
  const statusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100);
  statusBarItem.text = "$(sparkle) Agent-S3";
  statusBarItem.tooltip = "Click to make a change request";
  statusBarItem.command = 'agent-s3.request';
  statusBarItem.show();
  context.subscriptions.push(statusBarItem);

  // Check if workspace is initialized
  checkInitialization();
}

/**
 * Deactivate the extension.
 */
export function deactivate() {
  if (agentTerminal) {
    agentTerminal.dispose();
  }
}

/**
 * Check if Agent-S3 is initialized in this workspace.
 * Per instructions.md, this checks for the existence of the .github/copilot-instructions.md file.
 */
async function checkInitialization() {
  const workspaceFolders = vscode.workspace.workspaceFolders;
  if (!workspaceFolders) {
    return;
  }

  const rootPath = workspaceFolders[0].uri.fsPath;
  const guidelinesPath = path.join(rootPath, '.github', 'copilot-instructions.md');
  const scratchpadPath = path.join(rootPath, 'scratchpad.txt');
  
  isInitialized = fs.existsSync(guidelinesPath) && fs.existsSync(scratchpadPath);
  
  if (!isInitialized) {
    vscode.window.showInformationMessage(
      'Agent-S3 is not initialized in this workspace. Run "Agent-S3: Initialize workspace" to get started.',
      'Initialize Now'
    ).then(selection => {
      if (selection === 'Initialize Now') {
        initializeWorkspace();
      }
    });
  }
}

/**
 * Initialize the Agent-S3 workspace.
 */
async function initializeWorkspace() {
  const terminal = getAgentTerminal();
  terminal.show();
  terminal.sendText('python -m agent_s3.cli /init');
  
  // Set initialization flag after a short delay
  setTimeout(() => {
    isInitialized = true;
  }, 5000);
  
  vscode.window.showInformationMessage('Initializing Agent-S3 workspace...');
}

/**
 * Show Agent-S3 help information.
 */
async function showHelp() {
  const terminal = getAgentTerminal();
  terminal.show();
  terminal.sendText('python -m agent_s3.cli /help');
}

/**
 * Show coding guidelines.
 */
async function showGuidelines() {
  const terminal = getAgentTerminal();
  terminal.show();
  terminal.sendText('python -m agent_s3.cli /guidelines');
}

/**
 * Make a change request.
 */
async function makeChangeRequest() {
  if (!isInitialized) {
    const choice = await vscode.window.showWarningMessage(
      'Agent-S3 needs to be initialized first.', 
      'Initialize Now', 
      'Cancel'
    );
    
    if (choice === 'Initialize Now') {
      await initializeWorkspace();
    } else {
      return;
    }
  }
  
  const request = await vscode.window.showInputBox({
    prompt: 'Enter your change request',
    placeHolder: 'Describe the changes you want to make...'
  });
  
  if (request) {
    const terminal = getAgentTerminal();
    terminal.show();
    terminal.sendText(`python -m agent_s3.cli "${request.replace(/"/g, '\\"')}"`); // Escape quotes
    
    // Show progress notification
    vscode.window.showInformationMessage(`Processing request: ${request}`);
    
    // Start monitoring for progress updates
    monitorProgress();
  }
}

/**
 * Open a dedicated Copilot-style chat WebviewPanel.
 */
function openChatWindow() {
  const panel = vscode.window.createWebviewPanel(
    'agentS3Chat',
    'Agent-S3 Chat',
    vscode.ViewColumn.Beside,
    { enableScripts: true, retainContextWhenHidden: true }
  );

  const nonce = Date.now().toString();
  
  // Load message history from workspaceState
  const MAX_MESSAGES = 20;
  let messageHistory = extensionContext.workspaceState.get('agent-s3.chatHistory', []);
  
  panel.webview.html = getWebviewContent(nonce);

  // Send history to webview once it's ready
  panel.webview.onDidReceiveMessage(msg => {
    if (msg.command === 'ready') {
      // Send saved message history to webview
      panel.webview.postMessage({ command: 'loadHistory', history: messageHistory });
    }
    else if (msg.command === 'send' && msg.text) {
      // Add message to history
      const userMessage = { type: 'user', content: msg.text, timestamp: new Date().toISOString() };
      messageHistory = [...messageHistory, userMessage];
      
      // Trim history to last MAX_MESSAGES
      if (messageHistory.length > MAX_MESSAGES) {
        messageHistory = messageHistory.slice(messageHistory.length - MAX_MESSAGES);
      }
      
      // Save history
      extensionContext.workspaceState.update('agent-s3.chatHistory', messageHistory);
      
      // Send to terminal
      const safe = msg.text.replace(/"/g, '\\"');
      const term = getAgentTerminal();
      term.show(true);
      term.sendText(`python -m agent_s3.cli "${safe}"`);
      
      // NOTE: Ideally we would also capture the agent's response and add it
      // to history, but that requires additional terminal output parsing
    }
  }, undefined, extensionContext.subscriptions);
  
  // Handle panel disposal
  panel.onDidDispose(() => {
    // Final save of history when panel closes
    extensionContext.workspaceState.update('agent-s3.chatHistory', messageHistory);
  }, null, extensionContext.subscriptions);
}

/**
 * Generate HTML content for the chat panel, including CSP nonce and ARIA attributes.
 */
function getWebviewContent(nonce: string): string {
  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'nonce-${nonce}'; style-src 'unsafe-inline';" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Agent-S3 Chat</title>
  <style>
    body { font-family: var(--vscode-font-family); color: var(--vscode-terminal-foreground); background-color: var(--vscode-editor-background); margin: 0; display: flex; flex-direction: column; height: 100vh; }
    #messages { flex: 1; overflow-y: auto; padding: 1rem; }
    .message { margin-bottom: 1rem; padding: 0.5rem 0.8rem; border-radius: 6px; max-width: 80%; }
    .message.user { text-align: right; background-color: var(--vscode-button-background); color: var(--vscode-button-foreground); margin-left: auto; }
    .message.agent { background-color: var(--vscode-editorWidget-background); color: var(--vscode-editorWidget-foreground); margin-right: auto; }
    .message.system { background-color: var(--vscode-statusBar-background); color: var(--vscode-statusBar-foreground); margin-left: auto; margin-right: auto; font-style: italic; text-align: center; }
    #input { display: flex; padding: 0.75rem; border-top: 1px solid var(--vscode-editorWidget-border); }
    #msg { flex: 1; padding: 0.5rem; font-size: 1rem; min-height: 2.5rem; resize: vertical; background-color: var(--vscode-input-background); color: var(--vscode-input-foreground); border: 1px solid var(--vscode-input-border); }
    #send { margin-left: 0.5rem; padding: 0.5rem 1rem; background-color: var(--vscode-button-background); color: var(--vscode-button-foreground); border: none; border-radius: 3px; }
    #send:hover { background-color: var(--vscode-button-hoverBackground); }
    .typing { font-style: italic; opacity: 0.7; }
    .message-time { font-size: 0.7rem; opacity: 0.7; margin-top: 0.3rem; }
  </style>
</head>
<body>
  <div id="messages" role="log" aria-live="polite"></div>
  <div id="input">
    <textarea id="msg" aria-label="Type a message" placeholder="Type a message..." rows="2"></textarea>
    <button id="send" aria-label="Send message">Send</button>
  </div>
  <script nonce="${nonce}">
    const vscode = acquireVsCodeApi();
    const messages = document.getElementById('messages');
    const input = document.getElementById('msg');
    const sendBtn = document.getElementById('send');
    
    // Format timestamp for display
    function formatTime(timestamp) {
      try {
        const date = new Date(timestamp);
        return date.toLocaleTimeString();
      } catch (e) {
        return '';
      }
    }
    
    // Add a message to the UI
    function addMessageToUI(message) {
      const bubble = document.createElement('div');
      bubble.className = \`message \${message.type || 'user'}\`;
      bubble.setAttribute('role', 'listitem');
      
      const content = document.createElement('div');
      content.className = 'message-content';
      content.textContent = message.content;
      bubble.appendChild(content);
      
      if (message.timestamp) {
        const time = document.createElement('div');
        time.className = 'message-time';
        time.textContent = formatTime(message.timestamp);
        bubble.appendChild(time);
      }
      
      messages.appendChild(bubble);
      messages.scrollTop = messages.scrollHeight;
    }
    
    // Add a typing indicator
    function showTypingIndicator() {
      const typing = document.createElement('div');
      typing.className = 'message agent typing';
      typing.textContent = 'Agent is typing...';
      typing.id = 'typing-indicator';
      messages.appendChild(typing);
      messages.scrollTop = messages.scrollHeight;
    }
    
    // Remove typing indicator
    function removeTypingIndicator() {
      const indicator = document.getElementById('typing-indicator');
      if (indicator) {
        indicator.remove();
      }
    }
    
    // Send message handler
    function sendMessage() {
      const text = input.value.trim();
      if (!text) return;
      
      addMessageToUI({
        type: 'user',
        content: text,
        timestamp: new Date().toISOString()
      });
      
      input.value = '';
      
      // Send to extension
      vscode.postMessage({ command: 'send', text });
      
      // Show typing indicator for agent
      showTypingIndicator();
      
      // Simulate a response (in real implementation, the extension would
      // capture CLI output and send it back to the webview)
      setTimeout(() => {
        removeTypingIndicator();
        // This would normally come from the actual agent response
        addMessageToUI({
          type: 'agent',
          content: 'Processing your request. Check the Agent-S3 terminal for progress updates.',
          timestamp: new Date().toISOString()
        });
      }, 2000);
    }
    
    // Event listeners
    sendBtn.addEventListener('click', sendMessage);
    
    // Keyboard handling (send on Ctrl+Enter or Enter without shift)
    input.addEventListener('keydown', (e) => {
      if ((e.key === 'Enter' && (e.ctrlKey || !e.shiftKey))) {
        e.preventDefault();
        sendMessage();
      }
    });

    // Listen for history load
    window.addEventListener('message', event => {
      const message = event.data;
      if (message.command === 'loadHistory' && Array.isArray(message.history)) {
        if (message.history.length > 0) {
          // Add a system message if loading history
          addMessageToUI({
            type: 'system',
            content: 'Previous conversation loaded',
            timestamp: new Date().toISOString()
          });
        }
        
        // Render all messages in history
        message.history.forEach(msg => addMessageToUI(msg));
      }
    });

    // Set focus to input
    setTimeout(() => input.focus(), 100);

    // Notify extension that webview is ready
    vscode.postMessage({ command: 'ready' });
  </script>
</body>
</html>`;
}

/**
 * Get or create the Agent-S3 terminal.
 */
function getAgentTerminal(): vscode.Terminal {
  if (!agentTerminal || isTerminalClosed(agentTerminal)) {
    agentTerminal = vscode.window.createTerminal('Agent-S3');
  }
  return agentTerminal;
}

/**
 * Check if a terminal is closed.
 */
function isTerminalClosed(terminal: vscode.Terminal): boolean {
  return vscode.window.terminals.indexOf(terminal) === -1;
}

/**
 * Monitor progress updates from Agent-S3.
 */
async function monitorProgress() {
  const workspaceFolders = vscode.workspace.workspaceFolders;
  if (!workspaceFolders) {
    return;
  }
  
  const rootPath = workspaceFolders[0].uri.fsPath;
  const progressPath = path.join(rootPath, 'progress_log.json');
  
  // Initial delay to let the progress file be created/updated
  await new Promise(resolve => setTimeout(resolve, 1000));
  
  let lastEntryCount = 0;
  
  // Check progress every 2 seconds
  const intervalId = setInterval(async () => {
    try {
      if (fs.existsSync(progressPath)) {
        const progressData = JSON.parse(fs.readFileSync(progressPath, 'utf8'));
        const entries = progressData.entries || [];
        
        if (entries.length > lastEntryCount) {
          // Get newest entries
          const newEntries = entries.slice(lastEntryCount);
          lastEntryCount = entries.length;
          
          // Process the newest entry
          const latestEntry = newEntries[newEntries.length - 1];
          updateProgressStatus(latestEntry);
          
          // Check if process is complete
          if (
            latestEntry.phase === 'execution' && 
            latestEntry.status === 'completed'
          ) {
            clearInterval(intervalId);
            vscode.window.showInformationMessage('Agent-S3 has completed the request successfully!');
          } else if (
            (latestEntry.phase === 'execution' && latestEntry.status === 'failed') ||
            (latestEntry.phase === 'issue_creation' && latestEntry.status === 'failed') ||
            (latestEntry.phase === 'prompt_approval' && latestEntry.status === 'rejected')
          ) {
            clearInterval(intervalId);
            vscode.window.showWarningMessage('Agent-S3 encountered an issue processing the request.');
          }
          // Handle pull request creation notifications
          if (latestEntry.phase === 'pr_creation') {
            clearInterval(intervalId);
            if (latestEntry.status === 'completed' && latestEntry.url) {
              vscode.window.showInformationMessage(`Agent-S3 created pull request: ${latestEntry.url}`);
            } else if (latestEntry.status === 'failed') {
              vscode.window.showWarningMessage('Agent-S3 failed to create the pull request.');
            } else if (latestEntry.status === 'skipped') {
              vscode.window.showInformationMessage('Agent-S3 skipped pull request creation.');
            }
          }
        }
      }
    } catch (error) {
      console.error('Error monitoring progress:', error);
    }
  }, 2000);
  
  // Stop monitoring after 10 minutes to prevent indefinite polling
  setTimeout(() => {
    clearInterval(intervalId);
  }, 10 * 60 * 1000);
}

/**
 * Update status bar based on progress.
 */
function updateProgressStatus(entry: any) {
  let message: string | undefined;
  
  switch (entry.phase) {
    case 'planning':
      message = `Agent-S3: Planning ${entry.status === 'plan_generated' ? 'complete' : 'in progress'}...`;
      break;
    case 'prompt_approval':
      message = 'Agent-S3: Waiting for plan approval...';
      break;
    case 'issue_creation':
      message = `Agent-S3: ${entry.status === 'completed' ? 'Created GitHub issue' : 'Creating GitHub issue...'}`;  
      break;
    case 'execution':
      const iteration = entry.iteration || 1;
      if (entry.status === 'completed') {
        message = 'Agent-S3: Changes applied successfully!';
      } else if (entry.status === 'test_failed') {
        message = `Agent-S3: Tests failed, refining plan (iteration ${iteration})...`;
      } else {
        message = `Agent-S3: Applying changes (iteration ${iteration})...`;
      }
      break;
  }
  
  if (message) {
    vscode.window.setStatusBarMessage(message, 5000);
  }
}
