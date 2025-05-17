import unittest
from unittest.mock import MagicMock, patch
import json
import os
import sys
from pathlib import Path

from agent_s3.tools.static_analyzer import StaticAnalyzer
from agent_s3.tools.phase_validator import validate_architecture_implementation

class TestArchitecturalValidation(unittest.TestCase):
    """Test suite for architectural validation functions."""

    def setUp(self):
        """Set up the test environment."""
        self.static_analyzer = StaticAnalyzer()
        
        # Sample architecture review
        self.architecture = {
            "logical_gaps": [
                {
                    "description": "Error handling is missing for API failures",
                    "impact": "High - application may crash on network errors",
                    "recommendation": "Add try/catch blocks around API calls",
                    "affected_components": ["src/services/api.js", "src/components/DataFetcher.js"]
                },
                {
                    "description": "No caching strategy for repeated API calls",
                    "impact": "Medium - performance degradation with repeated requests",
                    "recommendation": "Implement a caching layer",
                    "affected_components": ["src/services/api.js"]
                }
            ],
            "optimization_suggestions": [
                {
                    "description": "Implementation uses inefficient data structure",
                    "benefit": "Improved memory usage and performance",
                    "implementation_approach": "Replace arrays with Map objects for O(1) lookups",
                    "affected_components": ["src/utils/dataProcessor.js"]
                }
            ],
            "additional_considerations": [
                "Security: API keys should be stored securely",
                "Performance: Consider pagination for large datasets"
            ]
        }
        
        # Implementation that addresses the concerns
        self.complete_implementation = {
            "src/services/api.js": [
                {
                    "function": "async function fetchData(url, options = {})",
                    "description": "Fetch data from API with error handling and caching",
                    "steps": [
                        "Check if response is in cache",
                        "If cached and not expired, return cached data",
                        "Try to fetch data with fetch API",
                        "Handle network errors with try/catch",
                        "Cache successful responses",
                        "Return data or throw error"
                    ],
                    "edge_cases": [
                        "Network errors",
                        "Invalid responses",
                        "Cache expiration"
                    ]
                }
            ],
            "src/components/DataFetcher.js": [
                {
                    "function": "function DataFetcher({ url })",
                    "description": "React component to fetch and display data",
                    "steps": [
                        "Use useState for loading, error, and data states",
                        "Use useEffect to fetch data",
                        "Handle loading state",
                        "Handle errors with try/catch",
                        "Render data when available"
                    ],
                    "edge_cases": [
                        "Component unmount during fetch",
                        "Error display and retry"
                    ]
                }
            ],
            "src/utils/dataProcessor.js": [
                {
                    "function": "function processData(items)",
                    "description": "Process data items using Map for efficiency",
                    "steps": [
                        "Create a Map for O(1) lookups",
                        "Process items efficiently",
                        "Return processed data"
                    ],
                    "edge_cases": [
                        "Empty data",
                        "Duplicate keys"
                    ]
                }
            ]
        }
        
        # Implementation missing components
        self.incomplete_implementation = {
            "src/services/api.js": [
                {
                    "function": "async function fetchData(url, options = {})",
                    "description": "Fetch data from API",
                    "steps": [
                        "Call fetch API",
                        "Return data"
                    ],
                    "edge_cases": []
                }
            ]
        }
        
        # Implementation with unaddressed concerns
        self.unaddressed_implementation = {
            "src/services/api.js": [
                {
                    "function": "async function fetchData(url, options = {})",
                    "description": "Fetch data from API",
                    "steps": [
                        "Call fetch API",
                        "Parse JSON response",
                        "Return data"
                    ],
                    "edge_cases": []
                }
            ],
            "src/components/DataFetcher.js": [
                {
                    "function": "function DataFetcher({ url })",
                    "description": "React component to fetch and display data",
                    "steps": [
                        "Use useState for data state",
                        "Use useEffect to fetch data",
                        "Render data when available"
                    ],
                    "edge_cases": []
                }
            ],
            "src/utils/dataProcessor.js": [
                {
                    "function": "function processData(items)",
                    "description": "Process data items using arrays",
                    "steps": [
                        "Create array for storage",
                        "Loop through items (O(n) lookups)",
                        "Return processed data"
                    ],
                    "edge_cases": []
                }
            ]
        }

    def test_direct_validation(self):
        """Test validation with direct calls to the phase validator."""
        # Test with complete implementation
        is_valid, message, details = validate_architecture_implementation(
            self.architecture,
            self.complete_implementation
        )
        self.assertTrue(is_valid)
        self.assertEqual(len(details.get("unaddressed_gaps", [])), 0)
        self.assertEqual(len(details.get("unaddressed_optimizations", [])), 0)
        
        # Test with incomplete implementation (missing components)
        is_valid, message, details = validate_architecture_implementation(
            self.architecture,
            self.incomplete_implementation
        )
        self.assertFalse(is_valid)
        self.assertTrue("DataFetcher.js" in message or "dataProcessor.js" in message)
        
        # Test with implementation that doesn't address concerns
        is_valid, message, details = validate_architecture_implementation(
            self.architecture,
            self.unaddressed_implementation
        )
        self.assertFalse(is_valid)
        self.assertTrue(
            any("Error handling" in gap.get("description", "") 
                for gap in details.get("unaddressed_gaps", []))
        )

    def test_static_analyzer_integration(self):
        """Test integration with the static analyzer."""
        # Test with complete implementation
        is_valid, message, details = self.static_analyzer.validate_architecture_implementation(
            self.architecture,
            self.complete_implementation
        )
        self.assertTrue(is_valid)
        
        # Test with incomplete implementation
        is_valid, message, details = self.static_analyzer.validate_architecture_implementation(
            self.architecture,
            self.incomplete_implementation
        )
        self.assertFalse(is_valid)
        
        # Test with implementation that doesn't address concerns
        is_valid, message, details = self.static_analyzer.validate_architecture_implementation(
            self.architecture,
            self.unaddressed_implementation
        )
        self.assertFalse(is_valid)

    def test_component_matching(self):
        """Test component matching logic."""
        # Test with partial component naming
        partial_arch = {
            "logical_gaps": [
                {
                    "description": "Missing validation",
                    "affected_components": ["userService"]
                }
            ],
            "optimization_suggestions": [],
            "additional_considerations": []
        }
        
        partial_impl = {
            "src/services/userService.js": [
                {
                    "function": "validateUser",
                    "steps": ["Validate user data"]
                }
            ]
        }
        
        is_valid, message, details = validate_architecture_implementation(
            partial_arch,
            partial_impl
        )
        self.assertTrue(is_valid)
        
        # Test with non-matching components
        non_matching_arch = {
            "logical_gaps": [
                {
                    "description": "Missing validation",
                    "affected_components": ["authService"]
                }
            ],
            "optimization_suggestions": [],
            "additional_considerations": []
        }
        
        is_valid, message, details = validate_architecture_implementation(
            non_matching_arch,
            partial_impl
        )
        self.assertFalse(is_valid)

    def test_complex_architecture(self):
        """Test with a complex architecture with many components."""
        complex_arch = {
            "logical_gaps": [
                {
                    "description": "Gap 1",
                    "affected_components": ["component1", "component2", "component3"]
                },
                {
                    "description": "Gap 2",
                    "affected_components": ["component4", "component5"]
                }
            ],
            "optimization_suggestions": [
                {
                    "description": "Optimization 1",
                    "affected_components": ["component6", "component7"]
                }
            ],
            "additional_considerations": []
        }
        
        complex_impl = {
            "component1": [{"function": "f1", "steps": ["Handle Gap 1"]}],
            "component2": [{"function": "f2", "steps": ["Handle Gap 1"]}],
            "component3": [{"function": "f3", "steps": ["Handle Gap 1"]}],
            "component4": [{"function": "f4", "steps": ["Handle Gap 2"]}],
            "component5": [{"function": "f5", "steps": ["Handle Gap 2"]}],
            "component6": [{"function": "f6", "steps": ["Apply Optimization 1"]}],
            "component7": [{"function": "f7", "steps": ["Apply Optimization 1"]}]
        }
        
        is_valid, message, details = validate_architecture_implementation(
            complex_arch,
            complex_impl
        )
        self.assertTrue(is_valid)
        
        # Test with incomplete complex implementation
        incomplete_complex_impl = {
            "component1": [{"function": "f1", "steps": ["Handle Gap 1"]}],
            "component3": [{"function": "f3", "steps": ["Handle Gap 1"]}],
            "component5": [{"function": "f5", "steps": ["Handle Gap 2"]}],
            "component7": [{"function": "f7", "steps": ["Apply Optimization 1"]}]
        }
        
        is_valid, message, details = validate_architecture_implementation(
            complex_arch,
            incomplete_complex_impl
        )
        self.assertTrue(is_valid, "Should still be valid if at least one component addresses each concern")

if __name__ == "__main__":
    unittest.main()
