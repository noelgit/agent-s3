import * as vscode from 'vscode';
import { ConnectionManager } from '../config/connectionManager';

export interface HttpResponse {
    result: string;
    output?: string;
    success: boolean;
}

export class HttpClient {
    private connectionManager: ConnectionManager;

    constructor() {
        this.connectionManager = ConnectionManager.getInstance();
    }

    public async sendCommand(command: string): Promise<HttpResponse> {
        const config = await this.connectionManager.getConnectionConfig();
        const timeout = vscode.workspace.getConfiguration('agent-s3').get('httpTimeoutMs') as number || 10000;

        const headers: Record<string, string> = {
            'Content-Type': 'application/json'
        };

        if (config.auth_token) {
            headers['Authorization'] = `Bearer ${config.auth_token}`;
        }

        try {
            const response = await fetch(`${config.base_url}/command`, {
                method: 'POST',
                headers,
                body: JSON.stringify({ command }),
                signal: AbortSignal.timeout(timeout)
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: Request failed`);
            }

            const data = await response.json() as HttpResponse;
            return data;
        } catch (error) {
            console.error('HTTP command failed:', error);
            throw error;
        }
    }


    public async testConnection(): Promise<boolean> {
        return await this.connectionManager.testConnection();
    }
}
