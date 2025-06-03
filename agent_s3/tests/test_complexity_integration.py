#!/usr/bin/env python3
from agent_s3.complexity_analyzer import ComplexityAnalyzer
from agent_s3.errors import PrePlanningError as ComplexityError
import pytest

# Create a complexity analyzer
analyzer = ComplexityAnalyzer()

# Create a function that uses the analyzer and raises ComplexityError when needed
def assess_complexity_with_threshold(data, task_description, threshold=60):
    """Assess complexity and raise an error if it exceeds the threshold."""
    result = analyzer.assess_complexity(data, task_description)

    if result["complexity_score"] > threshold:
        raise ComplexityError(
            message=(
                f"Task complexity exceeds threshold ({result['complexity_score']:.1f} > {threshold})"
            ),
            complexity_score=result["complexity_score"],
            complexity_factors=result["complexity_factors"]
        )

    return {"success": True, "complexity": result}

def test_assess_complexity_with_threshold():
    complex_task = {
        "feature_groups": [
            {
                "group_name": "Security Features",
                "group_description": "Authentication and authorization features",
                "features": [
                    {
                        "name": "OAuth Implementation",
                        "description": "Implement secure authentication with OAuth2 and JWT",
                        "complexity": 5,
                        "implementation_steps": [
                            {"file_path": "auth/oauth.js"},
                            {"file_path": "auth/jwt.js"},
                            {"file_path": "middleware/auth.js"},
                            {"file_path": "models/user.js"},
                            {"file_path": "routes/auth.js"}
                        ]
                    }
                ]
            }
        ]
    }
    task_description = "Implement secure authentication system with OAuth2"
    with pytest.raises(ComplexityError) as exc_info:
        assess_complexity_with_threshold(complex_task, task_description, threshold=40)
    assert "Task complexity exceeds threshold" in str(exc_info.value)
