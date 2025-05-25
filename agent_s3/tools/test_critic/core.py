"""
Core test critic functionality for agent-s3.

This module provides the main orchestration for test criticism, selecting the appropriate adapter
based on the workspace and running various test quality metrics. It also includes the static
analysis capabilities from the original TestCritic class.
"""

import logging
import re
import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Set
from enum import StrEnum

from .adapters.base import Adapter

logger = logging.getLogger(__name__)

# TestType as StrEnum to make it more compatible with serialization
class TestType(StrEnum):
    """Enum representing different test types."""
    COLLECTION = "collection"
    SMOKE = "smoke"
    COVERAGE = "coverage"
    MUTATION = "mutation"
    UNIT = "unit"
    INTEGRATION = "integration"
    APPROVAL = "approval" # Often corresponds to acceptance tests
    PROPERTY_BASED = "property_based"
    STATIC = "static"
    FORMAL = "formal"
    ACCEPTANCE = "acceptance" # Explicitly add if different from approval

class TestVerdict(StrEnum):
    """Enum representing the verdict on test quality."""
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"

def select_adapter(workspace: Path, lang_hint: Optional[str] = None) -> 'Adapter':
    """
    Select the appropriate test adapter based on the workspace content and optional language hint.

    Args:
        workspace: Path to the workspace directory
        lang_hint: Optional language hint to prioritize adapter selection

    Returns:
        Selected adapter instance

    Raises:
        ValueError: If no suitable adapter is found
    """
    from .adapters.python_pytest import PythonPytestAdapter
    from .adapters.js_jest import JsJestAdapter
    from .adapters.php_pest import PhpPestAdapter

    # Create a list of adapters to check
    adapters = [
        PythonPytestAdapter(),
        JsJestAdapter(),
        PhpPestAdapter()
    ]

    # If language hint is provided, prioritize the corresponding adapter
    if lang_hint:
        lang_hint = lang_hint.lower()

        # Reorder adapters based on hint
        if lang_hint in ["python", "py"]:
            adapters.insert(0, adapters.pop(adapters.index(next(a for a in adapters if isinstance(a, PythonPytestAdapter)))))
        elif lang_hint in ["javascript", "js", "typescript", "ts"]:
            adapters.insert(0, adapters.pop(adapters.index(next(a for a in adapters if isinstance(a, JsJestAdapter)))))
        elif lang_hint in ["php"]:
            adapters.insert(0, adapters.pop(adapters.index(next(a for a in adapters if isinstance(a, PhpPestAdapter)))))

    # Try each adapter's detect method
    for adapter in adapters:
        if adapter.detect(workspace):
            logger.info("Selected test adapter: %s", adapter.name)
            return adapter

    # If no adapter detected, try to use a default based on common file patterns
    if (
        (workspace / "pyproject.toml").exists()
        or (workspace / "setup.py").exists()
        or list(workspace.glob("**/*.py"))
    ):
        logger.info(
            "Defaulting to Python test adapter based on pyproject.toml or .py files"
        )
        return adapters[0]  # Python adapter
    elif (workspace / "package.json").exists() or list(workspace.glob("**/*.js")) or list(workspace.glob("**/*.ts")):
        logger.info("Defaulting to JavaScript test adapter based on package.json or .js/.ts files")
        return adapters[1]  # JS adapter
    elif (workspace / "composer.json").exists() or list(workspace.glob("**/*.php")):
        logger.info("Defaulting to PHP test adapter based on composer.json or .php files")
        return adapters[2]  # PHP adapter

    # If still no adapter found, raise an error
    raise ValueError(f"No suitable test adapter found for workspace {workspace}")

