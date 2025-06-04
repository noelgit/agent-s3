/**
 * WebView API declarations for VS Code extensions
 */

declare module "vscode-webview" {
  /**
   * Post a message to the extension host
   */
  export function postMessage(message: unknown): void;

  /**
   * Get state previously set
   */
  export function getState(): unknown;

  /**
   * Set state that can be retrieved later
   */
  export function setState(state: unknown): void;

  /**
   * WebView API object
   */
  export const vscode: {
    postMessage: typeof postMessage;
    getState: typeof getState;
    setState: typeof setState;
  };
}
