"""
Prefix hash utility for semantic cache prefix matching.
"""
import hashlib

def prefix_hash(prompt: str, n_tokens: int = 50) -> str:
    """Hash the first n_tokens of a prompt for prefix-based cache lookup."""
    return hashlib.sha256(" ".join(prompt.split()[:n_tokens]).encode()).hexdigest()
