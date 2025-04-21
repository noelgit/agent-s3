import os
import json
import tempfile
import numpy as np  # type: ignore
import pytest
from agent_s3.tools.memory_manager import MemoryManager

@pytest.fixture
def temp_memory_file(tmp_path):
    return str(tmp_path / "mem.json")

@pytest.fixture(autouse=True)
def no_faiss(monkeypatch):
    # Prevent actual FAISS operations by monkeypatching embeddings client add and query
    class DummyEC:
        def __init__(self, *args, **kwargs):
            self.dim = 384
        def add_embeddings(self, embeddings, metadata): pass
        def query(self, query_embedding, top_k): return []
    monkeypatch.setattr('agent_s3.tools.memory_manager.EmbeddingClient', DummyEC)
    yield

def test_add_and_get_context(temp_memory_file):
    manager = MemoryManager(memory_path=temp_memory_file, max_context_items=5)
    manager.initialize()
    vid1 = manager.add_context('file', 'content1', {'path':'a.py'})
    vid2 = manager.add_context('file', 'content2', {'path':'b.py'})
    # History stores items
    ctx = manager.get_context(limit=2)
    assert isinstance(ctx, list)
    assert len(ctx) == 2
    # get by version
    item = manager.get_context_by_version(vid1)
    assert item['version_id'] == vid1

def test_get_relevant_context_fallback(temp_memory_file):
    manager = MemoryManager(memory_path=temp_memory_file)
    manager.initialize()
    manager.context_history = [
        {'type':'file','content':'foo','metadata':{'id':1},'version_id':'v1','timestamp':'t1'},
        {'type':'code','content':'bar','metadata':{'id':2},'version_id':'v2','timestamp':'t2'},
    ]
    res = manager.get_relevant_context('query', limit=1)
    # fallback returns last items
    assert len(res) == 1
    assert res[0]['version_id'] == 'v2'
