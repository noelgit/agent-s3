import * as vscode from 'vscode';
import { spawn, ChildProcess } from 'child_process'; // Added ChildProcess
import { WebviewUIManager } from './webview-ui-loader';
import { CHAT_HISTORY_KEY } from './constants';
import type { ChatHistoryEntry } from './types/message';
import { Agent3ChatProvider, Agent3HistoryProvider } from './tree-providers';
import { ConnectionManager } from './src/config/connectionManager';
import { HttpClient } from './src/http/httpClient';

// Declare process for Node.js environment
declare const process: {
    env: { [key: string]: string | undefined };
};

let chatManager: WebviewUIManager | undefined;
let messageHistory: ChatHistoryEntry[] = [];
// Use minimal type for terminalEmitter to avoid 'any' and generic issues
let terminalEmitter: { event: unknown; fire(data: string): void; dispose(): void } | undefined;
let agentTerminal: vscode.Terminal | undefined;
let connectionManager: ConnectionManager;
let httpClient: HttpClient;
let extensionContext: vscode.ExtensionContext; // Store context globally

// Function to clean up the active design session
function cleanupDesignSession(reason?: string) {
    if (activeDesignSession) {
        if (reason) {
            chatManager?.postMessage({
                type: 'CHAT_MESSAGE',
                id: activeDesignSession.streamId + '_cleanup',
                content: { text: `Design session ended: ${reason}`, source: 'system' }
            });
        }
        if (activeDesignSession.isProcessAlive && activeDesignSession.process) {
            activeDesignSession.process.kill();
        }
        activeDesignSession.isProcessAlive = false;
        // Detach listeners by replacing the process object or explicitly removing them if attached one by one
        // For simplicity here, we assume new listeners are setup on new process or old ones become no-ops
        if (activeDesignSession.process) {
            activeDesignSession.process.stdout?.removeAllListeners();
            activeDesignSession.process.stderr?.removeAllListeners();
            activeDesignSession.process.removeAllListeners('close');
            activeDesignSession.process.removeAllListeners('error');
        }
        activeDesignSession = null;
        console.log(`Active design session cleaned up. Reason: ${reason || 'N/A'}`);
    }
}

// New session state variable
interface ActiveDesignSession {
  process: ChildProcess;
  objective: string;
  streamId: string; // To correlate messages in chat
  isProcessAlive: boolean; // To track if the process is still running
}
let activeDesignSession: ActiveDesignSession | null = null;

/**
 * Determine the Python executable used for CLI commands.
 * Priority: VS Code setting `agent-s3.pythonExecutable` then
 *          environment variable `AGENT_S3_PYTHON_EXECUTABLE` then
 *          default 'python3'.
 */
function getPythonExecutable(): string {
    const configExec = vscode.workspace.getConfiguration('agent-s3').get('pythonExecutable') as string | undefined;
    const envExec = typeof process !== 'undefined' ? process.env.AGENT_S3_PYTHON_EXECUTABLE : undefined;
    return configExec || envExec || 'python3';
}

/**
 * Extension activation point
 */
