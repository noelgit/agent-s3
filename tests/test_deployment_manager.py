import re
from unittest.mock import MagicMock

from agent_s3.deployment_manager import DeploymentManager, DeploymentConfig


def test_create_env_file_quotes_special_values(tmp_path):
    dm = DeploymentManager()

    written = {}

    def mock_write(path, content):
        written['path'] = path
        written['content'] = content
        return True

    dm.file_tool = MagicMock()
    dm.file_tool.write_file.side_effect = mock_write

    config = DeploymentConfig(
        app_name="myapp",
        app_type="flask",
        extra_env_vars={
            "SAFE": "safe",
            "WITH_SPACES": "value with spaces",
            "SPECIAL": 'value "quote" and $dollar',
        },
    )

    result = dm._create_env_file(config)
    assert result["success"] is True
    content = written.get('content', '')

    # Ensure path is correct
    assert written['path'] == '.env'
    # Check that safe value is unquoted
    assert re.search(r"^SAFE=safe$", content, re.MULTILINE)
    # Values with spaces or quotes should be quoted and escaped
    assert 'WITH_SPACES="value with spaces"' in content
    assert 'SPECIAL="value \"quote\" and $dollar"' in content
