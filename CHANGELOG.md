<!--
File: CHANGELOG.md
Description: Release notes for Agent-S3.
-->

# Changelog

## [Unreleased]
### Added
- **Supabase-based remote LLM option** enabling prompts and responses to be stored remotely.
- Dependency on the `supabase-py` client for interacting with Supabase.

### Environment Variables
- `SUPABASE_URL` – base URL of the Supabase instance.
- `SUPABASE_SERVICE_ROLE_KEY` – key used for privileged Supabase operations.
- `SUPABASE_ANON_KEY` – optional key for anonymous access when applicable.
- `SUPABASE_EDGE_FUNCTION_PATH` – optional path to the Supabase Edge function used for LLM calls.

### Security
- API keys are now stored remotely via Supabase, reducing local exposure risk.
