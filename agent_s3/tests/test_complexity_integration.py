#!/usr/bin/env python3
from agent_s3.complexity_analyzer import ComplexityAnalyzer
from agent_s3.pre_planning_errors import ComplexityError
from agent_s3.pre_planning_errors import handle_pre_planning_errors

# Create a complexity analyzer
analyzer = ComplexityAnalyzer()

# Create a function that uses the analyzer and raises ComplexityError when needed
@handle_pre_planning_errors
def assess_complexity_with_threshold(data, task_description, threshold=60):
    """Assess complexity and raise an error if it exceeds the threshold."""
    result = analyzer.assess_complexity(data, task_description)

    if result["score"] > threshold:
        raise ComplexityError(
            message=f"Task complexity exceeds threshold ({result['score']:.1f} > {threshold})",
            complexity_score=result["score"],
            complexity_factors=result["factors"]
        )

    return {"success": True, "complexity": result}

# Test data
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

# Run with a low threshold to trigger the complexity error
task_description = "Implement secure authentication system with OAuth2"
result = assess_complexity_with_threshold(complex_task, task_description, threshold=40)

# Print results
print("Complexity error handling result:")
print(f"Success: {result['success']}")
print(f"Error Type: {result.get('error_type')}")
print(f"Message: {result['message']}")
print(f"Complexity Score: {result['details'].get('complexity_score', 'N/A')}")
print(f"Complexity Factors: {result['details'].get('complexity_factors', 'N/A')}")
