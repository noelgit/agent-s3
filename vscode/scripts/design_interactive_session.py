import sys
import json
import os
import logging

# Suppress INFO logging for cleaner interactive session
logging.getLogger().setLevel(logging.WARNING)
# Also suppress specific noisy loggers
logging.getLogger('faiss').setLevel(logging.WARNING)
logging.getLogger('agent_s3').setLevel(logging.WARNING)

# Add vscode directory to sys.path to allow agent_s3 import if script is run directly
# This might not be needed when spawned from extension.ts if PYTHONPATH is configured
script_dir = os.path.dirname(os.path.abspath(__file__))
vscode_dir = os.path.dirname(script_dir)
# sys.path.insert(0, vscode_dir) # Temporarily commented out, assuming extension handles PYTHONPATH

try:
    from agent_s3.coordinator import Coordinator
    from agent_s3.design_manager import DesignManager
except ImportError as e:
    # If imports fail, send an error message back to the extension
    error_message = {
        "type": "error",
        "content": f"Failed to import agent_s3 modules: {str(e)}. Ensure PYTHONPATH includes the project root."
    }
    print(json.dumps(error_message))
    sys.stdout.flush()
    sys.exit(1)

def send_response(response_type, content, is_complete=None):
    """Helper to send JSON responses."""
    try:
        payload = {"type": response_type, "content": content}
        if is_complete is not None:
            payload["is_complete"] = is_complete
        print(json.dumps(payload))
        sys.stdout.flush()
    except Exception as e:
        # Fallback error response
        error_payload = {"type": "error", "content": f"Failed to send response: {str(e)}"}
        print(json.dumps(error_payload))
        sys.stdout.flush()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        send_response("error", "Missing objective argument.")
        sys.exit(1)

    objective = sys.argv[1]

    try:
        coordinator = Coordinator()
        design_manager = DesignManager(coordinator) # TODO: Consider loading existing state if any
        send_response("system_message", f"Initialized design manager successfully for objective: {objective}")
    except Exception as e:
        send_response("error", f"Failed to initialize DesignManager: {str(e)}")
        sys.exit(1)

    # Initial response
    try:
        ai_response = design_manager.start_design_conversation(objective)
        # Check for completion right after starting, in case the objective is immediately resolvable
        # or if start_design_conversation itself can mark it complete.
        is_complete = False
        if hasattr(design_manager, 'detect_design_completion'):
            is_complete = design_manager.detect_design_completion()

        send_response("ai_response", ai_response, is_complete)

        if is_complete:
            if hasattr(design_manager, 'write_design_to_file'):
                success, message = design_manager.write_design_to_file()
                send_response("system_message", f"Write to file after initial prompt: {message}")
            sys.exit(0)

    except Exception as e:
        send_response("error", f"Error in start_design_conversation: {str(e)}")
        sys.exit(1)

    while True:
        try:
            line = sys.stdin.readline()
            if not line:  # EOF
                send_response("system_message", "Stdin closed, terminating.")
                break

            line = line.strip()
            if not line:  # Skip empty lines
                continue

            try:
                user_input_data = json.loads(line)
                user_input = user_input_data.get("content")
                if user_input is None:
                    send_response("error", "Invalid input: JSON 'content' field missing.")
                    continue
            except json.JSONDecodeError:
                send_response("error", f"Invalid input: Not valid JSON. Received: {line}")
                continue

            if user_input.lower() == "/finalize-design":
                # This is a placeholder. Actual finalization might be more complex
                # and depend on DesignManager's capabilities.
                # For now, we assume it triggers completion.
                final_design_response = "Attempting to finalize design. (Placeholder)"
                if hasattr(design_manager, 'finalize_design'):
                    final_design_response = design_manager.finalize_design()

                send_response("ai_response", f"Finalizing design... {final_design_response}", True)
                is_complete = True
            else:
                ai_response, is_complete = design_manager.continue_conversation(user_input)
                send_response("ai_response", ai_response, is_complete)

            if is_complete:
                if hasattr(design_manager, 'write_design_to_file'):
                    success, message = design_manager.write_design_to_file()
                    send_response("system_message", f"Write to file after conversation turn: {message}")
                break

        except KeyboardInterrupt: # Graceful exit on Ctrl+C
            send_response("system_message", "Session interrupted by user (KeyboardInterrupt).")
            break
        except Exception as e:
            send_response("error", f"Runtime error in conversation loop: {str(e)}")
            break

    sys.exit(0)
