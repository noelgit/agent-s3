"""
Context Manager component that orchestrates token budget and compression.

This module serves as the central orchestrator for context management,
providing background optimization and continuous adaptation of context.
"""

import copy
import threading
import time
import logging
from typing import Dict, Any, List, Optional, Union, Set
import os
from dataclasses import dataclass, field
from collections import defaultdict

from agent_s3.tools.context_management.context_size_monitor import (
    ContextSizeMonitor,
)
from agent_s3.tools.context_management.content_pruning_manager import (
    ContentPruningManager,
)
from enum import Enum, auto

from agent_s3.tools.context_management.compression import CompressionManager
from agent_s3.tools.context_management.token_budget import TokenBudgetAnalyzer, DynamicAllocationStrategy, TaskAdaptiveAllocation
from agent_s3.tools.context_management.context_adapter import ContextAdapter
from agent_s3.tools.context_management.adaptive_config import (
    AdaptiveConfigManager
)

logger = logging.getLogger(__name__)

class ToolCapability(Enum):
    """Enum defining capabilities that tools can provide to the context manager."""
    FILE_OPERATIONS = auto()
    TECH_STACK_DETECTION = auto()
    CODE_ANALYSIS = auto()
    FILE_HISTORY = auto()
    MEMORY_MANAGEMENT = auto()
    TEST_PLANNING = auto()
    TEST_FRAMEWORKS = auto()
    TOKEN_BUDGET = auto()
    COMPRESSION = auto()
    STATIC_ANALYSIS = auto()

@dataclass
class ToolRegistration:
    """Represents a registered tool with its capabilities and metadata."""
    tool: Any
    capabilities: Set[ToolCapability]
    name: str
    priority: int = 1  # Higher values indicate higher priority
    metadata: Dict[str, Any] = field(default_factory=dict)

class ToolRegistry:
    """
    Central registry for context manager tools providing capability-based lookup.

    Features:
    - Register tools with multiple capabilities
    - Lookup tools by capability with priority-based resolution
    - Track tool metadata and usage statistics
    - Dependency resolution between tools
    """

    def __init__(self):
        """Initialize the tool registry."""
        self._tools: Dict[str, ToolRegistration] = {}
        self._capabilities: Dict[ToolCapability, List[str]] = defaultdict(list)
        self._tool_dependencies: Dict[str, Set[str]] = defaultdict(set)
        self._usage_stats: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"access_count": 0, "last_access": 0})

    def register_tool(self, tool_name: str, tool: Any, capabilities: List[ToolCapability],
                     priority: int = 1, depends_on: List[str] = None) -> None:
        """
        Register a tool with its capabilities.

        Args:
            tool_name: Unique identifier for the tool
            tool: The tool instance
            capabilities: List of capabilities this tool provides
            priority: Priority level (higher is more preferred)
            depends_on: List of other tool names this tool depends on
        """
        # Create the registration
        registration = ToolRegistration(
            tool=tool,
            capabilities=set(capabilities),
            name=tool_name,
            priority=priority
        )

        # Store the tool registration
        self._tools[tool_name] = registration

        # Update capability mappings
        for capability in capabilities:
            # Insert based on priority
            tools_with_capability = self._capabilities[capability]

            # Find insertion point based on priority
            for i, existing_tool in enumerate(tools_with_capability):
                if self._tools[existing_tool].priority < priority:
                    tools_with_capability.insert(i, tool_name)
                    break
            else:
                tools_with_capability.append(tool_name)

        # Record dependencies if any
        if depends_on:
            self._tool_dependencies[tool_name].update(depends_on)

    def get_tool_by_capability(self, capability: ToolCapability) -> Optional[Any]:
        """
        Get the highest priority tool that provides the requested capability.

        Args:
            capability: The capability to look for

        Returns:
            The tool instance or None if no tool with the capability is registered
        """
        tools = self._capabilities.get(capability, [])
        if not tools:
            return None

        # Get highest priority tool
        tool_name = tools[0]
        # Update usage statistics
        self._usage_stats[tool_name]["access_count"] += 1
        self._usage_stats[tool_name]["last_access"] = time.time()

        return self._tools[tool_name].tool

    def get_all_tools_by_capability(self, capability: ToolCapability) -> List[Any]:
        """
        Get all tools that provide the requested capability in priority order.

        Args:
            capability: The capability to look for

        Returns:
            List of tool instances in priority order (highest first)
        """
        tools = []
        for tool_name in self._capabilities.get(capability, []):
            tools.append(self._tools[tool_name].tool)
            # Update usage statistics
            self._usage_stats[tool_name]["access_count"] += 1
            self._usage_stats[tool_name]["last_access"] = time.time()

        return tools

    def has_capability(self, capability: ToolCapability) -> bool:
        """
        Check if any registered tool provides the requested capability.

        Args:
            capability: The capability to check for

        Returns:
            True if at least one tool provides the capability, False otherwise
        """
        return len(self._capabilities.get(capability, [])) > 0

    def get_tool_by_name(self, tool_name: str) -> Optional[Any]:
        """
        Get a tool by its registered name.

        Args:
            tool_name: The name of the tool to retrieve

        Returns:
            The tool instance or None if no tool with that name is registered
        """
        if tool_name not in self._tools:
            return None

        # Update usage statistics
        self._usage_stats[tool_name]["access_count"] += 1
        self._usage_stats[tool_name]["last_access"] = time.time()

        return self._tools[tool_name].tool

    def get_tool_capabilities(self, tool_name: str) -> Set[ToolCapability]:
        """
        Get the capabilities provided by a specific tool.

        Args:
            tool_name: The name of the tool

        Returns:
            Set of capabilities the tool provides or empty set if tool not found
        """
        if tool_name not in self._tools:
            return set()

        return self._tools[tool_name].capabilities

    def get_dependent_tools(self, tool_name: str) -> List[str]:
        """
        Get the names of tools that depend on the specified tool.

        Args:
            tool_name: The name of the tool to find dependents for

        Returns:
            List of tool names that depend on the specified tool
        """
        dependent_tools = []
        for t_name, dependencies in self._tool_dependencies.items():
            if tool_name in dependencies:
                dependent_tools.append(t_name)

        return dependent_tools

    def get_tool_stats(self) -> Dict[str, Dict[str, Any]]:
        """
        Get usage statistics for all registered tools.

        Returns:
            Dictionary of tool usage statistics
        """
        return self._usage_stats

    def shutdown_all_tools(self) -> None:
        """
        Gracefully shutdown all tools that support it.
        """
        for tool_name, registration in self._tools.items():
            tool = registration.tool
            # Check if tool has a shutdown/close/cleanup method and call it
            for method_name in ["shutdown", "close", "cleanup"]:
                if hasattr(tool, method_name) and callable(getattr(tool, method_name)):
                    try:
                        getattr(tool, method_name)()
                        logger.debug("%s", Successfully shutdown tool: {tool_name})
                    except Exception as e:
                        logger.error("%s", Error shutting down tool {tool_name}: {e})


