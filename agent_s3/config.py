"""Loads fixed coding guidelines from .github/copilot-instructions.md.

As per instructions.md:
"load fixed coding guidelines from .github/copilot-instructions.md"
"""

import os
import re
from pathlib import Path
from typing import Dict, List, Any, Optional

# Constants loaded from environment or defaults
# Update default context window sizes to match llm.json
CONTEXT_WINDOW_SCAFFOLDER = int(os.getenv('CONTEXT_WINDOW_SCAFFOLDER', '1047576')) # gpt-4.1-nano
CONTEXT_WINDOW_PLANNER   = int(os.getenv('CONTEXT_WINDOW_PLANNER',   '327680'))  # llama-4-scout
CONTEXT_WINDOW_GENERATOR = int(os.getenv('CONTEXT_WINDOW_GENERATOR', '1048576')) # gemini-2.5-flash
TOP_K_RETRIEVAL          = int(os.getenv('TOP_K_RETRIEVAL',          '5'))
EVICTION_THRESHOLD       = float(os.getenv('EVICTION_THRESHOLD',       '0.90'))
VECTOR_STORE_PATH        = os.getenv('VECTOR_STORE_PATH',        './data/vector_store.faiss')
MAX_RETRIES              = int(os.getenv('MAX_RETRIES',              '3'))
INITIAL_BACKOFF          = float(os.getenv('INITIAL_BACKOFF',          '1.0'))
BACKOFF_MULTIPLIER       = float(os.getenv('BACKOFF_MULTIPLIER',       '2.0'))
FAILURE_THRESHOLD        = int(os.getenv('FAILURE_THRESHOLD',        '5'))
COOLDOWN_PERIOD          = int(os.getenv('COOLDOWN_PERIOD',          '300'))
DEV_MODE                 = os.getenv('DEV_MODE', 'false').lower() == 'true'
DEV_GITHUB_TOKEN         = os.getenv('DEV_GITHUB_TOKEN')
TARGET_ORG               = os.getenv('TARGET_ORG')
# Remove individual keys, add OPENROUTER_KEY
OPENROUTER_KEY           = os.getenv('OPENROUTER_KEY')


