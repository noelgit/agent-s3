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

interface Buffer {}
declare const Buffer: {
  new(...args: any[]): Buffer;
  from(input: string | any[] | ArrayBuffer | SharedArrayBuffer): Buffer;
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
