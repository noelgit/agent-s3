#!/usr/bin/env python3
import unittest
from agent_s3.pre_planning_errors import (
    AgentS3BaseError, PrePlanningError, ValidationError,
    SchemaError, RepairError, ComplexityError, handle_pre_planning_errors
)

class TestPrePlanningErrors(unittest.TestCase):
    
    def test_error_inheritance(self):
        """Test the inheritance hierarchy of error classes."""
        self.assertTrue(issubclass(PrePlanningError, AgentS3BaseError))
        self.assertTrue(issubclass(ValidationError, PrePlanningError))
        self.assertTrue(issubclass(SchemaError, PrePlanningError))
        self.assertTrue(issubclass(RepairError, PrePlanningError))
        self.assertTrue(issubclass(ComplexityError, PrePlanningError))
    
    def test_error_to_dict(self):
        """Test the to_dict method of error classes."""
        # Create a validation error
        validation_error = ValidationError(
            message="Validation failed", 
            errors=["Error 1", "Error 2"]
        )
        
        # Convert to dictionary
        error_dict = validation_error.to_dict()
        
        # Check dictionary structure
        self.assertEqual(error_dict["error"], "ValidationError")
        self.assertEqual(error_dict["message"], "Validation failed")
        self.assertIn("details", error_dict)
        self.assertIn("errors", error_dict["details"])
        self.assertEqual(len(error_dict["details"]["errors"]), 2)
    
    def test_error_decorator(self):
        """Test the error handling decorator."""
        
        # Define a function with the decorator
        @handle_pre_planning_errors
        def function_with_validation_error():
            raise ValidationError("Validation failed", ["Error 1"])
        
        @handle_pre_planning_errors
        def function_with_schema_error():
            raise SchemaError("Schema validation failed", ["Schema error"])
        
        @handle_pre_planning_errors
        def function_with_repair_error():
            raise RepairError("Repair failed", ["Cannot repair"])
        
        @handle_pre_planning_errors
        def function_with_complexity_error():
            raise ComplexityError("Too complex", 85.0, {"factor1": 10.0, "factor2": 75.0})
        
        @handle_pre_planning_errors
        def function_with_unexpected_error():
            raise ValueError("Unexpected error")
        
        # Test the decorated functions
        result = function_with_validation_error()
        self.assertFalse(result["success"])
        self.assertEqual(result["error_type"], "validation")
        
        result = function_with_schema_error()
        self.assertFalse(result["success"])
        self.assertEqual(result["error_type"], "schema")
        
        result = function_with_repair_error()
        self.assertFalse(result["success"])
        self.assertEqual(result["error_type"], "repair")
        
        result = function_with_complexity_error()
        self.assertFalse(result["success"])
        self.assertEqual(result["error_type"], "complexity")
        self.assertIn("complexity_score", result["details"])
        
        result = function_with_unexpected_error()
        self.assertFalse(result["success"])
        self.assertEqual(result["error_type"], "unexpected")

if __name__ == '__main__':
    unittest.main()
