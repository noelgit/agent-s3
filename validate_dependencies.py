#!/usr/bin/env python3
"""
Dependency validation script for Agent-S3 project.
Validates all dependencies across Python, Node.js, and tree-sitter ecosystems.
"""

import subprocess
import sys
import json
import os
from typing import List, Dict, Any, Tuple


class DependencyValidator:
    """Validates dependencies across multiple ecosystems."""
    
    def __init__(self):
        self.results = {
            'python': {'status': 'unknown', 'details': []},
            'nodejs': {'status': 'unknown', 'details': []},
            'tree_sitter': {'status': 'unknown', 'details': []},
            'overall': {'status': 'unknown', 'passed': 0, 'failed': 0}
        }
    
    def run_command(self, cmd: List[str], cwd: str = None) -> Tuple[bool, str]:
        """Run a command and return success status and output."""
        try:
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                cwd=cwd,
                timeout=30
            )
            return result.returncode == 0, result.stdout + result.stderr
        except subprocess.TimeoutExpired:
            return False, "Command timed out"
        except Exception as e:
            return False, f"Command failed: {str(e)}"
    
    def validate_python_deps(self) -> bool:
        """Validate Python dependencies."""
        print("🐍 Validating Python dependencies...")
        
        # Check if requirements.txt exists
        if not os.path.exists('requirements.txt'):
            self.results['python']['details'].append("❌ requirements.txt not found")
            return False
        
        # Try to install dependencies in dry-run mode
        success, output = self.run_command(['pip', 'install', '--dry-run', '-r', 'requirements.txt'])
        
        if success:
            self.results['python']['details'].append("✅ All Python dependencies can be installed")
            self.results['python']['status'] = 'passed'
            return True
        else:
            self.results['python']['details'].append(f"❌ Python dependency issues: {output[:200]}...")
            self.results['python']['status'] = 'failed'
            return False
    
    def validate_nodejs_deps(self) -> bool:
        """Validate Node.js dependencies."""
        print("📦 Validating Node.js dependencies...")
        
        all_passed = True
        
        # Check main package.json
        if os.path.exists('package.json'):
            success, output = self.run_command(['npm', 'install', '--dry-run'])
            if success:
                self.results['nodejs']['details'].append("✅ Main package.json dependencies valid")
            else:
                self.results['nodejs']['details'].append(f"❌ Main package.json issues: {output[:100]}...")
                all_passed = False
        
        # Check VSCode extension
        if os.path.exists('vscode/package.json'):
            success, output = self.run_command(['npm', 'install', '--dry-run'], cwd='vscode')
            if success:
                self.results['nodejs']['details'].append("✅ VSCode extension dependencies valid")
            else:
                self.results['nodejs']['details'].append(f"❌ VSCode extension issues: {output[:100]}...")
                all_passed = False
        
        # Check webview UI
        if os.path.exists('vscode/webview-ui/package.json'):
            success, output = self.run_command(['npm', 'install', '--dry-run'], cwd='vscode/webview-ui')
            if success:
                self.results['nodejs']['details'].append("✅ Webview UI dependencies valid")
            else:
                self.results['nodejs']['details'].append(f"❌ Webview UI issues: {output[:100]}...")
                all_passed = False
        
        self.results['nodejs']['status'] = 'passed' if all_passed else 'failed'
        return all_passed
    
    def validate_tree_sitter_deps(self) -> bool:
        """Validate tree-sitter dependencies."""
        print("🌳 Validating tree-sitter dependencies...")
        
        required_parsers = [
            'tree_sitter_python',
            'tree_sitter_javascript', 
            'tree_sitter_typescript',
            'tree_sitter_php'
        ]
        
        all_passed = True
        
        for parser in required_parsers:
            try:
                __import__(parser)
                self.results['tree_sitter']['details'].append(f"✅ {parser} available")
            except ImportError:
                self.results['tree_sitter']['details'].append(f"❌ {parser} not available")
                all_passed = False
        
        self.results['tree_sitter']['status'] = 'passed' if all_passed else 'failed'
        return all_passed
    
    def validate_all(self) -> bool:
        """Validate all dependencies."""
        print("🔍 Starting comprehensive dependency validation...\n")
        
        python_ok = self.validate_python_deps()
        nodejs_ok = self.validate_nodejs_deps() 
        tree_sitter_ok = self.validate_tree_sitter_deps()
        
        # Calculate overall results
        passed = sum([python_ok, nodejs_ok, tree_sitter_ok])
        failed = 3 - passed
        
        self.results['overall'] = {
            'status': 'passed' if failed == 0 else 'failed',
            'passed': passed,
            'failed': failed
        }
        
        return failed == 0
    
    def print_results(self):
        """Print detailed validation results."""
        print("\n" + "="*60)
        print("📊 DEPENDENCY VALIDATION RESULTS")
        print("="*60)
        
        for category, data in self.results.items():
            if category == 'overall':
                continue
                
            status_icon = "✅" if data['status'] == 'passed' else "❌"
            print(f"\n{status_icon} {category.upper()}: {data['status'].upper()}")
            
            for detail in data['details']:
                print(f"   {detail}")
        
        print(f"\n📈 OVERALL: {self.results['overall']['passed']}/3 categories passed")
        
        if self.results['overall']['status'] == 'passed':
            print("🎉 All dependencies are properly configured!")
        else:
            print("⚠️  Some dependencies need attention.")
    
    def save_results(self, filename: str = 'dependency_validation_results.json'):
        """Save results to JSON file."""
        with open(filename, 'w') as f:
            json.dump(self.results, f, indent=2)
        print(f"\n💾 Results saved to {filename}")


def main():
    """Main validation function."""
    validator = DependencyValidator()
    
    try:
        success = validator.validate_all()
        validator.print_results()
        validator.save_results()
        
        # Exit with appropriate code
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        print("\n❌ Validation interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Validation failed with error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()