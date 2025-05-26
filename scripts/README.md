# Agent-S3 Maintenance Scripts

This directory contains consolidated maintenance scripts for the Agent-S3 repository.

## Scripts Overview

### 🧹 `cleanup.py` - Repository Cleanup Tool
Comprehensive cleanup tool to remove unnecessary files and maintain repository hygiene.

**Features:**
- Remove duplicate files (with numbers, "copy", etc.)
- Clean backup directories
- Remove temporary files (.pyc, __pycache__, .tmp, etc.)
- Clean old log files
- Remove orphaned node_modules
- Fix file permissions

**Usage:**
```bash
# Full cleanup (interactive)
python scripts/cleanup.py

# Dry run to see what would be removed
python scripts/cleanup.py --dry-run

# Force cleanup without prompts
python scripts/cleanup.py --force

# Specific cleanup operations
python scripts/cleanup.py --duplicates-only
python scripts/cleanup.py --python-only
python scripts/cleanup.py --temp-only
```

### 🔍 `lint_and_fix.py` - Linting and Fixing Tool
Unified tool for code quality checks and automatic fixes.

**Features:**
- Python syntax checking
- Ruff linting and formatting
- MyPy type checking
- JavaScript/TypeScript linting
- Dependency validation
- Security vulnerability scanning
- Test execution

**Usage:**
```bash
# Check code quality
python scripts/lint_and_fix.py

# Fix issues automatically
python scripts/lint_and_fix.py --fix

# Specific checks
python scripts/lint_and_fix.py --python-only
python scripts/lint_and_fix.py --js-only
python scripts/lint_and_fix.py --deps-only
python scripts/lint_and_fix.py --syntax-only
python scripts/lint_and_fix.py --tests-only

# Verbose output
python scripts/lint_and_fix.py --verbose
```

### 🔧 `maintenance.py` - Comprehensive Maintenance Tool
High-level maintenance orchestrator that runs multiple maintenance operations.

**Usage:**
```bash
# Individual operations
python scripts/maintenance.py cleanup
python scripts/maintenance.py lint
python scripts/maintenance.py fix
python scripts/maintenance.py deps
python scripts/maintenance.py test
python scripts/maintenance.py health

# Full maintenance cycle
python scripts/maintenance.py full

# Dry run
python scripts/maintenance.py cleanup --dry-run
```

## Quick Start

### Daily Development Workflow
```bash
# Quick health check
python scripts/maintenance.py health

# Fix any issues found
python scripts/maintenance.py fix
```

### Weekly Maintenance
```bash
# Full cleanup and maintenance
python scripts/maintenance.py full
```

### Before Commits
```bash
# Ensure code quality
python scripts/maintenance.py lint
```

### Before Releases
```bash
# Comprehensive check
python scripts/maintenance.py full
python scripts/maintenance.py test
```

## Migration from Old Scripts

These new scripts replace the following old maintenance files:

### ❌ Replaced Scripts (can be safely removed):
- `cleanup_repository.sh` → Use `scripts/cleanup.py`
- `cleanup_duplicates.sh` → Use `scripts/cleanup.py --duplicates-only`
- `fix_lint_issues.py` → Use `scripts/lint_and_fix.py --fix`
- `fix_python_imports.py` → Use `scripts/lint_and_fix.py --fix --python-only`
- `fix_ts_js_issues.js` → Use `scripts/lint_and_fix.py --fix --js-only`
- `fix_ts_syntax.js` → Use `scripts/lint_and_fix.py --fix --js-only`
- `delete_file_duplicates.py` → Use `scripts/cleanup.py --duplicates-only`
- `consolidate_files.py` → Use `scripts/cleanup.py`
- `validate_dependencies.py` → Use `scripts/lint_and_fix.py --deps-only`
- `test_file_analyzer.py` → Use `scripts/lint_and_fix.py --tests-only`

### 📝 Log Files (can be cleaned):
- `test_cleanup.log`
- `legacy_test_mover.log`

## Integration with CI/CD

These scripts are designed to integrate easily with CI/CD pipelines:

```yaml
# Example GitHub Actions usage
- name: Repository Health Check
  run: python scripts/maintenance.py health

- name: Lint and Fix
  run: python scripts/maintenance.py fix

- name: Run Tests
  run: python scripts/maintenance.py test
```

## Features

### Safety Features
- Dry run mode for all operations
- Interactive confirmation prompts
- Detailed logging
- Error handling and recovery
- Git repository detection

### Performance Features
- Efficient file scanning
- Parallel operations where safe
- Progress reporting
- Verbose mode for debugging

### Flexibility Features
- Modular design
- Command-line interface
- Configurable operations
- Extension-friendly architecture

## Contributing

To add new maintenance operations:

1. Extend the appropriate script with new methods
2. Add command-line options as needed
3. Update this README
4. Test thoroughly with `--dry-run` first

## Support

For issues with these scripts:
1. Check the logs for specific error messages
2. Try running with `--verbose` for more details
3. Use `--dry-run` to see what would be done
4. Check file permissions and repository state