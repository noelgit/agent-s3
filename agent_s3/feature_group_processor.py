"""Feature group processor for organizing complex tasks into manageable units.

This module processes pre-planning output into feature groups that can be implemented.
"""

import json
import logging
import uuid
import traceback
import difflib
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)


class FeatureGroupProcessor:
    """Processes feature groups from pre-planning output."""

    def __init__(self, coordinator):
        """Initialize the feature group processor.

        Args:
            coordinator: The coordinator instance that manages components
        """
        self.coordinator = coordinator

        # Access the test critic through the coordinator if available
        if hasattr(coordinator, "test_critic"):
            self.test_critic = coordinator.test_critic
        else:
            self.test_critic = None
            logger.warning("Test critic not available in coordinator")

    def process_pre_planning_output(
        self, pre_plan_data: Dict[str, Any], task_description: str
    ) -> Dict[str, Any]:
        """
        Process the pre-planning output to generate consolidated plans for each feature group.

        Args:
            pre_plan_data: The pre-planning output data containing feature groups
            task_description: The original task description

        Returns:
            Dictionary with processed groups, success flag, and potential error information
        """
        result = {"success": False, "processed_groups": []}

        try:
            # Extract feature groups from pre-planning output
            feature_groups = pre_plan_data.get("feature_groups", [])

            if not feature_groups:
                raise ValueError("No feature groups found in pre-planning output")

            self.coordinator.scratchpad.log(
                "FeatureGroupProcessor",
                f"Processing {len(feature_groups)} feature groups...",
            )

            processed_groups = []
            all_groups_valid = True

            for feature_group in feature_groups:
                group_name = feature_group.get("group_name", "Unnamed Group")
                self.coordinator.scratchpad.log(
                    "FeatureGroupProcessor", f"Processing feature group: {group_name}"
                )

                try:
                    # Set up context for the feature group
                    context = self._gather_context_for_feature_group(feature_group)

                    # Extract system design from feature group
                    system_design = {}
                    for feature in feature_group.get("features", []):
                        if isinstance(feature, dict) and "system_design" in feature:
                            feature_system_design = feature.get("system_design", {})
                            # Merge system design from all features
                            for key, value in feature_system_design.items():
                                if key not in system_design:
                                    system_design[key] = value
                                elif isinstance(value, list) and isinstance(
                                    system_design[key], list
                                ):
                                    system_design[key].extend(value)

                    # STEP 1: Architecture Review
                    self.coordinator.scratchpad.log(
                        "FeatureGroupProcessor",
                        f"Generating architecture review for {group_name}...",
                    )
                    self.coordinator.progress_tracker.update_progress(
                        {
                            "phase": "architecture_review",
                            "status": "started",
                            "group": group_name,
                        }
                    )

                    architecture_review, arch_discussion = (
                        self._generate_architecture_review(
                            feature_group,
                            task_description,
                            context,
                        )
                    )

                    self.coordinator.progress_tracker.update_progress(
                        {
                            "phase": "architecture_review",
                            "status": "completed",
                            "group": group_name,
                        }
                    )

                    # STEP 2 & 3: Tests
                    self.coordinator.scratchpad.log(
                        "FeatureGroupProcessor",
                        f"Refining test specifications for {group_name}...",
                    )
                    self.coordinator.progress_tracker.update_progress(
                        {
                            "phase": "test_refinement",
                            "status": "started",
                            "group": group_name,
                        }
                    )

                    (
                        tests,
                        test_strategy,
                        refined_test_specs,
                        test_implementations_data,
                        test_refinement_discussion,
                        test_implementation_discussion,
                    ) = self._generate_tests(
                        feature_group,
                        architecture_review,
                        task_description,
                        context,
                        system_design,
                    )

                    self.coordinator.progress_tracker.update_progress(
                        {
                            "phase": "test_refinement",
                            "status": "completed",
                            "group": group_name,
                        }
                    )
                    self.coordinator.progress_tracker.update_progress(
                        {
                            "phase": "test_implementation",
                            "status": "completed",
                            "group": group_name,
                        }
                    )

                    # Run Test Critic on generated tests
                    self.coordinator.scratchpad.log(
                        "FeatureGroupProcessor",
                        f"Running Test Critic for {group_name}...",
                    )
                    test_critic_results = None
                    if self.test_critic:
                        test_critic_results = self.test_critic.critique_tests(
                            tests,
                            feature_group.get("risk_assessment", {}),
                        )

                    # STEP 4: Implementation Planning
                    self.coordinator.scratchpad.log(
                        "FeatureGroupProcessor",
                        f"Generating implementation plan for {group_name}...",
                    )
                    self.coordinator.progress_tracker.update_progress(
                        {
                            "phase": "implementation_planning",
                            "status": "started",
                            "group": group_name,
                        }
                    )

                    (
                        implementation_plan,
                        implementation_plan_data,
                        implementation_discussion,
                    ) = self._generate_implementation_plan(
                        system_design,
                        architecture_review,
                        tests,
                        task_description,
                        context,
                    )

                    self.coordinator.progress_tracker.update_progress(
                        {
                            "phase": "implementation_planning",
                            "status": "completed",
                            "group": group_name,
                        }
                    )

                    # STEP 5: Semantic Validation to ensure coherence between phases
                    self.coordinator.scratchpad.log(
                        "FeatureGroupProcessor",
                        f"Validating semantic coherence for {group_name}...",
                    )
                    self.coordinator.progress_tracker.update_progress(
                        {
                            "phase": "semantic_validation",
                            "status": "started",
                            "group": group_name,
                        }
                    )

                    try:
                        from .planner_json_enforced import (
                            validate_planning_semantic_coherence,
                        )

                        validation_results = validate_planning_semantic_coherence(
                            self.coordinator.router_agent,
                            architecture_review,
                            refined_test_specs,
                            test_implementations_data,
                            implementation_plan_data,
                            task_description,
                            context,
                        )

                        semantic_validation = validation_results.get(
                            "validation_results", {}
                        )
                        coherence_score = semantic_validation.get("coherence_score", 0)
                        consistency_score = semantic_validation.get(
                            "technical_consistency_score", 0
                        )
                        critical_issues = semantic_validation.get("critical_issues", [])

                        self.coordinator.scratchpad.log(
                            "FeatureGroupProcessor",
                            f"Semantic validation complete: Coherence={coherence_score:.2f}, Consistency={consistency_score:.2f}, Issues={len(critical_issues)}",
                        )

                    except Exception as validation_error:
                        self.coordinator.scratchpad.log(
                            "FeatureGroupProcessor",
                            f"Semantic validation error: {str(validation_error)}",
                        )
                        semantic_validation = {"error": str(validation_error)}

                    self.coordinator.progress_tracker.update_progress(
                        {
                            "phase": "semantic_validation",
                            "status": "completed",
                            "group": group_name,
                        }
                    )

                    # Combine discussions into an overall plan discussion
                    plan_discussion = (
                        f"Architecture Review: {arch_discussion}\n\n"
                        f"Test Refinement: {test_refinement_discussion}\n\n"
                        f"Test Implementation: {test_implementation_discussion}\n\n"
                        f"Implementation Planning: {implementation_discussion}"
                    )

                    # Create the consolidated plan
                    consolidated_plan = self._create_consolidated_plan(
                        feature_group,
                        architecture_review,
                        implementation_plan,
                        tests,
                        task_description,
                        plan_discussion,
                    )

                    # Add semantic validation results
                    consolidated_plan["semantic_validation"] = semantic_validation

                    # Add test critic results
                    if test_critic_results:
                        consolidated_plan["test_critic_results"] = test_critic_results

                    processed_groups.append(consolidated_plan)
                    self.coordinator.scratchpad.log(
                        "FeatureGroupProcessor",
                        f"Successfully processed feature group: {group_name}",
                    )

                except Exception as e:
                    all_groups_valid = False
                    self.coordinator.scratchpad.log(
                        "FeatureGroupProcessor",
                        f"Error processing feature group {group_name}: {e}",
                        level="ERROR",
                    )

                    # Create error entry
                    error_entry = {
                        "group_name": group_name,
                        "error": str(e),
                        "success": False,
                        "traceback": traceback.format_exc(),
                    }
                    processed_groups.append(error_entry)

            # Update result
            result["success"] = all_groups_valid
            result["processed_groups"] = processed_groups

        except Exception as e:
            self.coordinator.scratchpad.log(
                "FeatureGroupProcessor",
                f"Error processing pre-planning output: {e}",
                level="ERROR",
            )
            result["error"] = str(e)
            result["error_context"] = traceback.format_exc()

        return result

    def _gather_context_for_feature_group(
        self, feature_group: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Gather necessary context for a feature group.

        This method collects relevant context information for a specific feature group
        by utilizing the context registry to fetch tech stack, file metadata, project structure,
        and other relevant information. It also gathers feature-specific context based on
        the feature group's description and affected files.

        Args:
            feature_group: The feature group to gather context for

        Returns:
            Dictionary with consolidated context information relevant to the feature group
        """
        context = {}
        try:
            # Base description to use for context queries
            group_description = feature_group.get("group_description", "")
            feature_descriptions = []
            affected_files = []

            # Extract feature descriptions and affected files from the feature group
            for feature in feature_group.get("features", []):
                if isinstance(feature, dict):
                    if "description" in feature:
                        feature_descriptions.append(feature["description"])

                    # Collect affected files from each feature
                    if "files_affected" in feature and isinstance(
                        feature["files_affected"], list
                    ):
                        affected_files.extend(feature["files_affected"])

                    # Also check system_design.code_elements for target files
                    if "system_design" in feature and isinstance(
                        feature["system_design"], dict
                    ):
                        code_elements = feature["system_design"].get(
                            "code_elements", []
                        )
                        for element in code_elements:
                            if isinstance(element, dict) and "target_file" in element:
                                target_file = element["target_file"]
                                if target_file not in affected_files:
                                    affected_files.append(target_file)

            # Create a rich description for context queries
            context_query = group_description
            if feature_descriptions:
                context_query += " " + " ".join(feature_descriptions)

            # Use context registry to fetch relevant context
            if (
                hasattr(self.coordinator, "context_registry")
                and self.coordinator.context_registry
            ):
                # Get tech stack information
                tech_stack_context = self.coordinator.get_current_context_snapshot(
                    context_type="tech_stack"
                )
                if tech_stack_context:
                    context.update(tech_stack_context)

                # Get project structure information
                project_context = self.coordinator.get_current_context_snapshot(
                    context_type="project_structure"
                )
                if project_context:
                    context.update(project_context)

                # Get file metadata for affected files
                file_metadata = {}
                for file_path in affected_files:
                    file_context = self.coordinator.get_current_context_snapshot(
                        context_type="file_metadata", query=file_path
                    )
                    if file_context and "file_metadata" in file_context:
                        file_metadata[file_path] = file_context["file_metadata"]

                if file_metadata:
                    context["file_metadata"] = file_metadata

                # Get dependencies information
                deps_context = self.coordinator.get_current_context_snapshot(
                    context_type="dependencies"
                )
                if deps_context:
                    context.update(deps_context)

                # Get test requirements information
                test_context = self.coordinator.get_current_context_snapshot(
                    context_type="test_requirements"
                )
                if test_context:
                    context.update(test_context)

                # Get task-specific context based on the feature group description
                if context_query:
                    query_context = self.coordinator.get_current_context_snapshot(
                        query=context_query
                    )
                    if query_context:
                        context.update(query_context)

            # Collect file contents for the affected files using file_tool
            file_contents = {}
            if hasattr(self.coordinator, "file_tool") and affected_files:
                for file_path in affected_files:
                    try:
                        content = self.coordinator.file_tool.read(file_path)
                        if content:
                            file_contents[file_path] = content
                    except Exception:
                        # Silently continue if file doesn't exist - it might be a new file
                        pass

            if file_contents:
                context["file_contents"] = file_contents

            # Add source code snippets from code_analysis_tool if available
            if hasattr(self.coordinator, "code_analysis_tool") and context_query:
                try:
                    code_snippets = (
                        self.coordinator.code_analysis_tool.find_relevant_code_snippets(
                            context_query
                        )
                    )
                    if code_snippets:
                        context["code_snippets"] = code_snippets
                except Exception as e:
                    # Log the error but continue gathering other context
                    self.coordinator.scratchpad.log(
                        "FeatureGroupProcessor",
                        f"Error getting code snippets: {e}",
                        level="WARNING",
                    )
        except Exception as e:
            # Log error but return whatever context we've managed to gather
            self.coordinator.scratchpad.log(
                "FeatureGroupProcessor",
                f"Error gathering context: {e}",
                level="WARNING",
            )

        return context

    def _create_consolidated_plan(
        self,
        feature_group: Dict[str, Any],
        architecture_review: Dict[str, Any],
        implementation_plan: Dict[str, Any],
        tests: Dict[str, Any],
        task_description: str,
        plan_discussion: str,
    ) -> Dict[str, Any]:
        """Create the final consolidated plan structure for a feature group."""
        import uuid

        plan_id = f"plan_{uuid.uuid4()}"

        consolidated_plan = {
            "plan_id": plan_id,
            "group_name": feature_group.get("group_name", "Unnamed Group"),
            "group_description": feature_group.get("group_description", ""),
            "architecture_review": architecture_review,
            "implementation_plan": implementation_plan,
            "tests": tests,
            "discussion": plan_discussion,
            "dependencies": feature_group.get("dependencies", {}),
            "risk_assessment": feature_group.get("risk_assessment", {}),
            # The semantic_validation field will be added later if available
            "success": True,
            "timestamp": str(uuid.uuid4()),  # Timestamp for reference
        }

        return consolidated_plan

    # ------------------------------------------------------------------
    # Helper methods for modularized planning steps
    # ------------------------------------------------------------------

    def _generate_architecture_review(
        self,
        feature_group: Dict[str, Any],
        task_description: str,
        context: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], str]:
        """Generate architecture review for a feature group."""
        try:
            from .planner_json_enforced import generate_architecture_review

            review_data = generate_architecture_review(
                self.coordinator.router_agent,
                feature_group,
                task_description,
                context,
            )
            return (
                review_data.get("architecture_review", {}),
                review_data.get("discussion", ""),
            )
        except Exception as e:
            self.coordinator.scratchpad.log(
                "FeatureGroupProcessor",
                f"Architecture review error for {feature_group.get('group_name')}: {e}",
                level="ERROR",
            )
            raise

    def _generate_tests(
        self,
        feature_group: Dict[str, Any],
        architecture_review: Dict[str, Any],
        task_description: str,
        context: Dict[str, Any],
        system_design: Dict[str, Any],
    ) -> Tuple[
        Dict[str, Any],
        Dict[str, Any],
        Dict[str, Any],
        Dict[str, Any],
        str,
        str,
    ]:
        """Generate refined tests and implementations."""
        from .planner_json_enforced import (
            generate_refined_test_specifications,
            generate_test_implementations,
        )

        try:
            refined_data = generate_refined_test_specifications(
                self.coordinator.router_agent,
                feature_group,
                architecture_review,
                task_description,
                context,
            )
            refined_specs = refined_data.get("refined_test_requirements", {})
            refinement_discussion = refined_data.get("discussion", "")

            impl_data = generate_test_implementations(
                self.coordinator.router_agent,
                refined_specs,
                system_design,
                task_description,
                context,
            )
            tests = impl_data.get("tests", {})
            strategy = impl_data.get("test_strategy_implementation", {})
            impl_discussion = impl_data.get("discussion", "")

            return (
                tests,
                strategy,
                refined_specs,
                impl_data,
                refinement_discussion,
                impl_discussion,
            )
        except Exception as e:
            self.coordinator.scratchpad.log(
                "FeatureGroupProcessor",
                f"Test generation error for {feature_group.get('group_name')}: {e}",
                level="ERROR",
            )
            raise

    def _generate_implementation_plan(
        self,
        system_design: Dict[str, Any],
        architecture_review: Dict[str, Any],
        tests: Dict[str, Any],
        task_description: str,
        context: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], Dict[str, Any], str]:
        """Generate implementation plan based on prior steps."""
        from .planner_json_enforced import generate_implementation_plan

        try:
            impl_data = generate_implementation_plan(
                self.coordinator.router_agent,
                system_design,
                architecture_review,
                tests,
                task_description,
                context,
            )
            return (
                impl_data.get("implementation_plan", {}),
                impl_data,
                impl_data.get("discussion", ""),
            )
        except Exception as e:
            self.coordinator.scratchpad.log(
                "FeatureGroupProcessor",
                f"Implementation planning error: {e}",
                level="ERROR",
            )
            raise

    def present_consolidated_plan_to_user(
        self,
        consolidated_plan: Dict[str, Any],
        original_plan: Optional[Dict[str, Any]] = None,
    ) -> Tuple[str, Optional[str]]:
        """
        Present the consolidated plan to the user for approval.

        Args:
            consolidated_plan: The consolidated plan to present

        Returns:
            Tuple of (decision, modification_text)
        """
        if not consolidated_plan:
            return "no", "No consolidated plan provided"

        group_name = consolidated_plan.get("group_name", "Unnamed Group")
        self.coordinator.scratchpad.log(
            "FeatureGroupProcessor",
            f"Presenting consolidated plan for {group_name} to user",
        )

        if original_plan:
            original_text = json.dumps(original_plan, indent=2, sort_keys=True)
            new_text = json.dumps(consolidated_plan, indent=2, sort_keys=True)
            diff = "\n".join(
                difflib.unified_diff(
                    original_text.splitlines(),
                    new_text.splitlines(),
                    fromfile="original",
                    tofile="modified",
                )
            )
            print("\nPLAN MODIFICATIONS DIFF:\n" + diff)

        # Use the PromptModerator to present the consolidated plan
        return self.coordinator.prompt_moderator.present_consolidated_plan(
            consolidated_plan
        )

    def update_plan_with_modifications(
        self, plan: Dict[str, Any], modifications: str
    ) -> Dict[str, Any]:
        """
        Update the consolidated plan with user modifications.

        Args:
            plan: The original consolidated plan
            modifications: Text describing user's requested modifications

        Returns:
            Updated consolidated plan
        """
        self.coordinator.scratchpad.log(
            "FeatureGroupProcessor", "Updating plan with user modifications"
        )

        try:
            # Import planner helper for modification regeneration
            from .planner_json_enforced import (
                regenerate_consolidated_plan_with_modifications,
            )

            # Validator used during plan generation
            from agent_s3.tools.implementation_validator import (
                validate_implementation_plan,
            )

            # Regenerate the plan with the user's modifications
            updated_plan = regenerate_consolidated_plan_with_modifications(
                self.coordinator.router_agent,
                plan,
                modifications,
            )

            if updated_plan:
                updated_plan["is_modified_by_user"] = True
                updated_plan["modification_text"] = modifications

                required_keys = {"architecture_review", "tests", "implementation_plan"}
                missing_keys = required_keys - set(updated_plan.keys())

                structural_issues = []
                if missing_keys:
                    structural_issues.append(
                        f"Missing required keys: {', '.join(missing_keys)}"
                    )

                # Validate element IDs against system design
                from agent_s3.test_spec_validator import (
                    extract_element_ids_from_system_design,
                )

                system_design = updated_plan.get("system_design") or plan.get(
                    "system_design", {}
                )
                valid_ids = extract_element_ids_from_system_design(system_design)

                invalid_test_ids = set()
                tests = updated_plan.get("tests", {})
                for t in tests.get("unit_tests", []):
                    tid = t.get("target_element_id")
                    if tid and tid not in valid_ids:
                        invalid_test_ids.add(tid)
                for t in tests.get("property_based_tests", []):
                    tid = t.get("target_element_id")
                    if tid and tid not in valid_ids:
                        invalid_test_ids.add(tid)
                for t in tests.get("integration_tests", []):
                    for tid in t.get("target_element_ids", []):
                        if tid not in valid_ids:
                            invalid_test_ids.add(tid)
                for t in tests.get("acceptance_tests", []):
                    for tid in t.get("target_element_ids", []):
                        if tid not in valid_ids:
                            invalid_test_ids.add(tid)

                if invalid_test_ids:
                    structural_issues.append(
                        f"Invalid test element IDs: {', '.join(sorted(invalid_test_ids))}"
                    )

                invalid_impl_ids = set()
                for funcs in updated_plan.get("implementation_plan", {}).values():
                    if isinstance(funcs, list):
                        for func in funcs:
                            eid = func.get("element_id")
                            if eid and eid not in valid_ids:
                                invalid_impl_ids.add(eid)

                if invalid_impl_ids:
                    structural_issues.append(
                        f"Invalid implementation element IDs: {', '.join(sorted(invalid_impl_ids))}"
                    )

                # Perform implementation plan validation
                validated_impl, validation_issues, needs_repair = (
                    validate_implementation_plan(
                        updated_plan.get("implementation_plan", {}),
                        system_design,
                        updated_plan.get("architecture_review", {}),
                        updated_plan.get("tests", {}),
                    )
                )
                updated_plan["implementation_plan"] = validated_impl

                revalidation_results = {
                    "implementation_plan_validation": {
                        "is_valid": not needs_repair and not validation_issues,
                        "issues": validation_issues,
                    }
                }

                if structural_issues:
                    revalidation_results["plan_structure"] = {
                        "is_valid": False,
                        "issues": structural_issues,
                    }

                is_valid_overall = (
                    not needs_repair and not validation_issues and not structural_issues
                )

                updated_plan["revalidation_results"] = revalidation_results
                updated_plan["revalidation_status"] = {
                    "is_valid": is_valid_overall,
                    "issues_found": validation_issues + structural_issues,
                    "timestamp": str(uuid.uuid4()),
                }

                # Present validation results to the user
                self._present_revalidation_results(updated_plan)

                return updated_plan
            else:
                # If regeneration failed, return original plan with error status
                plan["is_modified_by_user"] = False
                plan["revalidation_status"] = {
                    "is_valid": False,
                    "issues_found": ["Failed to generate modified plan"],
                    "timestamp": str(uuid.uuid4()),
                }
                return plan

        except Exception as e:
            self.coordinator.scratchpad.log(
                "FeatureGroupProcessor", f"Error updating plan: {e}", level="ERROR"
            )

            # Return original plan with error information
            plan["is_modified_by_user"] = False
            plan["modification_error"] = str(e)
            plan["revalidation_status"] = {
                "is_valid": False,
                "issues_found": [f"Error during plan modification: {str(e)}"],
                "timestamp": str(uuid.uuid4()),
            }

            return plan

    def _get_user_decision(self) -> str:
        """Get user's decision on the consolidated plan."""
        # Use prompt moderator if available
        if hasattr(self.coordinator, "prompt_moderator"):
            prompt_moderator = self.coordinator.prompt_moderator
            decision = prompt_moderator.ask_ternary_question(
                "Do you want to proceed with this plan? (yes/no/modify)"
            )
            return decision

        # Fallback to direct input
        while True:
            decision = (
                input("Do you want to proceed with this plan? (yes/no/modify): ")
                .lower()
                .strip()
            )
            if decision in ["yes", "no", "modify"]:
                return decision
            print("Invalid input. Please enter 'yes', 'no', or 'modify'.")

    def _present_revalidation_results(self, updated_plan: Dict[str, Any]) -> None:
        """Present revalidation results to the user.

        This basic implementation simply logs a summary. It can be
        overridden or patched in tests to verify that results are
        communicated correctly.
        """
        status = updated_plan.get("revalidation_status", {})
        self.coordinator.scratchpad.log(
            "FeatureGroupProcessor",
            f"Revalidation complete. Overall valid: {status.get('is_valid', False)}",
        )
