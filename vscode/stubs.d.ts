declare module "vscode" {
  const x: unknown;
  export = x;
}
declare module "fs" {
  const x: unknown;
  export = x;
}
declare module "path" {
  const x: unknown;
  export = x;
}

declare module "crypto" {
  const x: unknown;
  export = x;
}
interface Buffer {}
declare const Buffer: {
  new(...args: unknown[]): Buffer;
  from(input: unknown, encoding?: string): Buffer;
  isBuffer(input: unknown): boolean;
};
namespace NodeJS {
  type Timeout = unknown;
}
