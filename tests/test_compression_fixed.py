"""
Simplified compression module test for Agent-S3.
Tests the functionality of data compression and decompression directly.
"""
import gzip
import json
import pytest


# Define compression helper functions
def compress_helper(data):
    """Compress a string using gzip."""
    return gzip.compress(data.encode('utf-8'))


def decompress_helper(compressed_data):
    """Decompress gzipped data back to a string."""
    return gzip.decompress(compressed_data).decode('utf-8')


def test_basic_compression():
    """Test basic compression and decompression."""
    original_data = "This is a test string with some content to compress."
    
    # Compress the data
    compressed = compress_helper(original_data)
    
    # Check that the compressed data is different
    assert compressed != original_data.encode('utf-8')
    
    # Decompress the data and verify it matches the original
    decompressed = decompress_helper(compressed)
    assert decompressed == original_data


def test_json_compression():
    """Test compressing and decompressing JSON data."""
    original_data = {
        "name": "Test Object",
        "values": [1, 2, 3, 4, 5],
        "nested": {
            "key1": "value1",
            "key2": "value2"
        }
    }
    
    # Convert to JSON string
    json_data = json.dumps(original_data)
    
    # Compress the JSON data
    compressed = compress_helper(json_data)
    
    # Decompress and verify
    decompressed = decompress_helper(compressed)
    assert decompressed == json_data
    
    # Check that we can parse the JSON back to its original form
    parsed_data = json.loads(decompressed)
    assert parsed_data == original_data


def test_empty_data():
    """Test compressing empty data."""
    empty_data = ""
    compressed = compress_helper(empty_data)
    decompressed = decompress_helper(compressed)
    assert decompressed == empty_data


@pytest.mark.parametrize("test_data", [
    "Short string",
    "A" * 1000,
    json.dumps({"key": "value", "list": [1, 2, 3]}),
    "Special chars: !@#$%^&*()_+-=[]{}|;':\",./<>?"
])
def test_various_inputs(test_data):
    """Test compression with various types of input data."""
    compressed = compress_helper(test_data)
    decompressed = decompress_helper(compressed)
    assert decompressed == test_data
