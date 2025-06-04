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
    event: unknown;
    fire(data: T): void;
    dispose(): void;
  }

  interface Memento {
    get<T>(key: string): T | undefined;
    get<T>(key: string, defaultValue: T): T;
    update(key: string, value: unknown): Thenable<void>;
    [key: string]: unknown;
  }

  interface ExtensionContext {
    subscriptions: Disposable[];
    workspaceState: Memento;
    globalState: Memento;
    [key: string]: unknown;
  }

  type Thenable<T> = Promise<T>;

  const window: unknown;
  const workspace: unknown;
  const commands: unknown;
  const env: unknown;
  class Uri {
    fsPath: string;
    constructor(path?: string);
    static file(path: string): Uri;
    static joinPath(base: Uri, ...paths: string[]): Uri;
  }
  const ViewColumn: unknown;

  // Type placeholders used within the extension
  type OutputChannel = unknown;
  type Terminal = unknown;
  type Webview = unknown;
  type WebviewPanel = unknown;
  type StatusBarItem = unknown;
  enum StatusBarAlignment { Left, Right }
}

declare module "vscode" {
  export = vscode;
}
