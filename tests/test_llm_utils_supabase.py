"""Integration tests for Supabase-backed LLM utilities.

These tests verify that :func:`call_llm_via_supabase` formats requests
properly, attaches required authentication headers, parses responses, and
handles error scenarios gracefully. All HTTP calls are mocked to keep the
tests deterministic.
"""

