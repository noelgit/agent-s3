"""Integration tests for Supabase-based LLM utilities.

These tests ensure that :func:`call_llm_via_supabase` builds requests with the
proper authentication headers, parses responses, and gracefully handles error
conditions. All HTTP interactions are mocked for deterministic behavior.
"""

