/**
 * Type definitions for VS Code webview API
 */

declare const vscode: {
  /**
   * Post a message to the VS Code extension
   * @param message - The message to post
   */
  postMessage: (message: any) => void;

  /**
   * Get the VS Code API state
   * @returns The state object
   */
  getState: () => any;

  /**
   * Set the VS Code API state
   * @param state - The state to set
   */
  setState: (state: any) => void;
};

export { vscode };
