"""
Configuration system for LLM-based summarization with metrics, thresholds, and validation settings.
"""
from dataclasses import dataclass

@dataclass
class SummarizationConfig:
    model_name: str = "gpt-4"
    chunk_token_limit: int = 1500
    overlap_tokens: int = 100
    max_recursive_depth: int = 3
    temperature: float = 0.2
    faithfulness_threshold: float = 0.7
    detail_preservation_threshold: float = 0.8
    validation_enabled: bool = True
