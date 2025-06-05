"""
Coordinator Integration for Context Management.

This module provides integration points between the Context Manager
and the Coordinator, enabling context management to work with the
main application workflow.
"""

import logging
import traceback
import os
import time
from typing import Dict, Any, Optional
from dataclasses import dataclass

from agent_s3.tools.context_management.context_manager import ContextManager
from agent_s3.tools.context_management.adaptive_config import (
    AdaptiveConfigManager,
    ConfigExplainer,
    ProjectProfiler,
)

logger = logging.getLogger(__name__)

# Maximum number of characters from log messages to include in context updates
MAX_LOG_LEN = 500


@dataclass
class IntegrationMetrics:
    """Metrics for coordinator context integration."""

    context_optimizations: int = 0
    planning_contexts: int = 0
    pre_planning_contexts: int = 0
    error_recoveries: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    total_context_time: float = 0.0
    average_context_time: float = 0.0


class CoordinatorContextIntegration:
    """
    Enhanced integration layer between Coordinator and Context Management.

    This class provides methods to integrate context management with the
    Coordinator's workflow, allowing context to be optimized at key points
    with improved error handling and performance monitoring.
    """

    def __init__(
        self, coordinator: Any, context_manager: Optional[ContextManager] = None
    ):
        """
        Initialize with a coordinator instance and optional context manager.

        Args:
            coordinator: The Coordinator instance
            context_manager: Optional ContextManager instance (will create if not provided)
        """
        self.coordinator = coordinator
        self.adaptive_config_manager = None
        self.config_explainer = None
        self.metrics = IntegrationMetrics()
        self._context_cache: Dict[str, Any] = {}
        self._integration_health = True

        # Determine repository path from coordinator
        self.repo_path = self._get_repository_path()

        # Create context manager if not provided
        if context_manager is None:
            config = coordinator.config.config if hasattr(coordinator, "config") else {}

            # Initialize context management configuration if not present
            if "context_management" not in config:
                config["context_management"] = {
                    "optimization_interval": 60,
                    "compression_threshold": 8000,
                    "checkpoint_interval": 300,
                    "max_checkpoints": 10,
                    "adaptive_config": {"metrics_collection": True},
                }

            # Initialize adaptive configuration (always enabled)
            self._setup_adaptive_configuration(config)

            # If we have an adaptive config manager, use its config
            if self.adaptive_config_manager:
                adaptive_config = self.adaptive_config_manager.get_current_config()
                if adaptive_config and "context_management" in adaptive_config:
                    # Merge the adaptive config with the base config
                    config["context_management"].update(
                        adaptive_config["context_management"]
                    )
                    logger.info("Using adaptive configuration for context management")

            self.context_manager = ContextManager(config)

            # Connect context manager to adaptive configuration
            if self.adaptive_config_manager:
                self.context_manager.set_adaptive_config_manager(
                    self.adaptive_config_manager
                )
        else:
            self.context_manager = context_manager

    def _get_repository_path(self) -> Optional[str]:
        """
        Get the repository path from the coordinator.

        Returns:
            Repository path or None if not available
        """
        # Try different ways to get repository path depending on coordinator implementation
        if hasattr(self.coordinator, "workspace_dir"):
            return self.coordinator.workspace_dir
        elif hasattr(self.coordinator, "repo_path"):
            return self.coordinator.repo_path
        elif hasattr(self.coordinator, "project_root"):
            return self.coordinator.project_root
        elif hasattr(self.coordinator, "config") and hasattr(
            self.coordinator.config, "project_path"
        ):
            return self.coordinator.config.project_path

        # If we can't find it, log a warning and return None
        logger.warning("Could not determine repository path from coordinator")
        return None

    def _setup_adaptive_configuration(self, config: Dict[str, Any]) -> None:
        """
        Set up the adaptive configuration system.

        Args:
            config: Configuration dictionary
        """
        if not self.repo_path:
            logger.warning(
                "Cannot set up adaptive configuration without repository path"
            )
            return

        try:
            # Determine configuration directory
            config_dir = (
                config.get("context_management", {})
                .get("adaptive_config", {})
                .get("config_dir")
            )

            if not config_dir:
                config_dir = os.path.join(self.repo_path, ".agent_s3", "config")

            # Create config directory if it doesn't exist
            os.makedirs(config_dir, exist_ok=True)

            # Initialize adaptive config manager
            self.adaptive_config_manager = AdaptiveConfigManager(
                repo_path=self.repo_path, config_dir=config_dir
            )

            # Initialize config explainer
            self.config_explainer = ConfigExplainer(self.adaptive_config_manager)

            logger.info("Initialized adaptive configuration system in %s", config_dir)
        except Exception as e:
            logger.error("Failed to set up adaptive configuration: %s", e)
            logger.debug(traceback.format_exc())

    def integrate(self) -> bool:
        """
        Integrate context management with the Coordinator.

        This method adds hooks to various Coordinator methods to enable
        context management at key points in the workflow.

        Returns:
            True if integration was successful, False otherwise
        """
        try:
            # Register file modification tracking
            self._integrate_file_tracking()

            # Register memory management integration
            self._integrate_memory_management()

            # Register router agent integration
            self._integrate_router_agent()

            # Register with enhanced scratchpad
            self._integrate_enhanced_scratchpad()

            # Register configuration monitoring and optimization
            self._integrate_config_monitoring()

            # Add context manager as a property of the coordinator
            self.coordinator.context_manager = self.context_manager

            # Add adaptive configuration services to the coordinator (if available)
            if self.adaptive_config_manager:
                self.coordinator.adaptive_config_manager = self.adaptive_config_manager
                self.coordinator.config_explainer = self.config_explainer

                # Add config explanation method to coordinator
                def get_config_explanation():
                    """Get a human-readable explanation of the current configuration"""
                    if self.config_explainer:
                        return self.config_explainer.get_human_readable_report()
                    return "Configuration explanation not available"

                setattr(
                    self.coordinator, "get_config_explanation", get_config_explanation
                )

            # Register shutdown hook
            self._integrate_shutdown_hook()

            logger.info("Successfully integrated context management with Coordinator")
            return True

        except Exception as e:
            logger.error(
                "Failed to integrate context management with Coordinator: %s", e
            )
            logger.debug(traceback.format_exc())
            return False

    def _integrate_file_tracking(self) -> None:
        """
        Integrate with file modification tracking functionality.
        """
        # Save original function
        original_get_file_modification_info = getattr(
            self.coordinator, "get_file_modification_info", None
        )

        if original_get_file_modification_info is None:
            logger.warning(
                "Couldn't find get_file_modification_info method on Coordinator"
            )
            return

        # Create patched function
        def patched_get_file_modification_info():
            """Patched version that updates context manager with file info"""
            # Call original function
            file_info = original_get_file_modification_info()

            # Update context manager
            if file_info:
                self.context_manager.update_context(
                    {"file_modification_info": file_info}
                )

            return file_info

        # Apply patch
        setattr(
            self.coordinator,
            "get_file_modification_info",
            patched_get_file_modification_info,
        )

    def _integrate_memory_management(self) -> None:
        """
        Integrate with memory management functionality.
        """
        # Check if memory manager exists
        if not hasattr(self.coordinator, "memory_manager"):
            logger.warning("Couldn't find memory_manager on Coordinator")
            return

        memory_manager = self.coordinator.memory_manager

        # Save original function
        original_add_memory = getattr(memory_manager, "add_memory", None)
        original_retrieve_memory = getattr(memory_manager, "retrieve_memories", None)

        if original_add_memory is not None:
            # Create patched function
            def patched_add_memory(text, metadata=None):
                """Patched version that updates context manager with new memories"""
                # Call original function
                result = original_add_memory(text, metadata)

                # Update context manager in background
                if text:
                    self.context_manager.update_context(
                        {"recent_memories": {"text": text, "metadata": metadata or {}}}
                    )

                return result

            # Apply patch
            setattr(memory_manager, "add_memory", patched_add_memory)

        if original_retrieve_memory is not None:
            # Create patched function
            def patched_retrieve_memories(query, limit=5):
                """Patched version that updates context manager with retrieved memories"""
                # Call original function
                memories = original_retrieve_memory(query, limit)

                # Update context manager in background
                if memories:
                    self.context_manager.update_context(
                        {"retrieved_memories": memories}
                    )

                return memories

            # Apply patch
            setattr(memory_manager, "retrieve_memories", patched_retrieve_memories)

    def _integrate_router_agent(self) -> None:
        """
        Integrate with router agent functionality.
        """
        # Check if router agent exists
        if not hasattr(self.coordinator, "router_agent"):
            logger.warning("Couldn't find router_agent on Coordinator")
            return

        router_agent = self.coordinator.router_agent

        # Save original function
        original_route = getattr(router_agent, "route", None)

        if original_route is not None:
            # Create patched function
            def patched_route(prompt, **kwargs):
                """Patched version that optimizes prompt context before routing"""
                # Get model name from kwargs or default
                model_name = kwargs.get("model", "default")

                # Extract context from prompt
                context = {}
                if isinstance(prompt, dict) and "context" in prompt:
                    context = prompt["context"]
                elif isinstance(prompt, str):
                    # Simple prompt, extract code blocks as context
                    import re

                    code_blocks = {}
                    code_pattern = r"```(?:(?P<lang>\w+)\n)?(?P<code>.*?)```"
                    matches = re.finditer(code_pattern, prompt, re.DOTALL)
                    for i, match in enumerate(matches, 1):
                        lang = match.group("lang") or "txt"
                        code = match.group("code").strip()
                        file_path = f"code_block_{i}.{lang}"
                        code_blocks[file_path] = code

                    if code_blocks:
                        context["code_context"] = code_blocks

                        # Convert string prompt to dict with context
                        prompt = {"prompt": prompt, "context": context}

                # Optimize context if available
                if context:
                    optimized_context = self.context_manager.optimize_context(
                        context, model_name
                    )

                    # Always use direct context parameter approach
                    if isinstance(prompt, dict):
                        prompt["context"] = optimized_context
                    else:
                        # Convert any string prompt to a dict with context
                        prompt = {"prompt": prompt, "context": optimized_context}

                # Call original function with optimized prompt
                return original_route(prompt, **kwargs)

            # Apply patch
            setattr(router_agent, "route", patched_route)

            # Patch call_llm_by_role if it exists
            original_call_llm = getattr(router_agent, "call_llm_by_role", None)
            if original_call_llm is not None:

                def patched_call_llm_by_role(
                    role, system_prompt, user_prompt, *args, **kwargs
                ):
                    """Patched version that optimizes context when calling LLMs by role"""
                    # Extract code context from kwargs if present
                    code_context = kwargs.get("code_context", {})
                    tech_stack = kwargs.get("tech_stack", {})

                    # Create context for optimization if there's code context
                    if code_context:
                        context = {"code_context": code_context}
                        if tech_stack:
                            context["tech_stack"] = tech_stack

                        # Get model name from the role if possible
                        model_info = router_agent._models_by_role.get(role, {})
                        model_name = model_info.get("model", "default")

                        # Optimize the context
                        optimized = self.context_manager.optimize_context(
                            context, model_name
                        )

                        # Update kwargs with optimized context
                        if "code_context" in optimized:
                            kwargs["code_context"] = optimized["code_context"]

                    # Call original function with optimized context
                    return original_call_llm(
                        role, system_prompt, user_prompt, *args, **kwargs
                    )

                # Apply patch
                setattr(router_agent, "call_llm_by_role", patched_call_llm_by_role)

    def _integrate_enhanced_scratchpad(self) -> None:
        """
        Integrate with enhanced scratchpad functionality.
        """
        # Check if enhanced scratchpad exists
        if not hasattr(self.coordinator, "scratchpad"):
            logger.warning("Couldn't find scratchpad on Coordinator")
            return

        scratchpad = self.coordinator.scratchpad

        # Save original function
        original_log = getattr(scratchpad, "log", None)

        if original_log is not None:
            # Create patched function
            def patched_log(role, message, level=None, section=None, metadata=None):
                """Patched version that updates context manager with log entries"""
                # Call original function
                result = original_log(role, message, level, section, metadata)

                # Update context manager in background (only for significant logs)
                if level in ["WARNING", "ERROR"] or section is not None:
                    self.context_manager.update_context(
                        {
                            "recent_logs": {
                                "role": role,
                                "message": message[:MAX_LOG_LEN] if message else "",
                                "level": level,
                                "section": section,
                                "metadata": metadata or {},
                            }
                        }
                    )

                return result

            # Apply patch
            setattr(scratchpad, "log", patched_log)

    def _integrate_shutdown_hook(self) -> None:
        """
        Integrate with coordinator shutdown to ensure proper context management cleanup.
        """
        # Save original shutdown function
        original_shutdown = getattr(self.coordinator, "shutdown", None)

        if original_shutdown is None:
            logger.warning("Couldn't find shutdown method on Coordinator")
            return

        # Create patched shutdown function
        def patched_shutdown():
            """Patched shutdown that ensures context manager is properly stopped"""
            # Stop background context optimization
            if (
                hasattr(self.coordinator, "context_manager")
                and self.coordinator.context_manager
            ):
                logger.info("Stopping context management background optimization")
                self.coordinator.context_manager._stop_background_optimization()

                # Save metrics and finalize adaptive configuration
                if (
                    hasattr(self.coordinator.context_manager, "adaptive_config_manager")
                    and self.coordinator.context_manager.adaptive_config_manager
                ):
                    logger.info("Finalizing adaptive configuration metrics")
                    try:
                        # Nothing to do here, metrics are saved automatically by the metrics collector
                        pass
                    except Exception as e:
                        logger.error("Error finalizing adaptive configuration: %s", e)

            # Call original shutdown
            return original_shutdown()

        # Apply patch
        setattr(self.coordinator, "shutdown", patched_shutdown)

    def _integrate_config_monitoring(self) -> None:
        """
        Integrate with coordinator to monitor and optimize configuration.
        """
        # Only proceed if we have an adaptive config manager
        if not self.adaptive_config_manager:
            return

        # Save original completion handler if it exists
        original_handle_completion = getattr(
            self.coordinator, "handle_completion", None
        )

        if original_handle_completion:
            # Create a patched handler
            def patched_handle_completion(result, *args, **kwargs):
                """Patched completion handler that logs metrics for adaptive configuration"""
                # Call original handler
                response = original_handle_completion(result, *args, **kwargs)

                # Log context performance metrics after completion
                try:
                    # Extract relevance information if available
                    relevance_score = 0.8  # Default assumption
                    if isinstance(result, dict) and "relevance" in result:
                        relevance_score = float(result["relevance"])
                    elif isinstance(result, dict) and "context_quality" in result:
                        relevance_score = float(result["context_quality"])

                    # Determine task type
                    task_type = "general"
                    if isinstance(result, dict) and "task_type" in result:
                        task_type = result["task_type"]
                    elif hasattr(self.coordinator, "current_task_type"):
                        task_type = self.coordinator.current_task_type

                    # Log performance metrics
                    self.adaptive_config_manager.log_context_performance(
                        task_type=task_type, relevance_score=relevance_score
                    )

                    # Check if optimization is needed
                    if self.adaptive_config_manager.check_optimization_needed():
                        logger.info("Running adaptive configuration optimization")
                        self.adaptive_config_manager.optimize_configuration()

                except Exception as e:
                    logger.error("Error logging adaptive configuration metrics: %s", e)

                return response

            # Apply the patch
            setattr(self.coordinator, "handle_completion", patched_handle_completion)

    def _update_context_cache(self, key: str, value: Any) -> None:
        """
        Update the context cache with a new value.

        Args:
            key: Cache key
            value: Cache value
        """
        self._context_cache[key] = value

    def _get_context_cache(self, key: str) -> Any:
        """
        Get a value from the context cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not present
        """
        return self._context_cache.get(key)

    def _optimize_context_with_cache(
        self, context: Dict[str, Any], model_name: str
    ) -> Dict[str, Any]:
        """
        Optimize context using the context manager, with caching support.

        Args:
            context: Input context
            model_name: Model name for optimization

        Returns:
            Optimized context
        """
        cache_key = f"{model_name}:{hash(frozenset(context.items()))}"

        # Check cache first
        cached_result = self._get_context_cache(cache_key)
        if cached_result is not None:
            logger.info("Cache hit for context optimization")
            self.metrics.cache_hits += 1
            return cached_result

        # If not cached, optimize context
        logger.info("Optimizing context")
        self.metrics.cache_misses += 1
        optimized_context = self.context_manager.optimize_context(context, model_name)

        # Update cache with new result
        self._update_context_cache(cache_key, optimized_context)

        return optimized_context

    def _measure_context_optimization_time(
        self, context: Dict[str, Any], model_name: str
    ) -> float:
        """
        Measure the time taken to optimize context.

        Args:
            context: Input context
            model_name: Model name for optimization

        Returns:
            Time taken in seconds
        """
        start_time = time.time()
        self.context_manager.optimize_context(context, model_name)
        end_time = time.time()

        elapsed_time = end_time - start_time
        self.metrics.total_context_time += elapsed_time
        self.metrics.average_context_time = self.metrics.total_context_time / (
            self.metrics.context_optimizations + 1
        )

        return elapsed_time

    def _recover_from_error(self, error: Exception) -> None:
        """
        Recover from an error during integration.

        Args:
            error: The error that occurred
        """
        logger.error("Error during integration: %s", error)
        self.metrics.error_recoveries += 1

        # Attempt to reset configuration as a recovery action
        if hasattr(self.coordinator, "adaptive_config_manager"):
            logger.info("Attempting to reset configuration to recover")
            try:
                self.coordinator.adaptive_config_manager.reset_to_default()
                logger.info("Configuration reset successfully")
            except Exception as e:
                logger.error("Failed to reset configuration: %s", e)

        # Fallback to basic context manager integration if available
        if hasattr(self.coordinator, "context_manager"):
            logger.info("Falling back to basic context manager integration")
            self.coordinator.context_manager._stop_background_optimization()
            self.coordinator.context_manager = None

        # Mark integration as unhealthy
        self._integration_health = False

    def is_integration_healthy(self) -> bool:
        """
        Check if the integration is healthy.

        Returns:
            True if healthy, False otherwise
        """
        return self._integration_health

    def get_integration_metrics(self) -> Dict[str, Any]:
        """
        Get comprehensive metrics about the coordinator integration.

        Returns:
            Dictionary with integration metrics and health status
        """
        cache_hit_rate = 0.0
        if (self.metrics.cache_hits + self.metrics.cache_misses) > 0:
            cache_hit_rate = self.metrics.cache_hits / (
                self.metrics.cache_hits + self.metrics.cache_misses
            )

        return {
            "integration_health": self._integration_health,
            "context_optimizations": self.metrics.context_optimizations,
            "planning_contexts": self.metrics.planning_contexts,
            "pre_planning_contexts": self.metrics.pre_planning_contexts,
            "error_recoveries": self.metrics.error_recoveries,
            "cache_hits": self.metrics.cache_hits,
            "cache_misses": self.metrics.cache_misses,
            "cache_hit_rate": cache_hit_rate,
            "cache_size": len(self._context_cache),
            "total_context_time": self.metrics.total_context_time,
            "average_context_time": self.metrics.average_context_time,
            "context_manager_available": self.context_manager is not None,
            "adaptive_config_available": self.adaptive_config_manager is not None,
            "repository_path": self.repo_path,
        }

    def get_context_for_planning(self, task_description: str, **kwargs) -> str:
        """
        Get optimized context for planning workflows.

        Args:
            task_description: Description of the planning task
            **kwargs: Additional context parameters

        Returns:
            Formatted context string for planning
        """
        start_time = time.time()
        cache_key = (
            f"planning:{hash(task_description)}:{hash(str(sorted(kwargs.items())))}"
        )

        # Check cache first
        if cache_key in self._context_cache:
            self.metrics.cache_hits += 1
            self.metrics.planning_contexts += 1
            return self._context_cache[cache_key]

        self.metrics.cache_misses += 1

        try:
            # Gather context using modern API
            context_data = self.context_manager.gather_context(
                task_description=task_description,
                task_type="planning",
                **kwargs,
            )

            self.metrics.planning_contexts += 1
            context_time = time.time() - start_time
            self.metrics.total_context_time += context_time
            self.metrics.average_context_time = self.metrics.total_context_time / (
                self.metrics.planning_contexts + self.metrics.pre_planning_contexts
            )

            # Cache the result
            self._context_cache[cache_key] = context_data

            return context_data

        except Exception as e:
            logger.error(f"Error getting planning context: {e}")
            self.metrics.error_recoveries += 1
            self._integration_health = False
            return f"Context retrieval failed: {str(e)}"

    def get_context_for_pre_planning(self, query: str, **kwargs) -> str:
        """
        Get optimized context for pre-planning workflows.

        Args:
            query: Pre-planning query
            **kwargs: Additional context parameters

        Returns:
            Formatted context string for pre-planning
        """
        start_time = time.time()
        cache_key = f"pre_planning:{hash(query)}:{hash(str(sorted(kwargs.items())))}"

        # Check cache first
        if cache_key in self._context_cache:
            self.metrics.cache_hits += 1
            self.metrics.pre_planning_contexts += 1
            return self._context_cache[cache_key]

        self.metrics.cache_misses += 1

        try:
            # Gather context using modern API
            context_data = self.context_manager.gather_context(
                task_description=query,
                task_type="pre_planning",
                **kwargs,
            )

            self.metrics.pre_planning_contexts += 1
            context_time = time.time() - start_time
            self.metrics.total_context_time += context_time
            self.metrics.average_context_time = self.metrics.total_context_time / (
                self.metrics.planning_contexts + self.metrics.pre_planning_contexts
            )

            # Cache the result
            self._context_cache[cache_key] = context_data

            return context_data

        except Exception as e:
            logger.error(f"Error getting pre-planning context: {e}")
            self.metrics.error_recoveries += 1
            self._integration_health = False
            return f"Context retrieval failed: {str(e)}"

    def optimize_context_for_workflow(
        self, workflow_stage: str, context_hint: Optional[str] = None
    ) -> None:
        """
        Optimize context management for specific workflow stages.

        Args:
            workflow_stage: Current workflow stage (e.g., 'planning', 'execution', 'review')
            context_hint: Optional hint about what context might be needed
        """
        try:
            if hasattr(self.context_manager, "optimize_for_workflow"):
                self.context_manager.optimize_for_workflow(workflow_stage, context_hint)
                self.metrics.context_optimizations += 1
                logger.debug(f"Context optimized for workflow stage: {workflow_stage}")
            else:
                logger.warning("Context manager does not support workflow optimization")

        except Exception as e:
            logger.error(f"Error optimizing context for workflow {workflow_stage}: {e}")
            self.metrics.error_recoveries += 1

    def health_check(self) -> Dict[str, Any]:
        """
        Perform a comprehensive health check of the integration.

        Returns:
            Dictionary with health check results
        """
        health_results = {
            "overall_health": True,
            "context_manager": False,
            "adaptive_config": False,
            "coordinator_integration": False,
            "cache_system": False,
            "errors": [],
        }

        try:
            # Check context manager
            if self.context_manager:
                # Try a simple context retrieval
                self.context_manager.get_context("health_check_test", max_results=1)
                health_results["context_manager"] = True
            else:
                health_results["errors"].append("Context manager not available")

        except Exception as e:
            health_results["errors"].append(f"Context manager error: {str(e)}")

        try:
            # Check adaptive config
            if self.adaptive_config_manager:
                config = self.adaptive_config_manager.get_current_config()
                health_results["adaptive_config"] = config is not None
            else:
                health_results["errors"].append("Adaptive config manager not available")

        except Exception as e:
            health_results["errors"].append(f"Adaptive config error: {str(e)}")

        try:
            # Check coordinator integration
            if (
                hasattr(self.coordinator, "context_manager")
                and self.coordinator.context_manager
            ):
                health_results["coordinator_integration"] = True
            else:
                health_results["errors"].append("Coordinator integration not active")

        except Exception as e:
            health_results["errors"].append(f"Coordinator integration error: {str(e)}")

        # Check cache system
        health_results["cache_system"] = isinstance(self._context_cache, dict)

        # Overall health
        health_results["overall_health"] = (
            health_results["context_manager"]
            and health_results["coordinator_integration"]
            and health_results["cache_system"]
            and len(health_results["errors"]) == 0
        )

        return health_results

    def clear_cache(self) -> None:
        """Clear the integration cache."""
        cache_size = len(self._context_cache)
        self._context_cache.clear()
        logger.info(f"Cleared integration cache ({cache_size} entries)")

    def reset_metrics(self) -> None:
        """Reset integration metrics."""
        self.metrics = IntegrationMetrics()
        logger.info("Integration metrics reset")


