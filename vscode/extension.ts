import * as vscode from 'vscode';
import { spawn } from 'child_process';
import { WebviewUIManager } from './webview-ui-loader';
import { CHAT_HISTORY_KEY } from './constants';
import type { ChatHistoryEntry } from './types/message';
import { Agent3ChatProvider, Agent3HistoryProvider } from './tree-providers';
import { ConnectionManager } from './src/config/connectionManager';
import { HttpClient } from './src/http/httpClient';

let chatManager: WebviewUIManager | undefined;
let messageHistory: ChatHistoryEntry[] = [];
// Use minimal type for terminalEmitter to avoid 'any' and generic issues
let terminalEmitter: { event: unknown; fire(data: string): void; dispose(): void } | undefined;
let agentTerminal: vscode.Terminal | undefined;
let connectionManager: ConnectionManager;
let httpClient: HttpClient;

/**
 * Extension activation point
 */
export function activate(context: vscode.ExtensionContext): void {
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
                    messageHistory.push(entry);
                    await context.workspaceState.update(CHAT_HISTORY_KEY, messageHistory);

                    // Send initial response to chat
                    chatManager?.postMessage({ type: 'COMMAND_RESULT', content: { result: 'Processing...', success: null, command: text } });
                    
                    try {
                        // Try HTTP first, fallback to CLI
                        const result = await executeAgentCommandWithOutput(text);
                        
                        // Send successful completion with output to chat
                        const ack: ChatHistoryEntry = { role: 'assistant', content: result, timestamp: new Date().toISOString() };
                        messageHistory.push(ack);
                        await context.workspaceState.update(CHAT_HISTORY_KEY, messageHistory);
                        
                        // Send completion signal to chat interface
                        chatManager?.postMessage({ type: 'COMMAND_RESULT', content: { result: result, success: true, command: text } });
                        chatManager?.postMessage({ type: 'CHAT_MESSAGE', content: { text: ack.content, source: 'agent' } });
                        
                        // Refresh tree views
                        chatProvider.refresh();
                        historyProvider.refresh();
                    } catch (error) {
                        // Send error completion
                        const errorMsg = `Command failed: ${error instanceof Error ? error.message : String(error)}`;
                        const errorAck: ChatHistoryEntry = { role: 'assistant', content: errorMsg, timestamp: new Date().toISOString() };
                        messageHistory.push(errorAck);
                        await context.workspaceState.update(CHAT_HISTORY_KEY, messageHistory);
                        
                        // Send error completion signal to chat interface
                        chatManager?.postMessage({ type: 'COMMAND_RESULT', content: { result: errorMsg, success: false, command: text } });
                        chatManager?.postMessage({ type: 'CHAT_MESSAGE', content: { text: errorMsg, source: 'agent' } });
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
        const CLI_TIMEOUT_MS = 30000; // 30 seconds timeout for CLI operations
        let processResolved = false;
        let output = '';
        
        // Use CLI dispatcher as fallback
        const childProcess = spawn('python', ['-m', 'agent_s3.cli', command], {
            cwd: workspacePath,
            stdio: 'pipe'
        });

        // Set up timeout for CLI process
        const timeoutHandle = setTimeout(() => {
            if (!processResolved) {
                processResolved = true;
                const timeoutMsg = '[TIMEOUT] CLI command timed out after 30 seconds';
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

// Note: HTTP-related interfaces and functions removed - CLI dispatcher is now the single source of truth

// Note: tryHttpCommand function removed - CLI dispatcher is now the single source of truth

// Note: pollForResult function removed - CLI dispatcher is now the single source of truth

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