export function activate(context: vscode.ExtensionContext): void {
    extensionContext = context; // Store context
    console.log('Agent-S3 HTTP Extension activated');

    // Initialize connection management
    connectionManager = ConnectionManager.getInstance();
    httpClient = new HttpClient();

    // Register tree data providers
    const chatProvider = new Agent3ChatProvider(context);
    const historyProvider = new Agent3HistoryProvider(context);
    
    vscode.window.registerTreeDataProvider('agent-s3-chat', chatProvider);
    vscode.window.registerTreeDataProvider('agent-s3-history', historyProvider);

    // Initialize command
    const initCommand = vscode.commands.registerCommand('agent-s3.init', async () => {
        await executeAgentCommand('/init');
        chatProvider.refresh();
        historyProvider.refresh();
    });

    // Help command
    const helpCommand = vscode.commands.registerCommand('agent-s3.help', async () => {
        await executeAgentCommand('/help');
    });

    // Guidelines command
    const guidelinesCommand = vscode.commands.registerCommand('agent-s3.guidelines', async () => {
        await executeAgentCommand('/guidelines');
    });

    // Request command
    const requestCommand = vscode.commands.registerCommand('agent-s3.request', async () => {
        const input = await vscode.window.showInputBox({
            prompt: 'Enter change request description',
            placeHolder: 'Add a login form with validation'
        });
        
        if (input) {
            await executeAgentCommand(`/request ${input}`);
            historyProvider.refresh();
        }
    });

    // Design Auto command  
    const designAutoCommand = vscode.commands.registerCommand('agent-s3.designAuto', async () => {
        const input = await vscode.window.showInputBox({
            prompt: 'Enter design description',
            placeHolder: 'Design a user dashboard with metrics'
        });
        
        if (input) {
            await executeAgentCommand(`/design-auto ${input}`);
            historyProvider.refresh();
        }
    });

    // Interactive Design command
    const designCommand = vscode.commands.registerCommand('agent-s3.design', async () => {
        const input = await vscode.window.showInputBox({
            prompt: 'Enter design objective for interactive design session',
            placeHolder: 'Create a todo application with user authentication'
        });
        
        if (input) {
            // Show information about the interactive design process
            const proceed = await vscode.window.showInformationMessage(
                `Starting interactive design session for: "${input}"\n\nThis will open the chat window where you can have a conversation with the AI designer. The AI will ask clarifying questions and guide you through the design process.`,
                'Start Design Session',
                'Cancel'
            );
            
            if (proceed === 'Start Design Session') {
                // Open chat window for interactive design
                if (!chatManager) {
                    chatManager = new WebviewUIManager(context.extensionUri, 'agent-s3-design', 'Agent-S3 Interactive Design');
                }
                chatManager.createOrShowPanel();
                
                // Send the design command through chat for interactive conversation
                chatManager.postMessage({ 
                    type: 'SEND_COMMAND', 
                    content: { command: `/design ${input}` } 
                });
                
                historyProvider.refresh();
            }
        }
    });

    const chatCommand = vscode.commands.registerCommand('agent-s3.openChatWindow', async () => {
        if (!chatManager) {
            chatManager = new WebviewUIManager(context.extensionUri, 'agent-s3-chat', 'Agent-S3 Chat');
            chatManager.setMessageHandler(async (msg: unknown) => {
                const message = msg as { type: string; text?: string };
                if (message.type === 'webview-ready') {
                    messageHistory = context.workspaceState.get<ChatHistoryEntry[]>(CHAT_HISTORY_KEY, []);
                    chatManager?.postMessage({ type: 'LOAD_HISTORY', history: messageHistory, has_more: false });
                    return;
                }

                if (message.type === 'send') {
                    const text = typeof message.text === 'string' ? message.text : '';
                    const entry: ChatHistoryEntry = { role: 'user', content: text, timestamp: new Date().toISOString() };
                    
                    // Add user's message to the visual chat immediately
                    // The history for general commands is handled below, design session messages are not added to general history here.
                    // chatManager?.postMessage({ type: 'CHAT_MESSAGE', content: { text: text, source: 'user' } });
                    // No, App.tsx already adds user message to its display when 'send' is emitted.

                    if (activeDesignSession && activeDesignSession.isProcessAlive && activeDesignSession.process.stdin) {
                        // Design session is active, route input to Python script
                        console.log(`Forwarding to design session: ${text}`);
                        try {
                            const jsonInput = JSON.stringify({ content: text });
                            activeDesignSession.process.stdin.write(jsonInput + '\n');

                            // Optionally, add this user message to a specific design history if needed,
                            // but not to the main `messageHistory` which is for general commands.
                            // For now, the Python script's echo/response will be the record.
                            const designEntry: ChatHistoryEntry = { role: 'user', content: `(Design Session) ${text}`, timestamp: new Date().toISOString() };
                            // If you want to store design session chat, use a separate key or integrate carefully.
                            // messageHistory.push(designEntry);
                            // await context.workspaceState.update(CHAT_HISTORY_KEY, messageHistory);

                        } catch (e) {
                            const errorMsg = `Failed to send message to design script: ${e instanceof Error ? e.message : String(e)}`;
                            console.error(errorMsg);
                            chatManager?.postMessage({ type: 'CHAT_MESSAGE', content: { text: errorMsg, source: 'system' } });
                            // Optionally cleanup if stdin write fails catastrophically
                            // cleanupDesignSession("Error writing to design script stdin.");
                        }
                    } else {
                        // No active design session, proceed with normal command execution
                        const entry: ChatHistoryEntry = { role: 'user', content: text, timestamp: new Date().toISOString() };
                        messageHistory.push(entry); // Add to general history
                        await context.workspaceState.update(CHAT_HISTORY_KEY, messageHistory);

                        // Send initial "Processing..." response to chat
                        chatManager?.postMessage({ type: 'COMMAND_RESULT', content: { result: 'Processing...', success: null, command: text } });
                        
                        try {
                            const result = await executeAgentCommandWithOutput(text);

                            const ack: ChatHistoryEntry = { role: 'assistant', content: result, timestamp: new Date().toISOString() };
                            messageHistory.push(ack);
                            await context.workspaceState.update(CHAT_HISTORY_KEY, messageHistory);

                            chatManager?.postMessage({ type: 'COMMAND_RESULT', content: { result: result, success: true, command: text } });
                            // The 'CHAT_MESSAGE' for assistant is now typically sent by the command itself if it's interactive,
                            // or here for simple commands. Design session handles its own CHAT_MESSAGE.
                            if (!text.startsWith('/design ') || text.startsWith('/design-auto ')) { // Avoid double message for design starts
                                chatManager?.postMessage({ type: 'CHAT_MESSAGE', content: { text: ack.content, source: 'agent' } });
                            }

                            chatProvider.refresh();
                            historyProvider.refresh();
                        } catch (error) {
                            const errorMsg = `Command failed: ${error instanceof Error ? error.message : String(error)}`;
                            const errorAck: ChatHistoryEntry = { role: 'assistant', content: errorMsg, timestamp: new Date().toISOString() };
                            messageHistory.push(errorAck);
                            await context.workspaceState.update(CHAT_HISTORY_KEY, messageHistory);

                            chatManager?.postMessage({ type: 'COMMAND_RESULT', content: { result: errorMsg, success: false, command: text } });
                            chatManager?.postMessage({ type: 'CHAT_MESSAGE', content: { text: errorMsg, source: 'agent' } });
                        }
                    }
                }
            });
        }

        chatManager.createOrShowPanel();
    });

    // Quick command
    const quickCommand = vscode.commands.registerCommand('agent-s3.openQuickCommand', async () => {
        const input = await vscode.window.showInputBox({
            prompt: 'Enter Agent-S3 command for immediate execution',
            placeHolder: '/plan add user authentication'
        });

        if (!input) return;
        await executeAgentCommand(input);
        historyProvider.refresh();
    });

    // Show chat entry command
    const showChatCommand = vscode.commands.registerCommand('agent-s3.showChatEntry', async (entry?: ChatHistoryEntry) => {
        if (entry) {
            // Show the chat entry content in an information message
            const timestamp = entry.timestamp ? new Date(entry.timestamp).toLocaleString() : 'Unknown time';
            vscode.window.showInformationMessage(
                `${entry.role} (${timestamp}): ${entry.content}`,
                'Copy to Clipboard'
            ).then((selection: string | undefined) => {
                if (selection === 'Copy to Clipboard') {
                    vscode.env.clipboard.writeText(entry.content);
                }
            });
        } else {
            // Fallback to input box
            const input = await vscode.window.showInputBox({
                prompt: 'Enter message to add to chat',
                placeHolder: 'Your message here'
            });

            if (input) {
                // For now, treat as a command
                await executeAgentCommand(input);
                chatProvider.refresh();
                historyProvider.refresh();
            }
        }
    });

    // Refresh commands
    const refreshChatCommand = vscode.commands.registerCommand('agent-s3.refreshChat', async () => {
        chatProvider.refresh();
        vscode.window.showInformationMessage('Chat view refreshed');
    });

    const refreshHistoryCommand = vscode.commands.registerCommand('agent-s3.refreshHistory', async () => {
        historyProvider.refresh();
        vscode.window.showInformationMessage('History view refreshed');
    });

    // HTTP status command with connection info
    const statusCommand = vscode.commands.registerCommand('agent-s3.status', async () => {
        try {
            const config = await connectionManager.getConnectionConfig();
            const isRemote = config.host !== 'localhost' && config.host !== '127.0.0.1';
            const protocol = config.use_tls ? 'https' : 'http';
            
            // Test connection
            const testResult = await httpClient.testConnection();
            const status = testResult ? '✅ Connected' : '❌ Disconnected';
            
            const timeout = vscode.workspace.getConfiguration('agent-s3').get('httpTimeoutMs') as number || 10000;
            
            const message = [
                `Agent-S3 Connection Status:`,
                `${status}`,
                `Endpoint: ${protocol}://${config.host}:${config.port}`,
                `Remote: ${isRemote ? 'Yes' : 'No (Local)'}`,
                `Auth: ${config.auth_token ? 'Enabled' : 'None'}`,
                `Timeout: ${timeout}ms`
            ].join('\n');
            
            vscode.window.showInformationMessage(message);
        } catch (error) {
            vscode.window.showErrorMessage(`Status check failed: ${error instanceof Error ? error.message : String(error)}`);
        }
    });

    // Test connection command
    const testConnectionCommand = vscode.commands.registerCommand('agent-s3.testConnection', async () => {
        try {
            const config = await connectionManager.getConnectionConfig();
            const protocol = config.use_tls ? 'https' : 'http';
            
            vscode.window.showInformationMessage(`Testing connection to ${protocol}://${config.host}:${config.port}...`);
            
            const testResult = await httpClient.testConnection();
            
            if (testResult) {
                vscode.window.showInformationMessage(`✅ Connection successful to Agent-S3 backend`);
            } else {
                vscode.window.showWarningMessage(`❌ Connection failed to Agent-S3 backend`);
            }
        } catch (error) {
            vscode.window.showErrorMessage(`Connection test failed: ${error instanceof Error ? error.message : String(error)}`);
        }
    });

    context.subscriptions.push(
        initCommand,
        helpCommand, 
        guidelinesCommand,
        requestCommand,
        designAutoCommand,
        designCommand,
        chatCommand,
        quickCommand,
        showChatCommand,
        refreshChatCommand,
        refreshHistoryCommand,
        statusCommand,
        testConnectionCommand
    );
}