def setup_context_management(coordinator):
    """
    Set up context management for the coordinator.

    Args:
        coordinator: The Coordinator instance

    Returns:
        True if setup was successful, False otherwise
    """
    try:
        # Check if context management is already set up
        if hasattr(coordinator, "context_manager") and coordinator.context_manager:
            logger.info("Context management already set up for coordinator")
            return True

        # Create context manager through integration
        config = coordinator.config.config if hasattr(coordinator, "config") else {}

        # Initialize context management configuration if not present
        if "context_management" not in config:
            config["context_management"] = {
                "optimization_interval": 60,
                "compression_threshold": 8000,
                "checkpoint_interval": 300,
                "max_checkpoints": 10,
                "adaptive_config": {"metrics_collection": True},
            }

        # Set up coordinator integration - this will create the context manager internally
        coordinator_integration = CoordinatorContextIntegration(coordinator)
        integration_result = coordinator_integration.integrate()

        if not integration_result:
            logger.error("Failed to integrate context management with coordinator")
            return False

        # Get the context manager that was created during integration
        context_manager = coordinator.context_manager

        # Set up LLM integration
        from agent_s3.tools.context_management.llm_integration import (
            integrate_with_llm_utils,
        )

        llm_integration_result = integrate_with_llm_utils()

        if not llm_integration_result:
            logger.warning("Failed to integrate context management with LLM utilities")
            # Continue anyway as this is not critical

        # Create initial checkpoints for important context
        if hasattr(coordinator, "tech_stack") and coordinator.tech_stack:
            context_manager.update_context({"tech_stack": coordinator.tech_stack})

            # If we have adaptive config, update the tech stack info there too
            if (
                hasattr(coordinator, "adaptive_config_manager")
                and coordinator.adaptive_config_manager
            ):
                # This tech stack info could potentially be used for future config optimizations
                logger.info(
                    "Tech stack information provided to adaptive configuration system"
                )

        # Start background optimization (always enabled)
        context_manager._start_background_optimization()

        # Log successful setup
        setup_message = "Context management system initialized and integrated"
        if (
            hasattr(coordinator, "adaptive_config_manager")
            and coordinator.adaptive_config_manager
        ):
            setup_message += " with adaptive configuration enabled"

        if hasattr(coordinator, "scratchpad"):
            coordinator.scratchpad.log("ContextManager", setup_message)

        logger.info(setup_message)
        return True

    except Exception as e:
        # Log error
        logger.error("Failed to set up context management: %s", e)
        logger.debug(traceback.format_exc())

        if hasattr(coordinator, "scratchpad"):
            coordinator.scratchpad.log(
                "ContextManager",
                f"Failed to set up context management: {e}",
                level="ERROR",
            )

        return False


