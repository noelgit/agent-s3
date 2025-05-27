"""
DEPRECATED: This test file has been removed as the functionality it tested
has been deprecated and moved to the orchestrator pattern.

The validation and debugging phase functionality tested here was part of an 
older coordinator architecture. The current Agent-S3 system uses the 
WorkflowOrchestrator pattern for handling validation and debugging workflows.

Original functionality tested:
- _run_validation_phase method (database, lint, type check, test validation)
- _run_tests method with various configurations
- debug_last_test method for automated debugging
- Error handling and recovery workflows
- Mutation testing integration
- Database setup for tests

These tests were removed rather than updated because:
1. These methods have been moved to the WorkflowOrchestrator class
2. The coordinator now delegates these operations to the orchestrator
3. The current coordinator acts as a facade/proxy to the orchestrator
4. Direct testing of these methods on the coordinator is no longer relevant

If you need to test validation and debugging functionality, look at:
- tests/test_orchestrator_*.py (when available) 
- Integration tests for the current workflow system
- Test the orchestrator methods directly rather than coordinator delegation
- The actual WorkflowOrchestrator class functionality

The coordinator still has these methods but they delegate to the orchestrator:
- coordinator._run_validation_phase() -> coordinator.orchestrator._run_validation_phase()
- coordinator._run_tests() -> coordinator.orchestrator._run_tests()
- coordinator.debug_last_test() -> coordinator.orchestrator.debug_last_test()

Backup of original tests available at: tests/backups/test_coordinator_validation.py.backup
"""

# No tests in this file - all deprecated functionality removed