"""Task Manager that orchestrates workflow phases.

Handles planning, prompt generation, issue creation, and execution phases.
"""

import os
import requests
import json
import logging
from typing import Optional, List, Tuple, Dict, Any
import traceback
from pathlib import Path
from datetime import datetime  # Added missing import
import subprocess
import py_compile
import time  # Added for placeholder implementation

from agent_s3.config import Config
from agent_s3.planner import Planner
from agent_s3.code_generator import CodeGenerator
from agent_s3.prompt_moderator import PromptModerator
from agent_s3.scratchpad_manager import ScratchpadManager
from agent_s3.progress_tracker import ProgressTracker, Status
from agent_s3.tools.git_tool import GitTool
from agent_s3.tools.bash_tool import BashTool
from agent_s3.tools.file_tool import FileTool
from agent_s3.tools.code_analysis_tool import CodeAnalysisTool
from agent_s3.tools.memory_manager import MemoryManager
from agent_s3.cli import track_module_scaffold
from agent_s3.tools.tech_stack_manager import TechStackManager
from agent_s3.tool_definitions import ToolDefinitions

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class Coordinator:
    """Coordinates the workflow phases for Agent-S3."""

    def __init__(self, config: Config, github_token: Optional[str] = None):
        """Initialize the coordinator.

        Args:
            config: The loaded configuration
            github_token: Optional GitHub OAuth token for API access
        """
        self.config = config
        self.github_token = github_token
        self.is_workspace_valid: bool = False
        self.validation_failure_reason: Optional[str] = None
        
        # Initialize tech stack manager
        self.tech_stack_manager = TechStackManager()
        self.tech_stack: Optional[Dict[str, Any]] = None  # Will be populated during initialization
        self.custom_guidelines: Optional[str] = None  # Added to store generated guidelines

        # Initialize log managers
        self.scratchpad = ScratchpadManager(config)
        self.progress_tracker = ProgressTracker(config)

        # Initialize tools
        self.file_tool = FileTool()
        self.bash_tool = BashTool(sandbox=config.config["sandbox_environment"])
        self.git_tool = GitTool(github_token)
        self.code_analysis_tool = CodeAnalysisTool()
        self.memory_manager = MemoryManager()

        # Initialize components
        self.planner = Planner(self)
        self.code_generator = CodeGenerator(self)
        self.prompt_moderator = PromptModerator(self)

        # Check for interrupted tasks to resume
        self._check_for_interrupted_tasks()

        # Log initialization
        self.scratchpad.log("Coordinator", "Initialized Agent-S3 coordinator")
        if not self.progress_tracker.get_latest_progress():
            self.progress_tracker.update_progress({"phase": "initialization", "status": "pending"})

    def initialize_workspace(self):
        """Initializes the workspace by checking essential files and creating defaults if necessary."""
        logging.info("Initializing workspace...")
        self.workspace_path = Path.cwd()
        self.github_dir = self.workspace_path / ".github"
        self.guidelines_file = self.github_dir / "copilot-instructions.md"
        self.readme_file = self.workspace_path / "README.md"
        self.llm_json_file = self.workspace_path / "llm.json"

        # Core validation: README and guidelines must exist
        if not self.readme_file.exists():
            self.prompt_moderator.notify_user("README.md not found. Please add a README.md to the project root.", level="error")
            self.is_workspace_valid = False
            return
        if not self.guidelines_file.exists():
            self.prompt_moderator.notify_user(".github/copilot-instructions.md not found. Please create this file before initializing.", level="error")
            self.is_workspace_valid = False
            return
        # Optional LLM-based README.md structure validation
        if hasattr(self, '_validate_workspace_files'):
            try:
                valid = self._validate_workspace_files()
                if not valid:
                    self.prompt_moderator.notify_user("README.md structure validation failed.", level="error")
                    self.is_workspace_valid = False
                    return
            except Exception as e:
                self.scratchpad.log("Coordinator", f"Error validating README.md: {e}")
                self.prompt_moderator.notify_user("Error validating README.md structure.", level="error")
                self.is_workspace_valid = False
                return

        # Ensure .github directory exists for LLM files
        self.github_dir.mkdir(exist_ok=True)

        # Check/Create llm.json
        if not self.llm_json_file.exists():
            logging.warning(f"{self.llm_json_file} not found. Creating with default content.")
            try:
                default_content = self._get_llm_json_content()
                with open(self.llm_json_file, 'w', encoding='utf-8') as f:
                    f.write(default_content)
                logging.info(f"Created {self.llm_json_file} with default content.")
            except Exception as e:
                logging.error(f"Failed to create {self.llm_json_file}: {e}")

        # Validate essential files exist after potential creation
        if not self.guidelines_file.exists() or not self.llm_json_file.exists():
            logging.error("Essential configuration files (.github/copilot-instructions.md or llm.json) are missing and could not be created.")
            self.is_workspace_valid = False
        else:
            self.is_workspace_valid = True
            logging.info("Workspace initialized successfully.")

        # Load configuration after ensuring files exist
        if self.is_workspace_valid:
            self.config = Config(self.workspace_path)
            # Load actual guidelines from file, not default again
            try:
                with open(self.guidelines_file, 'r', encoding='utf-8') as f:
                    self.guidelines = f.read()
            except Exception as e:
                logging.error(f"Failed to read {self.guidelines_file} after creation/check: {e}")
                self.guidelines = self._get_default_guidelines()  # Fallback if read fails

            # Load llm.json content
            try:
                with open(self.llm_json_file, 'r', encoding='utf-8') as f:
                    self.llm_config = json.load(f)  # Load as JSON, not string
            except Exception as e:
                logging.error(f"Failed to read or parse {self.llm_json_file}: {e}")
                # Attempt to get default content as fallback, but parse it
                try:
                    self.llm_config = json.loads(self._get_llm_json_content())
                except json.JSONDecodeError:
                    logging.error("Failed to parse default llm.json content.")
                    self.llm_config = []  # Empty list as safe fallback

            # Re-initialize components that depend on config/guidelines/llm_config
            self.planner = Planner(self)
            self.code_generator = CodeGenerator(self)
            self.prompt_moderator = PromptModerator(self)
            self.scratchpad = ScratchpadManager(self.config)
            self.progress_tracker = ProgressTracker(self.config)

            # Detect tech stack after initialization
            try:
                self.tech_stack = self._detect_tech_stack()
            except Exception as e:
                self.scratchpad.log("Coordinator", f"Error detecting tech stack: {e}")
                self.prompt_moderator.notify_user("Tech stack analysis failed.", level="warning")
                self.tech_stack = {}

            # Generate AI-based project guidelines using initializer model
            try:
                prompt_text = f"Generate concise coding best practices and guidelines specific to the tech stack: {self.tech_stack}."
                ai_guidelines = self._call_llm_api('initializer', prompt_text)
                if ai_guidelines:
                    append = self.prompt_moderator.ask_binary_question(
                        f"AI-generated guidelines:\n{ai_guidelines}\n\nAppend to copilot-instructions.md?"
                    )
                    if append:
                        heading = "\n### AI-Generated Project Suggestions\n"
                        content = heading + ai_guidelines + "\n"
                        success, msg = self.file_tool.append_to_file(str(self.guidelines_file), content)
                        if success:
                            self.scratchpad.log("Coordinator", msg)
                        else:
                            self.scratchpad.log("Coordinator", f"Failed to append guidelines: {msg}")
                            self.prompt_moderator.notify_user(f"Failed to append AI guidelines: {msg}", level="error")
                    else:
                        self.scratchpad.log("Coordinator", "User declined AI-generated guidelines append")
            except Exception as e:
                self.scratchpad.log("Coordinator", f"AI guideline generation error: {e}")
                self.prompt_moderator.notify_user("Suggestion generation via AI failed.", level="warning")

    def _detect_tech_stack(self) -> Dict[str, Any]:
        """Detect the primary technologies used in the workspace using TechStackManager."""
        logging.info("Detecting tech stack with enhanced version information...")
        try:
            # Use the enhanced TechStackManager for better tech stack detection
            self.tech_stack_manager = TechStackManager(workspace_path=self.workspace_path)
            detected_stack = self.tech_stack_manager.detect_tech_stack()
            
            # Get structured tech stack data with versioning and best practices
            structured_data = self.tech_stack_manager.get_structured_tech_stack()
            
            # Log detected tech stack summary
            formatted_stack = self.tech_stack_manager.get_formatted_tech_stack()
            self.scratchpad.log("Coordinator", f"Detected tech stack:\n{formatted_stack}")
            logging.info(f"Tech stack detection complete with {len(structured_data['languages'])} languages, " 
                        f"{len(structured_data['frameworks'])} frameworks, " 
                        f"{len(structured_data['libraries'])} libraries")
            
            return structured_data
        except Exception as e:
            logging.error(f"Error detecting tech stack: {e}")
            self.scratchpad.log("Coordinator", f"Tech stack detection failed: {e}")
            return {"languages": [], "frameworks": [], "libraries": [], "tools": [], "versions": {}, "meta": {}}
    
    def get_file_modification_info(self) -> Dict[str, Dict[str, Any]]:
        """Get file modification information for context prioritization.
        
        Returns:
            Dictionary mapping file paths to modification metadata
        """
        file_info = {}
        try:
            # Get recent git history if available
            if not hasattr(self, 'git_tool') or not self.git_tool:
                return {}
                
            # Get repository modification history
            repo_path = str(Path.cwd())
            commit_history = self.git_tool.get_commit_history(repo_path, max_commits=30)
            
            # Track file modification counts and last modified dates
            file_counts = {}
            file_last_modified = {}
            
            if not commit_history:
                return {}
                
            current_time = datetime.now()
            
            # Process commits to extract file modification patterns
            for commit in commit_history:
                commit_date = datetime.fromisoformat(commit.get('date', '').replace('Z', '+00:00'))
                days_since = (current_time - commit_date).days
                
                # Process files changed in this commit
                files_changed = commit.get('files_changed', [])
                for file_path in files_changed:
                    # Update modification count
                    file_counts[file_path] = file_counts.get(file_path, 0) + 1
                    
                    # Update last modified date if this is more recent
                    if file_path not in file_last_modified or days_since < file_last_modified[file_path]:
                        file_last_modified[file_path] = days_since
            
            # Assemble file information dictionary
            for file_path, count in file_counts.items():
                file_info[file_path] = {
                    'modification_frequency': count,
                    'days_since_modified': file_last_modified.get(file_path, 365),
                    'last_modified': current_time - datetime.timedelta(days=file_last_modified.get(file_path, 0))
                }
                
            logging.info(f"Gathered modification info for {len(file_info)} files")
            return file_info
        except Exception as e:
            logging.error(f"Error getting file modification info: {e}")
            return {}

    def _get_default_guidelines(self) -> str:
        """Returns the default coding guidelines content."""
        return """# Default GitHub Copilot Instructions

## Core Development Criteria

### Security
- Follow OWASP Top 10.
- Validate and sanitize all inputs.
- Use parameterized queries.

### Performance
- Optimize database queries.
- Use efficient algorithms.

### Code Quality
- Follow SOLID principles.
- Write clean, readable code with comments.
- Handle errors gracefully.

### Accessibility
- Follow WCAG 2.1 AA.
- Use semantic HTML.
- Ensure keyboard navigation.
"""

    def _get_llm_json_content(self) -> str:
        """Get the llm.json content exactly as specified in instructions.md."""
        return """[
  {
    "model": "gpt-4o-mini",
    "role": "scaffolder",
    "context_window": 128000,
    "capabilities": ["fast chat","file scaffolding","simple Q&A","documentation generation","code formatting","template creation"],
    "pricing_per_million": {"input":0.15,"output":0.60},
    "api": {"endpoint":"POST https://api.openai.com/v1/chat/completions","auth_header":"Authorization: Bearer $OPENAI_KEY"},
    "example_call": "curl https://api.openai.com/v1/chat/completions \\\\n  -H \\"Authorization: Bearer $OPENAI_KEY\\" \\\\n  -H \\"Content-Type: application/json\\" \\\\n  -d '{\\\"model\\\":\\\"gpt-4o-mini\\\",\\\"messages\\\":[{\\\"role\\\":\\\"user\\\",\\\"content\\\":\\\"Generate a Python CLI project scaffold with setup.py and README\\\"}]}'",
    "use_cases": ["Generate file/project scaffolds","Format or lint code snippets","Quick dev Q&A","Boilerplate tests","Doc stubs"]
  },
  {
    "model": "mistral-7b-instruct",
    "role": "planner",
    "context_window": 32000,
    "capabilities": ["chain-of-thought planning","summarization","error analysis","dependency mapping","refactoring strategy"],
    "pricing_per_million": {"input":0.25,"output":0.25},
    "api": {"endpoint":"POST https://api.mistral.ai/v1/chat/completions","auth_header":"Authorization: Bearer $MISTRAL_KEY"},
    "example_call": "curl https://api.mistral.ai/v1/chat/completions \\\\n  -H \\"Authorization: Bearer $MISTRAL_KEY\\" \\\\n  -H \\"Content-Type: application/json\\" \\\\n  -d '{\\\"model\\\":\\\"mistral-7b-instruct\\\",\\\"messages\\\":[{\\\"role\\\":\\\"user\\\",\\\"content\\\":\\\"Plan a multi-file refactor to extract common utilities into a separate module\\\"}]}'",
    "use_cases": ["Analyze error logs","Generate refactoring plans","Summarize code","Map dependencies","Outline DB migrations"]
  },
  {
    "model": "gemini-2.5-pro",
    "role": "generator",
    "context_window": 1000000,
    "capabilities": ["multi-file code synthesis","function calling","multi-modal inputs","complex algorithm implementation","external API integration"],
    "pricing_per_million": {"free_tier_limit":200000,"paid":{"input":2.50,"output":15.00}},
    "api": {"rest_endpoint":"POST https://us-central1-aiplatform.googleapis.com/v1/projects/PROJECT/locations/LOCATION/publishers/google/models/gemini-2.5-pro:predict"},
    "example_call": "curl -X POST \\\\n  -H \\"Authorization: Bearer $GEMINI_KEY\\" \\\\n  -H \\"Content-Type: application/json\\" \\\\n  https://us-central1-aiplatform.googleapis.com/v1/projects/PROJECT/locations/LOCATION/publishers/google/models/gemini-2.5-pro:predict \\\\n  -d '{\\\"instances\\\":[{\\\"content\\\":\\\"Generate a patch to integrate OAuth2 login across all Flask routes\\\"}]}'",
    "use_cases": ["Generate multi-file patches","Implement complex features","Write end-to-end tests","Refactor large modules","Translate code between languages"]
  }
]"""

    def _check_for_interrupted_tasks(self) -> None:
        """Check development_status.json to potentially resume an interrupted task."""
        status_path = self.config.get_log_file_path("development")
        if not os.path.exists(status_path):
            self.scratchpad.log("Coordinator", "No development status file found, starting fresh.")
            return

        try:
            with open(status_path, "r") as f:
                status_data = json.load(f)

            last_status = status_data[-1] if status_data else None
            if not last_status:
                self.scratchpad.log("Coordinator", "Development status file is empty.")
                return

            phase = last_status.get("phase")
            status = last_status.get("status")
            timestamp = last_status.get("timestamp")
            request = last_status.get("request")

            self.scratchpad.log("Coordinator", f"Found previous state: Phase='{phase}', Status='{status}' at {timestamp}")

            if status != "completed" and phase != "initialization":
                print(f"\nDetected a potentially interrupted task from {timestamp} (Phase: {phase}).")
                if request:
                    print(f"Original request: {request}")

                user_input = input("Do you want to attempt resuming this task? (yes/no): ").strip().lower()
                if user_input in ["yes", "y"]:
                    self.scratchpad.log("Coordinator", "User chose to resume task.")
                    print("Resumption logic needs further implementation. Please re-enter the request manually if needed.")
                else:
                    self.scratchpad.log("Coordinator", "User chose not to resume task.")
        except Exception as e:
            self.scratchpad.log("Coordinator", f"Error checking for interrupted tasks: {e}")
            print(f"Warning: Could not parse development status file: {e}")

    def _update_development_status(self, status: str, message: str):
        """Update the development_status.json file with the current state."""
        status_path = self.config.get_log_file_path("development")
        entry = {
            "status": status,
            "message": message,
            "timestamp": datetime.now().isoformat()
        }
        self.scratchpad.log("Coordinator", f"Updating development status: Status='{status}', Message='{message}'")

        try:
            data = []
            if os.path.exists(status_path):
                try:
                    with open(status_path, "r") as f:
                        content = f.read()
                        if content.strip():
                            data = json.loads(content)
                            if not isinstance(data, list):
                                data = [data]
                        else:
                            data = []
                except json.JSONDecodeError:
                    self.scratchpad.log("Coordinator", f"Warning: development_status.json is corrupted. Starting fresh.")
                    data = []

            data.append(entry)

            max_entries = 100
            if len(data) > max_entries:
                data = data[-max_entries:]

            with open(status_path, "w") as f:
                json.dump(data, f, indent=2)

        except Exception as e:
            self.scratchpad.log("Coordinator", f"Error updating development status file: {e}")
            print(f"Warning: Failed to update development status: {e}")

    def _load_context_for_role(self, target_role: str, user_request: str, conversation_history: List[Dict[str, Any]]) -> Dict[str, str]:
        """
        Load system prompt and context data for the given role, managing token limits and truncation.
        Returns dict with 'system_prompt' and 'context_data'.
        """
        # Load role config
        role_cfg = {e['role']: e for e in self.llm_config}.get(target_role)
        if not role_cfg:
            return {'system_prompt': '', 'context_data': ''}
        # Load system prompt file
        sys_path = role_cfg.get('system_prompt_path', '')
        try:
            sys_prompt = PromptModerator.load_system_prompt(sys_path)
        except:
            sys_prompt = ''
        # Base context: user request and last 5 history turns
        hist = '\n'.join([f"{m['role']}: {m['content']}" for m in conversation_history[-5:]])
        context = f"User Request:\n{user_request}\n\nHistory (last 5):\n{hist}"
        # Inject tool definitions for tool_user
        if target_role == 'tool_user':
            tools = ToolDefinitions.get_all()  # assuming utility
            sys_prompt = sys_prompt.replace('{{TOOL_DEFINITIONS}}', tools)
        return {'system_prompt': sys_prompt, 'context_data': context}

    def _execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> str:
        """Execute specified tool and return its output as string."""
        try:
            tool = getattr(self, f"{tool_name}")
            if hasattr(tool, 'run'):
                return tool.run(**parameters)
            elif hasattr(tool, 'execute'):
                return tool.execute(**parameters)
        except Exception as e:
            return f"Error executing {tool_name}: {e}"
        return f"Unknown tool: {tool_name}"

    def run_task(self, task_description: str):
        """
        Orchestrates the execution of a given development task.

        Args:
            task_description: The user's request or task description.
        """
        self.scratchpad.log("Coordinator", f"Starting task: {task_description}")
        self.progress_tracker.update_progress({"phase": "initialization", "status": "started", "request": task_description})

        # --- Planning Phase ---
        try:
            self.progress_tracker.update_progress({"phase": "planning", "status": "started"})
            # Generate the initial plan with discussion
            plan_data, summary, code_context = self.planner.generate_plan(task_description)

            if not plan_data or not summary:
                # Error handled and logged within generate_plan
                self.scratchpad.log("Coordinator", "Task aborted due to planning failure.")
                self.progress_tracker.update_progress({"phase": "planning", "status": "failed", "error": "Plan generation returned None"})
                return # Abort task

            # Confirm plan with user (handles potential modification loop internally)
            user_decision, final_plan_data = self.planner.confirm_and_potentially_modify_plan(
                plan_data, task_description
            )

            # Handle user decision
            if user_decision == "no":
                self.scratchpad.log("Coordinator", "Task aborted by user after planning.")
                self.progress_tracker.update_progress({"phase": "planning", "status": "aborted_by_user"})
                return # Abort task
            elif user_decision == "yes":
                # User confirmed, proceed with the final plan
                plan = final_plan_data["plan"]
                discussion = final_plan_data["discussion"] # Keep discussion for potential later use/logging
                self.scratchpad.log("Coordinator", "Plan approved by user. Proceeding to issue creation.")
                self.progress_tracker.update_progress({"phase": "planning", "status": "completed"})
            else:
                # Should not happen if confirm_and_potentially_modify_plan works correctly
                self.scratchpad.log("Coordinator", f"Unexpected decision '{user_decision}' from planner confirmation. Aborting.")
                self.progress_tracker.update_progress({"phase": "planning", "status": "failed", "error": f"Unexpected confirmation result: {user_decision}"})
                return # Abort task

        except Exception as e:
            self.scratchpad.log("Coordinator", f"Error during planning phase: {e}")
            traceback.print_exc()
            self.progress_tracker.update_progress({"phase": "planning", "status": "failed", "error": str(e)})
            self.prompt_moderator.notify_user(f"An error occurred during planning: {e}", level="error")
            return # Abort task

        # --- GitHub Issue Creation Phase (if applicable) ---
        issue_url = None
        create_issue = self.config.config.get("create_github_issue", True) # Check config if issue creation is enabled

        if create_issue:
            self.progress_tracker.update_progress({"phase": "issue_creation", "status": "started"})
            try:
                self.scratchpad.log("Coordinator", "Creating GitHub issue...")
                # Prepare issue content (using plan and maybe discussion summary)
                issue_title = f"Implement: {summary}" # Use summary for title
                issue_body = f"**Original Request:**\n{task_description}\n\n**Implementation Plan:**\n```markdown\n{plan}\n```\n\n**Persona Discussion Summary:**\n(Add summary of discussion if needed, or link to full log)" # Include plan in body

                # Assume git_tool has a method create_github_issue
                if hasattr(self.git_tool, 'create_github_issue') and self.git_tool.is_configured():
                    repo_owner, repo_name = self.git_tool.get_repo_info()
                    if repo_owner and repo_name:
                        issue_url = self.git_tool.create_github_issue(repo_owner, repo_name, issue_title, issue_body)
                        if issue_url:
                            self.scratchpad.log("Coordinator", f"Created GitHub issue: {issue_url}")
                            self.prompt_moderator.notify_user(f"Successfully created GitHub issue: {issue_url}", level="success")
                            self.progress_tracker.update_progress({"phase": "issue_creation", "status": "completed", "url": issue_url})
                        else:
                            raise RuntimeError("git_tool.create_github_issue returned None")
                    else:
                        self.scratchpad.log("Coordinator", "Could not determine repo owner/name. Skipping GitHub issue creation.")
                        self.progress_tracker.update_progress({"phase": "issue_creation", "status": "skipped", "reason": "Repo info unavailable"})
                else:
                    self.scratchpad.log("Coordinator", "GitTool not configured or create_github_issue method missing. Skipping GitHub issue creation.")
                    self.prompt_moderator.notify_user("Skipping GitHub issue creation (GitTool not configured).", level="warning")
                    self.progress_tracker.update_progress({"phase": "issue_creation", "status": "skipped", "reason": "GitTool not configured"})

            except Exception as e:
                self.scratchpad.log("Coordinator", f"Error creating GitHub issue: {e}")
                traceback.print_exc()
                self.progress_tracker.update_progress({"phase": "issue_creation", "status": "failed", "error": str(e)})
                self.prompt_moderator.notify_user(f"Failed to create GitHub issue: {e}", level="error")
                # Decide whether to continue or abort if issue creation fails
                # For now, we continue to code generation
                self.prompt_moderator.notify_user("Continuing to code generation despite issue creation failure.", level="warning")
        else:
            self.scratchpad.log("Coordinator", "GitHub issue creation is disabled in config.")
            self.progress_tracker.update_progress({"phase": "issue_creation", "status": "skipped", "reason": "Disabled in config"})

        # --- Code Generation Phase ---
        try:
            self.progress_tracker.update_progress({"phase": "code_generation", "status": "started"})
            self.scratchpad.log("Coordinator", "Starting code generation phase.")

            # Pass the final, approved plan to the code generator along with code_context and tech_stack
            success = self.code_generator.generate_code(
                task_description, 
                plan, 
                issue_url, 
                tech_stack=self.tech_stack or {}, 
                code_context=code_context or {}
            )

            if success:
                self.scratchpad.log("Coordinator", "Code generation completed successfully.")
                self.progress_tracker.update_progress({"phase": "code_generation", "status": "completed"})
                self.prompt_moderator.notify_user("Code generation finished successfully.", level="success")
            else:
                # Errors should be handled within code_generator, but log here too
                self.scratchpad.log("Coordinator", "Code generation phase failed or was aborted.")
                self.progress_tracker.update_progress({"phase": "code_generation", "status": "failed", "error": "Code generation process did not complete successfully"})
                # Notification handled by code_generator or moderator

        except Exception as e:
            self.scratchpad.log("Coordinator", f"Error during code generation phase: {e}")
            traceback.print_exc()
            self.progress_tracker.update_progress({"phase": "code_generation", "status": "failed", "error": str(e)})
            self.prompt_moderator.notify_user(f"An error occurred during code generation: {e}", level="error")
            return # Abort task

        # --- Finalization Phase (e.g., PR creation, cleanup) ---
        # Add further steps like automated PR creation if needed
        self.scratchpad.log("Coordinator", "Task orchestration completed.")
        self.progress_tracker.update_progress({"phase": "finalization", "status": "completed"})

    # ... rest of the Coordinator class ...
