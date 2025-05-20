"""Tests for Supabase-backed LLM integration utilities.

This module verifies that the ``call_llm_via_supabase`` helper constructs
requests correctly, applies authentication headers, parses Supabase
responses, and handles error conditions gracefully. All network
interactions are mocked to ensure deterministic behavior.
"""

