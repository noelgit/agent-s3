import * as vscode from 'vscode';
import * as fs from 'fs';
import * as path from 'path';

export function activate(context: vscode.ExtensionContext) {
    console.log('Agent-S3 HTTP Extension activated');

    // Help command
    const helpCommand = vscode.commands.registerCommand('agent-s3.help', async () => {
        try {
            const response = await fetch('http://localhost:8081/help');
            const data = await response.json();
            
            // Show result in new document
            const doc = await vscode.workspace.openTextDocument({
                content: `Agent-S3 Help\n\n${data.result}`,
                language: 'markdown'
            });
            await vscode.window.showTextDocument(doc);
            
        } catch (error) {
            vscode.window.showErrorMessage(`Agent-S3 Error: ${error}`);
        }
    });

    // Chat command
    const chatCommand = vscode.commands.registerCommand('agent-s3.chat', async () => {
        const command = await vscode.window.showInputBox({
            prompt: 'Enter Agent-S3 command',
            placeHolder: '/help, /config, /plan <description>'
        });

        if (!command) return;

        try {
            const response = await fetch('http://localhost:8081/command', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ command })
            });
            
            const data = await response.json();
            
            // Show result in new document
            const doc = await vscode.workspace.openTextDocument({
                content: `Command: ${command}\n\nResult:\n${data.result}`,
                language: 'markdown'
            });
            await vscode.window.showTextDocument(doc);
            
        } catch (error) {
            vscode.window.showErrorMessage(`Agent-S3 Error: ${error}`);
        }
    });

    // Status command
    const statusCommand = vscode.commands.registerCommand('agent-s3.status', async () => {
        try {
            const response = await fetch('http://localhost:8081/health');
            const data = await response.json();
            
            if (data.status === 'ok') {
                vscode.window.showInformationMessage('Agent-S3 HTTP Server: Connected ✅');
            } else {
                vscode.window.showWarningMessage('Agent-S3 HTTP Server: Unexpected response');
            }
        } catch (error) {
            vscode.window.showErrorMessage('Agent-S3 HTTP Server: Not running ❌');
        }
    });

    context.subscriptions.push(helpCommand, chatCommand, statusCommand);
}

export function deactivate() {
    console.log('Agent-S3 HTTP Extension deactivated');
}