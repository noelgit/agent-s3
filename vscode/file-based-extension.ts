import * as vscode from 'vscode';
import * as fs from 'fs';
import * as path from 'path';

export function activate(context: vscode.ExtensionContext) {
    
    const helpCommand = vscode.commands.registerCommand('agent-s3.help', async () => {
        await sendCommand('/help');
    });

    const chatCommand = vscode.commands.registerCommand('agent-s3.chat', async () => {
        const input = await vscode.window.showInputBox({
            prompt: 'Enter command',
            placeHolder: '/help'
        });
        
        if (input) {
            await sendCommand(input);
        }
    });

    context.subscriptions.push(helpCommand, chatCommand);
}

async function sendCommand(command: string) {
    const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
    if (!workspaceFolder) {
        vscode.window.showErrorMessage('No workspace folder open');
        return;
    }

    const workspacePath = workspaceFolder.uri.fsPath;
    const commandFile = path.join(workspacePath, '.agent_s3_command.json');
    const responseFile = path.join(workspacePath, '.agent_s3_response.json');

    // Write command
    const commandData = {
        command: command,
        timestamp: Date.now(),
        id: Math.random().toString(36)
    };

    fs.writeFileSync(commandFile, JSON.stringify(commandData, null, 2));

    // Wait for response (with timeout)
    let attempts = 0;
    const maxAttempts = 30; // 30 seconds

    while (attempts < maxAttempts) {
        if (fs.existsSync(responseFile)) {
            try {
                const responseData = JSON.parse(fs.readFileSync(responseFile, 'utf-8'));
                
                if (responseData.id === commandData.id) {
                    // Show response
                    vscode.workspace.openTextDocument({
                        content: `Command: ${command}\n\nResponse:\n${responseData.result}`,
                        language: 'markdown'
                    }).then((doc: vscode.TextDocument) => {
                        vscode.window.showTextDocument(doc);
                    });

                    // Clean up
                    fs.unlinkSync(commandFile);
                    fs.unlinkSync(responseFile);
                    return;
                }
            } catch (e) {
                // Response file not ready yet
            }
        }

        attempts++;
        await new Promise(resolve => setTimeout(resolve, 1000));
    }

    vscode.window.showErrorMessage('Command timeout - no response from Agent-S3');
}