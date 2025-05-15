# Static Plan Checker

The Static Plan Checker is a critical validation component that ensures Pre-Planner outputs are structurally sound and logically consistent before they reach the Planner phase. This validation happens in milliseconds with zero token consumption.

## Key Benefits

- **Fast & Token-Free**: All checks run in milliseconds without consuming any LLM tokens
- **Early Error Detection**: Catches structural and logical issues before they reach expensive LLM phases
- **CI Integration**: Generates JUnit XML reports for CI/CD pipeline integration
- **GitHub Annotations**: Creates annotation-compatible output for PR reviews

## Validation Checks

The Static Plan Checker performs several deterministic checks:

| Check category          | Purpose                                                                                                |
| ----------------------- | ------------------------------------------------------------------------------------------------------ |
| **Schema & types**      | Ensures all objects match the JSON schema (arrays, enums, required keys) with proper types             |
| **Identifier hygiene**  | Verifies IDs are unique and function names follow naming conventions and aren't reserved keywords      |
| **Path validity**       | Confirms file paths refer to existing files or are clearly marked as new files to be created           |
| **Token budget**        | Checks that feature token estimates don't exceed complexity-based budgets                              |
| **Duplicate symbols**   | Ensures no function/route/environment key is defined in multiple features                              |
| **Reserved prefixes**   | Validates environment variables follow conventions (uppercase) and don't override system variables      |
| **Stub/test coherence** | Confirms every stub function has corresponding test coverage                                           |
| **Complexity sanity**   | Verifies complexity levels correlate logically with token estimates                                    |
| **Test-Risk alignment** | Validates tests include required types, keywords, and libraries based on risk assessment characteristics |

## Integration

The Static Plan Checker is integrated into the workflow between the Pre-Planner and Planner phases:

```
Pre‑Planner ──> Static Plan Checker ──> Planner
                 ▲
   fail-fast:    └─ fix or retry
```

When validation fails, the Pre-Planner may be retried or a human can intervene to fix issues before proceeding to the Planner phase.

## Implementation Details

- Uses standard Python libraries (`jsonschema`, regex, `glob`) for maximum portability
- Optionally produces JUnit XML output for CI/CD integration
- Can be extended with additional custom validation rules
- Error messages include enough context to identify and fix issues

## Test Coverage vs. Risk Assessment

The Static Plan Checker includes an enhanced validation of test coverage against risk assessment through the `validate_test_coverage_against_risk` function in `phase_validator.py`. This validation ensures that:

1. **Critical Files Coverage**: All files marked as "critical" in the risk assessment have associated tests
2. **High-Risk Areas Coverage**: All high-risk areas identified in the risk assessment have adequate test coverage
3. **Test Types Alignment**: Required test types match the risk profile (e.g., property-based for edge cases, integration for component interactions)
4. **Risk-Specific Test Characteristics**: Tests meet the specific characteristics required by the risk assessment:
   - **Required Test Types**: Verifies that all required test types (e.g., security, performance) are included
   - **Required Keywords**: Ensures test names, descriptions, or code contain required keywords (e.g., "injection", "unauthorized", "benchmark")
   - **Suggested Libraries**: Checks that the suggested testing libraries are used in the appropriate tests

The validation provides detailed reporting on missing test characteristics, enabling developers to pinpoint exactly which risk mitigation strategies are not adequately covered by tests.
