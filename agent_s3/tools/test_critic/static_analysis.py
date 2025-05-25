"""Static analysis utilities for TestCritic."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from .core import TestType, TestVerdict  # type: ignore  # circular import

logger = logging.getLogger(__name__)


class CriticStaticAnalyzer:
    """Encapsulates static analysis logic used by :class:`TestCritic`."""

    def __init__(self, llm=None, coordinator=None) -> None:
        self.llm = llm
        self.coordinator = coordinator
        self._init_test_patterns()

    def _init_test_patterns(self):
        """Initialize regex patterns for identifying test types."""
        self.patterns = {
            TestType.UNIT: {
                "python": [
                    r"def\s+test_\w+",
                    r"class\s+Test\w+",
                    r"assert\s+",
                    r"unittest\.TestCase",
                    r"self\.assert\w+"
                ],
                "javascript": [
                    r"test\s*\(",
                    r"it\s*\(",
                    r"describe\s*\(",
                    r"expect\s*\(",
                    r"assert\."
                ]
            },
            TestType.INTEGRATION: {
                "python": [
                    r"@pytest\.mark\.integration",
                    r"class\s+Integration",
                    r"integration_test",
                    r"test_integration",
                    r"mock\.patch",
                    r"requests_mock"
                ],
                "javascript": [
                    r"integration-test",
                    r"integrationTest",
                    r"supertest",
                    r"request\s*\("
                ]
            },
            TestType.APPROVAL: { #Often corresponds to acceptance or snapshot tests
                "python": [
                    r"approvaltests",
                    r"verify\(", # Common in approval testing libraries
                    r"assert_match_snapshot", # Snapshot testing
                    r"\.approved\.", # File naming convention
                    r"self\.verify\("
                ],
                "javascript": [
                    r"verify\(",
                    r"toMatchSnapshot\(", # Jest snapshot testing
                    r"\.approved\.",
                    r"approvals\."
                ]
            },
            TestType.PROPERTY_BASED: {
                "python": [
                    r"hypothesis",
                    r"@given",
                    r"strategies\.",
                    r"@hypothesis\.given",
                    r"@settings"
                ],
                "javascript": [
                    r"jsverify",
                    r"fast-check",
                    r"quickcheck",
                    r"forall",
                    r"fc\.property"
                ]
            },
            TestType.STATIC: {
                "python": [
                    r"mypy",
                    r"pylint",
                    r"flake8",
                    r"pycodestyle",
                    r"ruff",
                    r"# type:"
                ],
                "javascript": [
                    r"eslint",
                    r"tslint",
                    r"@ts-check",
                    r"@typescript-eslint",
                    r"prettier"
                ]
            },
            TestType.FORMAL: {
                "python": [
                    r"z3",
                    r"sympy",
                    r"formal verification",
                    r"model checking",
                    r"invariant"
                ],
                "javascript": [
                    r"jsverify", # Can be used for formal properties
                    r"invariant",
                    r"contract\."
                ]
            },
             TestType.ACCEPTANCE: { # Specific patterns for acceptance if distinct from approval
                "python": [
                    r"behave", # BDD framework
                    r"pytest-bdd",
                    r"@scenario",
                    r"given\(", r"when\(", r"then\(" # Gherkin keywords often in test code
                ],
                "javascript": [
                    r"cucumber", # BDD framework
                    r"testcafe", # E2E testing
                    r"cypress",  # E2E testing
                    r"given\(", r"when\(", r"then\("
                ]
            }
        }

        # Framework-specific patterns for test assertions
        self.assertion_patterns = {
            "pytest": [r"assert\s+", r"pytest\.raises"],
            "unittest": [r"self\.assert\w+", r"self\.fail"],
            "jest": [r"expect\s*\(.*\)\.to", r"assert\."],
            "mocha": [r"assert\.", r"expect\s*\("],
        }

        # Patterns that indicate test quality issues
        self.quality_issue_patterns = [
            r"# TODO",
            r"# FIXME",
            r"pass  # No test implementation",
            r"//\s*TODO",
            r"//\s*FIXME",
            r"test\.skip",
            r"@pytest\.mark\.skip",
            r"@unittest\.skip"
        ]

    # =========================================================================
    # TDD/ATDD Workflow Methods - Running Actual Tests
    # =========================================================================

    def analyze_test_file(self, file_path: str, content: str) -> Dict[str, Any]:
        """
        Analyze a test file to determine test types, quality and coverage.

        Args:
            file_path: Path to the test file
            content: Content of the test file

        Returns:
            Dictionary with analysis results
        """
        # Determine language from file extension
        language = "javascript" if file_path.endswith(('.js', '.jsx', '.ts', '.tsx')) else "python"

        # Initialize results
        results = {
            "file_path": file_path,
            "language": language,
            "test_types": [],
            "test_count": 0,
            "assertion_count": 0,
            "issues": [],
            "verdict": TestVerdict.FAIL # Start with FAIL, upgrade if conditions met
        }

        # Count tests
        results["test_count"] = self._count_tests(content, language)

        # Count assertions
        results["assertion_count"] = self._count_assertions(content, language)

        # Detect test types
        detected_test_types: Set[TestType] = set()
        for test_type_enum_member in TestType: # Iterate through all enum members
            # Skip meta-types or types not directly identified from code patterns here
            if test_type_enum_member in [TestType.COLLECTION, TestType.SMOKE, TestType.COVERAGE, TestType.MUTATION]:
                continue
            if self._detect_test_type(content, test_type_enum_member, language):
                detected_test_types.add(test_type_enum_member)
        results["test_types"] = sorted(list(t.value for t in detected_test_types))


        # Detect quality issues
        issues = self._detect_quality_issues(content)
        if issues:
            results["issues"].extend(issues) # Append to existing issues

        # Determine verdict based on tests, assertions and issues
        results["verdict"] = self._determine_static_verdict(results)

        return results

    def critique_tests(self, tests_plan: Dict[str, Any], risk_assessment: Dict[str, Any])
         -> Dict[str, Any]:        """
        Critiques the planned test implementations against the risk assessment.
        This method is called by FeatureGroupProcessor on the *planned* tests.

        Args:
            tests_plan: A dictionary where keys are test types (e.g., "unit_tests")
                        and values are lists of planned test objects (each with "file",
                        "test_name", "code", "description", etc.). This comes from
                        planner_json_enforced.
            risk_assessment: A dictionary containing risk information like
                             "critical_files", "potential_regressions",
                             "required_test_characteristics".

        Returns:
            A dictionary with critique results, including a verdict and issues.
        """
        critique_results = {
            "verdict": TestVerdict.PASS,  # Start optimistic
            "issues_found": [],
            "risk_coverage_notes": [],
            "planned_test_analysis": {} # Stores analysis of individual planned tests
        }
        all_issues: List[Dict[str, str]] = [] # {severity: "critical"|"major"|"minor", description: "..."}

        # 1. Analyze Overall Plan Structure (Planned Test Types)
        required_test_characteristics = risk_assessment.get("required_test_characteristics", {})
        # Normalize required_types from risk assessment (e.g., "unit" -> "unit_tests")
        required_types_from_risk_normalized = {
            (t.lower() if t.lower().endswith("_tests") else t.lower() + "_tests")
            for t in required_test_characteristics.get("required_types", [])
        }

        # Define some default essential test types
        default_essential_types_normalized = {"unit_tests", "integration_tests"}
        all_required_categories_normalized = required_types_from_risk_normalized.union(default_essential_types_normalized)

        for req_category_key_normalized in all_required_categories_normalized:
            # Check if the normalized key exists in tests_plan or its non-plural form + "_tests"
            category_present = False
            if req_category_key_normalized in tests_plan:
                 planned_tests_for_category = tests_plan.get(req_category_key_normalized)
                 if isinstance(planned_tests_for_category, list) and planned_tests_for_category:
                     category_present = True

            if not category_present:
                issue_desc = f"Missing or empty plan for required/essential test category: {req_category_key_normalized.replace('_tests', '')}"
                all_issues.append({"severity": "major", "description": issue_desc})

        # 2. Analyze the content of each planned test
        for test_category_key, planned_tests_list in tests_plan.items():
            if not isinstance(planned_tests_list, list):
                logger.warning("%s", Unexpected format for planned tests in category '{test_category_key}'. Expected list, got {type(planned_tests_list)})
                continue

            critique_results["planned_test_analysis"][test_category_key] = []
            for i, p_test_obj in enumerate(planned_tests_list):
                if not isinstance(p_test_obj, dict):
                    all_issues.append({"severity": "minor", "description": f"Malformed planned test object (not a dict) in {test_category_key} at index {i}."})
                    continue

                planned_code = p_test_obj.get("code", "")
                planned_file_path = p_test_obj.get("file", f"unknown_planned_file_{test_category_key}_{i}.py") # Fallback path
                planned_test_name = p_test_obj.get("test_name", "Unnamed Planned Test")

                if not planned_code:
                     all_issues.append({"severity": "minor", "description": f"Planned test '{planned_test_name}' in {test_category_key} has no code."})
                     # Still create an analysis entry, but it will likely fail

                # Use analyze_test_file for static analysis of the planned code
                individual_analysis = self.analyze_test_file(planned_file_path, planned_code)
                critique_results["planned_test_analysis"][test_category_key].append({
                    "planned_test_name": planned_test_name,
                    "static_analysis": individual_analysis
                })

                if individual_analysis["verdict"] != TestVerdict.PASS:
                    for issue_desc in individual_analysis.get("issues", []):
                         all_issues.append({"severity": "minor", "description": f"Issue in planned test '{planned_test_name}' ({planned_file_path}): {issue_desc}"})

        # 3. Cross-reference with risk_assessment
        #    - Critical Files:
        critical_files_risk = risk_assessment.get("critical_files", [])
        covered_critical_files: Set[str] = set()
        if critical_files_risk: # Only proceed if there are critical files defined
            for test_cat_list in tests_plan.values():
                if isinstance(test_cat_list, list):
                    for p_test_obj in test_cat_list:
                        if isinstance(p_test_obj, dict):
                            for func_ref in p_test_obj.get("tested_functions", []):
                                if isinstance(func_ref, str) and "::" in func_ref:
                                    tested_file_path = func_ref.split("::")[0].strip()
                                    if tested_file_path in critical_files_risk:
                                        covered_critical_files.add(tested_file_path)

            uncovered_critical = [f for f in critical_files_risk if f not in covered_critical_files]
            if uncovered_critical:
                issue_desc = f"Critical files from risk assessment not explicitly covered by planned tests (via 'tested_functions'): {', '.join(uncovered_critical)}"
                all_issues.append({"severity": "critical", "description": issue_desc})
                critique_results["risk_coverage_notes"].append(issue_desc)

        #    - Potential Regressions:
        potential_regressions_risk = risk_assessment.get("potential_regressions", [])
        if potential_regressions_risk:
            note = f"Risk assessment mentions {len(potential_regressions_risk)} potential regression area(s). Manual review recommended to ensure planned tests adequately cover these regression scenarios."
            critique_results["risk_coverage_notes"].append(note)
            # More advanced: keyword match regression descriptions against test descriptions/code.
            for regression_desc in potential_regressions_risk:
                found_regression_keyword = False
                reg_keywords = set(re.findall(r'\b\w{4,}\b', regression_desc.lower())) # Keywords from regression desc
                if not reg_keywords:
                    continue

                for test_cat_list in tests_plan.values():
                    if isinstance(test_cat_list, list):
                        for p_test_obj in test_cat_list:
                            if isinstance(p_test_obj, dict):
                                test_text = (p_test_obj.get("test_name", "") + " " +
                                             p_test_obj.get("description", "")).lower()
                                if any(rk in test_text for rk in reg_keywords):
                                    found_regression_keyword = True
                                    break
                        if found_regression_keyword:
                            break
                if not found_regression_keyword:
                    issue_desc = f"Planned tests do not seem to explicitly mention keywords related to potential regression: '{regression_desc[:50]}...'"
                    all_issues.append({"severity": "major", "description": issue_desc})
                    critique_results["risk_coverage_notes"].append(issue_desc)


        #    - Required Test Characteristics (Keywords):
        req_keywords_risk = required_test_characteristics.get("required_keywords", [])
        if req_keywords_risk:
            for r_keyword_lower in (k.lower() for k in req_keywords_risk):
                found_keyword_in_plan = False
                for test_cat_list in tests_plan.values():
                    if isinstance(test_cat_list, list):
                        for p_test_obj in test_cat_list:
                             if isinstance(p_test_obj, dict) and (
                                r_keyword_lower in p_test_obj.get("test_name", "").lower() or
                                r_keyword_lower in p_test_obj.get("description", "").lower() or
                                r_keyword_lower in p_test_obj.get("code", "").lower() # Check planned code too
                             ):
                                found_keyword_in_plan = True
                                break
                        if found_keyword_in_plan:
                            break
                if not found_keyword_in_plan:
                    issue_desc = f"Required keyword '{r_keyword_lower}' from risk assessment not found in any planned test's name, description, or code."
                    all_issues.append({"severity": "major", "description": issue_desc})
                    critique_results["risk_coverage_notes"].append(issue_desc)

        #    - Suggested Libraries:
        suggested_libs_risk = required_test_characteristics.get("suggested_libraries", [])
        if suggested_libs_risk:
            for s_lib_lower in (lib.lower() for lib in suggested_libs_risk):
                found_library_in_plan = False
                for test_cat_list in tests_plan.values():
                     if isinstance(test_cat_list, list):
                        for p_test_obj in test_cat_list:
                            if isinstance(p_test_obj, dict):
                                planned_code_lower = p_test_obj.get("code", "").lower()
                                # Basic check for import or direct usage
                                if f"import {s_lib_lower}" in planned_code_lower or \
                                   f"from {s_lib_lower}" in planned_code_lower or \
                                   s_lib_lower + "." in planned_code_lower:
                                    found_library_in_plan = True
                                    break
                        if found_library_in_plan:
                            break
                if not found_library_in_plan:
                    issue_desc = f"Suggested library '{s_lib_lower}' from risk assessment not apparently used in planned test code."
                    all_issues.append({"severity": "minor", "description": issue_desc}) # Minor as it's a suggestion
                    critique_results["risk_coverage_notes"].append(issue_desc)


        critique_results["issues_found"] = all_issues

        # Determine final verdict based on severity of issues
        current_verdict = TestVerdict.PASS
        if any(i["severity"] == "critical" for i in all_issues):
            current_verdict = TestVerdict.FAIL
        elif any(i["severity"] == "major" for i in all_issues):
            current_verdict = TestVerdict.WARN
        elif all_issues: # Any minor issues
            current_verdict = TestVerdict.WARN

        critique_results["verdict"] = current_verdict
        return critique_results

    def analyze_plan(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze a plan to ensure it includes all required test types.

        Args:
            plan: Plan data (from planner module's JSON output, specifically the 'tests' key
                  as defined in planner_json_enforced.py)

        Returns:
            Analysis results
        """
        results = {
            "required_test_types": [TestType.UNIT, TestType.INTEGRATION,
                                   TestType.APPROVAL, TestType.PROPERTY_BASED, TestType.ACCEPTANCE],
            "has_test_section": False, # This will be true if 'tests' key exists and is a dict
            "planned_test_types": [],  # This will be populated from plan["tests"]
            "test_coverage": 0.0,
            "issues": [],
            "verdict": TestVerdict.FAIL
        }

        # The 'plan' argument is the full planner output. We look for the 'tests' key.
        planner_tests_output = plan.get("tests")

        if planner_tests_output and isinstance(planner_tests_output, dict):
            results["has_test_section"] = True

            # Extract planned test types based on the keys present in planner_tests_output
            # This aligns with the structure in planner_json_enforced.py
            # Map planner keys to TestType enum members
            key_to_test_type_map = {
                "unit_tests": TestType.UNIT,
                "integration_tests": TestType.INTEGRATION,
                "acceptance_tests": TestType.ACCEPTANCE, # Using TestType.ACCEPTANCE
                "property_based_tests": TestType.PROPERTY_BASED,
                # Consider if "approval_tests" key might appear or if "acceptance_tests" covers it.
                # For now, TestType.APPROVAL is in required_test_types but not directly mapped from a key.
            }

            planned_test_type_enums: Set[TestType] = set()
            for key, test_type_enum in key_to_test_type_map.items():
                if planner_tests_output.get(key) and isinstance(planner_tests_output[key], list) and planner_tests_output[key]:
                    planned_test_type_enums.add(test_type_enum)

            results["planned_test_types"] = sorted([t.value for t in planned_test_type_enums])

        # Calculate test coverage based on required vs planned types
        required_count = len(results["required_test_types"])
        # Count how many of the required_test_types (enum members) are present in planned_test_type_enums
        planned_and_required_count = sum(1 for req_type_enum in results["required_test_types"]
                                         if req_type_enum in planned_test_type_enums) # type: ignore

        if required_count > 0:
            results["test_coverage"] = planned_and_required_count / required_count
        elif not results["required_test_types"] and results["planned_test_types"]:
            results["test_coverage"] = 1.0
        elif not results["required_test_types"] and not results["planned_test_types"]:
             results["test_coverage"] = 1.0 # Or 0.0, depending on interpretation

        # Identify missing test types
        missing_tests_enums = [req_type for req_type in results["required_test_types"]
                               if req_type not in planned_test_type_enums] # type: ignore

        if missing_tests_enums:
            missing_tests_values = [mt.value for mt in missing_tests_enums]
            results["issues"].append(f"Missing required test types in plan: {', '.join(missing_tests_values)}")

        if not results["has_test_section"] and results["required_test_types"]:
            results["issues"].append("No 'tests' section found in plan, but test types are required.")
        elif results["has_test_section"] and not results["planned_test_types"] and results["required_test_types"]:
            results["issues"].append("The 'tests' section in the plan is empty or does not map to known test types, but test types are required.")

        # Determine verdict
        if results["test_coverage"] >= 1.0 and not results["issues"]:
            results["verdict"] = TestVerdict.PASS
        elif results["test_coverage"] > 0.5 and not results["issues"]:
            results["verdict"] = TestVerdict.WARN
        else:
            results["verdict"] = TestVerdict.FAIL

        return results

    def analyze_implementation(self, file_path: str, content: str, test_files: List[Dict[str, Any]])
         -> Dict[str, Any]:        """
        Analyze an implementation file and its associated test files.

        Args:
            file_path: Path to the implementation file
            content: Content of the implementation file
            test_files: List of test file analysis results (from analyze_test_file)

        Returns:
            Analysis results
        """
        language = "javascript" if file_path.endswith(('.js', '.jsx', '.ts', '.tsx')) else "python"

        results = {
            "file_path": file_path,
            "language": language,
            "has_tests": len(test_files) > 0,
            "test_files": [tf["file_path"] for tf in test_files],
            "test_types_covered": [], # Will be list of TestType enum values
            "missing_test_types": [], # Will be list of TestType enum values
            "total_test_count": 0,
            "total_assertion_count": 0,
            "issues": [],
            "verdict": TestVerdict.FAIL
        }

        # Collect test types from all test files
        all_test_types_found_enums: Set[TestType] = set()
        for test_file_analysis in test_files:
            # test_file_analysis["test_types"] is List[str], convert to List[TestType]
            for type_str in test_file_analysis.get("test_types", []):
                try:
                    all_test_types_found_enums.add(TestType(type_str))
                except ValueError:
                    logger.warning("%s", Unknown test type string '{type_str}' found in test file analysis for {test_file_analysis.get('file_path)}")
            results["total_test_count"] += test_file_analysis.get("test_count", 0)
            results["total_assertion_count"] += test_file_analysis.get("assertion_count", 0)

        results["test_types_covered"] = sorted([t.value for t in all_test_types_found_enums])

        # Check which required test types are missing
        # Using a common set of "generally required" test types for implementation analysis
        generally_required_types = [TestType.UNIT, TestType.INTEGRATION, TestType.ACCEPTANCE] # Example set
        results["missing_test_types"] = sorted([
            t.value for t in generally_required_types if t not in all_test_types_found_enums
        ])

        # Detect functions/classes in implementation file
        implementable_elements = self._extract_implementable_elements(content, language)

        # Check if all elements are covered by tests
        if implementable_elements and results["total_test_count"] < len(implementable_elements):
            results["issues"].append(f"Potentially not all elements are tested: found {len(implementable_elements)} elements in implementation but only {results['total_test_count']} tests in associated test files.")

        # Check if there are enough assertions per test (heuristic: at least 1 per test)
        if results["total_test_count"] > 0 and results["total_assertion_count"] < results["total_test_count"]:
            results["issues"].append(f"Low assertion count: only {results['total_assertion_count']} assertions for {results['total_test_count']} tests across associated test files.")

        # Determine verdict
        if not results["missing_test_types"] and not results["issues"] and results["has_tests"]:
            results["verdict"] = TestVerdict.PASS
        elif len(results["missing_test_types"]) <= 1 and results["has_tests"] and not any("Potentially not all elements are tested" in issue for issue in results["issues"]): # Allow one missing type for WARN
            results["verdict"] = TestVerdict.WARN
        else:
            results["verdict"] = TestVerdict.FAIL # Default or more significant issues

        return results

    def analyze_generated_code(self, files: Dict[str, str]) -> Dict[str, Any]:
        """
        Analyze generated code for test coverage and quality.

        Args:
            files: Dictionary mapping file paths to content

        Returns:
            Analysis results
        """
        results = {
            "total_files": len(files),
            "implementation_files": [],
            "test_files": [],
            "test_implementation_ratio": 0.0,
            "test_types_found": set(), # Store TestType enum members
            "missing_test_types": [],  # Store string values of missing TestType enums
            "coverage_estimate": 0.0,  # Heuristic based on ratio and type coverage
            "issues": [],
            "verdict": TestVerdict.FAIL
        }

        implementation_files_dict: Dict[str, str] = {}
        test_files_dict: Dict[str, str] = {}

        for file_path, content in files.items():
            if self._is_test_file(file_path, content):
                test_files_dict[file_path] = content
                results["test_files"].append(file_path)
            else:
                implementation_files_dict[file_path] = content
                results["implementation_files"].append(file_path)

        # Calculate test/implementation ratio
        impl_count = len(implementation_files_dict)
        test_count = len(test_files_dict)

        if impl_count > 0:
            results["test_implementation_ratio"] = test_count / impl_count
        elif test_count > 0 : # Only test files
             results["test_implementation_ratio"] = float('inf') # Or some other indicator
        else: # No files or no impl files
            results["test_implementation_ratio"] = 0.0


        # Analyze each test file to identify test types
        found_test_type_enums: Set[TestType] = set()
        for file_path, content in test_files_dict.items():
            analysis = self.analyze_test_file(file_path, content)
            # analysis["test_types"] is List[str], convert to Set[TestType]
            for type_str in analysis.get("test_types", []):
                try:
                    found_test_type_enums.add(TestType(type_str))
                except ValueError:
                     logger.warning("%s", Unknown test type string '{type_str}' from analyze_test_file for {file_path})
        results["test_types_found"] = found_test_type_enums # Store the Set of enum members


        # Check for missing test types against a general set of expectations
        # Using a common set of "generally required" test types for generated code analysis
        generally_required_types = [TestType.UNIT, TestType.INTEGRATION, TestType.ACCEPTANCE]
        missing_type_enums = [t for t in generally_required_types if t not in found_test_type_enums]
        results["missing_test_types"] = sorted([t.value for t in missing_type_enums])

        # Estimate coverage based on test files and types
        if impl_count > 0 or test_count > 0: # Calculate if there's anything to cover or any tests
            # Base coverage on test/implementation ratio and test types coverage
            if generally_required_types:
                type_coverage_metric = (len(generally_required_types) - len(missing_type_enums)) / len(generally_required_types)
            else:
                type_coverage_metric = 1.0 if found_test_type_enums else 0.0 # If no types are required, 100% if any found.

            # Heuristic weighted formula
            ratio_weight = 0.6
            type_weight = 0.4

            # Cap ratio at 1.0 for coverage calculation (e.g. if more test files than impl files)
            effective_ratio = min(1.0, results["test_implementation_ratio"]) if results["test_implementation_ratio"] != float('inf') else 1.0

            coverage = (ratio_weight * effective_ratio) + (type_weight * type_coverage_metric)
            results["coverage_estimate"] = coverage

        # Identify issues
        if test_count == 0 and impl_count > 0 : # If there are impl files but no test files
            results["issues"].append("No test files found for the implementation files.")

        if results["missing_test_types"]:
            results["issues"].append(f"Missing generally expected test types: {', '.join(results['missing_test_types'])}")

        # Test implementation ratio warning only if there are implementation files
        if impl_count > 0 and results["test_implementation_ratio"] < 0.5:
            results["issues"].append(f"Low test-to-implementation ratio: {results['test_implementation_ratio']:.2f}. Consider adding more tests.")

        # Determine verdict
        if not results["issues"] and results["coverage_estimate"] >= 0.8:
            results["verdict"] = TestVerdict.PASS
        elif results["coverage_estimate"] >= 0.5 and not any("No test files found" in issue for issue in results["issues"]): # WARN if some coverage and no critical "no tests" issue
            results["verdict"] = TestVerdict.WARN
        else:
            results["verdict"] = TestVerdict.FAIL # Default or more significant issues

        # Convert set of TestType enums to list of strings for JSON serialization if needed by caller
        # results["test_types_found"] = sorted([t.value for t in found_test_type_enums]) # Already handled by missing_test_types for output

        return results

    # =========================================================================
    # Helper Methods for Static Analysis
    # =========================================================================

    def _count_tests(self, content: str, language: str) -> int:
        """Count the number of test cases in a file."""
        if language == "python":
            # Count test functions and methods
            test_patterns = [
                r"def\s+test_\w+",
                r"@pytest\.mark\.parametrize.*\ndef\s+test_", # More specific for parametrized tests
                r"class\s+Test\w+[\s\S]*?def\s+\w+\s*\(self", # Methods in unittest-style classes
            ]
        else:  # javascript/typescript
            test_patterns = [
                r"test\s*\(",
                r"it\s*\(",
                r"describe\s*\(.*,\s*function\s*\(\s*\)\s*{[\s\S]*?(?:test|it)\s*\(", # Nested tests
            ]

        count = 0
        for pattern in test_patterns:
            count += len(re.findall(pattern, content))

        # A simple `describe` might not contain tests itself, but group them.
        # This basic count might overcount `describe` if not careful with regex.
        # The current JS regex tries to ensure `test` or `it` is within `describe`.
        return count

    def _count_assertions(self, content: str, language: str) -> int:
        """Count the number of assertions in a file."""
        count = 0

        # Use a combined list of assertion patterns for the given language
        lang_assertion_patterns = []
        if language == "python":
            lang_assertion_patterns.extend(self.assertion_patterns.get("pytest", []))
            lang_assertion_patterns.extend(self.assertion_patterns.get("unittest", []))
        elif language == "javascript":
            lang_assertion_patterns.extend(self.assertion_patterns.get("jest", []))
            lang_assertion_patterns.extend(self.assertion_patterns.get("mocha", []))
            # Add generic JS assert
            lang_assertion_patterns.append(r"assert\(")


        for pattern in lang_assertion_patterns:
            count += len(re.findall(pattern, content))

        return count

    def _detect_test_type(self, content: str, test_type: TestType, language: str) -> bool:
        """Detect if a specific test type is present in the content."""
        # Ensure test_type is an enum member
        if not isinstance(test_type, TestType):
            try:
                test_type = TestType(str(test_type).lower())
            except ValueError:
                logger.warning("%s", Invalid test_type value '{test_type}' provided to _detect_test_type.)
                return False

        if test_type not in self.patterns or language not in self.patterns[test_type]:
            return False

        patterns_for_type_lang = self.patterns[test_type][language]
        for pattern in patterns_for_type_lang:
            if re.search(pattern, content, re.IGNORECASE): # Add IGNORECASE for broader matching
                return True

        return False

    def _detect_quality_issues(self, content: str) -> List[str]:
        """Detect test quality issues."""
        issues = []
        for pattern in self.quality_issue_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE) # Add IGNORECASE
            if matches:
                issues.append(f"Found {len(matches)} instance(s) of '{pattern}' indicating incomplete or skipped tests.")

        # Check for empty test functions (Python)
        # Regex to find 'def test_something(self): pass' or 'def test_something(): # optional comment then pass'
        empty_py_tests = re.findall(r"def\s+test_\w+
            \s*\([^)]*\):\s*(?:#.*?\n\s*)?pass(?!\w)", content)        if empty_py_tests:
            issues.append(f"Found {len(empty_py_tests)} empty Python test functions (ending in 'pass').")

        # Check for empty test blocks (JavaScript) - e.g., it('should do something', () => {});
        empty_js_tests = re.findall(r"(?:it|test)\s*\((?:'[^']*'|\"[^\"]*\"|`[^`]*`)\s*,\s*\(\s*\)\s*=>\s*{\s*(?:/\*.*?\*/|//.*?\n\s*)?}\s*\);?", content)
        if empty_js_tests:
            issues.append(f"Found {len(empty_js_tests)} empty JavaScript test blocks.")

        return issues

    def _determine_static_verdict(self, results: Dict[str, Any]) -> TestVerdict:
        """Determine the verdict based on test analysis results."""
        # No tests or assertions - definite fail if assertions are expected for the identified test types
        has_assertive_types = any(tt in results.get("test_types", []) for tt in [TestType.UNIT.value, TestType.INTEGRATION.value, TestType.ACCEPTANCE.value, TestType.PROPERTY_BASED.value])

        if results.get("test_count", 0) == 0 and has_assertive_types: # If assert-requiring types are detected but no tests counted
            return TestVerdict.FAIL
        if results.get("assertion_count", 0) == 0 and has_assertive_types and results.get("test_count", 0) > 0:
             results["issues"].append("No assertions found in counted tests that typically require them.") # Add to issues
             return TestVerdict.FAIL


        # Issues found - warning or fail depending on severity (currently all are treated as leading to WARN if not FAIL)
        if results.get("issues"):
            # More nuanced: if issues indicate skipped/empty tests, it's closer to FAIL
            if any("empty" in issue.lower() or "skip" in issue.lower() or "incomplete" in issue.lower() for issue in results["issues"]):
                return TestVerdict.FAIL
            return TestVerdict.WARN

        # At least one relevant test type detected and reasonable assertion ratio - pass
        if results.get("test_types") and results.get("test_count",0) > 0 and results.get("assertion_count", 0) >= results.get("test_count", 0):
            return TestVerdict.PASS

        # If tests are present but assertions are low compared to test count
        if results.get("test_count",0) > 0 and results.get("assertion_count", 0) < results.get("test_count",0) and has_assertive_types:
            results["issues"].append("Low assertion count compared to the number of tests.")
            return TestVerdict.WARN

        # Default to pass if no specific fail/warn conditions met but some tests are present
        if results.get("test_count",0) > 0:
            return TestVerdict.PASS

        return TestVerdict.FAIL # Default to FAIL if no tests counted and no other positive indicators

    def _extract_test_types_from_specs(self, test_specs: List[Dict[str, Any]]) -> List[TestType]:
        """Extract test types from test specifications in a plan."""
        test_types_found: Set[TestType] = set()

        for spec in test_specs:
            # Unit tests are most common, always assume them if we have test specs
            test_types_found.add(TestType.UNIT)

            framework = spec.get("framework", "").lower()
            scenarios = spec.get("scenarios", [])
            security_tests_spec = spec.get("security_tests", []) # Renamed to avoid conflict
            property_tests_spec = spec.get("property_tests", []) # Renamed
            approval_tests_spec = spec.get("approval_tests", []) # Renamed

            # Check for integration tests by keyword in framework or scenarios
            if "integration" in framework:
                test_types_found.add(TestType.INTEGRATION)

            for scenario in scenarios:
                function_name = scenario.get("function", "") # Renamed to avoid conflict
                if "integration" in function_name.lower(): # Check function name as well
                    test_types_found.add(TestType.INTEGRATION)

                # Look for property-based testing patterns
                cases = scenario.get("cases", [])
                for case in cases:
                    description = case.get("description", "").lower()
                    if any(kw in description for kw in ["property", "invariant", "all inputs", "every input", "generated inputs"]):
                        test_types_found.add(TestType.PROPERTY_BASED)

            # Look for approval testing patterns from approval_tests spec
            if approval_tests_spec:
                 test_types_found.add(TestType.APPROVAL)
            # Also check scenarios for keywords
            for scenario in scenarios:
                cases = scenario.get("cases", [])
                for case in cases:
                    description = case.get("description", "").lower()
                    if any(kw in description for kw in ["approval", "approved", "verify output", "snapshot"]):
                        test_types_found.add(TestType.APPROVAL) # Or TestType.ACCEPTANCE depending on context

            # Property tests directly from spec
            if property_tests_spec:
                test_types_found.add(TestType.PROPERTY_BASED)

            # Security tests often indicate formal verification elements or specific security testing
            if security_tests_spec:
                # Depending on detail, could map to TestType.FORMAL or just note security focus
                # For now, let's add a generic "security" if TestType had it, or just log.
                # Current TestType enum doesn't have a direct "SECURITY"
                logger.info("Security tests specified in plan, consider specialized analysis or mapping.")

        return sorted(list(test_types_found), key=lambda x: x.value)

    def _is_test_file(self, file_path: str, content: str) -> bool:
        """Determine if a file is a test file based on path and content."""
        file_path_lower = file_path.lower()
        # Check path patterns
        # More specific patterns first
        if re.search(r'(^|[/_\.-])test[s]?([/_\.-]|$)', file_path_lower) or \
           re.search(r'\.spec\.([tj]sx?|py)$', file_path_lower) or \
           file_path_lower.startswith('test_') or \
           file_path_lower.endswith(('_test.py', '_spec.js', '_test.js')):
            return True

        # Check content for test frameworks and patterns
        # Determine language first for more accurate pattern matching
        language = "javascript" if file_path.endswith(('.js', '.jsx', '.ts', '.tsx')) else "python"

        for test_type_enum_member in [TestType.UNIT, TestType.INTEGRATION, TestType.ACCEPTANCE]: # Common types indicating a test file
            if language in self.patterns[test_type_enum_member]:
                for pattern in self.patterns[test_type_enum_member][language]:
                    if re.search(pattern, content, re.IGNORECASE):
                        return True

        return False

    def _extract_implementable_elements(self, content: str, language: str) -> List[str]:
        """Extract functions, methods and classes that should be tested."""
        elements = []

        if language == "python":
            # Find functions (excluding private/magic methods unless explicitly for testing them)
            functions = re.findall(r"def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(", content)
            # Find classes
            classes = re.findall(r"class\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*[\(:]", content)

            elements.extend(f for f in functions if not f.startswith('_')) # Exclude private conventionally
            elements.extend(c for c in classes if not c.startswith('_'))
        else:  # javascript/typescript
            # Find functions (named and assigned to const/let/var)
            functions = re.findall(r"function\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\s*\(", content)
            arrow_funcs_assigned = re.findall(r"(?:const|let|var)\s+
                ([a-zA-Z_$][a-zA-Z0-9_$]*)\s*=\s*(?:async\s*)?\(.*\)\s*=>", content)            class_methods = re.findall(r"(?:async\s+
                                                        )?([a-zA-Z_$][a-zA-Z0-9_$]*)\s*\([^)]*\)\s*{", content) # More general, might catch non-methods
            # Find classes
            classes = re.findall(r"class\s+([a-zA-Z_$][a-zA-Z0-9_$]*)", content)

            elements.extend(f for f in functions if not f.startswith('_'))
            elements.extend(af for af in arrow_funcs_assigned if not af.startswith('_'))
            # Filtering class_methods needs more context to avoid non-method functions
            # For now, include them if they don't look like standard keywords
            js_keywords = {"if", "for", "while", "switch", "catch", "function"}
            elements.extend(m for m in class_methods if not m.startswith('_') and m not in js_keywords)
            elements.extend(c for c in classes if not c.startswith('_'))

        return list(set(elements)) # Unique elements

    def perform_llm_analysis(self, content: str, prompt: str = None) -> Dict[str, Any]:
        """
        Perform a lightweight LLM analysis of test quality.

        Args:
            content: Test file content
            prompt: Optional custom prompt

        Returns:
            Analysis results
        """
        if not self.llm:
            logger.warning("LLM client not available in TestCritic for perform_llm_analysis.")
            return {"error": "No LLM available for analysis"}

        # Default prompt for test analysis
        if not prompt:
            prompt = """
            You are a test quality critic evaluating the following test code.
            Focus ONLY on these aspects:
            1. Are there proper assertions present for most test cases?
            2. Is there an attempt to cover both happy path and edge/error cases?
            3. Do the tests appear to isolate dependencies (e.g., using mocks if applicable)?
            4. Are there any obvious gaps where critical functionality seems untested by this code?

            Provide your assessment in JSON format:
            {
              "has_assertions": true/false, // true if assertions are generally present
              "covers_edge_cases": true/false/partial, // true if edge cases seem covered, false if not, partial if some attempt
              "isolates_dependencies": true/false/na, // na if not applicable
              "obvious_gaps": ["description of gap 1 (if any)", "description of gap 2 (if any)"],
              "overall_quality_impression": "high"/"medium"/"low", // based on the above
              "suggestions_for_improvement": ["suggestion 1", "suggestion 2"]
            }

            Test code:
            ```
            """ + content + "\n```"

        # Use coordinator's LLM to analyze
        try:
            # Assuming self.coordinator.llm.generate exists and works like a typical LLM call
            # The actual call might be self.coordinator.llm.call_llm_by_role or similar
            # For this example, let's assume a simple .generate method
            if hasattr(self.coordinator, 'router_agent') and hasattr(self.coordinator.router_agent, 'call_llm_by_role'):
                 # Using a generic role or a specific one if defined for test analysis
                response = self.coordinator.router_agent.call_llm_by_role(
                    role='test_analyzer', # Assuming such a role is configured or a default one is used
                    system_prompt="You are a test quality critic.", # Part of the prompt is now system
                    user_prompt=f"Analyze the following test code focusing on assertions, edge cases, dependency isolation, and gaps. Test code:\n```\n{content}\n```\nRespond ONLY in the specified JSON format.",
                    config={"response_format": {"type": "json_object"}}, # Enforce JSON output if API supports
                    scratchpad=getattr(self.coordinator, 'scratchpad', None)
                )
            elif hasattr(self.coordinator.llm, 'generate'): # Fallback to a simple generate
                 response = self.coordinator.llm.generate(prompt)
            else:
                logger.error("LLM client in TestCritic does not have a recognized method for generation.")
                return {"error": "LLM client misconfigured."}


            # Try to extract JSON from response
            # Look for JSON block
            json_match = re.search(r'```json\n(.*?)\n```', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # Try to find JSON object with braces if no markdown block
                json_match_direct = re.search(r'^\s*(\{[\s\S]*\})\s*$', response, re.DOTALL)
                if json_match_direct:
                    json_str = json_match_direct.group(1)
                else: # Assume the whole response is JSON if no specific markers
                    json_str = response

            try:
                analysis = json.loads(json_str)
                return analysis
            except json.JSONDecodeError as e:
                logger.exception(
                    "Could not parse LLM response as JSON for test analysis. Error: %s. Response: %s",
                    e,
                    response,
                )
                return {"error": "Could not parse LLM response as JSON", "raw_response": response}

        except Exception as e:
            logger.exception("Error during LLM test analysis")
            return {"error": f"Error during LLM analysis: {str(e)}"}


