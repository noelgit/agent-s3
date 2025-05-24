"""Tool definitions for Agent-S3 system.

Contains standardized definitions and schemas for supported tools.
Implements secure tool registration, validation, and resource management.
"""

from typing import Dict, Any, Optional, List
import os
import logging
import traceback

from agent_s3.tools.file_tool import FileTool
from agent_s3.tools.bash_tool import BashTool
from agent_s3.tools.git_tool import GitTool
from agent_s3.tools.embedding_client import EmbeddingClient
from agent_s3.terminal_executor import TerminalExecutor
from agent_s3.tools.code_analysis_tool import CodeAnalysisTool
from agent_s3.tools.database_tool import DatabaseTool

logger = logging.getLogger(__name__)

class ToolDefinitions:
    """Manages definitions and schemas for tools available to LLMs."""

    @staticmethod
    def get_all(registry: Optional['ToolRegistry'] = None) -> str:
        """Get all tool definitions formatted as a string for LLM consumption.

        Generates tool definitions dynamically from registry if provided, otherwise
        uses static definitions. This ensures LLMs have accurate and up-to-date
        information about available tools and their parameters.

        Args:
            registry: Optional ToolRegistry to dynamically generate definitions

        Returns:
            Formatted string containing all tool definitions
        """
        # Use registry to get actual tool descriptions if available
        if registry:
            tool_names = registry.get_tool_names()
            tool_descriptions = registry.get_tool_descriptions()
            tools = []

            # Get parameter info from the actual tool instances
            for name in tool_names:
                tool = registry.get_tool(name)
                parameters = {}

                # Extract parameter info from tool methods if available
                if hasattr(tool, 'get_parameter_schema'):
                    parameters = tool.get_parameter_schema()
                else:
                    # Fallback to basic parameters based on tool type
                    if name == "file_tool":
                        parameters = {
                            "action": "The file operation (read, write, append, list, etc.)",
                            "path": "The file path to operate on",
                            "content": "Optional content for write operations"
                        }
                    elif name == "bash_tool":
                        parameters = {
                            "command": "The command to execute"
                        }
                    elif name == "git_tool":
                        parameters = {
                            "action": "The Git operation to perform",
                            "repo_path": "Path to the repository",
                            "files": "Files to include in the operation (optional)",
                            "message": "Commit message (for commit operations)"
                        }
                    elif name == "code_analysis_tool":
                        parameters = {
                            "query": "The query to search for in the codebase",
                            "file_path": "Optional specific file to analyze",
                            "top_n": "Number of results to return"
                        }
                    elif name == "tech_stack_manager":
                        parameters = {
                            "action": "The action to perform (detect, get_info, etc.)"
                        }

                tools.append({
                    "name": name,
                    "description": tool_descriptions.get(name, f"Tool: {name}"),
                    "parameters": parameters
                })
        else:
            # Fallback to static definitions
            tools = [
                {
                    "name": "file_tool",
                    "description": "Read, write, and manipulate files in the workspace",
                    "parameters": {
                        "action": "The file operation (read, write, append, list, etc.)",
                        "path": "The file path to operate on",
                        "content": "Optional content for write operations"
                    }
                },
                {
                    "name": "bash_tool",
                    "description": "Execute shell commands in the workspace",
                    "parameters": {
                        "command": "The command to execute"
                    }
                },
                {
                    "name": "git_tool",
                    "description": "Perform Git operations including repo analysis and commits",
                    "parameters": {
                        "action": "The Git operation to perform",
                        "repo_path": "Path to the repository",
                        "files": "Files to include in the operation (optional)",
                        "message": "Commit message (for commit operations)"
                    }
                },
                {
                    "name": "code_analysis_tool",
                    "description": "Analyze code for relevance, patterns, and structure",
                    "parameters": {
                        "query": "The query to search for in the codebase",
                        "file_path": "Optional specific file to analyze",
                        "top_n": "Number of results to return"
                    }
                },
                {
                    "name": "tech_stack_manager",
                    "description": "Detect and provide information about the project's tech stack",
                    "parameters": {
                        "action": "The action to perform (detect, get_info, etc.)"
                    }
                }
            ]

        # Format tools as a string
        result = "# Available Tools\n\n"
        for tool in tools:
            result += f"## {tool['name']}\n"
            result += f"{tool['description']}\n\n"
            result += "Parameters:\n"
            for param_name, param_desc in tool['parameters'].items():
                result += f"- `{param_name}`: {param_desc}\n"
            result += "\n"

        return result

