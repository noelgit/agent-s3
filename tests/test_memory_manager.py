import os
import json
import tempfile
import numpy as np  # type: ignore
import pytest
import tiktoken
from unittest.mock import MagicMock, patch
from agent_s3.tools.memory_manager import MemoryManager, DEFAULT_MODEL_NAME

@pytest.fixture
def temp_workspace_dir(tmp_path):
    """Create a temporary workspace directory for testing."""
    cache_dir = tmp_path / ".cache"
    cache_dir.mkdir()
    return tmp_path

@pytest.fixture
def mock_components():
    """Create mock components needed for MemoryManager initialization."""
    mock_embedding_client = MagicMock()
    mock_embedding_client.dim = 384
    mock_embedding_client.add_embeddings = MagicMock()
    mock_embedding_client.remove_embeddings_by_metadata = MagicMock(return_value=1)
    
    mock_file_tool = MagicMock()
    mock_file_tool.read_file = MagicMock(return_value="test file content")
    
    mock_llm_client = MagicMock()
    mock_llm_client.generate = MagicMock(return_value="test summary")
    
    return {
        "embedding_client": mock_embedding_client,
        "file_tool": mock_file_tool,
        "llm_client": mock_llm_client
    }

def test_add_to_history_and_get_history(temp_workspace_dir, mock_components):
    """Test adding to and retrieving context history."""
    config = {"workspace_path": str(temp_workspace_dir)}
    manager = MemoryManager(
        config,
        mock_components["embedding_client"],
        mock_components["file_tool"],
        mock_components["llm_client"]
    )
    
    # Add entries to history
    entry1 = {"type": "file", "content": "content1", "metadata": {"path": "a.py"}}
    entry2 = {"type": "file", "content": "content2", "metadata": {"path": "b.py"}}
    
    manager.add_to_history(entry1)
    manager.add_to_history(entry2)
    
    # Get history
    history = manager.get_history()
    
    # Verify
    assert isinstance(history, list)
    assert len(history) == 2
    assert history[0] == entry1
    assert history[1] == entry2

def test_update_and_remove_embedding(temp_workspace_dir, mock_components):
    """Test updating and removing embeddings."""
    config = {"workspace_path": str(temp_workspace_dir)}
    manager = MemoryManager(
        config,
        mock_components["embedding_client"],
        mock_components["file_tool"],
        mock_components["llm_client"]
    )
    
    # Create a test file
    test_file = temp_workspace_dir / "test_file.py"
    with open(test_file, "w") as f:
        f.write("print('Hello world')")
    
    # Update embedding
    manager.update_embedding(str(test_file))
    
    # Verify embedding_client.add_embeddings was called
    mock_components["embedding_client"].add_embeddings.assert_called_once()
    
    # Remove embedding
    manager.remove_embedding(str(test_file))
    
    # Verify embedding_client.remove_embeddings_by_metadata was called
    mock_components["embedding_client"].remove_embeddings_by_metadata.assert_called_once()

def test_estimate_token_count_accuracy(mock_components):
    """Test that token counting with tiktoken is accurate."""
    # Initialize with an empty config
    config = {"workspace_path": "."}
    manager = MemoryManager(
        config,
        mock_components["embedding_client"],
        mock_components["file_tool"],
        mock_components["llm_client"]
    )
    
    # Test cases with known token counts for GPT models
    test_texts = [
        "",  # Empty string
        "Hello, world!",  # Short text
        "This is a longer piece of text that should have more tokens than the previous example.",
        "def factorial(n):\n    if n == 0:\n        return 1\n    else:\n        return n * factorial(n-1)"  # Code snippet
    ]
    
    # Get expected token counts using tiktoken directly
    encoding = tiktoken.encoding_for_model(DEFAULT_MODEL_NAME)
    expected_counts = [len(encoding.encode(text)) for text in test_texts]
    
    # Check actual counts match expected
    for i, text in enumerate(test_texts):
        actual_count = manager.estimate_token_count(text)
        assert actual_count == expected_counts[i], f"Token count mismatch for text: {text}"

def test_estimate_token_count_model_selection(mock_components):
    """Test token counting with different model configurations."""
    # Test different model configurations
    test_configs = [
        {"workspace_path": ".", "token_counting_model": "gpt-3.5-turbo"},
        {"workspace_path": ".", "planner_llm_model": "gpt-4"},
        {"workspace_path": ".", "token_counting_model": "openai/gpt-4"},  # With provider prefix
    ]
    
    test_text = "This is a test sentence for token counting."
    
    for config in test_configs:
        manager = MemoryManager(
            config,
            mock_components["embedding_client"],
            mock_components["file_tool"],
            mock_components["llm_client"]
        )
        
        # Extract expected model name (removing provider prefix if present)
        model_name = config.get('token_counting_model') or config.get('planner_llm_model') or DEFAULT_MODEL_NAME
        if "/" in model_name:
            model_name = model_name.split("/")[-1]
        
        # Get expected count directly from tiktoken
        try:
            encoding = tiktoken.encoding_for_model(model_name)
        except KeyError:
            encoding = tiktoken.get_encoding("cl100k_base")
        
        expected_count = len(encoding.encode(test_text))
        actual_count = manager.estimate_token_count(test_text)
        
        assert actual_count == expected_count, f"Token count mismatch for model {model_name}"

def test_estimate_token_count_fallback(mock_components):
    """Test that token counting falls back to approximation when tiktoken fails."""
    # Initialize with a config
    config = {"workspace_path": "."}
    manager = MemoryManager(
        config,
        mock_components["embedding_client"],
        mock_components["file_tool"],
        mock_components["llm_client"]
    )
    
    test_text = "This is a test sentence for fallback token counting."
    
    # Mock tiktoken to raise an exception
    with patch('tiktoken.encoding_for_model', side_effect=Exception("Simulated tiktoken failure")):
        with patch('tiktoken.get_encoding', side_effect=Exception("Simulated encoding failure")):
            # Should fall back to character-based approximation
            actual_count = manager.estimate_token_count(test_text)
            expected_approx = len(test_text) // 4
            
            assert actual_count == expected_approx, "Fallback approximation failed"
