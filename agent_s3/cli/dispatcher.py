"""Command dispatcher for Agent-S3 CLI."""

from typing import Callable, Dict

from agent_s3.command_processor import CommandProcessor

# Map command names to CommandProcessor method names
_COMMAND_MAP: Dict[str, str] = {
    "init": "execute_init_command",
    "plan": "execute_plan_command",
    "test": "execute_test_command",
    "debug": "execute_debug_command",
    "terminal": "execute_terminal_command",
    "personas": "execute_personas_command",
    "guidelines": "execute_guidelines_command",
    "design": "execute_design_command",
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


def dispatch(command_processor: CommandProcessor, raw_command: str) -> str:
    """Parse and dispatch a command to the appropriate handler."""
    if raw_command.startswith("/"):
        raw_command = raw_command[1:]
    cmd, _, args = raw_command.partition(" ")
    cmd = cmd.lower()
    handler_name = _COMMAND_MAP.get(cmd)
    if not handler_name:
        return f"Unknown command: {cmd}. Type /help for available commands."
    handler: Callable[[str], str] = getattr(command_processor, handler_name)
    return handler(args.strip())
