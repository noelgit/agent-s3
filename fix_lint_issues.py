#!/usr/bin/env python3
"""
A script to fix common linting issues across the codebase.
This script handles:
1. Removing trailing whitespace
2. Fixing long lines (where possible)
3. Adding type annotations
4. Fixing imports
"""
from pathlib import Path
import re

# Number of spaces to use for indentation
INDENT = 4

def remove_trailing_whitespace(file_path):
    """Remove trailing whitespace from a file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # Remove trailing whitespace
    fixed_lines = [line.rstrip() + '\n' for line in lines]

    # Don't modify the file if nothing changed
    if fixed_lines == lines:
        return False

    with open(file_path, 'w', encoding='utf-8') as f:
        f.writelines(fixed_lines)

    return True

def fix_line_length(file_path, max_length=100):
    """Fix lines that are too long by breaking them at appropriate points."""
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    fixed_lines = []
    modified = False

    for line in lines:
        if len(line.rstrip()) <= max_length:
            fixed_lines.append(line)
            continue

        # Don't try to fix comment lines or docstrings
        if line.strip().startswith('#') or '"""' in line or "'''" in line:
            fixed_lines.append(line)
            continue

        # Handle function arguments
        if re.search(r'\bdef\s+\w+\s*\(', line) and ')' in line:
            # Break long function signature
            indent = len(line) - len(line.lstrip())
            parts = re.split(r'(\(|\)|,)', line.strip())
            new_line = line[:indent]
            current_len = indent

            for i, part in enumerate(parts):
                if current_len + len(part) > max_length and i > 0:
                    new_line += '\n' + ' ' * (indent + 4)
                    current_len = indent + 4

                new_line += part
                current_len += len(part)

            fixed_lines.append(new_line)
            modified = True
            continue

        # Handle long string concatenation
        if '+' in line and ('"' in line or "'" in line):
            indent = len(line) - len(line.lstrip())
            parts = re.split(r'(\+)', line.strip())
            new_line = line[:indent]
            current_len = indent

            for i, part in enumerate(parts):
                if current_len + len(part) > max_length and i > 0 and parts[i-1] == '+':
                    new_line += '\n' + ' ' * (indent + 4)
                    current_len = indent + 4

                new_line += part
                current_len += len(part)

            fixed_lines.append(new_line)
            modified = True
            continue

        # For other lines, just append them unchanged
        fixed_lines.append(line)

    # Don't modify the file if nothing changed
    if not modified:
        return False

    with open(file_path, 'w', encoding='utf-8') as f:
        f.writelines(fixed_lines)

    return True

def fix_logging_format(file_path):
    """Fix f-strings in logging calls to use lazy % formatting."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Find logging f-strings and convert them to % formatting
    f_string_pattern = r'(logger\.\w+)\(f["\'](.+?)["\']\)'
    lazy_format = r'\1("%s", \2)'

    new_content = re.sub(f_string_pattern, lazy_format, content)

    # Don't modify the file if nothing changed
    if new_content == content:
        return False

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(new_content)

    return True

def fix_file(file_path):
    """Apply all fixes to a file."""
    modified = False

    if remove_trailing_whitespace(file_path):
        print(f"Removed trailing whitespace in {file_path}")
        modified = True

    if fix_line_length(file_path):
        print(f"Fixed long lines in {file_path}")
        modified = True

    if fix_logging_format(file_path):
        print(f"Fixed logging format in {file_path}")
        modified = True

    return modified

def main():
    """Main entry point."""
    # Get the root directory (agent-s3)
    root_dir = Path(__file__).parent

    # Process Python files
    for ext in ['.py', '.ts', '.js']:
        for file_path in root_dir.glob(f'**/*{ext}'):
            # Skip files in venv directories
            if 'venv' in str(file_path) or '__pycache__' in str(file_path):
                continue

            try:
                if fix_file(file_path):
                    print(f"Fixed {file_path}")
            except Exception as e:
                print(f"Error processing {file_path}: {str(e)}")

    print("Linting fixes complete!")

if __name__ == "__main__":
    main()
