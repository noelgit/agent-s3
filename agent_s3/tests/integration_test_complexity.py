#!/usr/bin/env python3
"""Integration test for the ComplexityAnalyzer module."""

import json
import sys
from agent_s3.complexity_analyzer import ComplexityAnalyzer

def main():
    """Test the complexity analyzer with some realistic data."""
    # Test data representing a feature request
    test_data = {
        "feature_groups": [
            {
                "group_name": "API Integration",
                "group_description": "External API integration features",
                "features": [
                    {
                        "name": "Authentication Integration",
                        "description": "Implement OAuth2 authentication with JWT token validation for secure API access",
                        "complexity": 5,
                        "implementation_steps": [
                            {"description": "Create Auth service", "file_path": "src/services/auth.js"},
                            {"description": "Implement token management", "file_path": "src/services/token.js"},
                            {"description": "Add authentication middleware", "file_path": "src/middleware/auth.js"},
                            {"description": "Create login form", "file_path": "src/components/LoginForm.js"},
                            {"description": "Add protected routes", "file_path": "src/routes/index.js"}
                        ],
                        "risk_assessment": {
                            "risk_level": "high",
                            "concerns": ["Security vulnerabilities", "Token management"]
                        }
                    },
                    {
                        "name": "Data Synchronization",
                        "description": "Implement data synchronization with external API",
                        "complexity": 3,
                        "implementation_steps": [
                            {"description": "Create sync service", "file_path": "src/services/sync.js"},
                            {"description": "Implement data mapping", "file_path": "src/utils/dataMapper.js"},
                            {"description": "Add error handling", "file_path": "src/services/errorHandler.js"}
                        ]
                    }
                ]
            },
            {
                "group_name": "UI Components",
                "group_description": "User interface components",
                "features": [
                    {
                        "name": "Dashboard Updates",
                        "description": "Update dashboard with new charts and filters",
                        "complexity": 2,
                        "implementation_steps": [
                            {"description": "Update chart component", "file_path": "src/components/Chart.js"},
                            {"description": "Add filter components", "file_path": "src/components/Filters.js"}
                        ]
                    }
                ]
            }
        ]
    }
    
    # Initialize the analyzer
    analyzer = ComplexityAnalyzer()
    
    # Run the complexity assessment
    task_description = "Implement secure API integration with OAuth2 and update the dashboard UI"
    result = analyzer.assess_complexity(test_data, task_description)
    
    # Print the results
    print("===== Complexity Assessment Results =====")
    print(f"Overall Complexity Score: {result['score']:.1f}/100")
    print(f"Complexity Level: {result['level']}/5")
    print(f"Is Complex Task: {result['is_complex']}")
    print("\nContributing Factors:")
    for factor, score in result['factors'].items():
        print(f"  - {factor}: {score:.1f}")
    
    print("\nJustification:")
    for reason in result['justification']:
        print(f"  - {reason}")
    
    print("\nAdvice:")
    print(result['advice'])
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
