"""Context analysis helpers for debugging system."""

import os
import re
from typing import Dict, Optional, Any


def get_related_files(file_path: str, content: str, file_tool: Any = None) -> Dict[str, str]:
    """
    Get related files based on imports or references in the content.

    Args:
        file_path: Path to the main file
        content: Content of the main file
        file_tool: File tool instance for reading files

    Returns:
        Dictionary mapping file paths to their content
    """
    related_files = {}

    try:
        # Extract imports
        import_pattern = r'(?:import|from)\s+([.\w]+)(?:\s+import|\s*$)'
        matches = re.findall(import_pattern, content)

        # Find potential local imports
        for match in matches:
            # Skip standard library imports
            if _is_standard_library_import(match):
                continue

            possible_paths = _get_possible_import_paths(match, file_path)

            # Check for references to other files
            file_ref_pattern = r'[\'\"]([.\w/\\-]+\.(py|js|ts|json|yaml|yml))[\'\"]'
            file_matches = re.findall(file_ref_pattern, content)

            for file_match, _ in file_matches:
                base_dir = os.path.dirname(file_path)
                possible_paths.append(os.path.join(base_dir, file_match))

            # Try to load each possible path
            for path in possible_paths:
                if path not in related_files and os.path.exists(path):
                    try:
                        if file_tool:
                            related_content = file_tool.read_file(path)
                        else:
                            with open(path, 'r', encoding='utf-8') as f:
                                related_content = f.read()
                        
                        if related_content:
                            related_files[path] = related_content
                            break  # Found a matching file, stop trying other patterns
                    except Exception:
                        pass

    except Exception:
        # Log warning if logger is available
        pass

    return related_files


def get_project_root(file_path: str) -> Optional[str]:
    """Try to determine the project root directory."""
    try:
        # Start from the directory containing the file
        current_dir = os.path.dirname(os.path.abspath(file_path))

        # Walk up the directory tree looking for common project markers
        max_levels = 5  # Limit the search depth
        for _ in range(max_levels):
            # Check for common project markers
            if _has_project_markers(current_dir):
                return current_dir

            # Move up one directory
            parent_dir = os.path.dirname(current_dir)
            if parent_dir == current_dir:  # Reached the root
                break
            current_dir = parent_dir

        # If no markers found, default to directory containing the file
        return os.path.dirname(os.path.abspath(file_path))
    except Exception:
        # In case of any errors, fall back to current directory
        return os.getcwd()


def is_safe_new_file(file_path: str, reference_file_path: Optional[str] = None) -> bool:
    """Check if a file path is in an expected location for new files."""
    # Convert to absolute path
    abs_path = os.path.abspath(file_path)

    # Get project root
    project_root = get_project_root(reference_file_path or os.getcwd())

    # Check if path is within project root
    if not abs_path.startswith(project_root):
        return False

    # Check path components for suspicious elements
    for part in abs_path.split(os.path.sep):
        # Skip empty parts
        if not part:
            continue

        # Check for hidden directories or files
        if part.startswith('.') and part not in ['.github', '.vscode', '.env']:
            return False

        # Check for sensitive directories
        if part.lower() in ['secret', 'secrets', 'password', 'credentials', 'private']:
            return False

    # It should be a Python, JavaScript, TypeScript, or config file
    valid_extensions = ['.py', '.js', '.ts', '.jsx', '.tsx', '.json', '.yaml', '.yml', '.toml', '.ini', '.cfg', '.md']
    if not any(file_path.endswith(ext) for ext in valid_extensions):
        return False

    return True


def analyze_error_context(error_message: str, traceback_text: str, file_path: Optional[str] = None) -> Dict[str, Any]:
    """Analyze error context and extract relevant information."""
    context = {
        'error_type': _extract_error_type(error_message),
        'error_location': _extract_error_location(traceback_text, file_path),
        'related_imports': _extract_imports_from_traceback(traceback_text),
        'suggestions': _generate_quick_suggestions(error_message, traceback_text),
    }
    
    return context


def get_file_dependencies(file_path: str, content: str) -> Dict[str, list]:
    """Get file dependencies including imports and file references."""
    dependencies = {
        'imports': [],
        'file_references': [],
        'potential_modules': [],
    }
    
    # Extract imports
    import_patterns = [
        r'(?:^|\n)import\s+([^\s#]+)',
        r'(?:^|\n)from\s+([^\s#]+)\s+import',
    ]
    
    for pattern in import_patterns:
        matches = re.findall(pattern, content, re.MULTILINE)
        dependencies['imports'].extend(matches)
    
    # Extract file references
    file_ref_pattern = r'[\'\"]([.\w/\\-]+\.(py|js|ts|json|yaml|yml))[\'\"]'
    file_matches = re.findall(file_ref_pattern, content)
    dependencies['file_references'] = [match[0] for match in file_matches]
    
    # Extract potential module references
    module_pattern = r'(?:^|\n)([a-zA-Z_][a-zA-Z0-9_]*)\.'
    module_matches = re.findall(module_pattern, content, re.MULTILINE)
    dependencies['potential_modules'] = list(set(module_matches))
    
    return dependencies


