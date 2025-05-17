// Utility for communicating with the VS Code extension
// This file provides a consistent way to post messages to the VS Code extension

interface VSCodeAPI {
  postMessage: (message: any) => void;
  getState: () => any;
  setState: (state: any) => void;
}

// Acquire the VS Code API object
declare const acquireVsCodeApi: () => VSCodeAPI;

// Get the VS Code API
const vscode = acquireVsCodeApi();

export { vscode };