"""
Compression utilities for Agent-S3.
Provides functions for compressing and decompressing data and files.
"""

import gzip
import json
from typing import Any, Dict

def compress_data(data: str) -> bytes:
    """
    Compress a string using gzip.
    
    Args:
        data: The string data to compress
        
    Returns:
        Compressed bytes
    """
    return gzip.compress(data.encode('utf-8'))

def decompress_data(compressed_data: bytes) -> str:
    """
    Decompress gzipped data back to a string.
    
    Args:
        compressed_data: The compressed bytes to decompress
        
    Returns:
        Decompressed string
    """
    return gzip.decompress(compressed_data).decode('utf-8')

def compress_file(input_path: str, output_path: str) -> None:
    """
    Compress a file using gzip.
    
    Args:
        input_path: Path to the input file
        output_path: Path to save the compressed file
    """
    with open(input_path, 'rb') as f_in:
        content = f_in.read()
        with gzip.open(output_path, 'wb') as f_out:
            f_out.write(content)

def decompress_file(input_path: str, output_path: str) -> None:
    """
    Decompress a gzipped file.
    
    Args:
        input_path: Path to the compressed file
        output_path: Path to save the decompressed file
    """
    with gzip.open(input_path, 'rb') as f_in:
        content = f_in.read()
        with open(output_path, 'wb') as f_out:
            f_out.write(content)

def compress_json(data: Dict[str, Any]) -> bytes:
    """
    Convert a dictionary to JSON and compress it.
    
    Args:
        data: Dictionary to compress
        
    Returns:
        Compressed bytes
    """
    json_str = json.dumps(data)
    return compress_data(json_str)

def decompress_json(compressed_data: bytes) -> Dict[str, Any]:
    """
    Decompress bytes and parse as JSON.
    
    Args:
        compressed_data: Compressed JSON data
        
    Returns:
        Parsed dictionary
    """
    json_str = decompress_data(compressed_data)
    return json.loads(json_str)
