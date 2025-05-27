"""
DEPRECATED: This test file has been removed as the functionality it tested
has been deprecated and moved to the orchestrator pattern.

The pre-planning JSON enforcement functionality tested here was part of an 
older coordinator architecture. The current Agent-S3 system uses the 
WorkflowOrchestrator pattern for handling planning workflows.

Original functionality tested:
- integrate_with_coordinator function
- Enforced JSON pre-planning prioritization  
- Direct integration function testing
- Test requirements integration
- Complexity scoring integration
- Repeated calls handling

These tests were removed rather than updated because:
1. The underlying pre-planner JSON enforcement system has been deprecated
2. Planning workflows are now handled by the orchestrator pattern
3. The coordinator no longer directly handles pre-planning integration
4. Updating these tests would require testing non-existent functionality

If you need to test planning functionality, look at:
- tests/test_orchestrator_*.py (when available)
- Integration tests for the current workflow system
- The actual WorkflowOrchestrator class functionality

Backup of original tests available at: tests/backups/test_coordinator_json_preplanning.py.backup
"""

# No tests in this file - all deprecated functionality removed