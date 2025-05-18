from agent_s3.tools import preemptive_planning_detector as ppd
from unittest.mock import patch


VALID_PLAN = {
    "original_request": "Test",
    "feature_groups": [
        {
            "group_name": "G1",
            "features": [
                {"name": "A", "description": "x"},
            ],
        }
    ],
}


def test_detect_preemptive_errors_returns_validator_errors(monkeypatch):
    with patch("agent_s3.tools.preemptive_planning_detector.validate_pre_plan") as mval:
        mval.return_value = (
            False,
            {"critical": [{"message": "bad path"}]},
        )
        errors = ppd.detect_preemptive_errors(VALID_PLAN)
        assert "bad path" in errors


def test_detect_duplicate_feature_names(monkeypatch):
    plan = {
        "original_request": "Test",
        "feature_groups": [
            {
                "group_name": "G1",
                "features": [
                    {"name": "A"},
                    {"name": "A"},
                ],
            }
        ],
    }
    with patch("agent_s3.tools.preemptive_planning_detector.validate_pre_plan", return_value=(True, {})):
        errors = ppd.detect_preemptive_errors(plan)
        assert any("Duplicate feature name" in e for e in errors)
