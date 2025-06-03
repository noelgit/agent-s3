import * as vscode from 'vscode';
import { spawn } from 'child_process';
import { WebviewUIManager } from './webview-ui-loader';
import { CHAT_HISTORY_KEY } from './constants';
import type { ChatHistoryEntry } from './types/message';

interface HealthResponse {
    status: string;
}

let chatManager: WebviewUIManager | undefined;
let messageHistory: ChatHistoryEntry[] = [];
let terminalEmitter: vscode.EventEmitter<string> | undefined;
let agentTerminal: vscode.Terminal | undefined;

/**
 * Extension activation point
 */
export function activate(context: vscode.ExtensionContext): void {
    console.log('Agent-S3 HTTP Extension activated');

    // Initialize command
    const initCommand = vscode.commands.registerCommand('agent-s3.init', async () => {
        await executeAgentCommand('/init');
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

                    appendToTerminal(`$ ${text}\n`);
                    chatManager?.postMessage({ type: 'COMMAND_RESULT', content: { result: 'Processing...', success: true, command: text } });
                    await executeAgentCommand(text);

                    const ack: ChatHistoryEntry = { role: 'assistant', content: 'See terminal for details.', timestamp: new Date().toISOString() };
                    messageHistory.push(ack);
                    await context.workspaceState.update(CHAT_HISTORY_KEY, messageHistory);
                    chatManager?.postMessage({ type: 'CHAT_MESSAGE', content: { text: ack.content, source: 'agent' } });
                }
            });
        }

        chatManager.createOrShowPanel();
    });

    // Interactive view command
    const interactiveCommand = vscode.commands.registerCommand('agent-s3.openInteractiveView', async () => {
        const input = await vscode.window.showInputBox({
            prompt: 'Enter Agent-S3 command for interactive processing',
            placeHolder: '/plan add user authentication'
        });

        if (!input) return;
        await executeAgentCommand(input);
    });

    // Show chat entry command
    const showChatCommand = vscode.commands.registerCommand('agent-s3.showChatEntry', async () => {
        const input = await vscode.window.showInputBox({
            prompt: 'Enter message to add to chat',
            placeHolder: 'Your message here'
        });

        if (input) {
            // For now, treat as a command
            await executeAgentCommand(input);
        }
    });

    // Refresh commands (placeholder)
    const refreshChatCommand = vscode.commands.registerCommand('agent-s3.refreshChat', async () => {
        vscode.window.showInformationMessage('Chat view refreshed');
    });

    const refreshHistoryCommand = vscode.commands.registerCommand('agent-s3.refreshHistory', async () => {
        vscode.window.showInformationMessage('History view refreshed');
    });

    // HTTP status command
    const statusCommand = vscode.commands.registerCommand('agent-s3.status', async () => {
        try {
            // Try to connect to HTTP server
            const response = await fetch('http://localhost:8081/health');
            const data = await response.json() as HealthResponse;
            
            if (data.status === 'ok') {
                vscode.window.showInformationMessage('Agent-S3 HTTP Server: Connected ✅');
            } else {
                vscode.window.showWarningMessage('Agent-S3 HTTP Server: Unexpected response');
            }
        } catch (error) {
            // Fallback to CLI if HTTP server not available
            vscode.window.showWarningMessage('Agent-S3 HTTP Server: Not running. Using CLI mode.');
        }
    });

    context.subscriptions.push(
        initCommand,
        helpCommand, 
        guidelinesCommand,
        requestCommand,
        designAutoCommand,
        chatCommand,
        interactiveCommand,
        showChatCommand,
        refreshChatCommand,
        refreshHistoryCommand,
        statusCommand
    );
}

async function executeAgentCommand(command: string): Promise<void> {
    const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
    if (!workspaceFolder) {
        vscode.window.showErrorMessage('No workspace folder open');
        return;
    }

    const workspacePath = workspaceFolder.uri.fsPath;
    const term = getAgentTerminal();
    term.show(true);

    // Try HTTP server first, fallback to CLI
    try {
        const httpResult = await tryHttpCommand(command);
        if (httpResult) {
            appendToTerminal(`$ ${command}\n${httpResult}\n`);
            return;
        }
    } catch (error) {
        console.log('HTTP server not available, falling back to CLI');
    }

    return new Promise<void>((resolve) => {
        const process = spawn('python', ['-m', 'agent_s3.cli', command], {
            cwd: workspacePath,
            stdio: 'pipe'
        });

        process.stdout.on('data', (data: Buffer) => {
            appendToTerminal(data.toString());
        });

        process.stderr.on('data', (data: Buffer) => {
            appendToTerminal(data.toString());
        });

        process.on('close', (code: number | null) => {
            if (code !== 0) {
                vscode.window.showErrorMessage('Agent-S3 command failed.');
            }
            resolve();
        });
    });
}

async function tryHttpCommand(command: string): Promise<string | null> {
    try {
        let response;
        
        if (command === '/help') {
            response = await fetch('http://localhost:8081/help');
        } else {
            response = await fetch('http://localhost:8081/command', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ command })
            });
        }
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        
        const data = await response.json() as { result?: string; error?: string };
        return data.result || data.error || 'Command executed';
    } catch (error) {
        return null; // HTTP not available
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

    const emitter = new vscode.EventEmitter();
    terminalEmitter = emitter;
    const pty: vscode.Pseudoterminal = {
        onDidWrite: emitter.event,
        open: () => { return undefined; },
        close: () => { return undefined; }
    };

    agentTerminal = vscode.window.createTerminal({ name: 'Agent-S3', pty });
    return agentTerminal!;
}

function appendToTerminal(text: string): void {
    const term = getAgentTerminal();
    if (terminalEmitter) {
        terminalEmitter.fire(text.replace(/\r?\n/g, '\r\n'));
    }
    term.show(true);
}