class ContextManager:
    """
    Orchestrates context management through background optimization.
    Implements all context provider interfaces for unified access, including
    a framework-aware dependency graph provider.

    NOTE: Interface Protocols are not inherited at runtime to avoid MRO errors.
    Use type annotations or isinstance checks for static type checking only.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the ContextManager with configuration.

        Args:
            config: Configuration dictionary (optional)
        """
        self.config = config or {}

        # Initialize the tool registry
        self._tool_registry = ToolRegistry()

        # Initialize adaptive configuration if enabled
        self.adaptive_config_manager = None
        if self.config.get("adaptive_config", {}).get("enabled", False):
            try:
                adaptive_config = self.config.get("adaptive_config", {})
                repo_path = adaptive_config.get("repo_path", os.getcwd())
                config_dir = adaptive_config.get("config_dir")
                metrics_dir = adaptive_config.get("metrics_dir")

                logger.info("%s", Initializing adaptive configuration for repository: {repo_path})
                self.adaptive_config_manager = AdaptiveConfigManager(
                    repo_path=repo_path,
                    config_dir=config_dir,
                    metrics_dir=metrics_dir
                )

                # Get the optimized configuration
                adaptive_settings = self.adaptive_config_manager.get_current_config()
                if adaptive_settings and "context_management" in adaptive_settings:
                    logger.info("%s", Using adaptive configuration (version {self.adaptive_config_manager.get_config_version()}))
                    # Update our configuration with the adaptive settings
                    self.config["context_management"] = adaptive_settings["context_management"]
            except Exception as e:
                logger.error("%s", Error initializing adaptive configuration: {e})
                logger.info("Falling back to default configuration")

        # Initialize basic components
        self.compression_manager = CompressionManager()

        # Get configuration values with adaptive settings or defaults
        cm_config = self.config.get("context_management", {})
        max_tokens = self.config.get("CONTEXT_BACKGROUND_OPT_TARGET_TOKENS", 16000)
        reserved_tokens = self.config.get("CONTEXT_RESERVED_TOKENS_FOR_PROMPT", 2000)

        self.token_budget_analyzer = TokenBudgetAnalyzer(
            max_tokens=max_tokens,
            reserved_tokens=reserved_tokens
        )
        self.context_adapter = ContextAdapter()

        # Set up allocation strategy with importance weights from adaptive config
        self.allocation_strategy = TaskAdaptiveAllocation(
            max_tokens=max_tokens,
            reserved_tokens=reserved_tokens
        )

        # Initialize memory management components
        self._context_size_monitor = ContextSizeMonitor(
            token_analyzer=self.token_budget_analyzer,
            max_tokens=max_tokens
        )
        self._pruning_manager = ContentPruningManager(
            token_analyzer=self.token_budget_analyzer
        )

        # Get configuration values for summarization from adaptive settings
        summarization_config = cm_config.get("summarization", {})
        self.compression_manager.set_summarization_threshold(
            summarization_config.get("threshold", 2000)
        )
        self.compression_manager.set_compression_ratio(
            summarization_config.get("compression_ratio", 0.5)
        )

        # Initialize state
        self.current_context: Dict[str, Any] = {}
        self._context_lock = threading.Lock()  # Lock for thread-safe access to current_context
        self.optimization_running = False
        self.optimization_thread = None
        self.last_optimization_time = 0
        self.optimization_interval = cm_config.get("optimization_interval", 60)  # seconds
        self.background_enabled = cm_config.get("background_enabled", True)

        # Register core tools
        self._tool_registry.register_tool(
            "token_budget_analyzer",
            self.token_budget_analyzer,
            [ToolCapability.TOKEN_BUDGET],
            priority=10  # Essential tool, give it high priority
        )

        self._tool_registry.register_tool(
            "compression_manager",
            self.compression_manager,
            [ToolCapability.COMPRESSION],
            priority=5
        )

        # Dependency graph state
        self._dependency_graph: Dict[str, Any] = {"nodes": {}, "edges": []}
        self._graph_last_updated: float = 0

        # Start background thread if enabled
        if self.background_enabled:
            self._start_background_optimization()

    def _get_relevant_files_from_graph(self, target_files: List[str], max_depth: int = 2) -> set:
        """
        Traverse the dependency graph to find related files up to max_depth.
        Returns a set of unique file paths.
        Traverses edges with appropriate directionality based on edge type:
        - 'import', 'use': source -> target (dependency direction)
        - 'contains': file -> element (parent -> child)
        - 'include': target -> source (what includes the target)
        - 'call': source -> target (caller -> callee)
        """
        graph = self.get_dependency_graph()
        nodes = graph.get('nodes', {})
        edges = graph.get('edges', [])
        # Map node IDs to file paths
        node_to_file = {nid: (n.get('path') or nid.split(':')[0]) for nid, n in nodes.items()}
        # Find starting file node IDs for target_files
        start_nodes = set()
        for f in target_files:
            for nid, n in nodes.items():
                if n.get('type') == 'file' and (n.get('path') == f or nid == f):
                    start_nodes.add(nid)
                # Also allow starting from code element nodes if file node not found
                elif n.get('path') == f:
                    start_nodes.add(nid)
        # BFS up to max_depth with directionally-aware edge traversal
        visited = set(start_nodes)
        queue = [(nid, 0) for nid in start_nodes]

        # Define edge traversal directions
        # source->target: import, use, call, inherit, implement, route_handler
        outgoing_edge_types = {'import', 'use', 'call', 'inherit', 'implement', 'route_handler'}
        # target->source: include, component_usage
        incoming_edge_types = {'include', 'component_usage'}
        # parent->child only: contains
        containment_edge_types = {'contains'}

        while queue:
            nid, depth = queue.pop(0)
            if depth >= max_depth:
                continue

            for e in edges:
                edge_type = e.get('type')

                # Skip edges with types we don't care about
                if edge_type not in (outgoing_edge_types | incoming_edge_types | containment_edge_types):
                    continue

                # Handle outgoing edges (follow dependencies)
                if edge_type in outgoing_edge_types and e.get('source') == nid:
                    tgt = e.get('target')
                    if tgt not in visited and tgt in nodes:
                        visited.add(tgt)
                        queue.append((tgt, depth + 1))

                # Handle incoming edges (what depends on this)
                elif edge_type in incoming_edge_types and e.get('target') == nid:
                    src = e.get('source')
                    if src not in visited and src in nodes:
                        visited.add(src)
                        queue.append((src, depth + 1))

                # Handle containment edges (parent->child only)
                elif edge_type in containment_edge_types and e.get('source') == nid:
                    tgt = e.get('target')
                    if tgt not in visited and tgt in nodes:
                        visited.add(tgt)
                        queue.append((tgt, depth + 1))
        # Collect file paths
        file_paths = set()
        for nid in visited:
            fpath = node_to_file.get(nid)
            if fpath:
                file_paths.add(fpath)
        return file_paths


    def get_nested_value(self, source_dict: Dict[str, Any], key_path: Union[str, List[str]],
         default: Any = None) -> Any:        """
        Get a value from a nested dictionary at any depth using a dot-notation key path or list of keys.

        Args:
            source_dict: The dictionary to retrieve from
            key_path: Either a dot-notation string ('a.b.c') or list of keys ['a', 'b', 'c']
            default: Value to return if the path doesn't exist

        Returns:
            The value at the specified path or the default value
        """
        if isinstance(key_path, str):
            keys = key_path.split('.')
        else:
            keys = key_path

        if not keys:
            return default

        # Navigate through the nested dictionary
        current = source_dict
        for key in keys:
            if not isinstance(current, dict) or key not in current:
                return default
            current = current[key]

        return current

    def _update_nested_dict(self, target_dict: Dict[str, Any], key_path: Union[str, List[str]],
         new_value: Any) -> None:        """
        Update a nested dictionary at any depth using a dot-notation key path or list of keys.

        Args:
            target_dict: The dictionary to update
            key_path: Either a dot-notation string ('a.b.c') or list of keys ['a', 'b', 'c']
            new_value: The value to set at the specified path
        """
        if isinstance(key_path, str):
            keys = key_path.split('.')
        else:
            keys = key_path

        if not keys:
            return

        # Navigate to the nested dictionary, creating intermediate dicts if needed
        current = target_dict
        for i, key in enumerate(keys[:-1]):
            if key not in current or not isinstance(current[key], dict):
                current[key] = {}
            current = current[key]

        # Set the value at the final level
        current[keys[-1]] = new_value

    def initialize_tools(self, tech_stack_detector=None, code_analysis_tool=None,
                        file_history_analyzer=None, file_tool=None,
                        memory_manager=None, test_planner=None, test_frameworks=None):
        """
        Initialize the tools required for context management.

        Args:
            tech_stack_detector: Tool for detecting tech stack
            code_analysis_tool: Tool for analyzing code
            file_history_analyzer: Tool for analyzing file history
            file_tool: Tool for file operations
            memory_manager: Tool for memory management
            test_planner: Tool for planning tests
            test_frameworks: Tool for checking test framework dependencies
        """
        # Register tools with capability-based mapping
        if tech_stack_detector:
            self._tool_registry.register_tool(
                "tech_stack_detector",
                tech_stack_detector,
                [ToolCapability.TECH_STACK_DETECTION],
                priority=8
            )

        if code_analysis_tool:
            self._tool_registry.register_tool(
                "code_analysis_tool",
                code_analysis_tool,
                [ToolCapability.CODE_ANALYSIS, ToolCapability.STATIC_ANALYSIS],
                priority=7
            )

        if file_history_analyzer:
            self._tool_registry.register_tool(
                "file_history_analyzer",
                file_history_analyzer,
                [ToolCapability.FILE_HISTORY],
                priority=5
            )

        if file_tool:
            self._tool_registry.register_tool(
                "file_tool",
                file_tool,
                [ToolCapability.FILE_OPERATIONS],
                priority=9  # High priority as many operations depend on file access
            )

        if memory_manager:
            self._tool_registry.register_tool(
                "memory_manager",
                memory_manager,
                [ToolCapability.MEMORY_MANAGEMENT],
                priority=6
            )

        if test_planner:
            self._tool_registry.register_tool(
                "test_planner",
                test_planner,
                [ToolCapability.TEST_PLANNING],
                priority=4
            )

        if test_frameworks:
            self._tool_registry.register_tool(
                "test_frameworks",
                test_frameworks,
                [ToolCapability.TEST_FRAMEWORKS],
                priority=3
            )

        # Log the initialized tools
        logger.info("%s", Context Manager initialized with {len(self._tool_registry._tools)} tools)

    def _start_background_optimization(self) -> None:
        """Start the background optimization thread."""
        if self.optimization_thread is not None and self.optimization_thread.is_alive():
            logger.warning("Background optimization thread already running")
            return

        self.optimization_running = True
        self.optimization_thread = threading.Thread(
            target=self._background_optimization_loop,
            daemon=True
        )
        self.optimization_thread.start()
        logger.debug("Started background optimization thread")

    def _stop_background_optimization(self) -> None:
        """Stop the background optimization thread."""
        self.optimization_running = False
        if self.optimization_thread and self.optimization_thread.is_alive():
            # Allow the thread to exit naturally
            self.optimization_thread.join(timeout=5.0)
            logger.debug("Stopped background optimization thread")

    def _background_optimization_loop(self) -> None:
        """Background thread that periodically optimizes the context."""
        while self.optimization_running:
            try:
                # Check if it's time to run optimization
                time_since_last = time.time() - self.last_optimization_time
                if time_since_last >= self.optimization_interval:
                    self._optimize_context()
                    self.last_optimization_time = time.time()

                # Sleep for a short time to avoid consuming too much CPU
                time.sleep(1.0)
            except Exception as e:
                logger.error("%s", Error in background optimization: {e})
                # Sleep longer after an error to avoid rapid error loops
                time.sleep(5.0)

    def _optimize_context(self) -> None:
        """
        Optimize the context to stay within token budget and maintain priority content.
        This method is called periodically by the background optimization thread
        or can be called directly to force optimization.
        Propagates task-keyword-boosted importance scores to ContentPruningManager before pruning.
        """
        # Skip if there's no context
        if not self.current_context:
            return
        with self._context_lock:
            context_copy = copy.deepcopy(self.current_context)
        try:
            self._context_size_monitor.update(context_copy)
            current_tokens = self._context_size_monitor.current_usage
            target_tokens = self.config.get("CONTEXT_BACKGROUND_OPT_TARGET_TOKENS", 16000)
            allocation_data = self.token_budget_analyzer.allocate_tokens(
                context_copy,
                task_type=None,  # Could be enhanced to use actual task_type if tracked
                task_keywords=None,
                force_optimization=False,
            )
            context_copy = allocation_data.get("optimized_context", context_copy)
            importance_scores = allocation_data.get("importance_scores", {})
            # Recalculate token usage after allocation in case the optimizer changed the context
            self._context_size_monitor.update(context_copy)
            current_tokens = self._context_size_monitor.current_usage
            # --- Begin: Comprehensive importance score propagation ---
            if importance_scores:  # Ensure the map is not empty
                for section_key, section_value in importance_scores.items():
                    if isinstance(section_value, dict):  # Handles nested structures like 'code_context'
                        for item_key, item_score in section_value.items():
                            full_key_path = f"{section_key}.{item_key}"
                            if self._pruning_manager:  # Defensive check
                                self._pruning_manager.set_importance(full_key_path, item_score)
                    elif isinstance(section_value, (float, int)):  # Handles direct scores for top-level sections
                        if self._pruning_manager:  # Defensive check
                            self._pruning_manager.set_importance(section_key, section_value)
                    else:
                        logger.warning("%s", Unexpected structure in importance_scores for section '{section_key}'. Type: {type(section_value)}. Skipping propagation for this section.)
            # --- End: Comprehensive importance score propagation ---
            if current_tokens > target_tokens:
                pruning_candidates = self._pruning_manager.identify_pruning_candidates(
                    context_copy, current_tokens, target_tokens
                )
                tokens_to_prune = current_tokens - target_tokens
                pruned_tokens = 0
                for key_path, value_score, token_count in pruning_candidates:
                    if pruned_tokens >= tokens_to_prune:
                        break
                    if value_score > 0.7:
                        continue
                    keys = key_path.split('.')
                    if len(keys) == 1:
                        if keys[0] in context_copy:
                            del context_copy[keys[0]]
                    else:
                        target_value = self.get_nested_value(context_copy, keys)
                        if isinstance(target_value, str) and len(target_value) > 100:
                            self._update_nested_dict(
                                context_copy,
                                keys,
                                target_value[:100] + "... [truncated during optimization]"
                            )
                        else:
                            parent_dict = self.get_nested_value(context_copy, keys[:-1])
                            if parent_dict and isinstance(parent_dict, dict):
                                if keys[-1] in parent_dict:
                                    del parent_dict[keys[-1]]
                    pruned_tokens += token_count
                    logger.debug(
                        "%s",
                        "Pruned %d tokens from %s (value score: %.2f)",
                        token_count,
                        key_path,
                        value_score,
                    )
            compressed_context = {}
            for key, value in context_copy.items():
                if isinstance(value, str) and len(value) > 1000:
                    compressed_context[key] = self.compression_manager.compress_text(value)
                elif isinstance(value, dict):
                    compressed_context[key] = value
                else:
                    compressed_context[key] = value
            with self._context_lock:
                self.current_context = compressed_context
        except Exception as e:
            logger.error("%s", Error during context optimization: {e})

    def optimize_context_immediately(self) -> None:
        """
        Force an immediate optimization of the context.

        This method can be called by clients to trigger optimization
        outside of the regular background schedule.
        """
        self._optimize_context()
        self.last_optimization_time = time.time()

    def _refine_current_context(self, files: List[str], max_tokens: int = None,
         task_keywords: Optional[List[str]] = None) -> None:        """
        Refine the current context based on the given files, token budget, and task keywords.

        Args:
            files: List of primary file paths to focus on.
            max_tokens: Optional maximum token budget for this refinement.
            task_keywords: Optional list of keywords from the task description.
        """
        if not max_tokens:
            max_tokens = self.config.get("CONTEXT_BACKGROUND_OPT_TARGET_TOKENS", 16000)

        # Get relevant files based on dependencies
        all_files = list(self._get_relevant_files_from_graph(files))

        # Prioritize explicitly requested files
        prioritized_files = files + [f for f in all_files if f not in files]

        # Allocate token budget
        file_tool = self._tool_registry.get_tool_by_capability(ToolCapability.FILE_OPERATIONS)
        if not file_tool:
            logger.warning("No file tool available for context refinement")
            return

        context_files = {}
        tokens_used = 0

        for file_path in prioritized_files:
            if tokens_used >= max_tokens:
                break

            try:
                content = file_tool.read_file(file_path)
                if not content:
                    continue

                content_tokens = self.token_budget_analyzer.get_token_count(content)

                # Skip extremely large files or truncate them
                if content_tokens > (max_tokens * 0.4):  # Skip if file would use >40% of budget
                    logger.info("%s", Skipping large file {file_path} ({content_tokens} tokens))
                    continue

                if tokens_used + content_tokens <= max_tokens:
                    context_files[file_path] = content
                    tokens_used += content_tokens
                else:
                    # We'd exceed budget - see if we can truncate
                    remaining_tokens = max_tokens - tokens_used
                    if remaining_tokens > 100:  # Only worth including if we can get a meaningful amount
                        truncated = content[:remaining_tokens * 4]  # Rough estimate of chars to tokens
                        truncated += "\n... [truncated due to token budget]"
                        context_files[file_path] = truncated
                        tokens_used = max_tokens  # Consider budget fully used
            except Exception as e:
                logger.error("%s", Error reading file {file_path}: {e})

        # Update the context with the refined file contents
        with self._context_lock:
            # Use _update_nested_dict for consistency
            self._update_nested_dict(self.current_context, "files", context_files)

    def gather_context(
        self,
        current_files: Optional[List[str]] = None,
        task_description: Optional[str] = None,
        task_type: Optional[str] = None,
        related_files: Optional[List[str]] = None,
        max_tokens: Optional[int] = None,
        task_keywords: Optional[List[str]] = None  # New parameter
    ) -> Dict[str, Any]:
        """
        Gather and optimize context based on various inputs.
        This is the primary method for external components to request context.

        Args:
            current_files: List of currently relevant file paths.
            task_description: Natural language description of the current task.
            task_type: Type of task (e.g., 'debugging', 'implementation').
            related_files: Additional files known to be related.
            max_tokens: Override for the maximum token budget for this specific call.
            task_keywords: Keywords extracted from the task description for relevance boosting.

        Returns:
            An optimized context dictionary.
        """
        # ...existing code...
        # Use the configured allocation strategy
        # The allocation strategy (e.g., TaskAdaptiveAllocation) should internally use task_keywords
        allocation_result = self.allocation_strategy.allocate(
            self.current_context,
            task_type=task_type,
            task_keywords=task_keywords,  # Pass keywords here
        )
        return allocation_result["optimized_context"]
        # ...existing code...

    def set_allocation_strategy(self, strategy: 'DynamicAllocationStrategy') -> None:
        """
        Set a new token allocation strategy for the ContextManager.
        This allows for dynamic changes in how context is prioritized and pruned.

        Args:
            strategy: An instance of a class that implements DynamicAllocationStrategy.
        """
        if not isinstance(strategy, DynamicAllocationStrategy): # Make sure DynamicAllocationStrategy is imported or defined
            raise ValueError("Strategy must be an instance of DynamicAllocationStrategy")

        logger.info("%s", Setting new allocation strategy: {strategy.__class__.__name__})
        self.allocation_strategy = strategy

    def set_adaptive_config_manager(self, adaptive_config_manager: 'AdaptiveConfigManager') -> None:
        """
        Connect this context manager to an adaptive configuration manager.

        Args:
            adaptive_config_manager: The AdaptiveConfigManager instance to use
        """
        logger.info("Connecting to adaptive configuration manager")
        self.adaptive_config_manager = adaptive_config_manager

        # Update our configuration with the adaptive settings
        if self.adaptive_config_manager:
            adaptive_settings = self.adaptive_config_manager.get_current_config()
            if adaptive_settings and "context_management" in adaptive_settings:
                # Get key parameters from the adaptive config
                cm_config = adaptive_settings.get("context_management", {})

                # Update embedding settings
                embedding_config = cm_config.get("embedding", {})
                if embedding_config:
                    chunk_size = embedding_config.get("chunk_size")
                    chunk_overlap = embedding_config.get("chunk_overlap")
                    max_chunks = embedding_config.get("max_chunks")
                    embedding_model = embedding_config.get("embedding_model")

                    if chunk_size:
                        logger.debug("%s", Using adaptive chunk size: {chunk_size})
                        self.config["embedding_chunk_size"] = chunk_size

                    if chunk_overlap:
                        logger.debug("%s", Using adaptive chunk overlap: {chunk_overlap})
                        self.config["embedding_chunk_overlap"] = chunk_overlap

                    if max_chunks:
                        logger.debug("%s", Using adaptive max chunks: {max_chunks})
                        self.config["embedding_max_chunks"] = max_chunks

                    if embedding_model:
                        logger.debug("%s", Using adaptive embedding model: {embedding_model})
                        self.config["embedding_model"] = embedding_model

                # Update search settings - BM25
                search_config = cm_config.get("search", {})
                bm25_config = search_config.get("bm25", {})
                if bm25_config:
                    k1 = bm25_config.get("k1")
                    b = bm25_config.get("b")
                    if k1:
                        logger.debug("%s", Using adaptive BM25 k1: {k1})
                        self.config.setdefault("search_params", {}).setdefault("bm25", {})["k1"] = k1
                    if b:
                        logger.debug("%s", Using adaptive BM25 b: {b})
                        self.config.setdefault("search_params", {}).setdefault("bm25", {})["b"] = b

                # Update vector search settings
                vector_config = search_config.get("vector", {})
                if vector_config:
                    top_k = vector_config.get("top_k")
                    similarity_threshold = vector_config.get("similarity_threshold")
                    similarity_metric = vector_config.get("similarity_metric")

                    if top_k:
                        logger.debug("%s", Using adaptive vector search top_k: {top_k})
                        self.config.setdefault("search_params", {}).setdefault("vector", {})["top_k"] = top_k

                    if similarity_threshold:
                        logger.debug("%s", Using adaptive similarity threshold: {similarity_threshold})
                        self.config.setdefault("search_params", {}).setdefault("vector", {})["similarity_threshold"] = similarity_threshold

                    if similarity_metric:
                        logger.debug("%s", Using adaptive similarity metric: {similarity_metric})
                        self.config.setdefault("search_params", {}).setdefault("vector", {})["similarity_metric"] = similarity_metric

                # Update hybrid search settings
                hybrid_config = search_config.get("hybrid", {})
                if hybrid_config:
                    bm25_weight = hybrid_config.get("bm25_weight")
                    vector_weight = hybrid_config.get("vector_weight")

                    if bm25_weight:
                        logger.debug("%s", Using adaptive hybrid search BM25 weight: {bm25_weight})
                        self.config.setdefault("search_params", {}).setdefault("hybrid", {})["bm25_weight"] = bm25_weight

                    if vector_weight:
                        logger.debug("%s", Using adaptive hybrid search vector weight: {vector_weight})
                        self.config.setdefault("search_params", {}).setdefault("hybrid", {})["vector_weight"] = vector_weight

                # Update summarization settings
                summarization_config = cm_config.get("summarization", {})
                if summarization_config:
                    threshold = summarization_config.get("threshold")
                    compression_ratio = summarization_config.get("compression_ratio")
                    min_tokens = summarization_config.get("min_tokens")
                    max_tokens = summarization_config.get("max_tokens")

                    if threshold:
                        logger.debug("%s", Using adaptive summarization threshold: {threshold})
                        self.compression_manager.set_summarization_threshold(threshold)
                        self.config.setdefault("summarization", {})["threshold"] = threshold

                    if compression_ratio:
                        logger.debug("%s", Using adaptive compression ratio: {compression_ratio})
                        self.compression_manager.set_compression_ratio(compression_ratio)
                        self.config.setdefault("summarization", {})["compression_ratio"] = compression_ratio

                    if min_tokens:
                        logger.debug("%s", Using adaptive min tokens for summarization: {min_tokens})
                        self.config.setdefault("summarization", {})["min_tokens"] = min_tokens

                    if max_tokens:
                        logger.debug("%s", Using adaptive max tokens for summarization: {max_tokens})
                        self.config.setdefault("summarization", {})["max_tokens"] = max_tokens

                # Update importance scoring weights
                importance_scoring = cm_config.get("importance_scoring", {})
                if importance_scoring and isinstance(self.allocation_strategy, TaskAdaptiveAllocation):
                    code_weight = importance_scoring.get("code_weight")
                    comment_weight = importance_scoring.get("comment_weight")
                    metadata_weight = importance_scoring.get("metadata_weight")
                    framework_weight = importance_scoring.get("framework_weight")
                    test_weight = importance_scoring.get("test_weight")
                    documentation_weight = importance_scoring.get("documentation_weight")

                    if code_weight:
                        logger.debug("%s", Using adaptive code weight: {code_weight})
                        self.allocation_strategy.code_weight = code_weight

                    if comment_weight:
                        logger.debug("%s", Using adaptive comment weight: {comment_weight})
                        self.allocation_strategy.comment_weight = comment_weight

                    if metadata_weight:
                        logger.debug("%s", Using adaptive metadata weight: {metadata_weight})
                        self.allocation_strategy.metadata_weight = metadata_weight

                    if framework_weight:
                        logger.debug("%s", Using adaptive framework weight: {framework_weight})
                        self.allocation_strategy.framework_weight = framework_weight

                    if test_weight and hasattr(self.allocation_strategy, 'test_weight'):
                        logger.debug("%s", Using adaptive test weight: {test_weight})
                        self.allocation_strategy.test_weight = test_weight

                    if documentation_weight and hasattr(self.allocation_strategy, 'documentation_weight'):
                        logger.debug("%s", Using adaptive documentation weight: {documentation_weight})
                        self.allocation_strategy.documentation_weight = documentation_weight

                    logger.debug("Updated importance weights from adaptive configuration")

                # Update token budget settings
                token_budget = cm_config.get("token_budget", {})
                if token_budget:
                    max_context_tokens = token_budget.get("max_context_tokens")
                    reserved_tokens = token_budget.get("reserved_tokens")

                    if max_context_tokens:
                        logger.debug("%s", Using adaptive max context tokens: {max_context_tokens})
                        self.token_budget_analyzer.max_tokens = max_context_tokens
                        if hasattr(self.allocation_strategy, 'max_tokens'):
                            self.allocation_strategy.max_tokens = max_context_tokens
                        if hasattr(self._context_size_monitor, 'max_tokens'):
                            self._context_size_monitor.max_tokens = max_context_tokens

                    if reserved_tokens:
                        logger.debug("%s", Using adaptive reserved tokens: {reserved_tokens})
                        self.token_budget_analyzer.reserved_tokens = reserved_tokens
                        if hasattr(self.allocation_strategy, 'reserved_tokens'):
                            self.allocation_strategy.reserved_tokens = reserved_tokens

                # Update background optimization settings
                background_opt = cm_config.get("background_optimization", {})
                if background_opt:
                    enabled = background_opt.get("enabled")
                    interval = background_opt.get("interval")

                    if enabled is not None:
                        logger.debug("%s", Setting background optimization enabled: {enabled})
                        self.background_enabled = enabled

                        # Start or stop background thread based on setting
                        if enabled and not self.optimization_thread:
                            self._start_background_optimization()
                        elif not enabled and self.optimization_thread:
                            self._stop_background_optimization()

                    if interval:
                        logger.debug("%s", Using adaptive optimization interval: {interval})
                        self.optimization_interval = interval

                # Update pruning settings for ContentPruningManager
                pruning_config = cm_config.get("pruning", {})
                if pruning_config and hasattr(self, '_pruning_manager'):
                    recency_weight = pruning_config.get("recency_weight")
                    frequency_weight = pruning_config.get("frequency_weight")
                    importance_weight = pruning_config.get("importance_weight")

                    if recency_weight:
                        logger.debug("%s", Using adaptive pruning recency weight: {recency_weight})
                        self._pruning_manager.recency_weight = recency_weight

                    if frequency_weight:
                        logger.debug("%s", Using adaptive pruning frequency weight: {frequency_weight})
                        self._pruning_manager.frequency_weight = frequency_weight

                    if importance_weight:
                        logger.debug("%s", Using adaptive pruning importance weight: {importance_weight})
                        self._pruning_manager.importance_weight = importance_weight

                logger.info("%s", Successfully applied adaptive configuration (version {self.adaptive_config_manager.get_config_version()}))

                # Register metrics callback if available
                if hasattr(self.adaptive_config_manager.metrics_collector, 'register_callback'):
                    try:
                        self.adaptive_config_manager.metrics_collector.register_callback(
                            'context_manager', self._collect_performance_metrics
                        )
                        logger.debug("Registered metrics callback for adaptive configuration")
                    except Exception as e:
                        logger.warning("%s", Failed to register metrics callback: {e})

    def _collect_performance_metrics(self) -> Dict[str, Any]:
        """
        Collect performance metrics for the adaptive configuration manager.

        Returns:
            Dictionary of metrics about context manager performance
        """
        metrics = {}

        # Collect token usage metrics
        if hasattr(self, '_context_size_monitor'):
            metrics['token_usage'] = {
                'current_tokens': self._context_size_monitor.current_usage,
                'max_tokens': self._context_size_monitor.max_tokens,
                'usage_ratio': self._context_size_monitor.current_usage / max(1, self._context_size_monitor.max_tokens),
                'section_breakdown': self._context_size_monitor.get_section_breakdown(),
                'growth_rate': self._context_size_monitor.get_growth_rate()
            }

        # Collect compression metrics if available
        if hasattr(self.compression_manager, 'get_compression_stats'):
            metrics['compression'] = self.compression_manager.get_compression_stats()

        # Add timing metrics
        metrics['timing'] = {
            'last_optimization': self.last_optimization_time,
            'optimization_interval': self.optimization_interval
        }

        return metrics

    # Implement ContextProvider interface methods
    def get_context(self) -> Dict[str, Any]:
        """Get the current context."""
        with self._context_lock:
            return copy.deepcopy(self.current_context)

    def update_context(self, updates: Dict[str, Any]) -> None:
        """
        Update the context with the provided updates.

        Args:
            updates: Dictionary of updates to apply to the context
        """
        with self._context_lock:
            for key, value in updates.items():
                self._update_nested_dict(self.current_context, key, value)

    def optimize_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Update and optimize the provided context.

        Args:
            context: New context dictionary to optimize.

        Returns:
            Optimized context dictionary.
        """
        with self._context_lock:
            self.current_context = copy.deepcopy(context)

        self._optimize_context()

        with self._context_lock:
            return copy.deepcopy(self.current_context)

    def clear_context(self) -> None:
        """Clear the entire context."""
        with self._context_lock:
            self.current_context = {}

    # Implement TechStackProvider interface methods
    def get_detected_frameworks(self) -> List[str]:
        """Get the list of detected frameworks in the project."""
        tech_detector = self._tool_registry.get_tool_by_capability(ToolCapability.TECH_STACK_DETECTION)
        if not tech_detector:
            return []

        try:
            return tech_detector.get_frameworks()
        except Exception as e:
            logger.error("%s", Error getting frameworks: {e})
            return []

    def get_tech_stack_details(self) -> Dict[str, Any]:
        """Get detailed information about the detected tech stack."""
        tech_detector = self._tool_registry.get_tool_by_capability(ToolCapability.TECH_STACK_DETECTION)
        if not tech_detector:
            return {}

        try:
            return tech_detector.get_tech_stack()
        except Exception as e:
            logger.error("%s", Error getting tech stack details: {e})
            return {}

    def get_package_dependencies(self) -> Dict[str, str]:
        """Get the package dependencies and their versions."""
        tech_detector = self._tool_registry.get_tool_by_capability(ToolCapability.TECH_STACK_DETECTION)
        if not tech_detector:
            return {}

        try:
            return tech_detector.get_dependencies()
        except Exception as e:
            logger.error("%s", Error getting package dependencies: {e})
            return {}

    # Implement FileContextProvider interface methods
    def get_file_content(self, file_path: str) -> Optional[str]:
        """
        Get the content of a specific file.

        Args:
            file_path: Path to the file

        Returns:
            File content or None if file not found
        """
        # First check if we already have it in context
        with self._context_lock:
            files = self.current_context.get("files", {})
            if file_path in files:
                return files[file_path]

        # Otherwise try to load it with the file tool
        file_tool = self._tool_registry.get_tool_by_capability(ToolCapability.FILE_OPERATIONS)
        if not file_tool:
            return None

        try:
            content = file_tool.read_file(file_path)

            # Add to context for future use
            with self._context_lock:
                files = self.current_context.get("files", {})
                files[file_path] = content
                self._update_nested_dict(self.current_context, "files", files)

            return content
        except Exception as e:
            logger.error("%s", Error reading file {file_path}: {e})
            return None

    def get_relevant_files(self, query: str) -> List[str]:
        """
        Get a list of files relevant to the given query.

        Args:
            query: Search query

        Returns:
            List of relevant file paths
        """
        try:
            # First try using code analysis tool if available
            code_tool = self._tool_registry.get_tool_by_capability(ToolCapability.CODE_ANALYSIS)
            if code_tool and hasattr(code_tool, "find_relevant_files"):
                return code_tool.find_relevant_files(query)

            # Fall back to simple file search
            file_tool = self._tool_registry.get_tool_by_capability(ToolCapability.FILE_OPERATIONS)
            if file_tool and hasattr(file_tool, "search_files"):
                return file_tool.search_files(query)

            return []
        except Exception as e:
            logger.error("%s", Error searching for relevant files: {e})
            return []

    # Implement ProjectContextProvider interface methods
    def get_project_structure(self) -> Dict[str, Any]:
        """Get the structure of the project."""
        file_tool = self._tool_registry.get_tool_by_capability(ToolCapability.FILE_OPERATIONS)
        if not file_tool or not hasattr(file_tool, "get_project_structure"):
            return {}

        try:
            return file_tool.get_project_structure()
        except Exception as e:
            logger.error("%s", Error getting project structure: {e})
            return {}

    def get_current_working_directory(self) -> str:
        """Get the current working directory."""
        file_tool = self._tool_registry.get_tool_by_capability(ToolCapability.FILE_OPERATIONS)
        if not file_tool or not hasattr(file_tool, "get_cwd"):
            return ""

        try:
            return file_tool.get_cwd()
        except Exception as e:
            logger.error("%s", Error getting current working directory: {e})
            return ""

    # Implement TestContextProvider interface methods
    def get_test_frameworks(self) -> List[str]:
        """Get the list of test frameworks used in the project."""
        test_frameworks = self._tool_registry.get_tool_by_capability(ToolCapability.TEST_FRAMEWORKS)
        if not test_frameworks:
            return []

        try:
            return test_frameworks.get_detected_frameworks()
        except Exception as e:
            logger.error("%s", Error getting test frameworks: {e})
            return []

    def get_test_files(self) -> List[str]:
        """Get the list of test files in the project."""
        test_frameworks = self._tool_registry.get_tool_by_capability(ToolCapability.TEST_FRAMEWORKS)
        if not test_frameworks:
            return []

        try:
            return test_frameworks.get_test_files()
        except Exception as e:
            logger.error("%s", Error getting test files: {e})
            return []

    # Implement MemoryContextProvider interface methods
    def store_memory(self, key: str, value: Any) -> None:
        """
        Store a value in the memory context.

        Args:
            key: Memory key
            value: Value to store
        """
        with self._context_lock:
            memory = self.current_context.get("memory", {})
            memory[key] = value
            self._update_nested_dict(self.current_context, "memory", memory)

        # Record access for the pruning manager
        self._pruning_manager.record_access(f"memory.{key}")

    def retrieve_memory(self, key: str) -> Optional[Any]:
        """
        Retrieve a value from the memory context.

        Args:
            key: Memory key

        Returns:
            Stored value or None if key not found
        """
        with self._context_lock:
            memory = self.current_context.get("memory", {})
            value = memory.get(key)

        # Record access for the pruning manager
        if value is not None:
            self._pruning_manager.record_access(f"memory.{key}")

        return value

    def clear_memory(self) -> None:
        """Clear all stored memories."""
        with self._context_lock:
            self._update_nested_dict(self.current_context, "memory", {})

    # Implement DependencyGraphProvider interface methods
    def get_dependency_graph(self) -> Dict[str, Any]:
        """Get the dependency graph of the project."""
        # If graph was recently updated, return the cached version
        if time.time() - self._graph_last_updated < 300:  # 5 minutes cache
            return self._dependency_graph

        # Otherwise try to refresh the graph
        code_tool = self._tool_registry.get_tool_by_capability(ToolCapability.CODE_ANALYSIS)
        if code_tool and hasattr(code_tool, "get_dependency_graph"):
            try:
                self._dependency_graph = code_tool.get_dependency_graph()
                self._graph_last_updated = time.time()
            except Exception as e:
                logger.error("%s", Error refreshing dependency graph: {e})

        return self._dependency_graph

    def get_file_dependencies(self, file_path: str) -> List[str]:
        """
        Get files that the specified file depends on.

        Args:
            file_path: Path to the file

        Returns:
            List of files it depends on
        """
        graph = self.get_dependency_graph()
        nodes = graph.get('nodes', {})
        edges = graph.get('edges', [])

        # Find the node for this file
        file_node_id = None
        for nid, node in nodes.items():
            if node.get('path') == file_path or nid == file_path:
                file_node_id = nid
                break

        if not file_node_id:
            return []

        # Find outgoing dependency edges
        dependencies = []
        for edge in edges:
            if edge.get('source') == file_node_id and edge.get('type') in ['import', 'use', 'include']:
                target_id = edge.get('target')
                if target_id in nodes:
                    target_path = nodes[target_id].get('path')
                    if target_path:
                        dependencies.append(target_path)

        return dependencies

    def get_dependent_files(self, file_path: str) -> List[str]:
        """
        Get files that depend on the specified file.

        Args:
            file_path: Path to the file

        Returns:
            List of files that depend on it
        """
        graph = self.get_dependency_graph()
        nodes = graph.get('nodes', {})
        edges = graph.get('edges', [])

        # Find the node for this file
        file_node_id = None
        for nid, node in nodes.items():
            if node.get('path') == file_path or nid == file_path:
                file_node_id = nid
                break

        if not file_node_id:
            return []

        # Find incoming dependency edges
        dependents = []
        for edge in edges:
            if edge.get('target') == file_node_id and edge.get('type') in ['import', 'use', 'include']:
                source_id = edge.get('source')
                if source_id in nodes:
                    source_path = nodes[source_id].get('path')
                    if source_path:
                        dependents.append(source_path)

        return dependents

    def _log_metrics_to_adaptive_config(self, context_used: Dict[str, Any],
                               task_type: Optional[str] = None,
                               relevance_score: Optional[float] = None) -> None:
        """
        Log metrics to the adaptive configuration system.

        Args:
            context_used: Context that was used
            task_type: Type of task being performed
            relevance_score: Optional relevance score for the context
        """
        if not self.adaptive_config_manager:
            return

        if not isinstance(context_used, dict):
            logger.error("%s", "Context data is missing or malformed when logging metrics")
            return

        try:
            # Log token usage using token estimation
            token_estimates = (
                self.token_budget_analyzer.estimator.estimate_tokens_for_context(context_used)
            )
            total_tokens = token_estimates.get("total", 0)
            available_tokens = self.token_budget_analyzer.max_tokens

            self.adaptive_config_manager.log_token_usage(
                total_tokens=total_tokens,
                available_tokens=available_tokens,
                allocated_tokens=token_estimates
            )

            # Log context performance if relevance score is provided
            if task_type and relevance_score is not None:
                self.adaptive_config_manager.log_context_performance(
                    task_type=task_type,
                    relevance_score=relevance_score
                )

        except Exception as e:
            logger.error("%s", Error logging metrics to adaptive config: {e})

    def shutdown(self) -> None:
        """
        Shutdown the context manager and its tools.

        This should be called when the application exits to ensure proper cleanup.
        """
        logger.info("Shutting down Context Manager")

        # Stop background optimization
        self._stop_background_optimization()

        # Shutdown all registered tools
        self._tool_registry.shutdown_all_tools()

        # Shutdown adaptive configuration manager
        if self.adaptive_config_manager:
            # Trigger final optimization before shutdown
            try:
                if self.adaptive_config_manager.check_optimization_needed():
                    self.adaptive_config_manager.optimize_configuration()
            except Exception as e:
                logger.error("%s", Error during final optimization: {e})