class ToolRegistry:
    """Registry for tools available to the agent.

    Provides secure tool registration with proper validation, configuration checks,
    on-demand loading, and resource cleanup. Follows the principle of least privilege
    by validating all credentials and configuration before use.
    """

    def __init__(self, config):
        """Initialize the tool registry with configuration.

        Args:
            config: Configuration object containing tool settings
        """
        self.config = config
        self.tools: Dict[str, Any] = {}
        self._initialized = False

    def initialize(self) -> None:
        """Initialize the tool registry and register basic tools.

        Performs lazy initialization to improve startup performance.
        """
        if self._initialized:
            return

        self.register_tools()
        self._initialized = True

    def _validate_config(self, tool_name: str, required_params: List[str]) -> bool:
        """Validate required configuration parameters exist for a tool.

        Args:
            tool_name: Name of the tool being configured
            required_params: List of required configuration parameters

        Returns:
            True if configuration is valid, False otherwise
        """
        missing_params = []
        for param in required_params:
            # Check nested parameters with dot notation
            if "." in param:
                parts = param.split(".")
                config_section = self.config.config
                valid = True

                for part in parts:
                    if isinstance(config_section, dict) and part in config_section:
                        config_section = config_section[part]
                    else:
                        valid = False
                        break

                if not valid:
                    missing_params.append(param)
            elif param not in self.config.config:
                missing_params.append(param)

        if missing_params:
            logger.warning(
                "%s",
                "Missing required configuration for %s: %s",
                tool_name,
                ", ".join(missing_params),
            )
            return False

        return True

    def _validate_token(self, token: Optional[str]) -> bool:
        """Validate that a token is properly formatted and non-empty.

        Provides basic validation for security credentials to prevent
        passing invalid tokens to external services.

        Args:
            token: The token to validate

        Returns:
            True if token appears valid, False otherwise
        """
        if not token:
            return False

        # Basic validation - check it's a non-empty string with reasonable length
        if not isinstance(token, str) or len(token) < 8:
            return False

        # Basic pattern checking for GitHub tokens (usually 40+ hex chars)
        # This is a simple check and not foolproof
        if token.startswith("github_") or all(c in "0123456789abcdefABCDEF" for c in token):
            return True

        logger.warning("GitHub token format appears invalid")
        return False

    def register_tool(self, tool_name: str) -> bool:
        """Register a specific tool by name.

        Provides on-demand tool registration to avoid unnecessary resource
        allocation for tools that aren't used.

        Args:
            tool_name: Name of the tool to register

        Returns:
            True if registration successful, False otherwise
        """
        if tool_name in self.tools:
            # Already registered
            return True

        try:
            if tool_name == "file_tool":
                if self._validate_config("file_tool", ["allowed_dirs"]):
                    self.tools["file_tool"] = FileTool(
                        allowed_dirs=self.config.config.get("allowed_dirs", [os.getcwd()]),
                        max_file_size=self.config.config.get("max_file_size", 10 * 1024 * 1024),
                        allowed_extensions=self.config.config.get("allowed_extensions", None)
                    )
                    return True
            elif tool_name == "terminal_executor":
                terminal_executor = TerminalExecutor(self.config)
                self.tools["terminal_executor"] = terminal_executor
                return True
            elif tool_name == "bash_tool":
                # Ensure TerminalExecutor is registered for fallback
                if "terminal_executor" not in self.tools:
                    self.register_tool("terminal_executor")
                terminal_executor = self.tools["terminal_executor"]

                self.tools["bash_tool"] = BashTool(
                    sandbox=self.config.config.get("sandbox_environment", True),
                    env_vars=self.config.config.get("env_vars", {})
                )
                # Attach the terminal executor for subprocess execution
                self.tools["bash_tool"].terminal_executor = terminal_executor
                return True
            elif tool_name == "code_analysis_tool":
                self.tools["code_analysis_tool"] = CodeAnalysisTool(
                    linters=self.config.config.get("linters", ["flake8"]),
                    ignore_patterns=self.config.config.get("ignore_patterns", []),
                    max_files=self.config.config.get("max_files_analysis", 50)
                )
                return True
            elif tool_name == "git_tool":
                # Validate GitHub token if present
                token = self.config.config.get("github_token") or self.config.config.get("dev_github_token")

                # Ensure terminal_executor is registered
                if "terminal_executor" not in self.tools:
                    self.register_tool("terminal_executor")
                terminal_executor = self.tools["terminal_executor"]

                if self._validate_token(token):
                    self.tools["git_tool"] = GitTool(
                        token=token,
                        org=self.config.config.get("target_org"),
                        repo=self.config.config.get("github_repo"),
                        terminal_executor=terminal_executor
                    )
                    logger.info("Registered git tool with valid GitHub token")
                else:
                    # Register with limited functionality
                    self.tools["git_tool"] = GitTool(
                        token=None,
                        terminal_executor=terminal_executor
                    )
                    logger.warning("Registered git tool with limited functionality (no GitHub API access)")
                return True
            elif tool_name == "tech_stack_manager":
                try:
                    from agent_s3.tools.tech_stack_manager import TechStackManager
                except ImportError:
                    logger.error("TechStackManager module not available")
                    return False

                self.tools["tech_stack_manager"] = TechStackManager(
                    workspace_path=self.config.config.get("workspace_path", os.getcwd())
                )
                return True
            elif tool_name == "embedding_client":
                if self._validate_config("embedding_client", ["vector_store_path"]):
                    client_config = {
                        "vector_store_path": self.config.config.get("vector_store_path", "./data/vector_store.faiss"),
                        "embedding_dim": self.config.config.get("embedding_dim", 384),
                        "top_k_retrieval": self.config.config.get("top_k_retrieval", 5),
                        "eviction_threshold": self.config.config.get("eviction_threshold", 0.90),
                        "workspace_path": self.config.config.get("workspace_path", os.getcwd()),
                    }
                    self.tools["embedding_client"] = EmbeddingClient(client_config)
                    return True
            elif tool_name == "database_tool":
                if "databases" in self.config.config:
                    # Ensure bash_tool is registered for fallback
                    if "bash_tool" not in self.tools:
                        self.register_tool("bash_tool")
                    bash_tool = self.tools["bash_tool"]

                    self.tools["database_tool"] = DatabaseTool(
                        config=self.config,
                        bash_tool=bash_tool  # Pass the BashTool instance for fallback
                    )
                    logger.info("Registered database tool with fallback support")
                    return True
                else:
                    logger.warning("Cannot register database_tool: No databases configured")
                    return False
            else:
                logger.warning("%s", Unknown tool: {tool_name})
                return False
        except Exception as e:
            logger.error("%s", Error registering tool {tool_name}: {e})
            logger.error("%s", Stack trace: {traceback.format_exc()})
            return False

        return False  # Default if we reach here

    def register_tools(self) -> None:
        """Register all available tools with validation.

        Registers core tools first, then optional tools with proper dependency
        handling and configuration validation.
        """
        try:
            # Register core tools
            core_tools = ["file_tool", "terminal_executor", "bash_tool", "code_analysis_tool", "git_tool"]
            for tool_name in core_tools:
                success = self.register_tool(tool_name)
                if success:
                    logger.debug("%s", Successfully registered core tool: {tool_name})
                else:
                    logger.warning("%s", Failed to register core tool: {tool_name})

            # Register optional tools
            optional_tools = ["embedding_client", "database_tool", "tech_stack_manager"]
            for tool_name in optional_tools:
                success = self.register_tool(tool_name)
                if success:
                    logger.debug("%s", Successfully registered optional tool: {tool_name})

            logger.info("%s", Successfully registered {len(self.tools)} tools)
        except Exception as e:
            logger.error("%s", Error registering tools: {e})
            raise

    def get_tool(self, tool_name: str) -> Optional[Any]:
        """Get a tool by name, registering it if needed.

        Provides lazy loading of tools - only instantiates them when requested.

        Args:
            tool_name: Name of the tool to retrieve

        Returns:
            The requested tool instance or None if unavailable
        """
        if not self._initialized:
            self.initialize()

        if tool_name in self.tools:
            return self.tools.get(tool_name)

        # Try to register the tool
        if self.register_tool(tool_name):
            return self.tools.get(tool_name)

        return None

    def get_all_tools(self) -> Dict[str, Any]:
        """Get all registered tools.

        Returns:
            Dictionary of all tools keyed by name
        """
        if not self._initialized:
            self.initialize()
        return self.tools

    def get_tool_names(self) -> List[str]:
        """Get names of all registered tools.

        Returns:
            List of tool names
        """
        if not self._initialized:
            self.initialize()
        return list(self.tools.keys())

    def get_tool_descriptions(self) -> Dict[str, str]:
        """Get descriptions of all tools.

        Returns:
            Dictionary mapping tool names to descriptions
        """
        if not self._initialized:
            self.initialize()
        descriptions = {}
        for name, tool in self.tools.items():
            doc = getattr(tool, "__doc__", "") or ""
            descriptions[name] = doc.strip().split('\n')[0] if doc else f"Tool: {name}"
        return descriptions

    def cleanup(self) -> None:
        """Clean up resources used by tools.

        Calls cleanup methods on tools that support it and releases resources.
        Should be called when the registry is no longer needed to prevent
        resource leaks.
        """
        for name, tool in self.tools.items():
            try:
                # Call cleanup method if it exists
                if hasattr(tool, 'cleanup') and callable(getattr(tool, 'cleanup')):
                    tool.cleanup()

                # Special handling for specific tools
                if name == "embedding_client" and hasattr(tool, 'close'):
                    tool.close()
            except Exception as e:
                logger.error("%s", Error cleaning up tool {name}: {e})

        self.tools.clear()
        self._initialized = False

    def __del__(self):
        """Destructor to ensure resources are cleaned up.

        Prevents resource leaks by automatically cleaning up when the registry
        is garbage collected.
        """
        try:
            self.cleanup()
        except Exception as e:
            # Avoid crashing during interpreter shutdown
            logger.error("%s", Error in ToolRegistry destructor: {e})


def get_tools(config):
    """
    Instantiate and return all available tools keyed by name.
    Legacy function for backward compatibility.
    """
    registry = ToolRegistry(config)
    return registry.get_all_tools()
