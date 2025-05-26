#!/usr/bin/env python3
"""
Agent-S3 Maintenance Tool
Comprehensive maintenance script for repository health.

This provides a unified interface for all maintenance operations.
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


class MaintenanceTool:
    """Comprehensive maintenance tool for Agent-S3."""
    
    def __init__(self, repo_root: Path, dry_run: bool = False):
        self.repo_root = repo_root
        self.dry_run = dry_run
        self.scripts_dir = repo_root / "scripts"
    
    def run_script(self, script_name: str, args: List[str] = None) -> bool:
        """Run a maintenance script."""
        if args is None:
            args = []
        
        script_path = self.scripts_dir / script_name
        if not script_path.exists():
            logger.error(f"Script not found: {script_path}")
            return False
        
        cmd = [sys.executable, str(script_path)] + args
        if self.dry_run:
            cmd.append("--dry-run")
        
        logger.info(f"Running: {' '.join(cmd)}")
        
        try:
            result = subprocess.run(cmd, cwd=self.repo_root, check=False)
            return result.returncode == 0
        except Exception as e:
            logger.error(f"Error running {script_name}: {e}")
            return False
    
    def cleanup_repository(self) -> bool:
        """Run repository cleanup."""
        logger.info("🧹 Running repository cleanup...")
        return self.run_script("cleanup.py")
    
    def lint_and_fix(self, fix: bool = False) -> bool:
        """Run linting and optionally fix issues."""
        logger.info(f"🔍 Running linting {'with fixes' if fix else ''}...")
        args = ["--fix"] if fix else []
        return self.run_script("lint_and_fix.py", args)
    
    def validate_dependencies(self) -> bool:
        """Validate dependencies."""
        logger.info("📦 Validating dependencies...")
        return self.run_script("lint_and_fix.py", ["--deps-only"])
    
    def run_tests(self) -> bool:
        """Run test suite."""
        logger.info("🧪 Running tests...")
        return self.run_script("lint_and_fix.py", ["--tests-only"])
    
    def full_maintenance(self, fix: bool = False) -> bool:
        """Run full maintenance cycle."""
        logger.info("🔧 Starting full maintenance cycle...")
        
        success = True
        
        # 1. Clean up repository
        success &= self.cleanup_repository()
        
        # 2. Lint and optionally fix
        success &= self.lint_and_fix(fix=fix)
        
        # 3. Validate dependencies
        success &= self.validate_dependencies()
        
        # 4. Run tests (if not fixing to avoid breaking changes)
        if not fix:
            success &= self.run_tests()
        
        if success:
            logger.info("🎉 Full maintenance cycle completed successfully!")
        else:
            logger.error("❌ Maintenance cycle completed with errors")
        
        return success
    
    def health_check(self) -> bool:
        """Run a quick health check."""
        logger.info("🏥 Running repository health check...")
        
        checks = [
            ("Python syntax", lambda: self.run_script("lint_and_fix.py", ["--syntax-only"])),
            ("Dependencies", lambda: self.run_script("lint_and_fix.py", ["--deps-only"])),
        ]
        
        all_passed = True
        for check_name, check_func in checks:
            logger.info(f"Checking {check_name}...")
            if check_func():
                logger.info(f"✅ {check_name} - OK")
            else:
                logger.error(f"❌ {check_name} - FAILED")
                all_passed = False
        
        return all_passed


def main():
    parser = argparse.ArgumentParser(description="Agent-S3 Maintenance Tool")
    parser.add_argument('command', choices=[
        'cleanup', 'lint', 'fix', 'deps', 'test', 'health', 'full'
    ], help="Maintenance command to run")
    parser.add_argument('--dry-run', action='store_true', help="Show what would be done without making changes")
    
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
    
    # Ensure scripts directory exists
    scripts_dir = repo_root / "scripts"
    if not scripts_dir.exists():
        logger.error(f"Scripts directory not found: {scripts_dir}")
        sys.exit(1)
    
    maintenance = MaintenanceTool(repo_root, dry_run=args.dry_run)
    
    success = False
    
    if args.command == 'cleanup':
        success = maintenance.cleanup_repository()
    elif args.command == 'lint':
        success = maintenance.lint_and_fix(fix=False)
    elif args.command == 'fix':
        success = maintenance.lint_and_fix(fix=True)
    elif args.command == 'deps':
        success = maintenance.validate_dependencies()
    elif args.command == 'test':
        success = maintenance.run_tests()
    elif args.command == 'health':
        success = maintenance.health_check()
    elif args.command == 'full':
        success = maintenance.full_maintenance(fix=True)
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()