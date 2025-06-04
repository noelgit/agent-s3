// Utility for communicating with the VS Code extension
// This file provides a consistent way to post messages to the VS Code extension

interface VSCodeAPI<TState = unknown> {
  postMessage: (message: unknown) => void;
  getState: () => TState | undefined;
  setState: (state: TState) => void;
}

// Acquire the VS Code API object
declare const acquireVsCodeApi: <TState>() => VSCodeAPI<TState>;

// Get the VS Code API
const vscode = acquireVsCodeApi();

export { vscode };
