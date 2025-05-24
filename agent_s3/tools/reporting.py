"""Reporting utilities for agent-s3.

Provides functions for generating reports in various formats, such as JUnit XML.
"""

import logging
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Dict, Any

logger = logging.getLogger(__name__)

def generate_junit_report(
    test_name: str, validation_results: Dict[str, Any],
    original_request: str = ""
) -> str:
    """Generate a JUnit XML report for validation results.

    This function creates a JUnit XML report from validation results,
    which can be used for CI integration and validation tracking.

    Args:
        test_name: Name of the test suite/validation set
        validation_results: Dictionary containing validation results including "critical" and "warnings" lists
        original_request: The original request text for context

    Returns:
        JUnit XML report as a string
    """
    # Create root testsuite element
    testsuite = ET.Element("testsuite")
    testsuite.set("name", f"Validation: {test_name}")
    testsuite.set("timestamp", datetime.now().isoformat())
    testsuite.set(
        "tests",
        str(
            len(validation_results.get("critical", []))
            + len(validation_results.get("warnings", []))
        ),
    )
    testsuite.set(
        "failures",
        str(len(validation_results.get("critical", []))),
    )
    testsuite.set("errors", "0")

    # Add properties element with request context
    if original_request:
        properties = ET.SubElement(testsuite, "properties")
        prop = ET.SubElement(properties, "property")
        prop.set("name", "original_request")
        prop.set("value", original_request[:1000])  # Limit context size

    # Add testcase for each critical error
    for i, error in enumerate(validation_results.get("critical", [])):
        testcase = ET.SubElement(testsuite, "testcase")
        testcase.set("name", f"critical_validation_{i+1}")
        testcase.set("classname", f"Validation.{test_name}.Critical")

        # Add failure element
        failure = ET.SubElement(testcase, "failure")
        if isinstance(error, dict):
            message = error.get("message", str(error))
            failure.set("message", message)
            if "affected_components" in error:
                affected = ", ".join(error["affected_components"])
                failure.set("affected", affected)
            if "recommendation" in error:
                failure.text = error["recommendation"]
        else:
            failure.set("message", str(error))

        failure.set("type", "ValidationFailure")

    # Add testcase for each warning
    for i, warning in enumerate(validation_results.get("warnings", [])):
        testcase = ET.SubElement(testsuite, "testcase")
        testcase.set("name", f"warning_validation_{i+1}")
        testcase.set("classname", f"Validation.{test_name}.Warning")

        # Add warning as a failure with lower severity
        if isinstance(warning, dict):
            message = warning.get("message", str(warning))
            if warning.get("severity") == "minor":
                # For minor warnings, add as skipped to distinguish from critical failures
                skipped = ET.SubElement(testcase, "skipped")
                skipped.set("message", message)
            else:
                # For major warnings, add as failures
                failure = ET.SubElement(testcase, "failure")
                failure.set("message", message)
                failure.set("type", "ValidationWarning")
                if "affected_components" in warning:
                    affected = ", ".join(warning["affected_components"])
                    failure.set("affected", affected)
                if "recommendation" in warning:
                    failure.text = warning["recommendation"]
        else:
            # Simple string warnings
            skipped = ET.SubElement(testcase, "skipped")
            skipped.set("message", str(warning))

    # Add a passing testcase if there are no errors or warnings
    if not validation_results.get("critical") and not validation_results.get("warnings"):
        testcase = ET.SubElement(testsuite, "testcase")
        testcase.set("name", "validation_passed")
        testcase.set("classname", f"Validation.{test_name}")

    # Convert the XML tree to a string
    from xml.dom import minidom
    xml_string = minidom.parseString(ET.tostring(testsuite, encoding='utf-8')).toprettyxml(indent="  ")

    return xml_string
