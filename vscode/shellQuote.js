"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.quote = quote;
/**
 * Utility to safely quote shell arguments.
 */
function quote(args) {
    return args
        .map((arg) => {
        if (arg === '') {
            return "''";
        }
        return `'${arg.replace(/'/g, `'\\''`)}'`;
    })
        .join(' ');
}