class Config:
    """Configuration manager for Agent-S3.
    
    Loads and provides access to configuration data and coding guidelines from .github/copilot-instructions.md.
    """
    
    def __init__(self, guidelines_path: Optional[str] = None):
        """Initialize the configuration manager.
        
        Args:
            guidelines_path: Optional path to the guidelines file. If not provided,
                           uses the default path in the project root.
        """
        # Default paths
        self.guidelines_path = guidelines_path or str(Path(os.getcwd()) / ".github" / "copilot-instructions.md")
        
        # Default values
        self.guidelines: List[str] = []
        self.config: Dict[str, Any] = {
            "models": {
                # Update default model names
                "scaffolder": "openai/gpt-4.1-nano",
                "planner": "meta-llama/llama-4-scout-17b-16e-instruct",
                "code_generator": "google/gemini-2.5-flash-preview",
                # Assuming scaffolder acts as fallback
                "fallback_planner": "openai/gpt-4.1-nano",
                "fallback_generator": "openai/gpt-4.1-nano"
            },
            "max_iterations": 5,
            "sandbox_environment": True,
            "log_files": {
                "scratchpad": "scratchpad.txt",
                "progress": "progress_log.json",
                "development": "development_status.json"
            },
            # Database configurations - disabled by default, uncomment to use
            "databases": {
                "default": {
                    "type": "postgresql",  # "postgresql", "mysql", or "sqlite"
                    "name": "default",     # Used for environment variable naming (DB_DEFAULT_USER)
                    "host": "localhost",
                    "port": 5432,
                    "database": "agent_s3_db",
                    "pool_size": 5,
                    "max_overflow": 10,
                    "timeout": 30,
                    "recycle": 3600
                }
                # To add SQLite support:
                # "sqlite_db": {
                #     "type": "sqlite",
                #     "name": "sqlite_db",
                #     "path": "./data/sqlite_db.sqlite"
                # }
            }
        }
    
    def load(self) -> None:
        """Load configuration and guidelines.
        
        As per instructions.md:
        - Load fixed coding guidelines from .github/copilot-instructions.md
        - Load runtime parameters from environment variables
        """
        # Extract guidelines from copilot-instructions.md
        self.guidelines = self._extract_guidelines_from_md()

        # Load runtime parameters
        env = os.environ
        self.config.update({
            'context_window_scaffolder': CONTEXT_WINDOW_SCAFFOLDER,
            'context_window_planner': CONTEXT_WINDOW_PLANNER,
            'context_window_generator': CONTEXT_WINDOW_GENERATOR,
            'top_k_retrieval': TOP_K_RETRIEVAL,
            'eviction_threshold': EVICTION_THRESHOLD,
            'vector_store_path': VECTOR_STORE_PATH,
            'max_retries': MAX_RETRIES,
            'initial_backoff': INITIAL_BACKOFF,
            'backoff_multiplier': BACKOFF_MULTIPLIER,
            'failure_threshold': FAILURE_THRESHOLD,
            'cooldown_period': COOLDOWN_PERIOD,
            'dev_mode': DEV_MODE,
            'dev_github_token': DEV_GITHUB_TOKEN,
            'github_app_id': env.get('GITHUB_APP_ID', ''),
            'github_private_key': env.get('GITHUB_PRIVATE_KEY', ''),
            # Remove individual keys, add OPENROUTER_KEY
            'openrouter_key': env.get('OPENROUTER_KEY', '')
        })
        # Security settings for shell command execution
        self.config['denylist'] = [cmd.strip() for cmd in env.get('DENYLIST_COMMANDS', 'rm,shutdown,reboot').split(',') if cmd.strip()]
        self.config['command_timeout'] = float(env.get('COMMAND_TIMEOUT', '30.0'))
        # Validate and raise on missing critical environment variables
        missing = []
        for var in ('github_app_id', 'github_private_key'):
            if not self.config.get(var):
                missing.append(var.upper())
        if missing:
            raise EnvironmentError(f"Missing required environment variables: {', '.join(missing)}")
        # Load allowed GitHub organizations for access control
        self.config['allowed_orgs'] = [org.strip() for org in env.get('GITHUB_ORG', '').split(',') if org.strip()]

        # Validate required keys
        self._validate_keys()

    def _validate_keys(self) -> None:
        """Validate that required API keys are present, especially outside DEV_MODE."""
        # Update required keys check
        required_keys_prod = [
            'github_app_id', 'github_private_key',
            'openrouter_key' # Check for OpenRouter key now
        ]
        missing_keys = []
        if not self.config.get('dev_mode'):
            for key in required_keys_prod:
                if not self.config.get(key):
                    missing_keys.append(key.upper()) # Use env var name convention

            if 'allowed_orgs' not in self.config or not self.config['allowed_orgs']:
                 missing_keys.append('GITHUB_ORG')

            if missing_keys:
                print(f"Warning: The following required environment variables are missing or empty: {', '.join(missing_keys)}")
                # In a real application, you might raise an error or exit here
                # raise ValueError(f"Missing required environment variables: {', '.join(missing_keys)}")
        elif not self.config.get('dev_github_token'):
             print("Warning: DEV_MODE is true, but DEV_GITHUB_TOKEN is missing or empty.")
             # Consider raising an error if DEV_GITHUB_TOKEN is essential for dev mode functionality

    def _extract_guidelines_from_md(self) -> List[str]:
        """Extract guidelines from .github/copilot-instructions.md."""
        guidelines = []
        
        if os.path.exists(self.guidelines_path):
            try:
                with open(self.guidelines_path, "r") as f:
                    content = f.read()
                
                # Extract guidelines from the markdown file
                # Look for lines with code quality guidelines and bullet points
                code_quality_section = False
                for line in content.split("\n"):
                    # Check if we've entered the code quality section
                    if "Code Quality" in line or "Project-Specific Guidelines" in line or "Code Style Guidelines" in line:
                        code_quality_section = True
                        continue
                    
                    # Look for bullet points in the code quality section
                    if code_quality_section and line.strip().startswith("-"):
                        # Extract the guideline text, removing the bullet point
                        guideline = line.strip()[1:].strip()
                        if guideline and len(guideline) > 5:  # Ensure it's not too short
                            guidelines.append(guideline)
                    
                    # Also look for numbered lists
                    numbered_match = re.match(r'^\s*\d+\.\s+(.+)$', line)
                    if code_quality_section and numbered_match:
                        guideline = numbered_match.group(1).strip()
                        if guideline and len(guideline) > 5:  # Ensure it's not too short
                            guidelines.append(guideline)
                
                # If we couldn't extract any guidelines, use default ones
                if not guidelines:
                    guidelines = self._get_default_guidelines()
            except Exception as e:
                print(f"Error extracting guidelines from {self.guidelines_path}: {e}")
                # Fall back to default guidelines
                guidelines = self._get_default_guidelines()
        else:
            # If the file doesn't exist, use default guidelines
            guidelines = self._get_default_guidelines()
        
        return guidelines
    
    def _get_default_guidelines(self) -> List[str]:
        """Get default guidelines."""
        return [
            "Use meaningful variable and function names",
            "Include type hints for function parameters and returns",
            "Document all functions and classes with docstrings",
            "Follow PEP 8 coding style guidelines",
            "Handle errors with appropriate try/except blocks",
            "Use f-strings for string formatting",
            "Use absolute imports within the package",
            "Avoid global variables",
            "Write unit tests for all functionality",
            "Log all operations with proper timestamp and role labels"
        ]
    
    def get_log_file_path(self, log_type: str) -> str:
        """Get the path to a log file.
        
        Args:
            log_type: The type of log file to get ("scratchpad", "progress", or "development")
            
        Returns:
            The absolute path to the log file
        """
        if log_type not in self.config["log_files"]:
            raise ValueError(f"Unknown log type: {log_type}")
        
        filename = self.config["log_files"][log_type]
        return str(Path(os.getcwd()) / filename)