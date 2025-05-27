#!/usr/bin/env python3
from agent_s3.errors import PrePlanningError as ValidationError
from agent_s3.errors import ErrorContext
from agent_s3.pre_planner_json_validator import PrePlannerJsonValidator as PrePlanningValidator

# Create a simple validator
validator = PrePlanningValidator()

# Wrap the validation method with our error handler
def validate_and_handle_errors(data):
    is_valid, errors = validator.validate_structure(data)
    if not is_valid:
        raise ValidationError("Pre-planning data validation failed", errors)
    return {"success": True, "message": "Validation passed"}

# Test with invalid data
invalid_data = {"missing_feature_groups": []}
result = validate_and_handle_errors(invalid_data)

# Print results
print("Error handling result:")
print(f"Success: {result['success']}")
print(f"Error Type: {result.get('error_type')}")
print(f"Message: {result['message']}")
print(f"Details: {result.get('details')}")
