declare module "fs" {
  interface Stats { size: number }
  function stat(path: string, callback: (err: NodeJS.ErrnoException | null, stats: Stats) => void): void;
  function createReadStream(path: string, options?: any): any;
  export { Stats, stat, createReadStream };
}

declare module "path" {
  const x: any;
  export = x;
}

declare module "child_process" {
  interface ChildProcess {
    stdout: any;
    stderr: any;
    on(event: string, listener: (code: number) => void): this;
  }
  function spawn(command: string, args?: string[], options?: any): ChildProcess;
  export { ChildProcess, spawn };
}

interface Buffer {}
declare const Buffer: {
  new(...args: any[]): Buffer;
  from(input: string | any[] | ArrayBuffer | SharedArrayBuffer, encoding?: string): Buffer;
};

declare namespace NodeJS {
  interface Timeout {}
  interface ErrnoException extends Error {
    code?: string | number;
  }
}

declare const console: any;
declare function setTimeout(handler: (...args: any[]) => void, timeout?: number, ...args: any[]): NodeJS.Timeout;
declare function clearTimeout(timeoutId: NodeJS.Timeout): void;
declare function setInterval(handler: (...args: any[]) => void, timeout?: number, ...args: any[]): NodeJS.Timeout;
declare function clearInterval(intervalId: NodeJS.Timeout): void;

declare function require(moduleName: string): any;

// Fetch API
declare function fetch(input: string, init?: any): Promise<{
  ok: boolean;
  status: number;
  json(): Promise<any>;
  text(): Promise<string>;
}>;

// Global Buffer for VS Code extension environment
declare const global: any;