export async function executeAgentCommand(command: string): Promise<void> {
    const result = await executeAgentCommandWithOutput(command);
    // For backward compatibility, show in terminal as well
    appendToTerminal(`$ ${command}\n${result}\n`);
}

export async function executeAgentCommandWithOutput(command: string): Promise<string> {
    const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
    if (!workspaceFolder) {
        throw new Error('No workspace folder open');
    }

    if (command.startsWith('/design ') && !command.startsWith('/design-auto ')) {
        return handleInteractiveDesignCommand(command, workspaceFolder.uri.fsPath);
    }

    // First try HTTP if connection is available
    try {
        const response = await httpClient.sendCommand(command);
        if (response.success) {
            return response.output || response.result || 'Command completed successfully';
        } else {
            throw new Error('HTTP command failed');
        }
    } catch (httpError) {
        console.log('HTTP failed, falling back to CLI:', httpError);
        
        // Fallback to CLI execution
        return executeCommandViaCLI(command, workspaceFolder.uri.fsPath);
    }
}

async function executeCommandViaCLI(command: string, workspacePath: string): Promise<string> {
    return new Promise<string>((resolve, reject) => {
        // Use longer timeout for interactive commands like /design
        const isInteractiveCommand = command.startsWith('/design ') || command.startsWith('/plan ');
        const CLI_TIMEOUT_MS = isInteractiveCommand ? 300000 : 30000; // 5 minutes for interactive, 30 seconds for others
        let processResolved = false;
        let output = '';
        
        // Use CLI dispatcher as fallback
        const pythonExec = getPythonExecutable();
        const childProcess = spawn(pythonExec, ['-m', 'agent_s3.cli', command], {
            cwd: workspacePath,
            stdio: 'pipe'
        });

        // Set up timeout for CLI process
        const timeoutHandle = setTimeout(() => {
            if (!processResolved) {
                processResolved = true;
                const timeoutMsg = `[TIMEOUT] CLI command timed out after ${CLI_TIMEOUT_MS / 1000} seconds`;
                console.log('CLI process timed out - process will be abandoned');
                reject(new Error(timeoutMsg));
            }
        }, CLI_TIMEOUT_MS);

        childProcess.stdout?.on('data', (data: Buffer) => {
            output += data.toString();
        });

        childProcess.stderr?.on('data', (data: Buffer) => {
            output += data.toString();
        });

        childProcess.on('error', (err: unknown) => {
            if (!processResolved) {
                processResolved = true;
                clearTimeout(timeoutHandle);
                reject(new Error(`Failed to start CLI: ${err instanceof Error ? err.message : String(err)}`));
            }
        });

        childProcess.on('close', (code: number | null) => {
            if (!processResolved) {
                processResolved = true;
                clearTimeout(timeoutHandle);
                if (code !== 0 && code !== null) {
                    reject(new Error(`Process exited with code ${code}\n${output}`));
                } else {
                    resolve(output || 'Command completed successfully');
                }
            }
        });
    });
}

