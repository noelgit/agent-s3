"""Command dispatcher for Agent-S3 CLI."""

from typing import Callable, Dict, Tuple

from agent_s3.command_processor import CommandProcessor

# Simple commands that don't require full Coordinator initialization
_SIMPLE_COMMANDS = {"help", "config"}

# Map command names to CommandProcessor method names
_COMMAND_MAP: Dict[str, str] = {
    "init": "execute_init_command",
    "plan": "execute_plan_command",
    "test": "execute_test_command",
    "debug": "execute_debug_command",
    "terminal": "execute_terminal_command",
    "guidelines": "execute_guidelines_command",
    "design": "execute_design_command",
    "design-auto": "execute_design_auto_command",
    "implement": "execute_implement_command",
    "continue": "execute_continue_command",
    "deploy": "execute_deploy_command",
    "help": "execute_help_command",
    "config": "execute_config_command",
    "reload-llm-config": "execute_reload_llm_config_command",
    "explain": "execute_explain_command",
    "request": "execute_request_command",
    "tasks": "execute_tasks_command",
    "clear": "execute_clear_command",
    "db": "execute_db_command",
}


def _handle_simple_help_command(args: str) -> Tuple[str, bool]:
    """Handle help command without Coordinator initialization - SINGLE SOURCE OF TRUTH."""
    
    if args.strip():
        # Show help for specific command
        command = args.strip().lower()
        if command.startswith('/'):
            command = command[1:]

        help_msgs = {
            "init": "Initialize workspace with essential files and context management system",
            "plan": "Generate a development plan from a request description",
            "test": "Run all tests in the codebase",
            "debug": "Debug last test failure",
            "terminal": "Execute a terminal command",
            "guidelines": "Create/update copilot-instructions.md with default content",
            "design": "Create a design document based on a design objective",
            "design-auto": "Run design workflow with automatic approvals",
            "implement": "Implement a design from design.txt",
            "continue": "Continue implementation from where it left off",
            "deploy": "Deploy an application based on a design",
            "help": "Show available commands or help for a specific command",
            "config": "Show current configuration",
            "reload-llm-config": "Reload LLM configuration",
            "explain": "Explain the last LLM interaction",
            "request": "Process a full change request (plan + execution)",
            "tasks": "List active tasks that can be resumed",
            "clear": "Clear a specific task state",
            "db": "Database operations (schema, query, test, etc.)"
        }

        if command in help_msgs:
            return f"/{command}: {help_msgs[command]}", True
        else:
            return f"Unknown command: {command}. Type /help for available commands.", False
    else:
        # Return the complete help text - SINGLE SOURCE OF TRUTH
        return """Agent-S3 Command-Line Interface

Usage:
  agent-s3 <prompt>          - Process a change request (full workflow)
  agent-s3 /<command>        - Execute specific commands (see below)

Available Commands:
  /plan <prompt>             - Generate a plan only (bypass execution)
  /request <prompt>          - Full change request (plan + execution)
  /init                      - Initialize the workspace
  /help                      - Display this help message
  /config                    - Show current configuration
  /reload-llm-config         - Reload LLM configuration
  /explain                   - Explain the last LLM interaction
  /terminal <cmd>            - Execute shell commands directly (bypassing LLM)
  /design <obj>              - Start a design process
  /design-auto <obj>         - Start design with automatic approvals
  /implement [file]          - Implement a design from design.txt
  /guidelines                - Generate default guidelines file
  /continue [id]             - Continue implementation from where it left off
  /deploy [file]             - Deploy an application based on a design
  /tasks                     - List active tasks that can be resumed
  /clear <id>                - Clear a specific task state
  /db <command>              - Database operations (see /db help for details)
  /test                      - Run tests
  /debug                     - Start debugging utilities

Note: Commands can be used either:
  - From command line: agent-s3 /command
  - In chat/prompt context: /command

""", True


def _handle_simple_config_command(args: str) -> Tuple[str, bool]:
    """Handle config command without Coordinator initialization."""
    try:
        from agent_s3.config import Config
        config = Config()
        config.load()
        
        result = "Current configuration:\n"
        for key, value in config.config.items():
            if key in ["openrouter_key", "github_token", "api_key"]:
                # Mask sensitive values
                result += f"  {key}: {'*' * 10}\n"
            else:
                result += f"  {key}: {value}\n"
        return result, True
    except Exception as e:
        return f"Error getting configuration: {e}", False


def dispatch(command_processor: CommandProcessor, raw_command: str) -> Tuple[str, bool]:
    """Parse and dispatch a command to the appropriate handler."""
    if raw_command.startswith("/"):
        raw_command = raw_command[1:]
    cmd, _, args = raw_command.partition(" ")
    cmd = cmd.lower()
    
    # Handle simple commands without coordinator
    if cmd in _SIMPLE_COMMANDS:
        if cmd == "help":
            return _handle_simple_help_command(args.strip())
        elif cmd == "config":
            return _handle_simple_config_command(args.strip())
    
    # Handle complex commands through coordinator
    handler_name = _COMMAND_MAP.get(cmd)
    if not handler_name:
        return f"Unknown command: {cmd}. Type /help for available commands.", False
    handler: Callable[[str], Tuple[str, bool]] = getattr(command_processor, handler_name)
    return handler(args.strip())