def get_configuration_report(coordinator):
    """
    Get a human-readable report of the current configuration.

    Args:
        coordinator: The Coordinator instance

    Returns:
        String with human-readable configuration report
    """
    if not hasattr(coordinator, "config_explainer") or not coordinator.config_explainer:
        return "Configuration explanation not available"

    try:
        return coordinator.config_explainer.get_human_readable_report()
    except Exception as e:
        logger.error("Failed to get configuration report: %s", e)
        return f"Error generating configuration report: {e}"


def optimize_configuration(coordinator, reason: str = "Manual optimization"):
    """
    Trigger manual optimization of the configuration.

    Args:
        coordinator: The Coordinator instance
        reason: Reason for optimization

    Returns:
        Tuple of (success, message)
    """
    if (
        not hasattr(coordinator, "adaptive_config_manager")
        or not coordinator.adaptive_config_manager
    ):
        return False, "Adaptive configuration not available"

    try:
        # Force optimization
        result = coordinator.adaptive_config_manager.optimize_configuration()

        if result:
            return True, "Configuration optimized successfully"
        else:
            return False, "No changes made to configuration"
    except Exception as e:
        logger.error("Failed to optimize configuration: %s", e)
        return False, f"Error optimizing configuration: {e}"


def reset_configuration(coordinator):
    """
    Reset configuration to default profile-based settings.

    Args:
        coordinator: The Coordinator instance

    Returns:
        Tuple of (success, message)
    """
    if (
        not hasattr(coordinator, "adaptive_config_manager")
        or not coordinator.adaptive_config_manager
    ):
        return False, "Adaptive configuration not available"

    try:
        result = coordinator.adaptive_config_manager.reset_to_default()

        if result:
            return True, "Configuration reset to default profile-based settings"
        else:
            return False, "Failed to reset configuration"
    except Exception as e:
        logger.error("Failed to reset configuration: %s", e)
        return False, f"Error resetting configuration: {e}"


def analyze_repository_profile(coordinator):
    """
    Analyze the repository profile and return characteristics.

    Args:
        coordinator: The Coordinator instance

    Returns:
        Dictionary with repository profile information
    """
    if not hasattr(coordinator, "context_manager") or not coordinator.context_manager:
        return {"error": "Context manager not available"}

    repo_path = None

    # Try different ways to get repository path
    if hasattr(coordinator, "workspace_dir"):
        repo_path = coordinator.workspace_dir
    elif hasattr(coordinator, "repo_path"):
        repo_path = coordinator.repo_path
    elif hasattr(coordinator, "project_root"):
        repo_path = coordinator.project_root
    elif hasattr(coordinator, "config") and hasattr(coordinator.config, "project_path"):
        repo_path = coordinator.config.project_path

    if not repo_path:
        return {"error": "Could not determine repository path"}

    try:
        profiler = ProjectProfiler(repo_path)
        return profiler.analyze_repository()
    except Exception as e:
        logger.error("Failed to analyze repository profile: %s", e)
        return {"error": str(e)}
