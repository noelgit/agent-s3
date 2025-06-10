import * as vscode from 'vscode';
import { spawn } from 'child_process';
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

    // Handle interactive design command specially
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
    
    try {
        // Start the design process
        const pythonExec = getPythonExecutable();
        const designProcess = spawn(pythonExec, ['-c', `
import sys
sys.path.append('${workspacePath.replace(/\\/g, '\\\\')}')
from agent_s3.coordinator import Coordinator
from agent_s3.design_manager import DesignManager

coordinator = Coordinator()
design_manager = DesignManager(coordinator)

# Start design conversation
response = design_manager.start_design_conversation("${objective.replace(/"/g, '\\"')}")
print("DESIGN_RESPONSE:" + response)

# Check if complete
is_complete = design_manager.detect_design_completion()
print("DESIGN_COMPLETE:" + str(is_complete))
`], {
            cwd: workspacePath,
            stdio: 'pipe'
        });

        let aiResponse = '';
        let isComplete = false;

        // Get initial response
        await new Promise<void>((resolve, reject) => {
            let buffer = '';
            designProcess.stdout?.on('data', (data: Buffer) => {
                buffer += data.toString();
                const lines = buffer.split('\n');
                buffer = lines.pop() || '';
                
                for (const line of lines) {
                    if (line.startsWith('DESIGN_RESPONSE:')) {
                        aiResponse = line.replace('DESIGN_RESPONSE:', '');
                    } else if (line.startsWith('DESIGN_COMPLETE:')) {
                        isComplete = line.replace('DESIGN_COMPLETE:', '') === 'True';
                    }
                }
            });

            designProcess.on('close', () => resolve());
            designProcess.on('error', reject);
        });

        // Show AI response and handle conversation
        let conversationOutput = `Design Session Started for: ${objective}\n\n`;
        conversationOutput += `AI Designer: ${aiResponse}\n\n`;

        // Continue conversation until complete
        while (!isComplete) {
            const userResponse = await vscode.window.showInputBox({
                prompt: 'Your response to the AI designer (or type "/finalize-design" to complete)',
                placeHolder: 'Provide more details, ask questions, or give feedback...',
                ignoreFocusOut: true
            });

            if (!userResponse) {
                conversationOutput += 'Design session cancelled by user.\n';
                break;
            }

            conversationOutput += `You: ${userResponse}\n\n`;

            // Send user response and get AI reply
            const continueProcess = spawn(pythonExec, ['-c', `
import sys
sys.path.append('${workspacePath.replace(/\\/g, '\\\\')}')
from agent_s3.coordinator import Coordinator
from agent_s3.design_manager import DesignManager

coordinator = Coordinator()
design_manager = DesignManager(coordinator)

# Load existing conversation from design.txt if it exists
try:
    with open('design.txt', 'r') as f:
        content = f.read()
    # Extract conversation from file and reload into design_manager
    # This is a simplified approach - in practice you'd want better state management
except:
    pass

# Continue conversation
response, complete = design_manager.continue_conversation("${userResponse.replace(/"/g, '\\"')}")
print("DESIGN_RESPONSE:" + (response or ""))
print("DESIGN_COMPLETE:" + str(complete))

# Write to file if complete
if complete:
    success, message = design_manager.write_design_to_file()
    print("WRITE_SUCCESS:" + str(success))
    print("WRITE_MESSAGE:" + message)
`], {
                cwd: workspacePath,
                stdio: 'pipe'
            });

            await new Promise<void>((resolve, reject) => {
                let buffer = '';
                continueProcess.stdout?.on('data', (data: Buffer) => {
                    buffer += data.toString();
                    const lines = buffer.split('\n');
                    buffer = lines.pop() || '';
                    
                    for (const line of lines) {
                        if (line.startsWith('DESIGN_RESPONSE:')) {
                            aiResponse = line.replace('DESIGN_RESPONSE:', '');
                        } else if (line.startsWith('DESIGN_COMPLETE:')) {
                            isComplete = line.replace('DESIGN_COMPLETE:', '') === 'True';
                        } else if (line.startsWith('WRITE_SUCCESS:')) {
                            const writeSuccess = line.replace('WRITE_SUCCESS:', '') === 'True';
                            if (writeSuccess) {
                                conversationOutput += 'Design successfully written to design.txt\n';
                            }
                        }
                    }
                });

                continueProcess.on('close', () => resolve());
                continueProcess.on('error', reject);
            });

            if (aiResponse) {
                conversationOutput += `AI Designer: ${aiResponse}\n\n`;
            }

            if (isComplete) {
                conversationOutput += 'Design conversation completed!\n';
                break;
            }
        }

        return conversationOutput;

    } catch (error) {
        return `Error in interactive design: ${error instanceof Error ? error.message : String(error)}`;
    }
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