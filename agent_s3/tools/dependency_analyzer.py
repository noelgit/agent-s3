"""AST-based dependency analyzer for code generation.

This module provides utilities to:
1. Extract imports from generated code using AST parsing
2. Verify compatibility of dependencies
3. Check for transitive dependencies and conflicts
"""

import logging
import os
import re
import sys
from typing import Dict, List, Set, Optional
from pathlib import Path
import pkg_resources
import subprocess

logger = logging.getLogger(__name__)

class DependencyAnalyzer:
    """Analyzes code for dependencies using AST parsing."""

    def __init__(self, pip_executable="pip", file_tool=None, parser_registry=None):
        """Initialize the dependency analyzer.

        Args:
            pip_executable: Path to pip executable or command name
            file_tool: Tool for file operations
            parser_registry: Registry for language-specific parsers
        """
        self.pip_executable = pip_executable
        self.file_tool = file_tool
        self.parser_registry = parser_registry
        self.installed_packages = self._get_installed_packages()

    def _get_installed_packages(self) -> Dict[str, str]:
        """Get all currently installed packages and their versions.

        Returns:
            Dict mapping package names to versions
        """
        try:
            installed = {pkg.key: pkg.version for pkg in pkg_resources.working_set}
            logger.debug("Found %d installed packages", len(installed))
            return installed
        except Exception as e:
            logger.error("Error getting installed packages: %s", e)
            return {}

    def extract_dependencies(self, file_path: str, language: str = None):
        """
        Extract dependencies from a file using the new parser system.
        """
        if not self.file_tool:
            logger.error("FileTool is not available. Cannot extract dependencies.")
            return []
        if not self.parser_registry:
            logger.error("ParserRegistry not available. Cannot extract dependencies.")
            return []
        try:
            content = self.file_tool.read_file(file_path)
            if content is None:
                logger.warning("Could not read content of file: %s", file_path)
                return []
        except Exception as e:
            logger.error("Error reading file %s: %s", file_path, e, exc_info=True)
            return []
        # Language detection
        if not language:
            if hasattr(self.file_tool, 'get_language_from_extension'):
                language = self.file_tool.get_language_from_extension(file_path)
            if not language:
                language = Path(file_path).suffix[1:].lower() if Path(file_path).suffix else 'unknown'
        parser = self.parser_registry.get_parser(language_name=language, file_path=file_path)
        if parser:
            try:
                logger.info(
                    "Extracting dependencies from %s with %s for language '%s'",
                    file_path,
                    type(parser).__name__,
                    language,
                )
                structure = parser.parse_code(content, file_path)
                return getattr(structure, 'dependencies', [])
            except Exception as e:
                logger.error(f"Error extracting dependencies from {file_path} with {type(parser).__name__}: {e}", exc_info=True)
                return []
        else:
            logger.error("No parser found for language '%s' for file %s", language, file_path)
            return []

    def check_missing_dependencies(self, imports: Set[str]) -> List[str]:
        """Check which imports are not installed.

        Args:
            imports: Set of imported module names

        Returns:
            List of missing dependencies
        """
        missing = []
        std_libs = self._get_standard_libraries()

        for imp in imports:
            # Skip standard library modules
            if imp in std_libs:
                continue

            # Check if installed
            if imp.lower() not in (pkg.lower() for pkg in self.installed_packages):
                missing.append(imp)

        return missing

    def _get_standard_libraries(self) -> Set[str]:
        """Get a set of Python standard library module names.

        Returns:
            Set of standard library module names
        """
        # This is a simplified approach; a more complete solution would use
        # the stdlib_list package or similar
        return set(sys.builtin_module_names)

    def check_dependency_compatibility(self, dependencies: Dict[str, str]) -> Dict[str, str]:
        """Check compatibility between requested dependencies.

        Args:
            dependencies: Dict mapping package names to version constraints

        Returns:
            Dict of incompatible packages with error messages
        """
        incompatible = {}

        if not dependencies:
            return incompatible

        # Create a temporary requirements file
        temp_req_file = "temp_requirements_check.txt"
        try:
            with open(temp_req_file, "w") as f:
                for pkg, version in dependencies.items():
                    f.write(f"{pkg}{version}\n")

            # Use pip check to verify compatibility
            cmd = [self.pip_executable, "check"]
            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode != 0:
                # Parse pip check output for incompatibilities
                for line in result.stderr.split('\n') + result.stdout.split('\n'):
                    if "Requirement" in line and "conflicts with" in line:
                        parts = line.split(":")
                        if len(parts) >= 2:
                            pkg = parts[0].strip().split()[-1]
                            incompatible[pkg] = parts[1].strip()
        except Exception as e:
            logger.error("Error checking dependency compatibility: %s", e)
        finally:
            # Clean up temporary file
            if os.path.exists(temp_req_file):
                os.remove(temp_req_file)

        return incompatible

    def get_dependency_versions(self, packages: List[str]) -> Dict[str, str]:
        """Get latest available versions for packages.

        Args:
            packages: List of package names

        Returns:
            Dict mapping package names to latest versions
        """
        versions = {}

        for pkg in packages:
            try:
                cmd = [self.pip_executable, "install", pkg, "--dry-run"]
                result = subprocess.run(cmd, capture_output=True, text=True)

                # Parse output to find version
                for line in result.stdout.split('\n'):
                    if f"Would install {pkg}" in line:
                        version_match = re.search(r'(\d+\.\d+\.\d+)', line)
                        if version_match:
                            versions[pkg] = version_match.group(1)
                            break
            except Exception as e:
                logger.error("Error getting version for %s: %s", pkg, e)

        return versions

    def analyze_code_changes(
        self,
        changes: List[Dict],
        language_map: Optional[Dict[str, str]] = None,
    ) -> Dict:
        """Analyze dependencies from a list of code changes.

        Args:
            changes: List of code change dictionaries (each with 'file_path' and 'content')
            language_map: Optional mapping of file extensions to languages

        Returns:
            Dict with analysis results including imports and missing dependencies
        """
        if language_map is None:
            language_map = {
                '.py': 'python',
                '.js': 'javascript',
                '.ts': 'typescript',
                '.jsx': 'javascript',
                '.tsx': 'typescript'
            }

        all_imports = set()
        files_analyzed = 0

        for change in changes:
            file_path = change.get('file_path', '')
            content = change.get('content', '')

            if not file_path or not content:
                continue

            # Determine language from file extension
            ext = os.path.splitext(file_path)[1].lower()
            language = language_map.get(ext)

            if not language:
                logger.debug("Skipping dependency analysis for unsupported file type: %s", file_path)
                continue

            imports = self.extract_dependencies(file_path, language)
            all_imports.update(imports)
            files_analyzed += 1

        # Check which imports are missing
        missing = self.check_missing_dependencies(all_imports)

        # Get recommended versions for missing dependencies
        versions = self.get_dependency_versions(missing)

        return {
            'imports': list(all_imports),
            'missing_dependencies': missing,
            'recommended_versions': versions,
            'files_analyzed': files_analyzed
        }
