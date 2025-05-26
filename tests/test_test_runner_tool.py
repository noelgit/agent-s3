# tests/test_test_runner_tool.py
"""Unit tests for TestRunnerTool._parse_test_failures."""
import unittest
from agent_s3.tools.test_runner_tool import TestRunnerTool


class DummyBashTool:
    def run_command(self, cmd: str, timeout: int = 300):
        return 0, ""


class TestParseTestFailures(unittest.TestCase):
    def setUp(self):
        self.tool = TestRunnerTool(DummyBashTool())

    def test_parse_pytest_failure(self):
        output = (
            "\n============================= test session starts =============================\n"
            "collected 1 item\n\n"
            "tests/test_math.py::test_addition FAILED                                   [100%]\n\n"
            "=================================== FAILURES ===================================\n"
            "_____________________________ tests/test_math.py::test_addition _____________________________\n"
            "tests/test_math.py:10: in test_addition\n    assert 1 == 2\n"
            "E   assert 1 == 2\n\n"
            "=========================== short test summary info ============================\n"
            "FAILED tests/test_math.py::test_addition - assert 1 == 2\n"
        )
        failures = self.tool._parse_test_failures(output)
        self.assertEqual(len(failures), 1)
        failure = failures[0]
        self.assertEqual(failure.get("test_name"), "test_addition")
        self.assertEqual(failure.get("test_file"), "tests/test_math.py")
        self.assertEqual(failure.get("line_number"), 10)
        self.assertIn("failure_category", failure)
        self.assertIn("possible_bad_test", failure)
        self.assertEqual(failure.get("expected"), "2")
        self.assertEqual(failure.get("actual"), "1")

    def test_parse_unittest_failure(self):
        output = (
            "FAIL: test_add (tests.test_math.TestMath)\n"
            "Traceback (most recent call last):\n"
            "  File \"/repo/tests/test_math.py\", line 15, in test_add\n"
            "    self.assertEqual(add(1, 2), 4)\n"
            "AssertionError: Expected 4, got 3\n\n"
        )
        failures = self.tool._parse_test_failures(output)
        self.assertEqual(len(failures), 1)
        failure = failures[0]
        self.assertEqual(failure.get("test_name"), "test_add")
        self.assertEqual(failure.get("test_class"), "tests.test_math.TestMath")
        self.assertEqual(failure.get("test_file"), "test_math.py")
        self.assertEqual(failure.get("line_number"), 15)
        self.assertIn("failure_category", failure)
        self.assertIn("possible_bad_test", failure)
        self.assertEqual(failure.get("expected"), "4")
        self.assertEqual(failure.get("actual"), "3")


if __name__ == "__main__":
    unittest.main()
