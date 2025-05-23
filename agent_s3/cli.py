"""Command-line interface for Agent-S3."""

import os
import sys
import argparse
import logging

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
  agent-s3 <prompt>          - Process a change request (full workflow)
  agent-s3 /plan <prompt>    - Generate a plan only (bypass execution)
  agent-s3 /request <prompt> - Full change request (plan, execute)
  agent-s3 /init             - Initialize the workspace
  agent-s3 /help             - Display this help message
  agent-s3 /config           - Show current configuration
  agent-s3 /reload-llm-config- Reload LLM configuration
  agent-s3 /explain          - Explain the last LLM interaction
  agent-s3 /terminal <cmd>   - Execute shell commands directly (bypassing LLM)
  agent-s3 /cli bash <cmd>   - Run multi-line bash script via heredoc
  agent-s3 /cli file <path>  - Write file content via heredoc
  agent-s3 /design <obj>     - Start a design process
  agent-s3 /personas         - Generate default personas file
  agent-s3 /guidelines       - Generate default guidelines file
  agent-s3 /continue [id]    - Continue implementation from where it left off
  agent-s3 /tasks            - List active tasks that can be resumed
  agent-s3 /clear <id>       - Clear a specific task state
  agent-s3 /db <command>     - Database operations (see /db help for details)
  agent-s3 /test             - Run tests
  agent-s3 /debug            - Start debugging utilities

Special Commands (can be used in prompt):
  /help                      - Display help message
  /init                      - Initialize workspace
  /config                    - Show current configuration
  /reload-llm-config         - Reload LLM configuration
  /explain                   - Explain the last LLM interaction
  /plan <prompt>             - Generate a plan only (bypass execution)
  /request <prompt>          - Full change request (plan + execution)
  /terminal <cmd>            - Execute shell commands literally (bypassing LLM)
  /cli bash <cmd>            - Multi-line bash execution (<<EOF ... EOF)
  /cli file <path>           - Multi-line file content
  /design <obj>              - Start a design process
  /personas                  - Generate default personas file
  /guidelines                - Generate default guidelines file
  /continue [id]             - Continue implementation from where it left off
  /tasks                     - List active tasks that can be resumed
  /clear <id>                - Clear a specific task state
  /db <command>              - Database operations (schema, query, test, etc.)
  /test                      - Run tests
  /debug                     - Start debugging utilities
  @<filename>                - Open a file in the editor
  #<tag>                     - Add a tag to the scratchpad
