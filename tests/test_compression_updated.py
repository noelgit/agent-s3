"""
Compression module tests for Agent-S3.
Tests the functionality of data compression and decompression features.
"""
import json
import pytest
from unittest.mock import MagicMock, patch, mock_open

# Import the compression module (assuming it's in this path)
from agent_s3.compression import compress_data, decompress_data, compress_file, decompress_file

class TestCompression:
    """Test suite for the compression functionality."""
    
    def test_compress_decompress_data(self):
        """Test compressing and decompressing string data."""
        original_data = "This is a test string with some content to compress."
        
        # Compress the data
        compressed = compress_data(original_data)
        
        # Check that the compressed data is different and smaller
        assert compressed != original_data
        assert len(compressed) < len(original_data)
        
        # Decompress the data and verify it matches the original
        decompressed = decompress_data(compressed)
        assert decompressed == original_data
    
    def test_compress_decompress_json(self):
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
        compressed = compress_data(json_data)
        
        # Check that the compressed data is different and smaller
        assert compressed != json_data
        assert len(compressed) < len(json_data)
        
        # Decompress and verify
        decompressed = decompress_data(compressed)
        assert decompressed == json_data
        
        # Check that we can parse the JSON back to its original form
        parsed_data = json.loads(decompressed)
        assert parsed_data == original_data
    
    @patch('builtins.open', new_callable=mock_open, read_data="File content for testing")
    @patch('gzip.open')
    def test_compress_file(self, mock_gzip_open, mock_file_open):
        """Test compressing a file."""
        # Setup the mock for gzip.open
        mock_gzip_file = MagicMock()
        mock_gzip_open.return_value.__enter__.return_value = mock_gzip_file
        
        # Call the function
        input_path = "/path/to/input.txt"
        output_path = "/path/to/output.gz"
        compress_file(input_path, output_path)
        
        # Verify the calls
        mock_file_open.assert_called_once_with(input_path, 'rb')
        mock_gzip_open.assert_called_once_with(output_path, 'wb')
        mock_gzip_file.write.assert_called_once()
    
    @patch('builtins.open', new_callable=mock_open)
    @patch('gzip.open')
    def test_decompress_file(self, mock_gzip_open, mock_file_open):
        """Test decompressing a file."""
        # Setup the mock for gzip.open
        mock_gzip_file = MagicMock()
        mock_gzip_file.read.return_value = b"Decompressed content"
        mock_gzip_open.return_value.__enter__.return_value = mock_gzip_file
        
        # Setup the mock for regular open
        mock_output_file = MagicMock()
        mock_file_open.return_value.__enter__.return_value = mock_output_file
        
        # Call the function
        input_path = "/path/to/input.gz"
        output_path = "/path/to/output.txt"
        decompress_file(input_path, output_path)
        
        # Verify the calls
        mock_gzip_open.assert_called_once_with(input_path, 'rb')
        mock_file_open.assert_called_once_with(output_path, 'wb')
        mock_output_file.write.assert_called_once_with(b"Decompressed content")
    
    def test_compress_empty_data(self):
        """Test compressing empty data."""
        empty_data = ""
        compressed = compress_data(empty_data)
        decompressed = decompress_data(compressed)
        assert decompressed == empty_data
    
    def test_compress_large_data(self):
        """Test compressing large repetitive data with good compression ratio."""
        # Create a large string with repetitive content
        large_data = "abcdefg" * 1000
        
        # Compress the data
        compressed = compress_data(large_data)
        
        # Verify the compression ratio is good (compressed size is much smaller)
        assert len(compressed) < len(large_data) * 0.2
        
        # Verify decompression works correctly
        decompressed = decompress_data(compressed)
        assert decompressed == large_data
    
    @pytest.mark.parametrize("test_data", [
        "Short string",
        "A" * 1000,
        json.dumps({"key": "value", "list": [1, 2, 3]}),
        "Special chars: !@#$%^&*()_+-=[]{}|;':\",./<>?"
    ])
    def test_compress_decompress_various_inputs(self, test_data):
        """Test compression with various types of input data."""
        compressed = compress_data(test_data)
        decompressed = decompress_data(compressed)
        assert decompressed == test_data
