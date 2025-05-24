"""
JavaScript/TypeScript Jest adapter for the test critic.

This adapter implements the necessary methods to run Jest commands for
test collection, smoke tests, coverage analysis, and mutation testing.
"""

import os
import re
import json
import logging
import subprocess
from pathlib import Path
from typing import List, Optional

from ..core import Adapter

logger = logging.getLogger(__name__)

class JsJestAdapter(Adapter):
    """JavaScript/TypeScript Jest adapter for test critic."""

    name = "js_jest"

    def detect(self, workspace: Path) -> bool:
        """
        Detect if this adapter is suitable for the workspace.

        Args:
            workspace: Path to the workspace directory

        Returns:
            True if this adapter should be used, False otherwise
        """
        # Check for package.json with Jest dependencies
        package_json_path = workspace / "package.json"
        if package_json_path.exists():
            try:
                with open(package_json_path, "r", encoding="utf-8") as f:
                    package_data = json.load(f)

                # Check dependencies and devDependencies for jest
                dependencies = package_data.get("dependencies", {})
                dev_dependencies = package_data.get("devDependencies", {})

                if "jest" in dependencies or "jest" in dev_dependencies:
                    logger.info("Detected Jest in package.json dependencies")
                    return True

                # Check scripts for jest commands
                scripts = package_data.get("scripts", {})
                for script in scripts.values():
                    if "jest" in script:
                        logger.info("Detected Jest in package.json scripts")
                        return True
            except Exception as e:
                logger.warning(
                    "Error parsing package.json: %s",
                    str(e),
                )

        # Check for jest.config.js
        if any([(workspace / filename).exists() for filename in [
            "jest.config.js", "jest.config.ts", "jest.config.json"
        ]]):
            logger.info("Detected Jest configuration files")
            return True

        # Check for test files with Jest patterns
        test_files = []
        for ext in [".js", ".jsx", ".ts", ".tsx"]:
            test_files.extend(list(workspace.glob(f"**/*.test{ext}")))
            test_files.extend(list(workspace.glob(f"**/*.spec{ext}")))
            test_files.extend(list(workspace.glob(f"**/__tests__/**/*{ext}")))

        if test_files:
            logger.info("%s", Found {len(test_files)} Jest-style test files)
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

            # Run Jest in list-only mode
            command = ["npx", "jest", "--listTests"]
            result = subprocess.run(command, capture_output=True, text=True)

            # If command failed, parse error output
            if result.returncode != 0:
                # Split by line and filter for error messages
                error_lines = []
                for line in result.stderr.splitlines() + result.stdout.splitlines():
                    # Filter for actual error messages
                    if any(pattern in line for pattern in ["Error:", "SyntaxError:", "Cannot find module", "Failed to load"]):
                        error_lines.append(line.strip())

                return error_lines

            # No errors found
            return []

        except Exception as e:
            logger.error("%s", Error listing Jest tests: {str(e)})
            return [f"Error listing Jest tests: {str(e)}"]

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

            # Run Jest with bail option
            command = ["npx", "jest", "--bail"]
            result = subprocess.run(command, capture_output=True, text=True)

            # Return True if all tests pass
            return result.returncode == 0

        except Exception as e:
            logger.error("%s", Error running Jest smoke tests: {str(e)})
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

            # Run Jest with coverage option and JSON reporter
            command = ["npx", "jest", "--coverage", "--coverageReporters=json-summary"]
            subprocess.run(command, capture_output=True)

            # Parse coverage report
            coverage_path = workspace / "coverage" / "coverage-summary.json"
            if coverage_path.exists():
                with open(coverage_path, "r") as f:
                    data = json.load(f)
                    total = data.get("total", {})
                    # We'll use statements coverage as the overall metric
                    if "statements" in total:
                        return total["statements"].get("pct", 0)
                    # Fallback to lines if statements not available
                    if "lines" in total:
                        return total["lines"].get("pct", 0)

            # If we can't find the report, check for lcov info
            lcov_path = workspace / "coverage" / "lcov.info"
            if lcov_path.exists():
                # Parse lcov info
                with open(lcov_path, "r") as f:
                    lcov_content = f.read()

                # Get total line coverage ratio
                lines_found = 0
                lines_hit = 0

                for line in lcov_content.splitlines():
                    if line.startswith("LF:"):
                        lines_found += int(line[3:])
                    elif line.startswith("LH:"):
                        lines_hit += int(line[3:])

                if lines_found > 0:
                    return 100.0 * lines_hit / lines_found

            # If we still can't find coverage info, check for console output
            # Fallback to extract from output
            logger.warning("Could not find coverage report, trying to run Jest with coverage again")
            result = subprocess.run(["npx", "jest", "--coverage"], capture_output=True, text=True)

            # Look for coverage output in console
            for line in result.stdout.splitlines():
                # Look for patterns like "Statements   : 75.44%" or similar
                coverage_match = re.search(r"(?:All files|Statements)\s*:?\s*([0-9.]+)%", line)
                if coverage_match:
                    return float(coverage_match.group(1))

            return None

        except Exception as e:
            logger.error("%s", Error running Jest coverage analysis: {str(e)})
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
            # Check if necessary mutation testing tools are installed
            package_json_path = workspace / "package.json"
            has_stryker = False

            if package_json_path.exists():
                with open(package_json_path, "r", encoding="utf-8") as f:
                    package_data = json.load(f)

                # Check dependencies and devDependencies for stryker
                dependencies = package_data.get("dependencies", {})
                dev_dependencies = package_data.get("devDependencies", {})

                for dep_name in list(dependencies.keys()) + list(dev_dependencies.keys()):
                    if "stryker" in dep_name or "mutation" in dep_name:
                        has_stryker = True
                        break

            # Check if stryker is installed or in node_modules
            if not has_stryker and not (workspace / "node_modules" / "@stryker-mutator").exists():
                # Try to check if it's available globally
                stryker_check = subprocess.run(["npx", "stryker", "--version"],
                                              capture_output=True, text=True)
                if stryker_check.returncode != 0:
                    logger.warning("Stryker Mutator not found, skipping mutation testing")
                    return None

            # Change to workspace directory
            original_dir = Path.cwd()
            os.chdir(workspace)

            # Find source directories to mutate
            source_dirs = []
            for dir_name in ["src", "lib", "app", "components"]:
                if (workspace / dir_name).exists() and list((workspace / dir_name).glob("**/*.{js,jsx,ts,tsx}")):
                    source_dirs.append(dir_name)

            if not source_dirs:
                source_dirs = ["."]

            # Create a glob pattern for source files
            source_pattern = " ".join([f"{dir}/**/*.{{js,jsx,ts,tsx}}" for dir in source_dirs])

            # Run stryker with Jest
            command = ["npx", "stryker", "run", "--testRunner", "jest", "--mutate", source_pattern]
            stryker_result = subprocess.run(command, capture_output=True, text=True)

            # Check reports directory for results
            reports_path = workspace / "reports" / "mutation"
            if reports_path.exists():
                latest_report = max(reports_path.iterdir(), key=lambda p: p.stat().st_mtime)
                if latest_report.suffix == ".json":
                    with open(latest_report, "r") as f:
                        data = json.load(f)
                        # Extract mutation score
                        score = data.get("mutationScore", None)
                        if score is not None:
                            return score

            # Try to extract score from output
            output = stryker_result.stdout + stryker_result.stderr
            score_match = re.search(r"Mutation score:\s*([0-9.]+)%", output)
            if score_match:
                return float(score_match.group(1))

            # No results found
            return None

        except Exception as e:
            logger.error("%s", Error running Stryker mutation testing: {str(e)})
            return None

        finally:
            # Change back to original directory
            os.chdir(original_dir)
