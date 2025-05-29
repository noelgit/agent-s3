#!/usr/bin/env python3
"""
Agent-S3 Lint and Fix Tool
Consolidated script to handle linting and automatic fixes.

This replaces multiple individual fix scripts with a unified tool.
"""
import argparse
import logging
import subprocess
import sys
from pathlib import Path
from typing import List

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class LintAndFix:
    """Handles linting and automatic fixes for the codebase."""
    
    def __init__(self, repo_root: Path, fix: bool = False, verbose: bool = False):
        self.repo_root = repo_root
        self.fix = fix
        self.verbose = verbose
    
    def run_command(self, cmd: List[str], description: str) -> bool:
        """Run a command and return success status."""
        if self.verbose:
            logger.info(f"Running: {' '.join(cmd)}")
        
        try:
            result = subprocess.run(
                cmd,
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                check=False
            )
            
            if result.returncode == 0:
                logger.info(f"✅ {description} - PASSED")
                if self.verbose and result.stdout:
                    print(result.stdout)
                return True
            else:
                logger.error(f"❌ {description} - FAILED")
                if result.stderr:
                    print(result.stderr)
                if result.stdout:
                    print(result.stdout)
                return False
        
        except FileNotFoundError:
            logger.error(f"❌ {description} - Command not found: {cmd[0]}")
            return False
        except Exception as e:
            logger.error(f"❌ {description} - Error: {e}")
            return False
    
    def check_python_syntax(self) -> bool:
        """Check Python syntax by compiling all Python files."""
        logger.info("Checking Python syntax...")
        
        python_files = list(self.repo_root.rglob("*.py"))
        if not python_files:
            logger.info("No Python files found")
            return True
        
        failed_files = []
        for py_file in python_files:
            if ".git" in py_file.parts or "__pycache__" in py_file.parts:
                continue
            
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    compile(f.read(), py_file, 'exec')
            except SyntaxError as e:
                failed_files.append(f"{py_file}: {e}")
            except Exception as e:
                logger.warning(f"Could not check {py_file}: {e}")
        
        if failed_files:
            logger.error("Python syntax errors found:")
            for error in failed_files:
                print(f"  {error}")
            return False
        
        logger.info("✅ Python syntax check - PASSED")
        return True
    
    def run_python_linting(self) -> bool:
        """Run Python linting tools."""
        success = True
        
        # Check if ruff is available
        if self.run_command(["ruff", "--version"], "Check ruff availability"):
            if self.fix:
                success &= self.run_command(
                    ["ruff", "check", "agent_s3/", "--fix"],
                    "Ruff linting with fixes"
                )
                success &= self.run_command(
                    ["ruff", "format", "agent_s3/"],
                    "Ruff formatting"
                )
            else:
                success &= self.run_command(
                    ["ruff", "check", "agent_s3/"],
                    "Ruff linting"
                )
        
        # Check if mypy is available
        if self.run_command(["mypy", "--version"], "Check mypy availability"):
            success &= self.run_command(
                ["mypy", "agent_s3/", "--config-file", "pyproject.toml"],
                "MyPy type checking"
            )
        
        return success
    
    def run_javascript_linting(self) -> bool:
        """Run JavaScript/TypeScript linting."""
        success = True
        
        # Check VS Code extension
        vscode_dir = self.repo_root / "vscode"
        if vscode_dir.exists():
            # Check if npm/yarn is available
            package_json = vscode_dir / "package.json"
            if package_json.exists():
                # Try to run eslint if available
                if self.run_command(["npm", "--version"], "Check npm availability"):
                    if self.fix:
                        success &= self.run_command(
                            ["npm", "run", "lint:fix"],
                            "ESLint with fixes (VS Code)"
                        )
                    else:
                        success &= self.run_command(
                            ["npm", "run", "lint"],
                            "ESLint (VS Code)"
                        )
        
        # Check webview UI
        webview_dir = self.repo_root / "vscode" / "webview-ui"
        if webview_dir.exists():
            package_json = webview_dir / "package.json"
            if package_json.exists():
                if self.run_command(["npm", "--version"], "Check npm availability"):
                    if self.fix:
                        success &= self.run_command(
                            ["npm", "run", "lint:fix"],
                            "ESLint with fixes (Webview UI)"
                        )
                    else:
                        success &= self.run_command(
                            ["npm", "run", "lint"],
                            "ESLint (Webview UI)"
                        )
        
        return success
    
    def check_dependencies(self) -> bool:
        """Check for dependency issues."""
        success = True
        
        # Check Python dependencies
        requirements_file = self.repo_root / "requirements.txt"
        if requirements_file.exists():
            success &= self.run_command(
                ["pip", "check"],
                "Python dependency check"
            )
        
        # Check for security vulnerabilities
        if self.run_command(["pip", "show", "safety"], "Check safety availability"):
            success &= self.run_command(
                ["safety", "check"],
                "Security vulnerability check"
            )
        
        return success
    
    def run_tests(self) -> bool:
        """Run tests to verify fixes don't break functionality."""
        logger.info("Running tests...")
        
        # Run Python tests
        test_dirs = ["tests", "test"]
        test_found = False
        
        for test_dir in test_dirs:
            if (self.repo_root / test_dir).exists():
                test_found = True
                break
        
        if test_found:
            return self.run_command(
                ["python", "-m", "pytest", "tests/", "-v", "--tb=short"],
                "Python tests"
            )
        else:
            logger.info("No test directory found, skipping tests")
            return True
    
    def run_all_checks(self) -> bool:
        """Run all linting and checking operations."""
        logger.info(f"Starting {'linting with fixes' if self.fix else 'linting'} for repository: {self.repo_root}")
        
        all_success = True
        
        # Syntax checks
        all_success &= self.check_python_syntax()
        
        # Linting
        all_success &= self.run_python_linting()
        all_success &= self.run_javascript_linting()
        
        # Dependency checks
        all_success &= self.check_dependencies()
        
        # Run tests if not fixing (to avoid breaking changes)
        if not self.fix:
            all_success &= self.run_tests()
        
        if all_success:
            logger.info("🎉 All checks passed!")
        else:
            logger.error("❌ Some checks failed")
        
        return all_success


def main():
    parser = argparse.ArgumentParser(description="Agent-S3 Lint and Fix Tool")
    parser.add_argument('--fix', action='store_true', help="Automatically fix issues where possible")
    parser.add_argument('--python-only', action='store_true', help="Only check Python files")
    parser.add_argument('--js-only', action='store_true', help="Only check JavaScript/TypeScript files")
    parser.add_argument('--deps-only', action='store_true', help="Only check dependencies")
    parser.add_argument('--syntax-only', action='store_true', help="Only check syntax")
    parser.add_argument('--tests-only', action='store_true', help="Only run tests")
    parser.add_argument('--verbose', '-v', action='store_true', help="Verbose output")
    
    args = parser.parse_args()
    
    # Find repository root
    current = Path.cwd()
    repo_root = current
    while repo_root != repo_root.parent:
        if (repo_root / '.git').exists():
            break
        repo_root = repo_root.parent
    else:
        logger.error("Not in a git repository")
        sys.exit(1)
    
    linter = LintAndFix(repo_root, fix=args.fix, verbose=args.verbose)
    
    success = True
    
    if args.python_only:
        success = linter.check_python_syntax() and linter.run_python_linting()
    elif args.js_only:
        success = linter.run_javascript_linting()
    elif args.deps_only:
        success = linter.check_dependencies()
    elif args.syntax_only:
        success = linter.check_python_syntax()
    elif args.tests_only:
        success = linter.run_tests()
    else:
        success = linter.run_all_checks()
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()