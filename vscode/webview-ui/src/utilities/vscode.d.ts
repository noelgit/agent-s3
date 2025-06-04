/**
 * Type definitions for VS Code webview API
 */

declare const vscode: {
  /**
   * Post a message to the VS Code extension
   * @param message - The message to post
   */
  postMessage: (message: unknown) => void;

  /**
   * Get the VS Code API state
   * @returns The state object
   */
  getState: () => unknown;

  /**
   * Set the VS Code API state
   * @param state - The state to set
   */
  setState: (state: unknown) => void;
};

export { vscode };
