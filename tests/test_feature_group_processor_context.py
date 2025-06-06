import pytest
from unittest.mock import MagicMock
from pathlib import Path

from agent_s3.feature_group_processor import FeatureGroupProcessor


def test_gather_context_reads_files_based_on_success(tmp_path):
    file_ok = tmp_path / "ok.txt"
    file_ok.write_text("data")

    feature_group = {
        "group_name": "g1",
        "features": [
            {"description": "a", "files_affected": [str(file_ok)]},
            {"description": "b", "files_affected": ["missing.txt"]},
        ],
    }

    coordinator = MagicMock()
    coordinator.scratchpad = MagicMock()
    coordinator.context_registry = True
    coordinator.get_current_context_snapshot.return_value = {}
    coordinator.file_tool = MagicMock()
    coordinator.file_tool.read_file.side_effect = [(True, "data"), (False, "error")]

    processor = FeatureGroupProcessor(coordinator)
    ctx = processor._gather_context_for_feature_group(feature_group)

    assert ctx["file_contents"] == {str(file_ok): "data"}

