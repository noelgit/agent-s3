#!/usr/bin/env python3
"""
A script to fix Python import issues.
This script handles:
1. Sorting imports
2. Grouping imports properly
3. Removing unused imports
"""
import ast
from pathlib import Path

def parse_imports(file_path):
    """Parse imports from a Python file using AST."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    try:
        tree = ast.parse(content)
    except SyntaxError:
        # Skip files with syntax errors
        return None

    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for name in node.names:
                imports.append({
                    'type': 'import',
                    'module': name.name,
                    'alias': name.asname,
                    'lineno': node.lineno
                })
        elif isinstance(node, ast.ImportFrom):
            module = node.module if node.module else ''
            for name in node.names:
                imports.append({
                    'type': 'from',
                    'module': module,
                    'name': name.name,
                    'alias': name.asname,
                    'level': node.level,
                    'lineno': node.lineno
                })

    return imports

def find_unused_imports(file_path, imports):
    """Find unused imports in a Python file."""
    if not imports:
        return []

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    try:
        tree = ast.parse(content)
    except SyntaxError:
        # Skip files with syntax errors
        return []

    # Extract all identifiers used in the file
    used_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            used_names.add(node.id)
        elif isinstance(node, ast.Attribute):
            # Handle attribute access like module.function
            if isinstance(node.value, ast.Name):
                used_names.add(node.value.id)

    # Check each import
    unused = []
    for imp in imports:
        if imp['type'] == 'import':
            # Check if the module name or its alias is used
            name_to_check = imp['alias'] if imp['alias'] else imp['module'].split('.')[0]
            if name_to_check not in used_names:
                unused.append(imp)
        elif imp['type'] == 'from':
            # Check if the imported name or its alias is used
            name_to_check = imp['alias'] if imp['alias'] else imp['name']
            if name_to_check not in used_names:
                unused.append(imp)

    return unused

def sort_imports(imports):
    """Sort imports according to PEP 8."""
    # Group imports
    stdlib = []
    third_party = []
    local = []
    relative = []

    # Standard library modules
    stdlib_modules = {
        'abc', 'argparse', 'ast', 'asyncio', 'base64', 'collections', 'concurrent',
        'contextlib', 'copy', 'csv', 'datetime', 'decimal', 'difflib', 'enum',
        'errno', 'fnmatch', 'functools', 'glob', 'gzip', 'hashlib', 'hmac',
        'html', 'http', 'importlib', 'inspect', 'io', 'ipaddress', 'itertools',
        'json', 'logging', 'math', 'mimetypes', 'multiprocessing', 'operator',
        'os', 'pathlib', 'pickle', 'pprint', 'queue', 'random', 're', 'secrets',
        'select', 'shutil', 'signal', 'socket', 'sqlite3', 'ssl', 'stat',
        'string', 'struct', 'subprocess', 'sys', 'tempfile', 'textwrap', 'threading',
        'time', 'timeit', 'token', 'tokenize', 'traceback', 'types', 'typing',
        'unittest', 'urllib', 'uuid', 'warnings', 'weakref', 'xml', 'zipfile'
    }

    for imp in imports:
        if imp['type'] == 'from' and imp['level'] > 0:
            relative.append(imp)
        elif imp['type'] == 'from':
            module = imp['module']
            if module.split('.')[0] in stdlib_modules or module.startswith('__'):
                stdlib.append(imp)
            elif module.startswith('.'):
                relative.append(imp)
            elif module.startswith('agent_s3.'):
                local.append(imp)
            else:
                third_party.append(imp)
        else:  # Direct import
            module = imp['module']
            if module.split('.')[0] in stdlib_modules:
                stdlib.append(imp)
            elif module.startswith('agent_s3.'):
                local.append(imp)
            else:
                third_party.append(imp)

    # Sort each group
    def sort_key(imp):
        if imp['type'] == 'from':
            return (imp['module'], imp['name'])
        else:
            return (imp['module'], '')

    stdlib.sort(key=sort_key)
    third_party.sort(key=sort_key)
    local.sort(key=sort_key)
    relative.sort(key=lambda x: (x['level'], x['module'], x['name']))

    return {
        'stdlib': stdlib,
        'third_party': third_party,
        'local': local,
        'relative': relative
    }

def format_imports(sorted_imports):
    """Format sorted imports into Python code."""
    result = []

    def format_import(imp):
        if imp['type'] == 'import':
            if imp['alias']:
                return f"import {imp['module']} as {imp['alias']}"
            else:
                return f"import {imp['module']}"
        else:  # from import
            module = '.' * imp['level'] + imp['module'] if imp['module'] else '.' * imp['level']
            if imp['alias']:
                return f"from {module} import {imp['name']} as {imp['alias']}"
            else:
                return f"from {module} import {imp['name']}"

    # Format each group
    for group_name in ['stdlib', 'third_party', 'local', 'relative']:
        group = sorted_imports[group_name]
        if group:
            for imp in group:
                result.append(format_import(imp))
            result.append('')  # Empty line between groups

    return '\n'.join(result)

def fix_imports(file_path):
    """Fix imports in a Python file."""
    imports = parse_imports(file_path)
    if imports is None:
        print(f"Skipping {file_path} - syntax error")
        return False

    if not imports:
        return False

    # Find unused imports
    unused = find_unused_imports(file_path, imports)

    # Filter out unused imports
    active_imports = [imp for imp in imports if imp not in unused]

    # Sort imports
    sorted_imports = sort_imports(active_imports)

    # Format imports
    formatted_imports = format_imports(sorted_imports)

    # Get original file content
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.readlines()

    # Find import lines to replace
    import_lines = set()
    for imp in imports:
        import_lines.add(imp['lineno'] - 1)  # Convert to 0-based

    # Expand to include consecutive import lines and empty lines between them
    all_import_lines = set()
    for line_num in sorted(import_lines):
        all_import_lines.add(line_num)
        # Check lines before and after
        curr = line_num - 1
        while curr >= 0 and (curr in import_lines or content[curr].strip() == ''):
            all_import_lines.add(curr)
            curr -= 1

        curr = line_num + 1
        while curr < len(content) and (curr in import_lines or content[curr].strip() == ''):
            all_import_lines.add(curr)
            curr += 1

    # If imports aren't consecutive, we can't safely replace them
    if len(all_import_lines) != max(all_import_lines) - min(all_import_lines) + 1:
        print(f"Skipping {file_path} - non-consecutive imports")
        return False

    # Replace import lines
    start_line = min(all_import_lines)
    end_line = max(all_import_lines) + 1

    new_content = content[:start_line] + [formatted_imports + '\n'] + content[end_line:]

    # Write back to file
    with open(file_path, 'w', encoding='utf-8') as f:
        f.writelines(new_content)

    print(f"Fixed imports in {file_path}")
    if unused:
        print(f"  Removed {len(unused)} unused imports")

    return True

def main():
    """Main entry point."""
    # Get the root directory (agent-s3)
    root_dir = Path(__file__).parent

    # Process Python files
    for file_path in root_dir.glob('**/*.py'):
        # Skip files in venv directories
        if 'venv' in str(file_path) or '__pycache__' in str(file_path):
            continue

        try:
            fix_imports(file_path)
        except Exception as e:
            print(f"Error processing {file_path}: {str(e)}")

    print("Import fixes complete!")

if __name__ == "__main__":
    main()
