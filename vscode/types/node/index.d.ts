declare module 'fs' {
  const x: any;
  export = x;
}

declare module 'path' {
  const x: any;
  export = x;
}

interface Buffer {}

declare namespace NodeJS {
  interface Timeout {}
  interface ErrnoException extends Error {
    code?: string | number;
  }
}

declare function require(moduleName: string): any;
