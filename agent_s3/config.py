"""Config manager module for Agent-S3.

Handles configuration loading and default parameters.
"""

import os
import re
import json
import logging
import platform
import threading
from pathlib import Path
from typing import Optional, Dict, List, Any

from pydantic import BaseModel, ValidationError, Field

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Default values with thread safety
_config_instance = None
_config_lock = threading.Lock()

# Adaptive Configuration settings - always enabled
ADAPTIVE_CONFIG_REPO_PATH = os.getcwd()
ADAPTIVE_CONFIG_DIR = os.path.join(ADAPTIVE_CONFIG_REPO_PATH, '.agent_s3', 'config')
ADAPTIVE_METRICS_DIR = os.path.join(ADAPTIVE_CONFIG_REPO_PATH, '.agent_s3', 'metrics')
ADAPTIVE_OPTIMIZATION_INTERVAL = 3600  # Optimize hourly

# Context Window Sizes (tokens)
CONTEXT_WINDOW_SCAFFOLDER = int(os.getenv('CONTEXT_WINDOW_SCAFFOLDER', '16384'))
CONTEXT_WINDOW_PLANNER = int(os.getenv('CONTEXT_WINDOW_PLANNER', '16384'))
CONTEXT_WINDOW_GENERATOR = int(os.getenv('CONTEXT_WINDOW_GENERATOR', '16384'))
# Context optimization settings
CONTEXT_BACKGROUND_OPT_TARGET_TOKENS = int(os.getenv('CONTEXT_BACKGROUND_OPT_TARGET_TOKENS', '16000'))

# Library parameters
TOP_K_RETRIEVAL = int(os.getenv('TOP_K_RETRIEVAL', '10'))
EVICTION_THRESHOLD = int(os.getenv('EVICTION_THRESHOLD', '10000'))
VECTOR_STORE_PATH = os.getenv('VECTOR_STORE_PATH', '.cache')

# Error recovery parameters
MAX_RETRIES = int(os.getenv('MAX_RETRIES', '3'))
INITIAL_BACKOFF = float(os.getenv('INITIAL_BACKOFF', '1.0'))
BACKOFF_MULTIPLIER = float(os.getenv('BACKOFF_MULTIPLIER', '2.0'))
FAILURE_THRESHOLD = int(os.getenv('FAILURE_THRESHOLD', '5'))
COOLDOWN_PERIOD = int(os.getenv('COOLDOWN_PERIOD', '300'))

# Default API parameters
DEV_MODE = os.getenv('DEV_MODE', 'true').lower() == 'true'
DEV_GITHUB_TOKEN = os.getenv('GITHUB_TOKEN', '')

# LLM API error recovery parameters
LLM_MAX_RETRIES = int(os.getenv('LLM_MAX_RETRIES', '3'))
LLM_INITIAL_BACKOFF = float(os.getenv('LLM_INITIAL_BACKOFF', '1.0'))
LLM_BACKOFF_FACTOR = float(os.getenv('LLM_BACKOFF_FACTOR', '2.0'))
LLM_FALLBACK_STRATEGY = os.getenv('LLM_FALLBACK_STRATEGY', 'retry_simplified')
LLM_DEFAULT_TIMEOUT = float(os.getenv('LLM_DEFAULT_TIMEOUT', '60.0'))
LLM_EXPLAIN_PROMPT_MAX_LEN = int(os.getenv('LLM_EXPLAIN_PROMPT_MAX_LEN', '1000'))
LLM_EXPLAIN_RESPONSE_MAX_LEN = int(os.getenv('LLM_EXPLAIN_RESPONSE_MAX_LEN', '1000'))

