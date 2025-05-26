#!/usr/bin/env python3
"""
Comprehensive import and dependency analysis for agent_s3 codebase
"""

import ast
import os
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
from collections import defaultdict
import importlib.util

def find_python_files(root_dir: str) -> List[Path]:
    """Find all Python files in the directory"""
    root_path = Path(root_dir)
    return list(root_path.rglob("*.py"))

def parse_file(file_path: Path) -> Optional[ast.AST]:
    """Parse a Python file and return its AST"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return ast.parse(content, filename=str(file_path))
    except Exception as e:
        print(f"Error parsing {file_path}: {e}")
        return None

def extract_imports(tree: ast.AST) -> Tuple[List[str], List[Tuple[str, str]]]:
    """Extract imports from AST
    Returns: (module_imports, from_imports)
    """
    module_imports = []
    from_imports = []
    
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                module_imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                for alias in node.names:
                    from_imports.append((node.module, alias.name))
    
    return module_imports, from_imports

def extract_function_calls(tree: ast.AST) -> List[str]:
    """Extract function calls from AST"""
    calls = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                calls.append(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                calls.append(node.func.attr)
    return calls

def extract_attribute_access(tree: ast.AST) -> List[str]:
    """Extract attribute access from AST"""
    attributes = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            attributes.append(node.attr)
    return attributes

def check_module_exists(module_name: str, base_path: Path) -> bool:
    """Check if a module exists in the local codebase or as an installed package"""
    # Check if it's a relative import within agent_s3
    if module_name.startswith('agent_s3'):
        module_path = module_name.replace('.', '/') + '.py'
        full_path = base_path.parent / module_path
        if full_path.exists():
            return True
        
        # Check if it's a package (directory with __init__.py)
        package_path = base_path.parent / module_name.replace('.', '/')
        if package_path.is_dir() and (package_path / '__init__.py').exists():
            return True
    
    # Check if it's a standard library or installed package
    try:
        importlib.util.find_spec(module_name)
        return True
    except (ImportError, ModuleNotFoundError, ValueError):
        return False

def analyze_file(file_path: Path, base_path: Path) -> Dict:
    """Analyze a single file for import issues"""
    tree = parse_file(file_path)
    if not tree:
        return {"error": f"Could not parse {file_path}"}
    
    module_imports, from_imports = extract_imports(tree)
    function_calls = extract_function_calls(tree)
    attributes = extract_attribute_access(tree)
    
    issues = {
        'file': str(file_path),
        'missing_modules': [],
        'missing_functions': [],
        'undefined_variables': [],
        'circular_imports': []
    }
    
    # Check module existence
    for module in module_imports:
        if not check_module_exists(module, file_path):
            issues['missing_modules'].append(module)
    
    for module, item in from_imports:
        if not check_module_exists(module, file_path):
            issues['missing_modules'].append(f"{module}.{item}")
    
    return issues

def find_circular_imports(file_imports: Dict[str, List[str]]) -> List[List[str]]:
    """Find circular import dependencies"""
    def dfs(node, path, visited, rec_stack):
        visited.add(node)
        rec_stack.add(node)
        path.append(node)
        
        for neighbor in file_imports.get(node, []):
            if neighbor in rec_stack:
                # Found a cycle
                cycle_start = path.index(neighbor)
                return path[cycle_start:] + [neighbor]
            elif neighbor not in visited:
                cycle = dfs(neighbor, path[:], visited, rec_stack)
                if cycle:
                    return cycle
        
        rec_stack.remove(node)
        return None
    
    cycles = []
    visited = set()
    
    for node in file_imports:
        if node not in visited:
            cycle = dfs(node, [], visited, set())
            if cycle:
                cycles.append(cycle)
    
    return cycles

def main():
    """Main analysis function"""
    base_dir = "/Users/noelpatron/Documents/GitHub/agent-s3/agent_s3"
    files = find_python_files(base_dir)
    
    print(f"Analyzing {len(files)} Python files...")
    
    all_issues = []
    file_imports = defaultdict(list)
    
    for file_path in files:
        relative_path = file_path.relative_to(Path(base_dir).parent)
        issues = analyze_file(file_path, Path(base_dir))
        
        if 'error' not in issues:
            all_issues.append(issues)
            
            # Track imports for circular dependency detection
            tree = parse_file(file_path)
            if tree:
                module_imports, from_imports = extract_imports(tree)
                file_key = str(relative_path)
                
                for module in module_imports:
                    if module.startswith('agent_s3'):
                        file_imports[file_key].append(module)
                
                for module, _ in from_imports:
                    if module and module.startswith('agent_s3'):
                        file_imports[file_key].append(module)
    
    # Find circular imports
    circular_imports = find_circular_imports(dict(file_imports))
    
    # Summarize issues
    print("\n=== IMPORT ANALYSIS RESULTS ===\n")
    
    critical_issues = []
    
    # Missing modules
    missing_modules = set()
    for issue in all_issues:
        for module in issue['missing_modules']:
            missing_modules.add(module)
    
    if missing_modules:
        print("🔴 CRITICAL: Missing Modules")
        for module in sorted(missing_modules):
            print(f"  - {module}")
            critical_issues.append(f"Missing module: {module}")
        print()
    
    # Circular imports
    if circular_imports:
        print("🟡 WARNING: Circular Import Dependencies")
        for i, cycle in enumerate(circular_imports):
            print(f"  Cycle {i+1}: {' -> '.join(cycle)}")
            critical_issues.append(f"Circular import: {' -> '.join(cycle)}")
        print()
    
    # Files with issues
    files_with_issues = [issue for issue in all_issues if any(issue[key] for key in ['missing_modules', 'missing_functions', 'undefined_variables'])]
    
    if files_with_issues:
        print("📁 Files with Import Issues:")
        for issue in files_with_issues:
            if issue['missing_modules']:
                print(f"  {issue['file']}: Missing modules: {', '.join(issue['missing_modules'])}")
        print()
    
    # Summary
    print("=== PRIORITY SUMMARY ===")
    if critical_issues:
        print("Critical issues found (fix immediately):")
        for i, issue in enumerate(critical_issues[:10], 1):  # Top 10
            print(f"{i}. {issue}")
    else:
        print("✅ No critical import issues found!")
    
    return len(critical_issues)

if __name__ == "__main__":
    exit_code = main()
    sys.exit(min(exit_code, 1))