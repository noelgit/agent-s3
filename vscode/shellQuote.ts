/**
 * Utility to safely quote shell arguments.
 */
export function quote(args: string[]): string {
  return args
    .map((arg) => {
      if (arg === '') {
        return "''";
      }
      return `'${arg.replace(/'/g, `'\\''`)}'`;
    })
    .join(' ');
}
