import * as vscode from 'vscode';
import * as path from 'path';
import * as fs from 'fs';

/**
 * Creates and manages a webview panel for React-based interactive components
 */
export class InteractiveWebviewManager {
  private panel: vscode.WebviewPanel | undefined;
  private extensionUri: vscode.Uri;
  private disposables: vscode.Disposable[] = [];
  private messageHandler: ((message: any) => void) | undefined;

  constructor(extensionUri: vscode.Uri) {
    this.extensionUri = extensionUri;
  }

  /**
   * Create and show the interactive webview panel
   */
  public createOrShowPanel(): vscode.WebviewPanel {
    // If we already have a panel, show it
    if (this.panel) {
      this.panel.reveal(vscode.ViewColumn.Beside);
      return this.panel;
    }

    // Otherwise, create a new panel
    this.panel = vscode.window.createWebviewPanel(
      'agent-s3-interactive',
      'Agent-S3 Interactive Components',
      vscode.ViewColumn.Beside,
      {
        enableScripts: true,
        retainContextWhenHidden: true,
        localResourceRoots: [
          vscode.Uri.joinPath(this.extensionUri, 'webview-ui')
        ]
      }
    );

    // Set webview content
    this.panel.webview.html = this.getWebviewContent(this.panel.webview);

    // Handle disposal
    this.panel.onDidDispose(() => {
      this.panel = undefined;
      
      // Dispose of all disposables associated with this panel
      while (this.disposables.length) {
        const disposable = this.disposables.pop();
        if (disposable) {
          disposable.dispose();
        }
      }
    }, null, this.disposables);

    // Handle messages from the webview
    this.panel.webview.onDidReceiveMessage(message => {
      if (this.messageHandler) {
        this.messageHandler(message);
      }
    }, null, this.disposables);

    return this.panel;
  }

  /**
   * Set a message handler for the webview
   */
  public setMessageHandler(handler: (message: any) => void): void {
    this.messageHandler = handler;
  }

  /**
   * Send a message to the webview
   */
  public postMessage(message: any): boolean {
    if (!this.panel) {
      return false;
    }

    return this.panel.webview.postMessage(message);
  }

  /**
   * Get the webview content
   */
  private getWebviewContent(webview: vscode.Webview): string {
    // Local path to the bundled React app
    const webviewPath = path.join(this.extensionUri.fsPath, 'webview-ui');
    const indexPath = path.join(webviewPath, 'index.html');

    // Read the HTML file
    let html = fs.existsSync(indexPath) 
      ? fs.readFileSync(indexPath, 'utf8')
      : this.getFallbackHtml();

    // Create a nonce for CSP
    const nonce = this.getNonce();

    // Convert all local resource paths to vscode-resource URLs
    html = html.replace(/{{cspSource}}/g, webview.cspSource);

    // Use a nonce for all scripts
    html = html.replace(/<script/g, `<script nonce="${nonce}"`);

    // Replace paths with proper webview URIs
    html = this.replaceResourcePaths(html, webview, webviewPath);

    return html;
  }

  /**
   * Get fallback HTML when the React app isn't built yet
   */
  private getFallbackHtml(): string {
    return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Agent-S3 Interactive View</title>
  <style>
    body { 
      font-family: var(--vscode-font-family); 
      color: var(--vscode-foreground); 
      background-color: var(--vscode-editor-background);
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      height: 100vh;
      margin: 0;
      padding: 0 2rem;
      text-align: center;
    }
    .loading {
      margin-bottom: 2rem;
    }
    .loading::after {
      content: '...';
      animation: dots 1.5s steps(5, end) infinite;
    }
    @keyframes dots {
      0%, 20% { content: '.'; }
      40% { content: '..'; }
      60% { content: '...'; }
      80%, 100% { content: ''; }
    }
  </style>
</head>
<body>
  <h1 class="loading">Loading Agent-S3 Interactive Components</h1>
  <p>If this message persists, the React app may not be built correctly.</p>
</body>
</html>`;
  }

  /**
   * Generate a nonce string
   */
  private getNonce(): string {
    let text = '';
    const possible = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
    for (let i = 0; i < 32; i++) {
      text += possible.charAt(Math.floor(Math.random() * possible.length));
    }
    return text;
  }

  /**
   * Replace local resource paths with webview URIs
   */
  private replaceResourcePaths(html: string, webview: vscode.Webview, basePath: string): string {
    // Find all resource paths in the HTML
    const srcRegex = /src=["']([^"']+)["']/g;
    const hrefRegex = /href=["']([^"']+)["']/g;

    // Replace src attributes
    html = html.replace(srcRegex, (match, src) => {
      // Skip external URLs and data URIs
      if (src.startsWith('http') || src.startsWith('data:')) {
        return match;
      }

      // Create a URI for the resource
      const resourcePath = path.join(basePath, src);
      const uri = webview.asWebviewUri(vscode.Uri.file(resourcePath));
      
      return `src="${uri}"`;
    });

    // Replace href attributes
    html = html.replace(hrefRegex, (match, href) => {
      // Skip external URLs and fragment identifiers
      if (href.startsWith('http') || href.startsWith('#')) {
        return match;
      }

      // Create a URI for the resource
      const resourcePath = path.join(basePath, href);
      const uri = webview.asWebviewUri(vscode.Uri.file(resourcePath));
      
      return `href="${uri}"`;
    });

    return html;
  }
}