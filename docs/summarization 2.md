# Agent-S3 Validated LLM Summarization System

## Overview
This system ensures that all LLM-generated summaries are:
- Faithful to the source
- Preserve critical details
- Structurally coherent

## Components
- **Prompt Factory**: Generates language- and task-specific prompts
- **Summary Validator**: Checks faithfulness, detail preservation, and structure
- **Summary Refiner**: Refines summaries that fail validation
- **Summary Cache**: Caches validated summaries for reuse
- **Benchmark/Evaluation**: Tools and datasets for measuring summary quality

## Quality Metrics
- **Faithfulness**: Embedding similarity between source and summary
- **Detail Preservation**: Key term overlap
- **Structural Coherence**: (Pluggable, e.g., AST checks)

## Usage
- All summarization flows (including AST-guided and file-level) use this system
- Summaries are validated and refined automatically
- See `tools/evaluate_summarization.py` for benchmarking

## Configuration
- Thresholds and refinement attempts are configurable in `validation_config.py`

## Extensibility
- Add new metrics or prompt templates as needed

## Testing
- See `tests/test_summary_validator.py` and `tests/test_summary_refiner.py`
