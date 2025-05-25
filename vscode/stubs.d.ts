declare module "vscode" {
  const x: any;
  export = x;
}
declare module "fs" {
  const x: any;
  export = x;
}
declare module "path" {
  const x: any;
  export = x;
}

declare module "crypto" {
  const x: any;
  export = x;
}
declare module "ws" {
  export as namespace WS;
  class WebSocket {
    static OPEN: number;
    constructor(url: string);
    readyState: number;
    on(event: string, listener: (...args: any[]) => void): void;
    send(data: any, cb?: (err?: Error) => void): void;
    close(code?: number, reason?: string): void;
  }
  type RawData = any;
}
interface Buffer {}
declare const Buffer: {
  new(...args: any[]): Buffer;
  from(input: any, encoding?: string): Buffer;
  isBuffer(input: any): boolean;
};
namespace NodeJS {
  type Timeout = any;
}
