import * as vscode from "vscode";
import * as path from "path";
import * as fs from "fs";
import * as crypto from "crypto";

/**
 * Creates and manages a webview panel for React-based interactive components
 */
export class WebviewUIManager {
  private panel: vscode.WebviewPanel | undefined;
  private extensionUri: vscode.Uri;
  private disposables: vscode.Disposable[] = [];
  private messageHandler: ((message: unknown) => void) | undefined;
  private panelId: string;
  private title: string;

  constructor(extensionUri: vscode.Uri, panelId: string, title: string) {
    this.extensionUri = extensionUri;
    this.panelId = panelId;
    this.title = title;
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
      this.panelId,
      this.title,
      vscode.ViewColumn.Beside,
      {
        enableScripts: true,
        retainContextWhenHidden: true,
        localResourceRoots: [
          vscode.Uri.joinPath(this.extensionUri, "webview-ui"),
        ],
      },
    );

    // Set webview content
    this.panel!.webview.html = this.getWebviewContent(this.panel!.webview);

    // Handle disposal
    this.panel!.onDidDispose(
      () => {
        this.panel = undefined;

        // Dispose of all disposables associated with this panel
        while (this.disposables.length) {
          const disposable = this.disposables.pop();
          if (disposable) {
            disposable.dispose();
          }
        }
      },
      null,
      this.disposables,
    );

    // Handle messages from the webview
    this.panel!.webview.onDidReceiveMessage(
      (message: unknown) => {
        if (this.messageHandler) {
          this.messageHandler(message);
        }
      },
      null,
      this.disposables,
    );

    return this.panel!;
  }

  /**
   * Set a message handler for the webview
   */
  public setMessageHandler(handler: (message: unknown) => void): void {
    this.messageHandler = handler;
  }

  /**
   * Send a message to the webview
   */
  public async postMessage(message: unknown): Promise<boolean> {
    if (!this.panel) {
      return false;
    }

    return await this.panel.webview.postMessage(message);
  }

  /**
   * Get the webview content
   */
  private getWebviewContent(webview: vscode.Webview): string {
    // Local path to the React app and possible build directory
    const webviewRoot = path.join(this.extensionUri.fsPath, "webview-ui");
    const buildIndexPath = path.join(webviewRoot, "build", "index.html");
    const devIndexPath = path.join(webviewRoot, "index.html");

    const indexPath = fs.existsSync(buildIndexPath)
      ? buildIndexPath
      : devIndexPath;

    // Read the HTML file
    let html = fs.existsSync(indexPath)
      ? fs.readFileSync(indexPath, "utf8")
      : this.getFallbackHtml();

    // Create a nonce for CSP
    const nonce = this.getNonce();

    // Convert all local resource paths to vscode-resource URLs
    html = html.replace(/{{cspSource}}/g, webview.cspSource);

    // Replace nonce placeholders
    html = html.replace(/{{nonce}}/g, nonce);

    // Use a nonce for all scripts and style tags
    html = html.replace(/<script/g, `<script nonce="${nonce}"`);
    html = html.replace(/<style/g, `<style nonce="${nonce}"`);

    // Replace paths with proper webview URIs
    const resourceBase = path.dirname(indexPath);
    html = this.replaceResourcePaths(html, webview, resourceBase);

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
    return crypto.randomBytes(16).toString("hex");
  }

  /**
   * Replace local resource paths with webview URIs
   */
  private replaceResourcePaths(
    html: string,
    webview: vscode.Webview,
    basePath: string,
  ): string {
    // Find all resource paths in the HTML
    const srcRegex = /src=["']([^"']+)["']/g;
    const hrefRegex = /href=["']([^"']+)["']/g;

    // Replace src attributes
    html = html.replace(srcRegex, (match, src) => {
      // Skip external URLs and data URIs
      if (src.startsWith("http") || src.startsWith("data:")) {
        return match;
      }

      // Normalize the relative path to avoid issues with leading slashes
      const cleaned = src.replace(/^\/?/, "").replace(/^\.\//, "");
      const resourcePath = path.join(basePath, cleaned);
      const uri = webview.asWebviewUri(vscode.Uri.file(resourcePath));

      return `src="${uri}"`;
    });

    // Replace href attributes
    html = html.replace(hrefRegex, (match, href) => {
      // Skip external URLs and fragment identifiers
      if (href.startsWith("http") || href.startsWith("#")) {
        return match;
      }

      const cleaned = href.replace(/^\/?/, "").replace(/^\.\//, "");
      const resourcePath = path.join(basePath, cleaned);
      const uri = webview.asWebviewUri(vscode.Uri.file(resourcePath));

      return `href="${uri}"`;
    });

    return html;
  }
}