# CLI command execution parameters - CLI command warnings always enabled for safety
CLI_COMMAND_MAX_SIZE     = int(os.getenv('CLI_COMMAND_MAX_SIZE',     '10000'))
# New configuration for CodeAnalysisTool query cache TTL
QUERY_CACHE_TTL_SECONDS  = int(os.getenv('QUERY_CACHE_TTL_SECONDS',  '3600')) # Default 1 hour
# Cache configuration for filesystem monitoring and memory management
CACHE_DEBOUNCE_DELAY     = float(os.getenv('CACHE_DEBOUNCE_DELAY',   '0.5'))  # Default 0.5 seconds
MAX_QUERY_THEMES         = int(os.getenv('MAX_QUERY_THEMES',        '50'))    # Default 50 themes
# Configuration for LLM summarization features - always enabled for token efficiency
MIN_SIZE_FOR_LLM_SUMMARIZATION = int(os.getenv('MIN_SIZE_FOR_LLM_SUMMARIZATION', '1000'))
SUMMARY_CACHE_MAX_SIZE   = int(os.getenv('SUMMARY_CACHE_MAX_SIZE',   '500'))
# Embedding generation configuration
EMBEDDING_RETRY_COUNT    = int(os.getenv('EMBEDDING_RETRY_COUNT',    '3'))
EMBEDDING_BACKOFF_INITIAL = float(os.getenv('EMBEDDING_BACKOFF_INITIAL', '1.0'))
EMBEDDING_BACKOFF_FACTOR = float(os.getenv('EMBEDDING_BACKOFF_FACTOR', '2.0'))
EMBEDDING_TIMEOUT        = float(os.getenv('EMBEDDING_TIMEOUT',      '30.0'))
# Default timeout for external HTTP requests
HTTP_DEFAULT_TIMEOUT     = float(os.getenv('HTTP_DEFAULT_TIMEOUT', '30.0'))
# Specialized LLM roles configuration
EMBEDDER_ROLE_NAME       = os.getenv('EMBEDDER_ROLE_NAME',     'embedder')
SUMMARIZER_ROLE_NAME     = os.getenv('SUMMARIZER_ROLE_NAME',   'summarizer')
SUMMARIZER_MAX_CHUNK_SIZE = int(os.getenv('SUMMARIZER_MAX_CHUNK_SIZE', '2048'))
SUMMARIZER_TIMEOUT       = float(os.getenv('SUMMARIZER_TIMEOUT',      '45.0'))
# System design pattern validation
MAX_DESIGN_PATTERNS      = int(os.getenv('MAX_DESIGN_PATTERNS', '3'))

class ModelsConfig(BaseModel):
    """Model names for various agent components."""

    scaffolder: str = "openai/gpt-4.1-nano"
    planner: str = "meta-llama/llama-4-scout-17b-16e-instruct"
    code_generator: str = "google/gemini-2.5-flash-preview"
    fallback_planner: str = "openai/gpt-4.1-nano"
    fallback_generator: str = "openai/gpt-4.1-nano"


class LogFilesConfig(BaseModel):
    """Paths to log files relative to workspace."""

    development: str = "progress_log.jsonl"
    debug: str = "debug_log.json"
    error: str = "error_log.json"


class EmbeddingConfig(BaseModel):
    chunk_size: int = 1000
    chunk_overlap: int = 200


class SearchBm25Config(BaseModel):
    k1: float = 1.2
    b: float = 0.75


class SearchConfig(BaseModel):
    bm25: SearchBm25Config = SearchBm25Config()


class SummarizationConfig(BaseModel):
    threshold: int = 2000
    compression_ratio: float = 0.5


class ImportanceScoringConfig(BaseModel):
    code_weight: float = 1.0
    comment_weight: float = 0.8
    metadata_weight: float = 0.7
    framework_weight: float = 0.9


class ContextManagementConfig(BaseModel):
    # Context management always enabled for optimal performance
    optimization_interval: int = 60
    embedding: EmbeddingConfig = EmbeddingConfig()
    search: SearchConfig = SearchConfig()
    summarization: SummarizationConfig = SummarizationConfig()
    importance_scoring: ImportanceScoringConfig = ImportanceScoringConfig()


class AdaptiveConfig(BaseModel):
    # Adaptive configuration always enabled for optimal performance
    auto_adjust: bool = True
    profile_repo_on_start: bool = True
    metrics_collection: bool = True
    repo_path: str = ADAPTIVE_CONFIG_REPO_PATH
    config_dir: str = ADAPTIVE_CONFIG_DIR
    metrics_dir: str = ADAPTIVE_METRICS_DIR
    optimization_interval: int = ADAPTIVE_OPTIMIZATION_INTERVAL


