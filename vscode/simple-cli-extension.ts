import * as vscode from 'vscode';
import * as cp from 'child_process';
import * as path from 'path';

const { spawn } = cp;

export function activate(context: vscode.ExtensionContext): void {
    
    // Simple help command
    const helpCommand = vscode.commands.registerCommand('agent-s3.help', async () => {
        const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
        if (!workspaceFolder) {
            vscode.window.showErrorMessage('No workspace folder open');
            return;
        }

        const terminal = vscode.window.createTerminal('Agent-S3');
        terminal.show();
        terminal.sendText(`cd "${workspaceFolder.uri.fsPath}" && python -m agent_s3.cli /help`);
    });

    // Chat window that sends commands directly
    const chatCommand = vscode.commands.registerCommand('agent-s3.chat', async () => {
        const input = await vscode.window.showInputBox({
            prompt: 'Enter Agent-S3 command (e.g., /help, /plan, etc.)',
            placeHolder: '/help'
        });

        if (!input) return;

        const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
        if (!workspaceFolder) {
            vscode.window.showErrorMessage('No workspace folder open');
            return;
        }

        // Execute command and show result
        executeAgentCommand(input, workspaceFolder.uri.fsPath);
    });

    context.subscriptions.push(helpCommand, chatCommand);
}

async function executeAgentCommand(command: string, workspacePath: string) {
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