<!--
File: CHANGELOG.md
Description: Release notes for Agent-S3.
-->

# Changelog

## [Unreleased]
### Added
- Example script for uploading and downloading files with AWS S3.

### Environment Variables
- `ALLOW_INTERACTIVE_CLARIFICATION` – optional flag (default: `True`) enabling interactive clarification questions.
- `MAX_CLARIFICATION_ROUNDS` – optional number of clarification rounds allowed during pre-planning (default: `3`).
- `MAX_PREPLANNING_ATTEMPTS` – optional number of retries for generating pre-planning data (default: `2`).

### Security
- Replaced all MD5 hashing with SHA-256 for better integrity verification.

### Removed
- Deprecated `validate_pre_planning_from_planner` helper in favor of direct
  `validate_pre_planning_output` usage.
- Dropped Supabase integration and removed the associated environment
  variables and dependencies.

## [0.1.1] - 2025-05-23
### Fixed
- Aligned `agent_s3.__version__` with `pyproject.toml`.
