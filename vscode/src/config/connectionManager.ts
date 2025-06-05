import * as vscode from 'vscode';
import * as fs from 'fs';
import * as path from 'path';

// Declare process for Node.js environment
declare const process: {
    env: { [key: string]: string | undefined };
};

export interface ConnectionConfig {
    type: 'http';
    host: string;
    port: number;
    base_url: string;
    auth_token?: string;
    use_tls?: boolean;
}

export class ConnectionManager {
    private static instance: ConnectionManager;
    private config: ConnectionConfig | null = null;

    public static getInstance(): ConnectionManager {
        if (!ConnectionManager.instance) {
            ConnectionManager.instance = new ConnectionManager();
        }
        return ConnectionManager.instance;
    }

    /**
     * Get connection configuration from multiple sources in priority order:
     * 1. VS Code settings
     * 2. Environment variables
     * 3. Local connection file
     * 4. Default localhost
     */
    public async getConnectionConfig(): Promise<ConnectionConfig> {
        if (this.config) {
            return this.config;
        }

        // Priority 1: VS Code settings
        const vsCodeConfig = vscode.workspace.getConfiguration('agent-s3');
        const remoteHost = vsCodeConfig.get('remoteHost') as string;
        const remotePort = vsCodeConfig.get('remotePort') as number;
        const authToken = vsCodeConfig.get('authToken') as string;
        const useTls = vsCodeConfig.get('useTls') as boolean || false;

        if (remoteHost && remotePort) {
            this.config = {
                type: 'http',
                host: remoteHost,
                port: remotePort,
                base_url: `${useTls ? 'https' : 'http'}://${remoteHost}:${remotePort}`,
                auth_token: authToken,
                use_tls: useTls
            };
            return this.config;
        }

        // Priority 2: Environment variables (Node.js environment)
        let envHost: string | undefined;
        let envPort: string | undefined;
        let envToken: string | undefined;
        let envTls = false;
        
        try {
            // Check if we're in a Node.js environment (extension host)
            if (typeof process !== 'undefined' && process.env) {
                envHost = process.env.AGENT_S3_HOST;
                envPort = process.env.AGENT_S3_PORT;
                envToken = process.env.AGENT_S3_AUTH_TOKEN;
                envTls = process.env.AGENT_S3_USE_TLS === 'true';
            }
        } catch (error) {
            // Ignore errors accessing process.env in browser environments
        }

        if (envHost && envPort) {
            this.config = {
                type: 'http',
                host: envHost,
                port: parseInt(envPort),
                base_url: `${envTls ? 'https' : 'http'}://${envHost}:${envPort}`,
                auth_token: envToken,
                use_tls: envTls
            };
            return this.config;
        }

        // Priority 3: Local connection file
        const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
        if (workspaceFolder) {
            const connectionFile = path.join(workspaceFolder.uri.fsPath, '.agent_s3_http_connection.json');
            if (fs.existsSync(connectionFile)) {
                try {
                    const fileContent = fs.readFileSync(connectionFile, 'utf-8');
                    const fileConfig = JSON.parse(fileContent) as ConnectionConfig;
                    this.config = fileConfig;
                    return this.config;
                } catch (error) {
                    console.warn('Failed to parse connection file:', error);
                }
            }
        }

        // Priority 4: Default localhost
        this.config = {
            type: 'http',
            host: 'localhost',
            port: 8081,
            base_url: 'http://localhost:8081'
        };
        return this.config;
    }

    public async testConnection(): Promise<boolean> {
        try {
            const config = await this.getConnectionConfig();
            const headers: Record<string, string> = {
                'Content-Type': 'application/json'
            };
            
            if (config.auth_token) {
                headers['Authorization'] = `Bearer ${config.auth_token}`;
            }

            const response = await fetch(`${config.base_url}/health`, {
                method: 'GET',
                headers,
                signal: AbortSignal.timeout(5000)
            });
            
            return response.ok;
        } catch (error) {
            console.error('Connection test failed:', error);
            return false;
        }
    }

    public clearConfig(): void {
        this.config = null;
    }
}