# Helper functions

def _is_standard_library_import(module_name: str) -> bool:
    """Check if a module is from the standard library."""
    standard_modules = {
        "os", "sys", "re", "json", "time", "datetime", "logging",
        "math", "random", "collections", "itertools", "functools",
        "pathlib", "typing", "enum", "abc", "io", "glob", "urllib",
        "http", "email", "csv", "xml", "html", "sqlite3", "hashlib",
        "base64", "pickle", "copy", "inspect", "ast", "dis", "gc",
        "weakref", "contextvars", "concurrent", "asyncio", "multiprocessing",
        "threading", "queue", "socket", "ssl", "uuid", "decimal",
        "fractions", "statistics", "secrets", "tempfile", "shutil",
        "zipfile", "tarfile", "gzip", "bz2", "lzma", "zlib", "configparser",
        "argparse", "getopt", "warnings", "traceback", "unittest",
    }
    
    return module_name.split('.')[0] in standard_modules


def _get_possible_import_paths(module_name: str, file_path: str) -> list[str]:
    """Get possible file paths for a module import."""
    possible_paths = []
    
    # For relative imports, look relative to current file
    if module_name.startswith('.'):
        base_dir = os.path.dirname(file_path)
        rel_path = module_name.lstrip('.')
        rel_path = rel_path.replace('.', os.path.sep)
        possible_paths.append(os.path.join(base_dir, f"{rel_path}.py"))
        possible_paths.append(os.path.join(base_dir, rel_path, "__init__.py"))
    else:
        # For absolute imports, try various patterns
        components = module_name.split('.')
        module_root = components[0]

        # Check if it's a top-level module in the current project
        project_root = get_project_root(file_path)
        if project_root:
            possible_paths.append(os.path.join(project_root, f"{module_root}.py"))
            possible_paths.append(os.path.join(project_root, module_root, "__init__.py"))
            
            # For nested modules
            if len(components) > 1:
                nested_path = os.path.join(project_root, *components[:-1], f"{components[-1]}.py")
                possible_paths.append(nested_path)
    
    return possible_paths


def _has_project_markers(directory: str) -> bool:
    """Check if a directory has common project markers."""
    markers = ["setup.py", "pyproject.toml", "package.json", ".git", "requirements.txt", "Pipfile", "poetry.lock"]
    return any(os.path.exists(os.path.join(directory, marker)) for marker in markers)


def _extract_error_type(error_message: str) -> str:
    """Extract the type of error from an error message."""
    error_types = {
        'SyntaxError': 'syntax_error',
        'TypeError': 'type_error', 
        'NameError': 'name_error',
        'AttributeError': 'attribute_error',
        'ImportError': 'import_error',
        'ModuleNotFoundError': 'import_error',
        'ValueError': 'value_error',
        'KeyError': 'key_error',
        'IndexError': 'index_error',
        'FileNotFoundError': 'file_not_found',
        'PermissionError': 'permission_error',
    }
    
    for error_class, error_type in error_types.items():
        if error_class in error_message:
            return error_type
    
    return 'unknown_error'


def _extract_error_location(traceback_text: str, file_path: Optional[str] = None) -> Dict[str, Any]:
    """Extract error location information from traceback."""
    location = {
        'file': file_path,
        'line': None,
        'function': None,
    }
    
    # Extract line number
    line_pattern = r'line (\d+)'
    line_matches = re.findall(line_pattern, traceback_text)
    if line_matches:
        location['line'] = int(line_matches[-1])
    
    # Extract function name
    function_pattern = r'in (\w+)'
    function_matches = re.findall(function_pattern, traceback_text)
    if function_matches:
        location['function'] = function_matches[-1]
    
    return location


def _extract_imports_from_traceback(traceback_text: str) -> list[str]:
    """Extract import-related information from traceback."""
    imports = []
    
    # Look for import statements in traceback
    import_pattern = r'(?:import|from)\s+([^\s]+)'
    matches = re.findall(import_pattern, traceback_text)
    imports.extend(matches)
    
    return list(set(imports))


def _generate_quick_suggestions(error_message: str, traceback_text: str) -> list[str]:
    """Generate quick suggestions based on error patterns."""
    suggestions = []
    
    if 'ModuleNotFoundError' in error_message:
        suggestions.append("Check if the module is installed or if the import path is correct")
        suggestions.append("Verify that the module is in your Python path")
    
    if 'SyntaxError' in error_message:
        suggestions.append("Check for missing parentheses, brackets, or quotes")
        suggestions.append("Verify proper indentation")
    
    if 'TypeError' in error_message:
        suggestions.append("Check function arguments and their types")
        suggestions.append("Verify that you're calling methods on the correct object types")
    
    if 'AttributeError' in error_message:
        suggestions.append("Check if the attribute or method exists on the object")
        suggestions.append("Verify the object type and available methods")
    
    return suggestions