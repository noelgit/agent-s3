#!/usr/bin/env python3
"""
Dependency Validation Script for Agent-S3

This script validates that all required dependencies are properly installed
and can be imported successfully.
"""

import sys
import importlib
import subprocess
from typing import List, Tuple, Dict, Any


def check_python_imports() -> List[Tuple[str, bool, str]]:
    """Check if Python dependencies can be imported."""
    
    # Core dependencies that should be importable
    core_imports = [
        'requests',
        'pydantic',
        'sqlalchemy', 
        'jsonschema',
        'cryptography',
        'dotenv',  # python-dotenv
        'psutil',
        'toml',
        'yaml',  # pyyaml
        'libcst',
        'tree_sitter',
        'gptcache',
        'faiss',
        'numpy',
        'tiktoken',
        'rank_bm25',
        'fastapi',
        'uvicorn',
        'websockets',
        'flask',
        'boto3',
        'botocore',
        'github',  # PyGithub
        'jwt',  # PyJWT
        'watchdog',
        'pytest',
        'psycopg2',
        'pymysql',
        'supabase',
        'phply'
    ]
    
    # Development dependencies
    dev_imports = [
        'pytest_cov',
        'pytest_asyncio', 
        'pytest_mock',
        'mypy',
        'ruff',
        'black',
        'isort',
        'sphinx',
        'sphinx_rtd_theme',
        'pre_commit',
        'tox',
        'aiohttp',
        'coverage',
        'line_profiler',
        'safety',
        'bandit'
    ]
    
    results = []
    
    for import_name in core_imports + dev_imports:
        try:
            importlib.import_module(import_name)
            results.append((import_name, True, "Successfully imported"))
        except ImportError as e:
            results.append((import_name, False, f"Import failed: {e}"))
        except Exception as e:
            results.append((import_name, False, f"Unexpected error: {e}"))
    
    return results


def check_tree_sitter_parsers() -> List[Tuple[str, bool, str]]:
    """Check if tree-sitter language parsers are available."""
    
    parsers = [
        'tree_sitter_python',
        'tree_sitter_javascript', 
        'tree_sitter_typescript',
        'tree_sitter_php'
    ]
    
    results = []
    
    for parser in parsers:
        try:
            importlib.import_module(parser)
            results.append((parser, True, "Parser available"))
        except ImportError as e:
            results.append((parser, False, f"Parser not found: {e}"))
        except Exception as e:
            results.append((parser, False, f"Unexpected error: {e}"))
    
    return results


def check_node_dependencies() -> List[Tuple[str, bool, str]]:
    """Check Node.js dependencies in VSCode extension."""
    
    try:
        # Check if npm is available
        result = subprocess.run(['npm', '--version'], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            return [("npm", False, "npm not available")]
        
        npm_version = result.stdout.strip()
        
        # Check VSCode extension dependencies
        vscode_result = subprocess.run(
            ['npm', 'ls', '--depth=0'], 
            cwd='vscode',
            capture_output=True, text=True, timeout=30
        )
        
        # Check webview dependencies
        webview_result = subprocess.run(
            ['npm', 'ls', '--depth=0'],
            cwd='vscode/webview-ui', 
            capture_output=True, text=True, timeout=30
        )
        
        results = [("npm", True, f"npm version {npm_version}")]
        
        if vscode_result.returncode == 0:
            results.append(("vscode-deps", True, "VSCode extension dependencies OK"))
        else:
            results.append(("vscode-deps", False, f"VSCode deps error: {vscode_result.stderr}"))
            
        if webview_result.returncode == 0:
            results.append(("webview-deps", True, "Webview UI dependencies OK"))
        else:
            results.append(("webview-deps", False, f"Webview deps error: {webview_result.stderr}"))
        
        return results
        
    except subprocess.TimeoutExpired:
        return [("npm", False, "npm command timed out")]
    except FileNotFoundError:
        return [("npm", False, "npm not found - Node.js not installed?")]
    except Exception as e:
        return [("npm", False, f"Unexpected error: {e}")]


def check_python_version() -> Tuple[str, bool, str]:
    """Check Python version compatibility."""
    
    major, minor = sys.version_info[:2]
    
    if major == 3 and minor >= 8:
        return ("python-version", True, f"Python {major}.{minor} (compatible)")
    else:
        return ("python-version", False, f"Python {major}.{minor} (requires >= 3.8)")


def print_results(category: str, results: List[Tuple[str, bool, str]]) -> None:
    """Print validation results in a formatted way."""
    
    print(f"\n{'='*60}")
    print(f"{category.upper()}")
    print('='*60)
    
    success_count = 0
    total_count = len(results)
    
    for name, success, message in results:
        status = "✓" if success else "✗"
        print(f"{status} {name:<30} {message}")
        if success:
            success_count += 1
    
    print(f"\nSummary: {success_count}/{total_count} successful")


def main():
    """Main validation function."""
    
    print("Agent-S3 Dependency Validation")
    print("="*60)
    
    # Check Python version
    python_version_result = check_python_version()
    print_results("Python Version", [python_version_result])
    
    # Check Python imports
    python_results = check_python_imports()
    print_results("Python Dependencies", python_results)
    
    # Check tree-sitter parsers
    parser_results = check_tree_sitter_parsers()
    print_results("Tree-sitter Parsers", parser_results)
    
    # Check Node.js dependencies
    node_results = check_node_dependencies()
    print_results("Node.js Dependencies", node_results)
    
    # Overall summary
    all_results = [python_version_result] + python_results + parser_results + node_results
    total_success = sum(1 for _, success, _ in all_results if success)
    total_count = len(all_results)
    
    print(f"\n{'='*60}")
    print("OVERALL SUMMARY")
    print('='*60)
    print(f"Total checks: {total_count}")
    print(f"Successful: {total_success}")
    print(f"Failed: {total_count - total_success}")
    
    if total_success == total_count:
        print("\n🎉 All dependency checks passed!")
        return 0
    else:
        print(f"\n⚠️  {total_count - total_success} dependency checks failed.")
        print("Please review the failed items above and install missing dependencies.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
