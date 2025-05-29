"""Command-line interface for Agent-S3."""

import os
import sys
import argparse
import logging
import time  # Added import for time.sleep
from fnmatch import fnmatch
from typing import Dict

from agent_s3.config import Config
from agent_s3.coordinator import Coordinator
from agent_s3.router_agent import RouterAgent
from .dispatcher import dispatch
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
        return

    try:
        result = dispatch(coordinator.command_processor, command)
        if result:
            print(result)
    except Exception as e:  # pragma: no cover - defensive
        print(f"Error processing command '{command}': {e}")
        logger.error(f"Command processing error: {e}", exc_info=True)


def gather_code_context(limit: int = 200) -> Dict[str, str]:
    """Return sanitized snippets of project code for LLM context."""

    import glob
    import itertools

    sensitive_path_patterns = [
        "*secret*",
        "*credential*",
        "*.env*",
        "*token*",
        "*password*",
    ]
    sensitive_keywords = {"secret", "password", "token", "key"}

    context: Dict[str, str] = {}
    for path in itertools.islice(glob.glob("**/*.py", recursive=True), limit):
        lower_path = path.lower()
        if any(fnmatch(lower_path, pat) for pat in sensitive_path_patterns):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read(5000)
        except OSError:
            continue
        lines = [
            ln
            for ln in content.splitlines()
            if not any(word in ln.lower() for word in sensitive_keywords)
        ]
        context[path] = "\n".join(lines)
    return context


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

    # Initialize the configuration
    config = Config()
    config.load()
    logger.debug("Configuration loaded")

    # Case 1: No arguments provided (server mode)
    if not args.prompt:
        logger.info("No command or prompt provided. Starting Agent-S3 in server mode.")
        coordinator = Coordinator(config)  # No auth needed for just starting server

        ws_host = config.config.get('WEBSOCKET_HOST', 'localhost') # Changed config.get to config.config.get
        ws_port = config.config.get('WEBSOCKET_PORT', 8765)  # Changed config.get to config.config.get

        print(f"Agent-S3 server mode started. WebSocket server running at ws://{ws_host}:{ws_port}")
        print("Press Ctrl+C to stop.")

        # Correctly handle shutdown
        # The Coordinator now starts the WebSocket server in a daemon thread.
        # The main CLI thread needs to stay alive and handle signals for graceful shutdown.
        try:
            # Keep the main thread alive. The WebSocket server is in a daemon thread.
            while True:
                time.sleep(1) 
        except KeyboardInterrupt:
            logger.info("Ctrl+C received. Shutting down Agent-S3 server...")
            # The Coordinator's shutdown method now handles stopping the WebSocket server.
            if hasattr(coordinator, 'shutdown'):
                try:
                    coordinator.shutdown() # This should call websocket_server.stop_sync()
                    logger.info("Coordinator shutdown sequence initiated.")
                except Exception as e:
                    logger.error(f"Error during coordinator shutdown: {e}", exc_info=True)
            else:
                logger.warning("Coordinator does not have a shutdown method. WebSocket server might not stop gracefully.")
            print("Agent-S3 server stopped.")
            sys.exit(0)
        except Exception as e:
            logger.error(f"An unexpected error occurred in server mode: {e}", exc_info=True)
            if hasattr(coordinator, 'shutdown'): # Attempt shutdown on other errors too
                coordinator.shutdown()
            sys.exit(1)
        return  # Exit after server mode

    # Case 2: Arguments provided (command or prompt mode)
    prompt_string = " ".join(args.prompt).strip()

    # Handle /help command without initializing coordinator fully
    if prompt_string == "/help":
        display_help()
        return

    # Initialize a coordinator (basic, without auth first)
    coordinator = Coordinator(config)
    logger.debug("Coordinator initialized for command/prompt.")

    # Process special commands
    if prompt_string.startswith("/"):
        process_command(coordinator, prompt_string)
        return

    # Authenticate the user if needed for bare prompts
    github_token = os.getenv("GITHUB_TOKEN")
    if not github_token:
        # Import here to avoid circular imports if not already done by other paths
        from agent_s3.auth import authenticate_user
        logger.info("GitHub token not found. Attempting interactive authentication for prompt processing.")
        github_token = authenticate_user()
        if not github_token:
            print("Authentication required for prompt processing and was not successful. Set GITHUB_TOKEN or authenticate via /init.")
            sys.exit(1)
        logger.info("Interactive authentication successful.")

    # Re-initialize coordinator with authentication for prompt processing
    # This follows the original pattern of re-initializing/replacing the coordinator instance
    coordinator = Coordinator(config, github_token=github_token)
    logger.debug("Coordinator re-initialized with authentication for prompt processing.")

    # Route bare-text prompt through RouterAgent (orchestrator)
    router = RouterAgent()
    # Orchestrator prompt template with definitions and examples
    orchestrator_prompt = '''
You are the orchestrator for an AI coding agent. Your job is to classify the user's bare text input into one of the following routing categories. Respond with a JSON object containing "category", "rationale", and "confidence" (0-1).

Categories:
- planner: Single-concern feature or simple code change request.
  Example: "Add a logout button to the navbar." Route to the planner.
- designer: Multi-concern or architectural/design requests.
  Example: "Redesign the authentication and notification systems." Route to the designer.
- tool_user: Not a feature or design request. User wants to execute a command
  (e.g., run tests, list files, run a script).
  Example: "Run all tests" or "Show me the last 10 git commits." Route to the tool_user LLM.
- general_qa: General question/answer, may or may not be about the codebase.
  Example: "What is the purpose of this project?" or "How does OAuth2 work?"
  Route to the general_qa LLM.

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

User input: ''' + repr(prompt_string)  # Use prompt_string here
    # Use a minimal scratchpad and config for logging
    class DummyScratchpad:
        def log(self, *a, **k):
            pass
    try:
        response = router.call_llm_by_role(
            role="orchestrator",
            system_prompt="Classify the user's intent for routing.",
            user_prompt=orchestrator_prompt,
            config=config.config,  # Pass the loaded config's dictionary part
            scratchpad=DummyScratchpad()
        )
        import json as _json # Local import for clarity
        try:
            result = _json.loads(response)
            category = result.get("category", "").strip().lower()
            rationale = result.get("rationale", "")
            confidence = float(result.get("confidence", 0))
        except _json.JSONDecodeError as json_exc: # More specific exception
            logger.error(f"Orchestrator response could not be parsed as JSON: {response}. Error: {json_exc}")
            print("Error: Orchestrator response could not be parsed. Please check logs.") # Corrected f-string
            return # Exit if parsing fails
        
        logger.info(f"[Orchestrator] Routing decision: {category} (confidence: {confidence:.2f}). Rationale: {rationale}")
        # print(f"[Orchestrator] Routing decision: {category} (confidence: {confidence:.2f})\\nRationale: {rationale}") # Original print

        if confidence < 0.7 or not category:
            logger.warning(f"Orchestrator confidence low ({confidence:.2f}) or category empty for: {prompt_string}")
            clarification_options = ["planner", "designer", "tool_user", "general_qa"]
            clarification = input(f"Orchestrator is not confident. Please clarify your intent ({'/'.join(clarification_options)}): ").strip().lower()
            if clarification in clarification_options:
                category = clarification
                logger.info(f"User clarified intent to: {category}")
            else:
                logger.warning(f"Invalid clarification: {clarification}. Proceeding with original or no category.")
                # Decide fallback behavior - e.g., default to general_qa or error out
                if not category:  # If category was initially empty and clarification failed
                    print("Could not determine intent. Please try rephrasing or use a specific /command.")
                    return

        if category == "planner":
            logger.info(f"Routing to planner for prompt: {prompt_string}")
            coordinator.process_change_request(prompt_string)
        elif category == "designer":
            logger.info(f"Routing to designer for prompt: {prompt_string}")
            # Assuming execute_design is the correct method on coordinator
            if hasattr(coordinator, 'execute_design'):
                coordinator.execute_design(prompt_string)
            else:  # Fallback or error if method doesn't exist
                logger.error("Designer route selected, but 'execute_design' not found on coordinator.")
                print("Error: Design functionality not available.")
        elif category == "tool_user":
            logger.info(f"Routing to tool_user for command: {prompt_string}")
            # Ensure command_processor is available on coordinator
            if not hasattr(coordinator, 'command_processor'):
                from agent_s3.command_processor import CommandProcessor
                coordinator.command_processor = CommandProcessor(coordinator)
                logger.debug("CommandProcessor initialized for tool_user route.")

            confirmation = input(
                f"Proceed to run \'{prompt_string}\' as a shell command? (y/n) "
            ).strip().lower()
            if confirmation == "y":
                coordinator.command_processor.execute_terminal_command(prompt_string)
            else:
                print("Command aborted by user.")
        elif category == "general_qa":
            logger.info(f"Routing to general_qa for prompt: {prompt_string}")
            code_context = gather_code_context()  # Ensure this function is robust
            system_prompt = (
                "You are a Q&A assistant. Use the provided codebase context to answer "
                "questions about the project. Never reveal credentials, secrets, or sensitive file paths."
            )
            # Call orchestrator or general_qa LLM role
            qa_response = router.call_llm_by_role(  # Use a different var name for response
                role="general_qa",  # Ensure this role is configured in LLM settings
                system_prompt=system_prompt,
                user_prompt=prompt_string,  # Pass the original user prompt
                config=config.config,
                scratchpad=DummyScratchpad(),
                code_context=code_context
            )
            print(qa_response)
        else:
            logger.warning(f"Unknown or unsupported routing category: {category} for prompt: {prompt_string}")
            print(f"Unknown or unsupported routing category: {category}. Try /help for commands.")

    except Exception as e:  # Catch broader exceptions during prompt routing
        logger.error(f"Error routing prompt \'{prompt_string}\' through orchestrator: {e}", exc_info=True)
        print(f"An error occurred while processing your request: {e}")
        # sys.exit(1) # Original exit, consider if always necessary


if __name__ == "__main__":
    main()
