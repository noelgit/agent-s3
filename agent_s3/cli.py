"""Command-line interface for Agent-S3."""

import os
import sys
import argparse
import json
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any

from agent_s3.config import Config
from agent_s3.coordinator import Coordinator
from agent_s3.router_agent import RouterAgent
# Import authenticate_user only when needed to prevent circular imports
# from agent_s3.auth import authenticate_user

logger = logging.getLogger(__name__)


def configure_logging(verbose: bool = False) -> None:
    """Configure the logging system.
    
    Args:
        verbose: Whether to enable verbose logging
    """
    level = logging.DEBUG if verbose else logging.INFO
    format_str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    logging.basicConfig(
        level=level,
        format=format_str,
        handlers=[logging.StreamHandler()]
    )
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)


def display_help() -> None:
    """Display help information for the command-line interface."""
    help_text = """
Agent-S3 Command-Line Interface

Commands:
  agent-s3 <prompt>        - Process a change request
  agent-s3 /init           - Initialize the workspace
  agent-s3 /help           - Display this help message
  agent-s3 /config         - Show current configuration
  agent-s3 /reload-llm-config - Reload LLM configuration

Special Commands (can be used in prompt):
  /help                    - Display help message
  /init                    - Initialize workspace
  /config                  - Show current configuration
  /reload-llm-config       - Reload LLM configuration
  @<filename>              - Open a file in the editor
  #<tag>                   - Add a tag to the scratchpad
"""
    print(help_text)


def track_module_scaffold(module_name: str) -> None:
    """Track a module as being scaffolded in development_status.json.
    
    Args:
        module_name: The name of the module being scaffolded
    """
    status_path = Path.cwd() / "development_status.json"
    try:
        if status_path.exists():
            with open(status_path, 'r') as f:
                try:
                    data = json.load(f)
                except json.JSONDecodeError:
                    data = []
        else:
            data = []

        # Add the module with created status
        data.append({
            "module": module_name,
            "status": "created"
        })

        # Write back to the file
        with open(status_path, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"Error tracking module scaffold for {module_name}: {e}")


def process_command(coordinator: Coordinator, command: str) -> None:
    """Process a special command.
    
    Args:
        coordinator: The coordinator instance
        command: The command to process
    """
    if command == "/help":
        display_help()
    elif command == "/init":
        print("Initializing workspace...")
        coordinator.initialize_workspace()
        print("Workspace initialized successfully.")
    elif command == "/config":
        print("Current configuration:")
        for key, value in coordinator.config.config.items():
            if key in ["openrouter_key", "github_token", "api_key"]:
                # Mask sensitive values
                print(f"  {key}: {'*' * 10}")
            else:
                print(f"  {key}: {value}")
    elif command == "/reload-llm-config":
        try:
            router = RouterAgent()
            router.reload_config()
            print("LLM configuration reloaded successfully.")
        except Exception as e:
            print(f"Failed to reload LLM configuration: {e}")
    else:
        print(f"Unknown command: {command}")


def main() -> None:
    """Main entry point for the command-line interface."""
    parser = argparse.ArgumentParser(description="Agent-S3 Command-Line Interface")
    parser.add_argument("prompt", nargs="*", help="The change request prompt or command")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    args = parser.parse_args()

    configure_logging(args.verbose)
    logger.debug("Starting Agent-S3 CLI")

    prompt = " ".join(args.prompt).strip()
    if not prompt:
        display_help()
        return

    # Initialize the configuration
    config = Config()
    config.load()
    logger.debug("Configuration loaded")

    # Initialize a coordinator
    coordinator = Coordinator(config)
    logger.debug("Coordinator initialized")

    # Process special commands
    if prompt.startswith("/"):
        process_command(coordinator, prompt)
        return

    # Authenticate the user if needed
    github_token = os.getenv("GITHUB_TOKEN")
    if not github_token and not prompt.startswith("/"):
        # Import here to avoid circular imports
        from agent_s3.auth import authenticate_user
        github_token = authenticate_user()
        if not github_token:
            print("Authentication required. Run agent-s3 /init to initialize or set GITHUB_TOKEN.")
            sys.exit(1)

    # Re-initialize coordinator with authentication
    coordinator = Coordinator(config, github_token=github_token)

    # Process the change request
    try:
        coordinator.process_change_request(prompt)
    except Exception as e:
        logger.error(f"Error processing change request: {e}", exc_info=True)
        print(f"Error processing change request: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