class ConfigModel(BaseModel):
    """Typed configuration validated by Pydantic."""

    models: ModelsConfig = ModelsConfig()
    max_iterations: int = 5
    complexity_threshold: int = 250
    complexity_scale_factor: float = 0.15
    complexity_scale_exponent: float = 0.8
    workspace_path: str = "."
    log_files: LogFilesConfig = LogFilesConfig()
    context_management: ContextManagementConfig = ContextManagementConfig()
    adaptive_config: AdaptiveConfig = AdaptiveConfig()
    # Security features always enabled
    check_auth: bool = True
    sandbox_environment: bool = True
    interactive: bool = True
    allow_interactive_clarification: bool = True
    openrouter_key: str = os.environ.get("OPENROUTER_KEY", "")
    openai_key: str = os.environ.get("OPENAI_KEY", "")
    encryption_key: str = os.environ.get("AGENT_S3_ENCRYPTION_KEY", "")
    dev_github_token: str = DEV_GITHUB_TOKEN
    llm_max_retries: int = LLM_MAX_RETRIES
    llm_initial_backoff: float = LLM_INITIAL_BACKOFF
    llm_backoff_factor: float = LLM_BACKOFF_FACTOR
    llm_fallback_strategy: str = LLM_FALLBACK_STRATEGY
    llm_default_timeout: float = LLM_DEFAULT_TIMEOUT
    llm_explain_prompt_max_len: int = LLM_EXPLAIN_PROMPT_MAX_LEN
    llm_explain_response_max_len: int = LLM_EXPLAIN_RESPONSE_MAX_LEN
    # CLI command warnings always enabled for safety
    cli_command_max_size: int = CLI_COMMAND_MAX_SIZE
    query_cache_ttl_seconds: int = QUERY_CACHE_TTL_SECONDS
    cache_debounce_delay: float = CACHE_DEBOUNCE_DELAY
    max_query_themes: int = MAX_QUERY_THEMES
    min_size_for_llm_summarization: int = MIN_SIZE_FOR_LLM_SUMMARIZATION
    summary_cache_max_size: int = SUMMARY_CACHE_MAX_SIZE
    # LLM summarization always enabled for token efficiency
    embedding_retry_count: int = EMBEDDING_RETRY_COUNT
    embedding_backoff_initial: float = EMBEDDING_BACKOFF_INITIAL
    embedding_backoff_factor: float = EMBEDDING_BACKOFF_FACTOR
    embedding_timeout: float = EMBEDDING_TIMEOUT
    http_default_timeout: float = HTTP_DEFAULT_TIMEOUT
    embedder_role_name: str = EMBEDDER_ROLE_NAME
    summarizer_role_name: str = SUMMARIZER_ROLE_NAME
    summarizer_max_chunk_size: int = SUMMARIZER_MAX_CHUNK_SIZE
    summarizer_timeout: float = SUMMARIZER_TIMEOUT
    max_design_patterns: int = MAX_DESIGN_PATTERNS
    # Adaptive configuration always enabled
    adaptive_config_repo_path: str = ADAPTIVE_CONFIG_REPO_PATH
    adaptive_config_dir: str = ADAPTIVE_CONFIG_DIR
    adaptive_metrics_dir: str = ADAPTIVE_METRICS_DIR
    adaptive_optimization_interval: int = ADAPTIVE_OPTIMIZATION_INTERVAL

    class Config:
        extra = "allow"


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

        # OS Detection
        self.host_os_type = platform.system().lower()
        self.host_os = self.host_os_type  # Add alias for compatibility

        # Flag to track if config loading failed
        self.load_failed = False

        # GitHub token placeholder
        self.github_token = None

        self.guidelines: List[str] = []
        self.settings: ConfigModel = ConfigModel()
        self._config_dict = self.settings.dict()
        
        # Thread safety for configuration updates
        self._settings_lock = threading.RLock()

    @property
    def config(self) -> Dict[str, Any]:
        """Dictionary representation for backward compatibility."""
        with self._settings_lock:
            self._config_dict = self.settings.dict()
            return self._config_dict.copy()  # Return a copy to prevent external modification

    @config.setter
    def config(self, new_config: Dict[str, Any]) -> None:
        with self._settings_lock:
            try:
                self.settings = ConfigModel(**new_config)
                self._config_dict = self.settings.dict()
            except ValidationError as exc:
                self.load_failed = True
                raise ValueError(f"Invalid configuration: {exc}") from exc

    def get_default_config(self) -> Dict[str, Any]:
        """Return default configuration as dictionary."""
        return ConfigModel().dict()

    def load(self, config_path: Optional[str] = None) -> None:
        """Load configuration from environment, optional JSON, and guidelines."""

        # Determine if the provided guidelines_path actually points to a JSON
        # configuration file for backward compatibility with older tests.
        json_path = config_path
        if json_path is None and self.guidelines_path and self.guidelines_path.endswith('.json'):
            if os.path.isfile(self.guidelines_path):
                json_path = self.guidelines_path
                # Reset guidelines path to the default location
                self.guidelines_path = str(Path(os.getcwd()) / '.github' / 'copilot-instructions.md')

        # Start with defaults populated from environment variables
        runtime_config: Dict[str, Any] = self.get_default_config()

        # Merge user supplied JSON configuration if provided
        if json_path and os.path.exists(json_path):
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    user_config = json.load(f)
                    if isinstance(user_config, dict):
                        runtime_config.update(user_config)
            except json.JSONDecodeError:
                logger.error("Invalid JSON in %s", json_path)
            except Exception as e:
                logger.error("Error loading %s: %s", json_path, e)

        # Load additional llm model configuration if available
        llm_config_path = os.path.join(os.getcwd(), 'llm.json')
        if os.path.exists(llm_config_path):
            try:
                with open(llm_config_path, 'r', encoding='utf-8') as f:
                    runtime_config['llm_models'] = json.load(f)
                    logger.info("Loaded LLM model configuration from llm.json")
            except json.JSONDecodeError:
                logger.error("Invalid JSON in llm.json")
            except Exception as e:
                logger.error("Error loading llm.json: %s", e)

        try:
            self.config = runtime_config
        except ValueError as exc:
            logger.error(exc)
            raise

        # Extract coding guidelines
        self.guidelines = self._extract_guidelines_from_md()

        # Store GitHub token if present
        if self.config.get('dev_github_token'):
            self.github_token = self.config.get('dev_github_token')

        logger.info("Configuration loaded")

    def reload(self):
        """Reload all configuration settings from scratch."""
        # Reset to initial state
        self.guidelines = []
        self.config = self.get_default_config()
        # Load fresh config
        self.load()
        logger.info("Configuration reloaded")

    def _extract_guidelines_from_md(self) -> List[str]:
        """Extract coding guidelines from .github/copilot-instructions.md.

        Returns:
            List of guidelines extracted from markdown headings and lists.
        """
        guidelines = []
        try:
            if os.path.exists(self.guidelines_path):
                with open(self.guidelines_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Extract section headings (##, ###)
                section_headers = re.findall(r'^#{2,3}\s+(.+?)$', content, re.MULTILINE)
                guidelines.extend(section_headers)

                # Extract list items (- bullet points)
                list_items = re.findall(r'^\s*-\s+(.+?)$', content, re.MULTILINE)
                guidelines.extend(list_items)

                logger.info("Extracted %d guidelines from %s", len(guidelines), self.guidelines_path)
            else:
                logger.warning("Guidelines file not found: %s", self.guidelines_path)
        except Exception as e:
            logger.error("Error extracting guidelines: %s", e)

        return guidelines

    def get_guideline_fragments(self, max_fragments: int = 5) -> List[str]:
        """Get a sample of guideline fragments to enhance prompts.

        Args:
            max_fragments: Maximum number of guideline fragments to return

        Returns:
            List of guideline fragments, limited to max_fragments
        """
        if not self.guidelines:
            return []

        # Return a sample of guidelines
        import random
        if len(self.guidelines) <= max_fragments:
            return self.guidelines
        else:
            return random.sample(self.guidelines, max_fragments)

    def get_log_file_path(self, log_type: str) -> str:
        """Get the path to a specific log file.

        Args:
            log_type: Type of log file ("development", "debug", or "error")

        Returns:
            Absolute path to the log file
        """
        if log_type in self.settings.log_files.dict():
            return os.path.join(os.getcwd(), self.settings.log_files.dict()[log_type])
        else:
            return os.path.join(os.getcwd(), f"{log_type}_log.jsonl")


def get_config():
    """Get the loaded configuration instance with thread safety.

    If the configuration hasn't been loaded yet, it will be loaded
    with default parameters.

    Returns:
        The loaded configuration dictionary.
    """
    global _config_instance
    
    # Double-checked locking pattern for thread safety
    if _config_instance is None:
        with _config_lock:
            # Check again inside the lock to handle race conditions
            if _config_instance is None:
                _config_instance = Config()
                try:
                    _config_instance.load()
                except Exception as e:
                    # Log the error instead of silently ignoring it
                    logging.error(f"Error loading configuration: {e}")
                    # Load default configuration values
                    _config_instance.config = _config_instance.get_default_config()
                    # Set load failure flag to allow callers to detect this condition
                    _config_instance.load_failed = True
    
    return _config_instance.settings
