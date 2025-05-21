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
- `SUPABASE_FUNCTION_NAME` – optional name of the Supabase function used for LLM calls.
- `MAX_CLARIFICATION_ROUNDS` – optional number of clarification rounds allowed during pre-planning (default: `3`).

### Security
- API keys are now stored remotely via Supabase, reducing local exposure risk.

### Removed
- Deprecated `validate_pre_planning_from_planner` helper in favor of direct
  `validate_pre_planning_output` usage.
