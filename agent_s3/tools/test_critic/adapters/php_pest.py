"""
PHP Pest/PHPUnit adapter for the test critic.

This adapter implements the necessary methods to run Pest or PHPUnit commands for
test collection, smoke tests, coverage analysis, and mutation testing.
"""

import os
import re
import json
import logging
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Optional

from ..core import Adapter

logger = logging.getLogger(__name__)

class PhpPestAdapter(Adapter):
    """PHP Pest/PHPUnit adapter for test critic."""

    name = "php_pest"

    def __init__(self):
        """Initialize the PHP adapter."""
        super().__init__()
        self.is_pest = False
        self.is_phpunit = False

    def detect(self, workspace: Path) -> bool:
        """
        Detect if this adapter is suitable for the workspace.

        Args:
            workspace: Path to the workspace directory

        Returns:
            True if this adapter should be used, False otherwise
        """
        # Check for composer.json with Pest or PHPUnit dependencies
        composer_json_path = workspace / "composer.json"
        if composer_json_path.exists():
            try:
                with open(composer_json_path, "r", encoding="utf-8") as f:
                    composer_data = json.load(f)

                # Check require and require-dev for pest or phpunit
                require = composer_data.get("require", {})
                require_dev = composer_data.get("require-dev", {})

                all_deps = {**require, **require_dev}

                for dep_name in all_deps:
                    if "pest" in dep_name.lower():
                        logger.info("Detected Pest in composer.json dependencies")
                        self.is_pest = True
                        return True
                    elif "phpunit" in dep_name.lower():
                        logger.info("Detected PHPUnit in composer.json dependencies")
                        self.is_phpunit = True
                        return True
            except Exception as e:
                logger.warning(
                    "Error parsing composer.json: %s",
                    str(e),
                )

        # Check for Pest or PHPUnit configuration files
        if any([(workspace / filename).exists() for filename in [
            "phpunit.xml", "phpunit.xml.dist", "pest.php"
        ]]):
            # Determine if it's Pest or PHPUnit
            if (workspace / "pest.php").exists() or (workspace / "Pest.php").exists():
                logger.info("Detected Pest configuration files")
                self.is_pest = True
            else:
                logger.info("Detected PHPUnit configuration files")
                self.is_phpunit = True
            return True

        # Check for PHP files with test patterns
        test_files = list(workspace.glob("**/tests/**/*.php")) +
             list(workspace.glob("**/test/**/*.php"))
        if test_files:
            # Sample some test files to see if they use Pest or PHPUnit style
            for test_file in test_files[:5]:  # Check up to 5 files
                try:
                    with open(test_file, "r", encoding="utf-8") as f:
                        content = f.read()
                        if "test(" in content or "it(" in content:
                            logger.info("%s", Found Pest-style tests in {test_file})
                            self.is_pest = True
                            return True
                        elif "extends TestCase" in content or "PHPUnit" in content:
                            logger.info("%s", Found PHPUnit-style tests in {test_file})
                            self.is_phpunit = True
                            return True
                except Exception:
                    # Skip files with encoding issues
                    pass

            # If we found test files but couldn't determine the type, assume PHPUnit
            logger.info("%s", Found {len(test_files)} PHP test files, assuming PHPUnit)
            self.is_phpunit = True
            return True

        return False

    def collect_only(self, workspace: Path) -> List[str]:
        """
        Run a test collection to check for syntax errors.

        Args:
            workspace: Path to the workspace directory

        Returns:
            List of error messages (empty if no errors)
        """
        try:
            # Change to workspace directory
            original_dir = Path.cwd()
            os.chdir(workspace)

            # Determine the test command (Pest or PHPUnit)
            if self.is_pest:
                command = ["vendor/bin/pest", "--list"]
            else:
                command = ["vendor/bin/phpunit", "--list-tests"]

            # Try to run the command
            result = subprocess.run(command, capture_output=True, text=True)

            # Parse output for errors
            if result.returncode != 0:
                # Extract error lines
                error_lines = []
                for line in result.stderr.splitlines() + result.stdout.splitlines():
                    # Filter for actual error messages
                    if any(pattern in line for pattern in ["error", "Error:", "Fatal error:", "Parse error:", "Exception:"]):
                        error_lines.append(line.strip())

                return error_lines

            # No errors found
            return []

        except Exception as e:
            logger.error("%s", Error collecting PHP tests: {str(e)})
            return [f"Error collecting PHP tests: {str(e)}"]

        finally:
            # Change back to original directory
            os.chdir(original_dir)

    def smoke_run(self, workspace: Path) -> bool:
        """
        Run a smoke test to check if tests pass.

        Args:
            workspace: Path to the workspace directory

        Returns:
            True if tests pass, False otherwise
        """
        try:
            # Change to workspace directory
            original_dir = Path.cwd()
            os.chdir(workspace)

            # Determine the test command (Pest or PHPUnit)
            if self.is_pest:
                command = ["vendor/bin/pest", "--stop-on-failure"]
            else:
                command = ["vendor/bin/phpunit", "--stop-on-failure"]

            # Run quick tests
            result = subprocess.run(command, capture_output=True, text=True)

            # Return True if all tests pass
            return result.returncode == 0

        except Exception as e:
            logger.error("%s", Error running PHP smoke tests: {str(e)})
            return False

        finally:
            # Change back to original directory
            os.chdir(original_dir)

    def coverage(self, workspace: Path) -> Optional[float]:
        """
        Run code coverage analysis.

        Args:
            workspace: Path to the workspace directory

        Returns:
            Coverage percentage or None if coverage analysis is not available
        """
        try:
            # Change to workspace directory
            original_dir = Path.cwd()
            os.chdir(workspace)

            # Determine the test command (Pest or PHPUnit)
            if self.is_pest:
                command = ["vendor/bin/pest", "--coverage-clover=coverage.xml"]
            else:
                command = ["vendor/bin/phpunit", "--coverage-clover=coverage.xml"]

            # Try to run the coverage analysis
            result = subprocess.run(command, capture_output=True, text=True)

            # Check if coverage is enabled
            if "The Xdebug extension is not loaded" in result.stderr or "The Xdebug extension is required" in result.stderr:
                logger.warning("PHP coverage analysis requires Xdebug extension")
                return None

            # Parse coverage report
            coverage_path = workspace / "coverage.xml"
            if coverage_path.exists():
                try:
                    tree = ET.parse(coverage_path)
                    root = tree.getroot()

                    # Look for metrics elements with line coverage
                    for metrics in root.findall(".//metrics"):
                        if "statements" in metrics.attrib and "coveredstatements" in metrics.attrib:
                            statements = int(metrics.attrib["statements"])
                            covered = int(metrics.attrib["coveredstatements"])
                            if statements > 0:
                                return 100.0 * covered / statements
                        elif "elements" in metrics.attrib and "coveredelements" in metrics.attrib:
                            elements = int(metrics.attrib["elements"])
                            covered = int(metrics.attrib["coveredelements"])
                            if elements > 0:
                                return 100.0 * covered / elements
                except Exception as e:
                    logger.error("%s", Error parsing coverage XML: {str(e)})

            # Try to extract from console output
            for line in result.stdout.splitlines():
                # Look for patterns like "Lines: 80.0%" or similar
                match = re.search(r"Lines:\s*([0-9.]+)%", line)
                if match:
                    return float(match.group(1))

            return None

        except Exception as e:
            logger.error("%s", Error running PHP coverage analysis: {str(e)})
            return None

        finally:
            # Change back to original directory
            os.chdir(original_dir)

    def mutation(self, workspace: Path) -> Optional[float]:
        """
        Run mutation testing.

        Args:
            workspace: Path to the workspace directory

        Returns:
            Mutation score percentage or None if mutation testing is not available
        """
        try:
            # Change to workspace directory
            original_dir = Path.cwd()
            os.chdir(workspace)

            # Check if infection is installed
            composer_json_path = workspace / "composer.json"
            has_infection = False

            if composer_json_path.exists():
                with open(composer_json_path, "r", encoding="utf-8") as f:
                    composer_data = json.load(f)

                # Check dependencies for infection
                require = composer_data.get("require", {})
                require_dev = composer_data.get("require-dev", {})

                all_deps = {**require, **require_dev}

                for dep_name in all_deps:
                    if "infection" in dep_name.lower():
                        has_infection = True
                        break

            # If infection is not in dependencies, check bin
            if not has_infection:
                if not (workspace / "vendor" / "bin" / "infection").exists():
                    logger.warning("Infection tool not found, skipping mutation testing")
                    return None

            # Try to run infection
            command = ["vendor/bin/infection", "--only-covered", "--min-msi=0", "--threads=2", "--no-progress"]
            result = subprocess.run(command, capture_output=True, text=True)

            # Extract mutation score from output
            output = result.stdout + result.stderr

            # Look for MSI percentage in the output
            msi_match = re.search(r"Mutation Score Indicator \(MSI\): ([0-9.]+)%", output)
            if msi_match:
                return float(msi_match.group(1))

            # Try alternative pattern
            alt_match = re.search(r"MSI:\s*([0-9.]+)%", output)
            if alt_match:
                return float(alt_match.group(1))

            return None

        except Exception as e:
            logger.error("%s", Error running PHP mutation testing: {str(e)})
            return None

        finally:
            # Change back to original directory
            os.chdir(original_dir)
