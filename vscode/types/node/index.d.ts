declare module "fs" {
  interface Stats { size: number }
  function stat(path: string, callback: (err: NodeJS.ErrnoException | null, stats: Stats) => void): void;
  function createReadStream(path: string, options?: unknown): unknown;
  export { Stats, stat, createReadStream };
}

declare module "path" {
  const x: unknown;
  export = x;
}

declare module "child_process" {
  interface ChildProcess {
    stdout: unknown;
    stderr: unknown;
    on(event: string, listener: (code: number) => void): this;
  }
  function spawn(command: string, args?: string[], options?: unknown): ChildProcess;
  export { ChildProcess, spawn };
}

interface Buffer {}
declare const Buffer: {
  new(...args: unknown[]): Buffer;
  from(input: string | unknown[] | ArrayBuffer | SharedArrayBuffer, encoding?: string): Buffer;
};

declare namespace NodeJS {
  interface Timeout {}
  interface ErrnoException extends Error {
    code?: string | number;
  }
}

declare const console: unknown;
declare function setTimeout(handler: (...args: unknown[]) => void, timeout?: number, ...args: unknown[]): NodeJS.Timeout;
declare function clearTimeout(timeoutId: NodeJS.Timeout): void;
declare function setInterval(handler: (...args: unknown[]) => void, timeout?: number, ...args: unknown[]): NodeJS.Timeout;
declare function clearInterval(intervalId: NodeJS.Timeout): void;

declare function require(moduleName: string): unknown;

// Fetch API
declare function fetch(input: string, init?: unknown): Promise<{
  ok: boolean;
  status: number;
  json(): Promise<unknown>;
  text(): Promise<string>;
}>;

// Global Buffer for VS Code extension environment
declare const global: unknown;