class TestCritic:
    """
    Unified TestCritic class combining both test execution and static analysis capabilities.
    Provides both actual test running (TDD workflow) and static analysis for test quality.

    For TDD workflow:
    - Executes test frameworks to verify tests fail before implementation
    - Runs code coverage and mutation testing

    For static analysis:
    - Analyzes test quality and coverage using pattern analysis
    - Evaluates test types and ensuring proper implementation
    - Reviews test plans for proper test coverage
    """

    def __init__(self, coordinator=None):
        """Initialize with optional coordinator for LLM access."""
        self.coordinator = coordinator
        self.llm = coordinator.llm if coordinator else None
        self.workspace = Path(coordinator.config.get_workspace_path()) if coordinator and hasattr(coordinator, 'config') and coordinator.config else Path.cwd()

        # Initialize static analyzer for non-execution-based checks
        from .static_analysis import CriticStaticAnalyzer
        self.static_analyzer = CriticStaticAnalyzer(self.llm, self.coordinator)

        # Try to detect the appropriate adapter
        try:
            self.adapter = select_adapter(self.workspace)
        except Exception as e:
            logger.warning(f"Could not select test adapter: {e}")
            self.adapter = None


    # =========================================================================
    # TDD/ATDD Workflow Methods - Running Actual Tests
    # =========================================================================

    def run_analysis(self, workspace: Optional[Path] = None) -> dict:
        """
        Run full test analysis using the appropriate adapter and return verdict.
        This is the primary method for the TDD workflow which executes actual tests.

        Args:
            workspace: Optional workspace path to use instead of the default

        Returns:
            Dictionary with test analysis results
        """
        if workspace:
            self.workspace = workspace
            try:
                self.adapter = select_adapter(workspace)
            except Exception as e:
                logger.warning(f"Could not select test adapter: {e}")
                return {
                    "verdict": TestVerdict.FAIL,
                    "details": {
                        "error": f"Could not select test adapter: {str(e)}",
                        "collect_errors": [f"Test critic error: {str(e)}"],
                        "smoke_passed": False,
                        "coverage_percent": 0.0,
                        "mutation_score": 0.0
                    }
                }

        # If no adapter is available, try to detect one
        if not self.adapter:
            try:
                self.adapter = select_adapter(self.workspace)
            except Exception as e:
                logger.warning(f"Could not select test adapter: {e}")
                return {
                    "verdict": TestVerdict.FAIL,
                    "details": {
                        "error": f"Could not select test adapter: {str(e)}",
                        "collect_errors": [f"Test critic error: {str(e)}"],
                        "smoke_passed": False,
                        "coverage_percent": 0.0,
                        "mutation_score": 0.0
                    }
                }

        # Run the tests and evaluate results
        try:
            logger.info(f"Running test critic with {self.adapter.name} adapter")

            # Run each test step
            results = {
                "collect_errors": self.adapter.collect_only(self.workspace),
                "smoke_passed": self.adapter.smoke_run(self.workspace),
                "coverage_percent": self.adapter.coverage(self.workspace),
                "mutation_score": self.adapter.mutation(self.workspace),
            }

            # Write results to files using the reporter
            from .reporter import Reporter
            Reporter(self.workspace).write(results)

            # Evaluate results and return verdict
            return self._evaluate_results(results)

        except Exception as e:
            logger.error(f"Error running test critic: {e}")
            # Return a result object indicating failure
            return {
                "verdict": TestVerdict.FAIL,
                "details": {
                    "collect_errors": [f"Test critic error: {str(e)}"],
                    "smoke_passed": False,
                    "coverage_percent": 0.0,
                    "mutation_score": 0.0,
                    "error": str(e)
                }
            }

    def _evaluate_results(self, results: dict) -> dict:
        """
        Evaluate test results against thresholds and produce verdict.

        Args:
            results: Dictionary of test results

        Returns:
            Dictionary with verdict and details
        """
        verdict = TestVerdict.PASS

        # Check collection errors
        if results.get("collect_errors"):
            verdict = TestVerdict.FAIL

        # Check smoke test
        if not results.get("smoke_passed", False):
            verdict = TestVerdict.FAIL

        # Check coverage threshold
        if (coverage := results.get("coverage_percent", 0)) is not None and coverage < 80.0 :
            verdict = max(verdict, TestVerdict.WARN) # type: ignore

        # Check mutation score threshold
        mutation = results.get("mutation_score")
        if mutation is not None and mutation < 70.0:
            verdict = max(verdict, TestVerdict.WARN) # type: ignore

        return {
            "verdict": verdict,
            "details": results
        }

    # ------------------------------------------------------------------
    # Static analysis wrappers
    # ------------------------------------------------------------------

    def analyze_test_file(self, file_path: str, content: str) -> Dict[str, Any]:
        """Delegate to :class:`CriticStaticAnalyzer`."""
        return self.static_analyzer.analyze_test_file(file_path, content)

    def critique_tests(self, tests_plan: Dict[str, Any], risk_assessment: Dict[str, Any]) -> Dict[str, Any]:
        """Delegate planned test critique to the static analyzer."""
        return self.static_analyzer.critique_tests(tests_plan, risk_assessment)

    def analyze_plan(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """Delegate plan analysis to the static analyzer."""
        return self.static_analyzer.analyze_plan(plan)

    def analyze_implementation(self, file_path: str, content: str, test_files: List[Dict[str, Any]]):
        """Delegate implementation analysis to the static analyzer."""
        return self.static_analyzer.analyze_implementation(file_path, content, test_files)

    def analyze_generated_code(self, files: Dict[str, str]) -> Dict[str, Any]:
        """Delegate generated code analysis to the static analyzer."""
        return self.static_analyzer.analyze_generated_code(files)

    def perform_llm_analysis(self, content: str, prompt: str | None = None) -> Dict[str, Any]:
        """Delegate LLM-based analysis to the static analyzer."""
        return self.static_analyzer.perform_llm_analysis(content, prompt)

