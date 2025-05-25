#!/usr/bin/env python3
"""
Legacy Test Mover for Agent-S3 Project.
This script moves test files with syntax errors to a legacy folder
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('legacy_test_mover.log')
    ]
)
logger = logging.getLogger('legacy_test_mover')

# Files with syntax errors identified by our analysis
PROBLEMATIC_FILES = [
    'tests/test_feature_based_workflow.py',
    'tests/test_compression.py',
    'tests/test_plan_validator.py',
    'tests/test_code_generator_complexity.py',
    'tests/test_pre_planner_json_enforced.py',
    'tests/test_advanced_workflows.py',
    'tests/test_command_processor.py',
    'tests/test_task_state_manager.py',
    'tests/test_implementation_validator_enhanced.py',
    'tests/test_implementation_manager.py',
    'tests/test_pre_planner_json_validator.py',
    'tests/test_implementation_validator.py',
    'tests/test_llm_utils_supabase.py',
    'tests/test_file_history_analyzer.py',
    'tests/test_coordinator_facade_methods.py',
    'tests/test_semantic_validation_workflow.py',
    'tests/test_pre_planner.py',
    'tests/test_debugging_manager.py',
    'tests/test_tech_stack_detector.py',
    'tests/test_enhanced_scratchpad_manager.py',
    'tests/test_code_generator_agentic.py',
    'tests/test_spec_validator_tests.py',
    'tests/test_message_protocol.py',
    'tests/test_phase_validation.py',
    'tests/test_workspace_initializer.py',
    'tests/test_token_budget.py',
    'tests/test_memory_manager.py',
    'tests/tools/context_management/test_adaptive_config_integration.py',
    'tests/integration/test_context_management_integration.py',
    'agent_s3/tests/test_architecture_validation.py',
    'agent_s3/tests/test_pre_planning_errors.py'
]

def create_legacy_directory(base_dir):
    """Create a legacy directory if it doesn't exist."""
    legacy_dir = os.path.join(base_dir, 'legacy')
    os.makedirs(legacy_dir, exist_ok=True)
    return legacy_dir

def move_file_to_legacy(file_path):
    """Move a file to a legacy folder."""
    # Create 'legacy' directory in the same directory as the file
    base_dir = os.path.dirname(file_path)
    legacy_dir = create_legacy_directory(base_dir)
    
    # Target path in the legacy directory
    filename = os.path.basename(file_path)
    target_path = os.path.join(legacy_dir, filename)
    
    # If the file exists, move it
    if os.path.exists(file_path):
        try:
            shutil.move(file_path, target_path)
            logger.info(f"Moved {file_path} to {target_path}")
            return True
        except Exception as e:
            logger.error(f"Error moving {file_path}: {str(e)}")
            return False
    else:
        logger.warning(f"File not found: {file_path}")
        return False

def main():
    """Main function."""
    logger.info("Starting legacy test mover")
    
    moved_count = 0
    error_count = 0
    
    for file_path in PROBLEMATIC_FILES:
        if move_file_to_legacy(file_path):
            moved_count += 1
        else:
            error_count += 1
    
    logger.info(f"Legacy test mover complete. Moved {moved_count} files, encountered {error_count} errors.")

if __name__ == "__main__":
    main()
