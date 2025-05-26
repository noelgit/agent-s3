import json
from pathlib import Path
from unittest.mock import MagicMock

from agent_s3.tools.test_runner_tool import TestRunnerTool


def test_parse_coverage_report(tmp_path):
    coverage_data = {"totals": {"percent_covered": 92.5}}
    coverage_file = tmp_path / ".coverage.json"
    coverage_file.write_text(json.dumps(coverage_data))
    tool = TestRunnerTool(MagicMock())
    old_cwd = Path.cwd()
    try:
        import os
        os.chdir(tmp_path)
        assert tool.parse_coverage_report() == 92.5
    finally:
        os.chdir(old_cwd)


def test_parse_coverage_report_missing(tmp_path):
    tool = TestRunnerTool(MagicMock())
    old_cwd = Path.cwd()
    try:
        import os
        os.chdir(tmp_path)
        assert tool.parse_coverage_report() == 0.0
    finally:
        os.chdir(old_cwd)
