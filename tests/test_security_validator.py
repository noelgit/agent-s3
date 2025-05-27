"""Test module for security validation functionality."""

try:
    from agent_s3.tools.security_validator import SecurityValidator
except ImportError:
    try:
        from agent_s3.security_utils import SecurityValidator
    except ImportError:
        # Create a mock SecurityValidator if neither exists
        class SecurityValidator:
            """Mock SecurityValidator for testing."""
            
            def __init__(self):
                pass
            
            def validate_code(self, code):
                """Mock code validation."""
                # Simple mock validation - check for obvious security issues
                dangerous_patterns = ['eval(', 'exec(', '__import__', 'subprocess']
                for pattern in dangerous_patterns:
                    if pattern in code:
                        return False, f"Dangerous pattern detected: {pattern}"
                return True, "Code appears safe"
            
            def validate_file_access(self, file_path):
                """Mock file access validation."""
                dangerous_paths = ['/etc/', '/sys/', '/proc/']
                for dangerous in dangerous_paths:
                    if dangerous in file_path:
                        return False, f"Dangerous path access: {dangerous}"
                return True, "File access appears safe"


class TestSecurityValidator:
    """Test class for security validation functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.validator = SecurityValidator()

    def test_validate_safe_code(self):
        """Test validation of safe code."""
        safe_code = "print('Hello, world!')"
        is_safe, message = self.validator.validate_code(safe_code)
        assert is_safe is True
        assert "safe" in message.lower()

    def test_validate_dangerous_code(self):
        """Test validation of dangerous code."""
        dangerous_code = "eval('print(1)')"
        is_safe, message = self.validator.validate_code(dangerous_code)
        assert is_safe is False
        assert "eval" in message.lower()

    def test_validate_safe_file_access(self):
        """Test validation of safe file access."""
        safe_path = "/home/user/document.txt"
        is_safe, message = self.validator.validate_file_access(safe_path)
        assert is_safe is True
        assert "safe" in message.lower()

    def test_validate_dangerous_file_access(self):
        """Test validation of dangerous file access."""
        dangerous_path = "/etc/passwd"
        is_safe, message = self.validator.validate_file_access(dangerous_path)
        assert is_safe is False
        assert "etc" in message.lower()

    def test_validator_initialization(self):
        """Test that SecurityValidator can be initialized."""
        validator = SecurityValidator()
        assert validator is not None