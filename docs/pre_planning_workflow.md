# Pre-Planning Workflow

## Overview

The pre-planning phase is a critical first step in the Agent-S3 workflow. It analyzes software development requests, decomposes them into features, and organizes those features into logical groups. This phase serves as the foundation for subsequent planning and implementation phases.

## Workflow

The pre-planning workflow follows these steps:

1. **Request Analysis**: The system analyzes the user's request to understand the underlying intent, requirements, and constraints.

2. **Feature Group Generation**: The request is decomposed into logical feature groups, each containing related features.

3. **JSON Schema Enforcement**: The pre-planning output is structured according to a strict JSON schema, ensuring consistency and completeness.

4. **Validation**: The output undergoes comprehensive validation, including schema validation, cross-reference validation, and content validation.

5. **Repair**: If validation issues are found, the system attempts to repair them automatically.

6. **User Interaction**: The system may ask clarifying questions to the user if needed. The number of clarification rounds is capped by the `MAX_CLARIFICATION_ROUNDS` environment variable (default: `3`).

7. **Retry Logic**: The system retries generating pre-planning data up to `MAX_PREPLANNING_ATTEMPTS` times (default: `2`).

8. **Complexity Assessment**: The complexity of the task is assessed to determine if user confirmation is required.

9. **User Confirmation**: The user reviews and approves, modifies, or rejects the pre-planning output.

## Key Components

### Pre-Planner JSON Enforced

The `pre_planner_json_enforced.py` module is the canonical implementation for pre-planning with enhanced JSON schema enforcement, validation, and repair capabilities. It provides:

- Strict JSON schema definition and enforcement
- Robust error handling and recovery
- User interaction for clarifications (limited by `MAX_CLARIFICATION_ROUNDS`)
- Automatic repair of validation issues

### Pre-Planner JSON Validator

The `pre_planner_json_validator.py` module provides comprehensive validation for pre-planning outputs, including:

- Schema validation to ensure structural correctness
- Cross-reference validation to ensure relationships between plan elements are valid
- Content validation to ensure technical feasibility and security
- Repair capabilities to fix validation issues
- Metrics tracking for validation performance

### Complexity Analyzer

The `complexity_analyzer.py` module assesses the complexity of implementation tasks based on multiple factors:

- Feature count and complexity
- Impacted files
- Requirements complexity
- Security sensitivity
- External integrations

### Plan Validator

The `tools/plan_validator.py` module provides fast, deterministic validation of pre-planning outputs, including:

- Schema validation
- Code syntax checking
- Identifier hygiene
- Path validity
- Token budget compliance
- Duplicate symbol detection
- Content scanning for dangerous operations

## JSON Schema

The pre-planning output follows a strict JSON schema that includes:

- Feature groups with names and descriptions
- Features with names, descriptions, and complexity ratings
- Implementation steps for each feature
- Test requirements including unit tests, integration tests, and acceptance tests
- Risk assessments including risk level, concerns, and mitigation strategies
- System design including code elements, data flow, and key algorithms

## Error Handling

The pre-planning phase includes robust error handling through the `pre_planning_errors.py` module, which provides:

- A consistent hierarchy of exceptions
- Error categorization for better diagnostics
- Decorators for consistent error handling

## Integration with Coordinator

The pre-planning phase is integrated with the Coordinator through the `run_task` method, which:

1. Calls the pre-planning workflow
2. Validates the pre-planning output
3. Presents the results to the user for approval
4. Proceeds with the planning and implementation phases

## Best Practices

When working with the pre-planning phase:

1. Always use the `pre_planner_json_enforced.py` module for pre-planning
2. Ensure all validation checks pass before proceeding to the planning phase
3. Pay attention to complexity assessments to determine if user confirmation is needed
4. Use the repair capabilities to fix validation issues automatically when possible
5. Provide clear, detailed feature descriptions to ensure accurate implementation

## Context-Aware Prompts

`pre_planning_workflow` accepts an optional `context` dictionary. When supplied,
the context is serialized to JSON and appended to the user prompt before calling
the language model. This enables the pre-planner to consider project specifics
such as the tech stack or current project structure during analysis.

## Pre-Planning Mode

The `pre_planning_mode` configuration sets how the pre-planning workflow runs. Valid values are:

- `off` – skip the pre-planning phase entirely.
- `json` – execute `pre_planning_workflow` without strict schema enforcement.
- `enforced_json` – run `call_pre_planner_with_enforced_json` with full validation (default).

This option replaces the older `use_json_pre_planning` and `use_enforced_json_pre_planning` flags.
Set `pre_planning_mode` to the desired value in your configuration to control the behavior.
