import json

import pytest

from agent_s3.config import Config
from agent_s3.config import ConfigModel

def test_load_defaults(tmp_path, monkeypatch):
    # Ensure no external config files
    monkeypatch.chdir(tmp_path)
    cfg = Config()
    cfg.load()
    assert isinstance(cfg.settings, ConfigModel)
    assert cfg.settings.max_iterations == 5
    assert cfg.settings.models.scaffolder


def test_invalid_config_file(tmp_path):
    bad_config = {"max_iterations": "not_int"}
    file_path = tmp_path / "cfg.json"
    file_path.write_text(json.dumps(bad_config))
    cfg = Config()
    with pytest.raises(ValueError):
        cfg.load(str(file_path))


def test_allow_interactive_clarification_defaults(monkeypatch, tmp_path):
    """Verify default and custom values for allow_interactive_clarification."""
    monkeypatch.chdir(tmp_path)
    cfg = Config()
    cfg.load()
    assert cfg.settings.allow_interactive_clarification is True

    updated = cfg.config
    updated["allow_interactive_clarification"] = False
    cfg.config = updated
    assert cfg.settings.allow_interactive_clarification is False
    assert cfg.config["allow_interactive_clarification"] is False

