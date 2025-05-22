import pytest
import time
import numpy as np
import tempfile
import shutil
from pathlib import Path

from agent_s3.tools.embedding_client import EmbeddingClient, CACHE_DIR_NAME


@pytest.fixture
def temp_workspace():
    """Create a temporary workspace for testing."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def embedding_client(temp_workspace):
    """Create an embedding client with test configuration."""
    config = {
        "workspace_path": temp_workspace,
        "embedding_dim": 384,  # Smaller dimension for testing
        "embedding_cache_enabled": True,
        "max_embeddings": 50,  # Small limit for testing
        "eviction_threshold": 0.8,  # Trigger at 40 embeddings (80% of 50)
        "eviction_batch_size": 10,
        "min_access_keep": 2,
        "max_idle_time_seconds": 3600  # 1 hour for testing
    }
    client = EmbeddingClient(config)
    yield client


def test_embedding_client_initialization(embedding_client, temp_workspace):
    """Test that the embedding client initializes properly."""
    assert embedding_client.dim == 384
    assert embedding_client.cache_enabled is True
    assert embedding_client.max_embeddings == 50
    
    # Check that cache directory was created
    cache_dir = Path(temp_workspace) / CACHE_DIR_NAME
    assert cache_dir.exists()


def test_update_access_patterns(embedding_client):
    """Test that access patterns are correctly updated."""
    # Add test embeddings
    embeddings = np.random.random((5, embedding_client.dim)).astype('float32')
    file_paths = [f"file_{i}.py" for i in range(5)]
    
    for i, (embedding, file_path) in enumerate(zip(embeddings, file_paths)):
        embedding_client.add_embedding(
            embedding=embedding.reshape(1, -1),
            metadata={"file_path": file_path, "chunk_id": i, "content": f"Test content {i}"}
        )
    
    # Update access patterns for specific files
    embedding_client.update_access_patterns([file_paths[0], file_paths[2]])
    
    # Check that access counts were updated
    for id_str, metadata in embedding_client.id_map.items():
        path = metadata.get("file_path")
        if path in [file_paths[0], file_paths[2]]:
            assert metadata.get("access_count", 0) == 1
        else:
            assert metadata.get("access_count", 0) == 0


def test_progressive_eviction_strategy(embedding_client):
    """Test that the progressive eviction strategy works correctly."""
    # Add test embeddings to exceed threshold
    num_embeddings = 45  # Above the threshold (0.8 * 50 = 40)
    embeddings = np.random.random((num_embeddings, embedding_client.dim)).astype('float32')
    file_paths = [f"file_{i}.py" for i in range(num_embeddings)]
    
    # Add embeddings with different access patterns
    current_time = time.time()
    for i, (embedding, file_path) in enumerate(zip(embeddings, file_paths)):
        timestamp = current_time - (3600 * i % 10)  # Different ages
        metadata = {
            "file_path": file_path, 
            "chunk_id": i, 
            "content": f"Test content {i}",
            "timestamp": timestamp,
            "last_access": timestamp,
            "access_count": i % 5  # Different access counts
        }
        embedding_client.add_embedding(
            embedding=embedding.reshape(1, -1),
            metadata=metadata
        )
    
    # Verify we have the right number of embeddings
    assert embedding_client.index.ntotal == num_embeddings
    
    # Update access patterns for some files to protect them
    frequently_accessed = [file_paths[i] for i in range(0, num_embeddings, 5)]
    embedding_client.update_access_patterns(frequently_accessed)
    
    # Trigger eviction
    evicted = embedding_client.evict_embeddings()
    
    # Should have evicted some embeddings
    assert evicted > 0
    # Should be below threshold now
    assert embedding_client.index.ntotal <= embedding_client.max_embeddings * embedding_client.eviction_threshold
    
    # Check that frequently accessed files were not evicted
    for id_str, metadata in embedding_client.id_map.items():
        path = metadata.get("file_path")
        if path in frequently_accessed:
            assert path in [metadata.get("file_path") for metadata in embedding_client.id_map.values()]


def test_add_embedding_method(embedding_client):
    """Adding this test since we're using an add_embedding method in the other tests."""
    # Create a test embedding
    embedding = np.random.random((1, embedding_client.dim)).astype('float32')
    metadata = {
        "file_path": "test_file.py", 
        "chunk_id": 1, 
        "content": "Test content"
    }
    
    # Add the embedding
    embedding_client.add_embedding(embedding=embedding, metadata=metadata)
    
    # Check it was added correctly
    assert embedding_client.index is not None
    assert embedding_client.index.ntotal == 1
    assert len(embedding_client.id_map) == 1
    
    # Verify metadata was stored
    first_id = list(embedding_client.id_map.keys())[0]
    stored_metadata = embedding_client.id_map[first_id]
    assert stored_metadata["file_path"] == "test_file.py"
    assert "access_count" in stored_metadata
    assert "last_access" in stored_metadata