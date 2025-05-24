/**
 * Minimal VS Code API typings for offline usage.
 * Provides loose 'any'-typed definitions so the extension can compile
 * without the full @types/vscode package.
 */

declare namespace vscode {
  interface Disposable {
    dispose(): void;
  }

  class EventEmitter<T> {
    event: any;
    fire(data: T): void;
    dispose(): void;
  }

  interface Memento {
    get(key: string, defaultValue?: any): any;
    update(key: string, value: any): Thenable<void>;
    [key: string]: any;
  }

  interface ExtensionContext {
    subscriptions: Disposable[];
    workspaceState: Memento;
    globalState: Memento;
    [key: string]: any;
  }

  type Thenable<T> = Promise<T>;

  const window: any;
  const workspace: any;
  const commands: any;
  const env: any;
  const Uri: any;
  const ViewColumn: any;

  // Type placeholders used within the extension
  type OutputChannel = any;
  type Terminal = any;
  type Webview = any;
  type WebviewPanel = any;
  type StatusBarItem = any;
  enum StatusBarAlignment { Left, Right }
}

declare module "vscode" {
  export = vscode;
}
