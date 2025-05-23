<!--
File: CHANGELOG.md
Description: Release notes for Agent-S3.
-->

# Changelog

## [Unreleased]
### Added
- **Supabase-based remote LLM option** enabling prompts and responses to be stored remotely.
- Dependency on the `supabase-py` client for interacting with Supabase.
- Example script for uploading and downloading files with AWS S3.

### Environment Variables
- `SUPABASE_URL` – base URL of the Supabase instance.
- `SUPABASE_SERVICE_ROLE_KEY` – key used for privileged Supabase operations.
- `SUPABASE_ANON_KEY` – optional key for anonymous access when applicable.
- `SUPABASE_FUNCTION_NAME` – optional name of the Supabase function used for LLM calls.
- `MAX_CLARIFICATION_ROUNDS` – optional number of clarification rounds allowed during pre-planning (default: `3`).
- `MAX_PREPLANNING_ATTEMPTS` – optional number of retries for generating pre-planning data (default: `2`).

### Security
- API keys are now stored remotely via Supabase, reducing local exposure risk.

### Removed
- Deprecated `validate_pre_planning_from_planner` helper in favor of direct
  `validate_pre_planning_output` usage.

## [0.1.1] - 2025-05-23
### Fixed
- Aligned `agent_s3.__version__` with `pyproject.toml`.
