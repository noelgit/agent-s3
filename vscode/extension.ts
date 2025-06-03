import * as vscode from 'vscode';
import * as fs from 'fs';
import * as path from 'path';
import { spawn } from 'child_process';

interface HealthResponse {
    status: string;
}

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

    // Chat window that sends commands directly
    const chatCommand = vscode.commands.registerCommand('agent-s3.openChatWindow', async () => {
        const input = await vscode.window.showInputBox({
            prompt: 'Enter Agent-S3 command (e.g., /help, /plan, etc.)',
            placeHolder: '/help'
        });

        if (!input) return;
        await executeAgentCommand(input);
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

    // Try HTTP server first, fallback to CLI
    try {
        const httpResult = await tryHttpCommand(command);
        if (httpResult) {
            // Show output in new document
            const doc = await vscode.workspace.openTextDocument({
                content: `Agent-S3 Command: ${command}\n\n${httpResult}`,
                language: 'markdown'
            });
            await vscode.window.showTextDocument(doc);
            return;
        }
    } catch (error) {
        console.log('HTTP server not available, falling back to CLI');
    }

    // Fallback to CLI execution
    return new Promise<void>((resolve) => {
        const process = spawn('python', ['-m', 'agent_s3.cli', command], {
            cwd: workspacePath,
            stdio: 'pipe'
        });

        let output = '';
        let error = '';

        process.stdout.on('data', (data: Buffer) => {
            output += data.toString();
        });

        process.stderr.on('data', (data: Buffer) => {
            error += data.toString();
        });

        process.on('close', (code: number | null) => {
            if (code === 0) {
                // Show output in new document
                vscode.workspace.openTextDocument({
                    content: `Agent-S3 Command: ${command}\n\n${output}`,
                    language: 'markdown'
                }).then((doc: vscode.TextDocument) => {
                    vscode.window.showTextDocument(doc);
                });
            } else {
                vscode.window.showErrorMessage(`Agent-S3 Error: ${error}`);
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
}