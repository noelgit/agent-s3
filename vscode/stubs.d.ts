/* eslint-disable @typescript-eslint/no-explicit-any */
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
interface Buffer {}
declare const Buffer: {
  new(...args: any[]): Buffer;
  from(input: any, encoding?: string): Buffer;
  isBuffer(input: any): boolean;
};
namespace NodeJS {
  type Timeout = any;
}
