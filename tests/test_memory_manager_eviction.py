import time
from unittest.mock import MagicMock

import pytest

from agent_s3.tools.memory_manager import MemoryManager


@pytest.fixture
def eviction_manager(tmp_path, mock_components):
    config = {
        "workspace_path": str(tmp_path),
        "max_embeddings": 1,
        "eviction_batch_size": 2,
    }
    manager = MemoryManager(
        config,
        mock_components["embedding_client"],
        mock_components["file_tool"],
        mock_components["llm_client"],
    )
    return manager


def test_prefix_eviction_selection(eviction_manager, tmp_path):
    manager = eviction_manager
    now = time.time()
    prefix_old = tmp_path / "old"
    prefix_old.mkdir()
    prefix_new = tmp_path / "new"
    prefix_new.mkdir()
    old_file = prefix_old / "a.py"
    new_file = prefix_new / "b.py"
    manager.embedding_access_log = {
        str(old_file): {"last_access": now - 86400 * 30, "access_count": 0, "created": now - 86400 * 40},
        str(new_file): {"last_access": now - 60, "access_count": 0, "created": now - 60},
    }

    removed = []

    def fake_remove(fp, record_removal=False):
        removed.append(fp)
        return True

    manager.remove_embedding = MagicMock(side_effect=fake_remove)
    evicted = manager.apply_progressive_eviction(force=True)

    assert removed
    assert removed[0].startswith(str(prefix_old))
    assert evicted == len(removed)
    assert manager.prefix_evictions == evicted


def test_prefix_eviction_counter_increment(eviction_manager, tmp_path):
    manager = eviction_manager
    now = time.time()
    file_path = tmp_path / "old" / "c.py"
    file_path.parent.mkdir(parents=True, exist_ok=True)
    manager.embedding_access_log = {
        str(file_path): {"last_access": now - 86400 * 10, "access_count": 0, "created": now - 86400 * 15}
    }

    manager.remove_embedding = MagicMock(return_value=True)
    evicted = manager.apply_progressive_eviction(force=True)

    manager.remove_embedding.assert_called_once_with(str(file_path), record_removal=True)
    assert evicted == 1
    assert manager.prefix_evictions == 1
