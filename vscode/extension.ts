import * as vscode from 'vscode';
import { spawn, type ChildProcessWithoutNullStreams } from 'child_process';
import { WebviewUIManager } from './webview-ui-loader';
import { CHAT_HISTORY_KEY, DEFAULT_HTTP_TIMEOUT_MS, HTTP_TIMEOUT_SETTING } from './constants';
import type { ChatHistoryEntry } from './types/message';

interface HttpConnection {
    host: string;
    port: number;
}

let cachedConnection: HttpConnection | null = null;

async function getHttpConnection(): Promise<HttpConnection> {
    if (cachedConnection) {
        return cachedConnection;
    }
    const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
    if (!workspaceFolder) {
        cachedConnection = { host: 'localhost', port: 8081 };
        return cachedConnection;
    }
    const connectionUri = vscode.Uri.joinPath(workspaceFolder.uri, '.agent_s3_http_connection.json');
    try {
        const data = await vscode.workspace.fs.readFile(connectionUri);
        const text = new TextDecoder('utf8').decode(data);
        const json = JSON.parse(text) as { host?: string; port?: number };
        if (typeof json.host === 'string' && typeof json.port === 'number') {
            cachedConnection = { host: json.host, port: json.port };
        } else {
            cachedConnection = { host: 'localhost', port: 8081 };
        }
    } catch {
        cachedConnection = { host: 'localhost', port: 8081 };
    }
    return cachedConnection;
}

interface HealthResponse {
    status: string;
}

let chatManager: WebviewUIManager | undefined;
let messageHistory: ChatHistoryEntry[] = [];
// Use minimal type for terminalEmitter to avoid 'any' and generic issues
let terminalEmitter: { event: unknown; fire(data: string): void; dispose(): void } | undefined;
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
            const { host, port } = await getHttpConnection();
            const response = await fetch(`http://${host}:${port}/health`);
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

export async function executeAgentCommand(command: string): Promise<void> {
    const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
    if (!workspaceFolder) {
        vscode.window.showErrorMessage('No workspace folder open');
        return;
    }

    const workspacePath = workspaceFolder.uri.fsPath;
    const term = getAgentTerminal();
    term.show(true);

    // Try HTTP server first, fallback to CLI if it fails or times out
    try {
        const httpResult = await tryHttpCommand(command);
        if (httpResult) {
            appendToTerminal(`$ ${command}\n${httpResult.output}${httpResult.result}\n`);
            if (httpResult.success === false) {
                vscode.window.showErrorMessage('Agent-S3 command failed.');
            } else if (httpResult.success === null) {
                vscode.window.showInformationMessage('Processing...');
            }
            return;
        }
    } catch (error) {
        console.log('HTTP server not available, falling back to CLI');
        vscode.window.showWarningMessage('Agent-S3 HTTP server not available. Using CLI mode.');
    }

    return new Promise<void>((resolve) => {
        const childProcess: ChildProcessWithoutNullStreams = spawn('python', ['-m', 'agent_s3.cli', command], {
            cwd: workspacePath,
            stdio: 'pipe'
        });

        childProcess.stdout.on('data', (data: Buffer) => {
            appendToTerminal(data.toString());
        });

        childProcess.stderr.on('data', (data: Buffer) => {
            appendToTerminal(data.toString());
        });

        childProcess.on('error', (err: Error) => {
            appendToTerminal(`Error starting CLI: ${err.message}\n`);
            vscode.window.showErrorMessage('Failed to start Agent-S3 CLI.');
            resolve();
        });

        childProcess.on('close', (code: number | null) => {
            if (code !== 0) {
                vscode.window.showErrorMessage('Agent-S3 command failed.');
            }
            resolve();
        });
    });
}

interface HttpResult { result: string; output: string; success: boolean | null }

export async function tryHttpCommand(command: string): Promise<HttpResult | null> {
    const config = vscode.workspace.getConfiguration('agent-s3');
    const timeoutEnv = process.env.AGENT_S3_HTTP_TIMEOUT;
    const timeoutMs = Number(timeoutEnv) ||
        (config.get(HTTP_TIMEOUT_SETTING.split('.')[1], DEFAULT_HTTP_TIMEOUT_MS) as number);

    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    const { host, port } = await getHttpConnection();
    const baseUrl = `http://${host}:${port}`;

    try {
        let response;

        if (command === '/help') {
            response = await fetch(`${baseUrl}/help`, {
                signal: controller.signal
            });
        } else {
            response = await fetch(`${baseUrl}/command`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ command }),
                signal: controller.signal
            });
        }

        clearTimeout(timer);

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json() as { result?: string; output?: string; success?: boolean; error?: string };
        if (data.error) {
            return { result: data.error, output: '', success: false };
        }
        return { result: data.result ?? '', output: data.output ?? '', success: data.success ?? true };
    } catch (error) {
        console.log(`HTTP command failed: ${String(error)}`);
        if ((error as { name?: string }).name === 'AbortError') {
            try {
                const health = await fetch(`${baseUrl}/health`);
                if (health.ok) {
                    return { result: 'Processing...', output: '', success: null };
                }
            } catch {
                // ignore
            }
        }
        return null; // HTTP not available or timed out
    } finally {
        clearTimeout(timer);
    }
}

async function pollForResult(baseUrl: string, jobId: string): Promise<HttpResult | null> {
    const config = vscode.workspace.getConfiguration('agent-s3');
    const interval = config.get('statusPollIntervalMs', 1000);
    const attempts = config.get('statusPollAttempts', 30);

    for (let i = 0; i < attempts; i++) {
        try {
            await new Promise(resolve => setTimeout(resolve, interval));
            const resp = await fetch(`${baseUrl}/status/${encodeURIComponent(jobId)}`);
            if (!resp.ok) {
                continue;
            }
            const data = await resp.json() as { ready?: boolean; result?: string; output?: string; success?: boolean };
            if (data.ready) {
                return { result: data.result ?? '', output: data.output ?? '', success: data.success ?? true };
            }
        } catch (err) {
            console.log(`Status polling error: ${String(err)}`);
        }
    }
    return null;
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