"""
    print(help_text)




def process_command(coordinator: Coordinator, command: str) -> None:
    """Process a special command by delegating to CommandProcessor.

    Args:
        coordinator: The coordinator instance
        command: The command to process
    """
    # Initialize CommandProcessor if not already done
    if not hasattr(coordinator, 'command_processor'):
        from agent_s3.command_processor import CommandProcessor
        coordinator.command_processor = CommandProcessor(coordinator)

    # Handle help command at CLI level since it's display-specific
    if command == "/help":
        display_help()
    else:
        try:
            # Delegate all other commands to CommandProcessor
            result = coordinator.command_processor.process_command(command)

            # Print result if it's non-empty
            if result:
                print(result)
        except Exception as e:
            print(f"Error processing command '{command}': {e}")
            logger.error(f"Command processing error: {e}", exc_info=True)


def main() -> None:
    """Main entry point for the command-line interface."""
    parser = argparse.ArgumentParser(
        description="Agent-S3 Command-Line Interface",
        formatter_class=argparse.RawTextHelpFormatter,
        add_help=False,
    )
    parser.add_argument("prompt", nargs="*", help="The change request prompt or command")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    parser.add_argument("--help", "-h", action="store_true", help="Show this help message and exit")
    args = parser.parse_args()

    if args.help:
        display_help()
        return

    configure_logging(args.verbose)
    logger.debug("Starting Agent-S3 CLI")

    prompt = " ".join(args.prompt).strip()
    if not prompt:
        display_help()
        return
        
    # Handle help command without initializing coordinator
    if prompt == "/help":
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

    # Route bare-text prompt through RouterAgent (orchestrator)
    router = RouterAgent()
    # Orchestrator prompt template with definitions and examples
    orchestrator_prompt = '''
You are the orchestrator for an AI coding agent. Your job is to classify the user's bare text input into one of the following routing categories. Respond with a JSON object containing "category", "rationale", and "confidence" (0-1).

Categories:
- planner: Single-concern feature or simple code change request. Example: "Add a logout button to the navbar." Route to the planner.
- designer: Multi-concern or architectural/design requests. Example: "Redesign the authentication and notification systems." Route to the designer.
- tool_user: Not a feature or design request. User wants to execute a command (e.g., run tests, list files, run a script). Example: "Run all tests" or "Show me the last 10 git commits." Route to the tool_user LLM.
- general_qa: General question/answer, may or may not be about the codebase. Example: "What is the purpose of this project?" or "How does OAuth2 work?" Route to the general_qa LLM.

If you are not confident, set confidence below 0.7 and explain why in rationale.

Examples:
Input: "Add a password reset feature."
Output: {"category": "planner", "rationale": "Single feature request.", "confidence": 0.95}
Input: "Refactor the database and add a new notification system."
Output: {"category": "designer", "rationale": "Multiple concerns: database and notifications.", "confidence": 0.92}
Input: "Run all tests."
Output: {"category": "tool_user", "rationale": "User wants to execute a command.", "confidence": 0.98}
Input: "What is a JWT?"
Output: {"category": "general_qa", "rationale": "General question.", "confidence": 0.99}

User input: ''' + repr(prompt)
    # Use a minimal scratchpad and config for logging
    class DummyScratchpad:
        def log(self, *a, **k):
            pass
    try:
        response = router.call_llm_by_role(
            role="orchestrator",
            system_prompt="Classify the user's intent for routing.",
            user_prompt=orchestrator_prompt,
            config=config.config,
            scratchpad=DummyScratchpad()
        )
        import json as _json
        try:
            result = _json.loads(response)
            category = result.get("category", "").strip().lower()
            rationale = result.get("rationale", "")
            confidence = float(result.get("confidence", 0))
        except Exception:
            print(f"Orchestrator response could not be parsed as JSON: {response}")
            return
        print(f"[Orchestrator] Routing decision: {category} (confidence: {confidence:.2f})\nRationale: {rationale}")
        # Log routing decision (could be to a file or audit log)
        # ...
        if confidence < 0.7 or not category:
            clarification = input("Orchestrator is not confident in routing. Please clarify your intent (planner/designer/tool_user/general_qa): ").strip().lower()
            category = clarification
        if category == "planner":
            coordinator.process_change_request(prompt)
        elif category == "designer":
            print("Routing to /design directive...")
            coordinator.execute_design(prompt)
        elif category == "tool_user":
            # Execute arbitrary shell command directly
            print("Routing to tool_user: executing shell command...")
            confirmation = input(
                f"Proceed to run '{prompt}' as a shell command? (y/n) "
            ).strip().lower()
            if confirmation == "y":
                # Run the command via CommandProcessor (lazy-loaded on access)
                coordinator.command_processor.execute_terminal_command(prompt)
            else:
                print("Command aborted.")
        elif category == "general_qa":
            # General Q&A: call the LLM with entire codebase as context
            print("Routing to general_qa: querying codebase context...")
            from pathlib import Path
            import glob
            import itertools
            # Gather a limited set of code files to avoid excessive memory usage
            code_context = {}
            for path in itertools.islice(glob.glob("**/*.py", recursive=True), 200):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        code_context[path] = f.read(5000)
                except OSError:
                    continue
            system_prompt = (
                "You are a Q&A assistant. Use the provided codebase context to answer questions about the project."
            )
            user_prompt = prompt
            # Call orchestrator or general_qa LLM role
            response = router.call_llm_by_role(
                role="general_qa",
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                config=config.config,
                scratchpad=DummyScratchpad(),
                code_context=code_context
            )
            print(response)
        else:
            print(f"Unknown or unsupported routing category: {category}")
    except Exception as e:
        print(f"Error routing prompt through orchestrator: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