/**
 * Handle interactive design commands with VS Code UI
 */
async function handleInteractiveDesignCommand(command: string, workspacePath: string): Promise<string> {
    const objective = command.replace('/design ', '').trim();

    if (activeDesignSession && activeDesignSession.isProcessAlive) {
        const message = 'An interactive design session is already in progress. Please complete or terminate it before starting a new one.';
        vscode.window.showErrorMessage(message);
        chatManager?.postMessage({ type: 'CHAT_MESSAGE', content: { text: message, source: 'system' } });
        return Promise.reject(new Error(message));
    }

    // Ensure chatManager is available
    if (!chatManager) {
        // This attempts to reuse the logic from agent-s3.openChatWindow to initialize chatManager
        // It's assumed that activate has already run and set up the command.
        // If this command is called without openChatWindow ever being called, chatManager might not be ready.
        // A more robust solution might involve ensuring chatManager is initialized earlier or providing a dedicated init method.
        await vscode.commands.executeCommand('agent-s3.openChatWindow');
        if (!chatManager) {
            const errorMsg = "Chat manager is not available. Cannot start interactive design.";
            vscode.window.showErrorMessage(errorMsg);
            return Promise.reject(new Error(errorMsg));
        }
    }
    chatManager.createOrShowPanel(); // Ensure panel is visible

    const pythonExec = getPythonExecutable();
    const streamId = `design_session_${Date.now()}`;

    const childProcess = spawn(pythonExec, ['-m', 'agent_s3.cli', `/design ${objective}`], {
        cwd: workspacePath,
        stdio: ['pipe', 'pipe', 'pipe'],
    });

    activeDesignSession = {
        process: childProcess,
        objective: objective,
        streamId: streamId,
        isProcessAlive: true,
    };

    // Add a user-facing message that the session is starting
    chatManager?.postMessage({
        type: 'CHAT_MESSAGE',
        id: streamId + '_init', // Unique ID for this system message
        content: { text: `Starting interactive design session for: "${objective}"...`, source: 'system' }
    });

    let initialMessageReceived = false;
    let accumulatedData = '';

    return new Promise<string>((resolve, reject) => {
        childProcess.stdout?.on('data', (data: Buffer) => {
            accumulatedData += data.toString();
            // Process line by line if possible, assuming JSON objects are newline-terminated
            let newlineIndex;
            while ((newlineIndex = accumulatedData.indexOf('\n')) >= 0) {
                const line = accumulatedData.substring(0, newlineIndex).trim();
                accumulatedData = accumulatedData.substring(newlineIndex + 1);

                if (line) {
                    try {
                        const messageFromPython = JSON.parse(line);
                        if (!initialMessageReceived) {
                            initialMessageReceived = true;
                            if (messageFromPython.type === 'ai_response') {
                                chatManager?.postMessage({
                                    type: 'CHAT_MESSAGE',
                                    id: streamId + '_first_ai',
                                    content: { text: messageFromPython.content, source: 'agent' }
                                });
                                // Inform the user that the session has started and they can now chat.
                                resolve(`Interactive design session started for "${objective}". Check the chat window to continue.`);
                            } else if (messageFromPython.type === 'error') {
                                const errorMsg = `Python script error on init: ${messageFromPython.content}`;
                                vscode.window.showErrorMessage(errorMsg);
                                chatManager?.postMessage({ type: 'CHAT_MESSAGE', content: { text: errorMsg, source: 'system' } });
                                if (activeDesignSession) activeDesignSession.isProcessAlive = false;
                                activeDesignSession = null;
                                reject(new Error(errorMsg));
                            } else {
                                // Unexpected first message
                                const errorMsg = `Unexpected first message type from Python script: ${messageFromPython.type}`;
                                vscode.window.showErrorMessage(errorMsg);
                                chatManager?.postMessage({ type: 'CHAT_MESSAGE', content: { text: errorMsg, source: 'system' } });
                                if (activeDesignSession) activeDesignSession.isProcessAlive = false;
                                activeDesignSession = null;
                                reject(new Error(errorMsg));
                            }
                        } else {
                            // For subsequent messages from Python (e.g. if it sends more before user input)
                            // This part will be more relevant in Part 2 when handling ongoing conversation
                            // For now, we primarily care about the first message.
                            // We can log other messages or decide if they need handling here.
                            // console.log("Further stdout from design script (should be handled by chat input handler):", messageFromPython);
                            // Handle subsequent messages
                            if (messageFromPython.type === 'ai_response') {
                                chatManager?.postMessage({ type: 'CHAT_MESSAGE', id: streamId + '_ai_' + Date.now(), content: { text: messageFromPython.content, source: 'agent' } });
                            } else if (messageFromPython.type === 'system_message') {
                                chatManager?.postMessage({ type: 'CHAT_MESSAGE', id: streamId + '_system_' + Date.now(), content: { text: messageFromPython.content, source: 'system' } });
                            } else if (messageFromPython.type === 'error') {
                                chatManager?.postMessage({ type: 'CHAT_MESSAGE', id: streamId + '_error_' + Date.now(), content: { text: messageFromPython.content, source: 'system' } });
                            }
                        }
                    } catch (e) {
                        console.error('Failed to parse JSON from Python script:', line, e);
                        // If parsing fails for the first message, reject.
                        if (!initialMessageReceived) {
                            const errorMsg = 'Error parsing initial response from design script.';
                            vscode.window.showErrorMessage(errorMsg);
                            chatManager?.postMessage({ type: 'CHAT_MESSAGE', content: { text: errorMsg, source: 'system' } });
                            if (activeDesignSession) activeDesignSession.isProcessAlive = false;
                            activeDesignSession = null;
                            reject(new Error(errorMsg));
                        } else {
                            // If it's not the first message, log to console and also inform user in chat.
                            chatManager?.postMessage({ type: 'CHAT_MESSAGE', id: streamId + '_json_parse_error_' + Date.now(), content: { text: `Error parsing response from design script: ${line}`, source: 'system' } });
                        }
                    }
                }
            }
        });

        childProcess.stderr?.on('data', (data: Buffer) => {
            const errorOutput = data.toString();
            console.error(`Interactive Design Python STDERR: ${errorOutput}`);
            // If this is the first message, it's an error in starting.
            if (!initialMessageReceived) {
                initialMessageReceived = true; // Prevent further success processing
                const errorMsg = `Error starting design session: ${errorOutput}`;
                vscode.window.showErrorMessage(errorMsg);
                chatManager?.postMessage({ type: 'CHAT_MESSAGE', content: { text: errorMsg, source: 'system' } });
                if (activeDesignSession) activeDesignSession.isProcessAlive = false;
                activeDesignSession = null;
                reject(new Error(errorMsg));
            } else {
                // Ongoing errors could be sent to chat as system messages
                 chatManager?.postMessage({ type: 'CHAT_MESSAGE', content: { text: `Design Script Error: ${errorOutput}`, source: 'system' } });
            }
        });

        childProcess.on('error', (err: Error) => {
            const errorMsg = `Failed to start interactive design process: ${err.message}`;
            vscode.window.showErrorMessage(errorMsg);
            chatManager?.postMessage({ type: 'CHAT_MESSAGE', content: { text: errorMsg, source: 'system' } });
            if (activeDesignSession) activeDesignSession.isProcessAlive = false;
            activeDesignSession = null;
            reject(new Error(errorMsg));
        });

        childProcess.on('close', (code: number | null) => {
            if (activeDesignSession) activeDesignSession.isProcessAlive = false; // Mark as not alive
            const closeMessage = `Design session process exited with code ${code}.`;
            console.log(closeMessage);
            // Only show message if it wasn't an error handled before or a clean startup
            if (code !== 0 && !initialMessageReceived ) { // If error code and we never got the first message
                 const errorMsg = `Design session process exited prematurely with code ${code}. Check logs.`;
                 vscode.window.showWarningMessage(errorMsg);
                 chatManager?.postMessage({ type: 'CHAT_MESSAGE', content: { text: errorMsg, source: 'system' } });
                 reject(new Error(errorMsg)); // Reject if it closes before first message and has error code
            } else if (!initialMessageReceived) { // Clean exit but no first message
                 const errorMsg = `Design session process exited cleanly but sent no initial response.`;
                 vscode.window.showWarningMessage(errorMsg);
                 chatManager?.postMessage({ type: 'CHAT_MESSAGE', content: { text: errorMsg, source: 'system' } });
                 reject(new Error(errorMsg));
            } else {
                // If it already started and then closes, Part 2 (chat handler) would manage this.
                // For now, just a log or a subtle system message.
                chatManager?.postMessage({ type: 'CHAT_MESSAGE', content: { text: closeMessage, source: 'system' } });
            }
            // Don't nullify activeDesignSession here if it successfully started,
            // so the user message handler in Part 2 can know the session ended.
            // Cleanup is now more explicitly handled by cleanupDesignSession.
            // The 'close' event should always try to clean up.
            if (!initialMessageReceived && code !== 0) { // If process died before init and had error
                reject(new Error(`Design session process exited prematurely with code ${code}.`));
            } else if (!initialMessageReceived) { // Process died before init, no error code
                reject(new Error(`Design session process exited cleanly but sent no initial response.`));
            }
            // If we are here, it means the process closed. Call cleanup.
            cleanupDesignSession(`Process exited with code ${code}.`);
        });
    });
}

export function deactivate(): void {
    console.log('Agent-S3 HTTP Extension deactivated');
    if (agentTerminal) {
        agentTerminal.dispose();
    }
    terminalEmitter?.dispose();
}

function getAgentTerminal(): vscode.Terminal {
    if (agentTerminal) {
        return agentTerminal;
    }

    // Use EventEmitter without type argument for compatibility with custom typings
    const emitter = new vscode.EventEmitter();
    terminalEmitter = emitter;
    const pty: vscode.Pseudoterminal = {
        onDidWrite: emitter.event,
        open: () => { /* no-op */ },
        close: () => { /* no-op */ }
    };

    agentTerminal = vscode.window.createTerminal({ name: 'Agent-S3', pty });
    return agentTerminal ?? vscode.window.createTerminal('Agent-S3');
}

function appendToTerminal(text: string): void {
    const term = getAgentTerminal();
    if (terminalEmitter) {
        terminalEmitter.fire(text.replace(/\r?\n/g, '\r\n'));
    }
    term.show(true);
}