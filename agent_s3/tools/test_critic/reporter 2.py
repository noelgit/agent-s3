"""
Test critic reporter for agent-s3.

This module handles reporting test critic results to files, including JSON and JUnit XML formats.
"""

import json
import logging
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

class Reporter:
    """Reporter for test critic results."""
    
    def __init__(self, workspace: Path):
        """
        Initialize the reporter.
        
        Args:
            workspace: Path to the workspace directory
        """
        self.workspace = workspace
        
    def write(self, results: Dict[str, Any]) -> None:
        """
        Write test critic results to files.
        
        Args:
            results: Dictionary containing test critic results
        """
        try:
            # Write JSON results
            self._write_json(results)
            
            # Write JUnit XML results
            self._write_junit_xml(results)
            
            logger.info("Test critic reports written successfully")
        except Exception as e:
            logger.error(f"Error writing test critic reports: {str(e)}")
    
    def _write_json(self, results: Dict[str, Any]) -> None:
        """
        Write test critic results to a JSON file.
        
        Args:
            results: Dictionary containing test critic results
        """
        output_path = self.workspace / "critic.json"
        
        # Add timestamp and format values
        output_data = {
            "timestamp": datetime.now().isoformat(),
            "collect_errors": results.get("collect_errors", []),
            "smoke_passed": results.get("smoke_passed", False),
            "coverage_percent": float(results.get("coverage_percent", 0) or 0),
            "mutation_score": float(results.get("mutation_score", 0) or 0),
        }
        
        # Write to file
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2)
        
        logger.info(f"Test critic JSON report written to {output_path}")
    
    def _write_junit_xml(self, results: Dict[str, Any]) -> None:
        """
        Write test critic results to a JUnit XML file.
        
        This format is recognized by CI systems like GitHub Actions and GitLab CI,
        allowing test results to be displayed in the CI interface.
        
        Args:
            results: Dictionary containing test critic results
        """
        output_path = self.workspace / "junit.xml"
        
        # Create XML structure
        testsuite = ET.Element("testsuite")
        testsuite.set("name", "TestCritic")
        testsuite.set("timestamp", datetime.now().isoformat())
        
        # Add test cases
        
        # Collect errors test case
        collect_case = ET.SubElement(testsuite, "testcase")
        collect_case.set("name", "test_collection")
        collect_case.set("classname", "TestCritic")
        
        collect_errors = results.get("collect_errors", [])
        if collect_errors:
            failure = ET.SubElement(collect_case, "failure")
            failure.set("message", "Test collection errors")
            failure.set("type", "TestCollectionError")
            failure.text = "\n".join(collect_errors)
        
        # Smoke test case
        smoke_case = ET.SubElement(testsuite, "testcase")
        smoke_case.set("name", "smoke_tests")
        smoke_case.set("classname", "TestCritic")
        
        if not results.get("smoke_passed", False):
            failure = ET.SubElement(smoke_case, "failure")
            failure.set("message", "Smoke tests failed")
            failure.set("type", "SmokeTestFailure")
        
        # Coverage test case
        coverage_case = ET.SubElement(testsuite, "testcase")
        coverage_case.set("name", "code_coverage")
        coverage_case.set("classname", "TestCritic")
        
        coverage = results.get("coverage_percent", 0)
        if coverage is None:
            skipped = ET.SubElement(coverage_case, "skipped")
            skipped.set("message", "Coverage analysis not available")
        elif coverage < 80:  # Default threshold
            failure = ET.SubElement(coverage_case, "failure")
            failure.set("message", f"Coverage {coverage}% below threshold 80%")
            failure.set("type", "CoverageThresholdFailure")
        
        # Mutation test case
        mutation_case = ET.SubElement(testsuite, "testcase")
        mutation_case.set("name", "mutation_testing")
        mutation_case.set("classname", "TestCritic")
        
        mutation = results.get("mutation_score", 0)
        if mutation is None:
            skipped = ET.SubElement(mutation_case, "skipped")
            skipped.set("message", "Mutation testing not available")
        elif mutation < 60:  # Default threshold
            failure = ET.SubElement(mutation_case, "failure")
            failure.set("message", f"Mutation score {mutation}% below threshold 60%")
            failure.set("type", "MutationThresholdFailure")
        
        # Create XML tree and write to file
        tree = ET.ElementTree(testsuite)
        tree.write(output_path, encoding='utf-8', xml_declaration=True)
        
        logger.info(f"Test critic JUnit XML report written to {output_path}")
