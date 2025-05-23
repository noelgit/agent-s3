"""Manages retrieval-augmented generation, hierarchical summarization, and context versioning.

This module provides advanced memory management capabilities as specified in instructions.md.
"""

import os
import json
import threading
import time
import logging
import gzip
import shutil  # For atomic saving
from typing import Dict, List, Any, Optional, Set, Tuple
from datetime import datetime, timezone
from pathlib import Path
import numpy as np  # type: ignore
import tiktoken  # Import tiktoken for accurate token counting
from agent_s3.tools.embedding_client import EmbeddingClient
from agent_s3.tools.file_tool import FileTool  # Assuming FileTool exists
# Import configuration values
from agent_s3.llm_prompts.summarization_prompts import SummarizationPromptGenerator
from agent_s3.tools.summarization.summary_validator import SummaryValidator
from agent_s3.tools.summarization.refinement_manager import SummaryRefinementManager

DEFAULT_MAX_TOKENS = 4096
DEFAULT_SUMMARY_TARGET_TOKENS = 1024
DEFAULT_CHUNK_SIZE = 1000  # Tokens per chunk for summarization

# Default settings for progressive embedding eviction
DEFAULT_MAX_EMBEDDINGS = 10000  # Maximum number of embeddings before eviction
DEFAULT_EVICTION_BATCH_SIZE = 100  # Number of embeddings to evict in one batch
DEFAULT_ACCESS_THRESHOLD = 30  # Days threshold for "cold" embeddings

logger = logging.getLogger(__name__)

CACHE_DIR_NAME = ".cache"
MEMORY_STATE_FILE = "memory_state.v1.json"
DEFAULT_MODEL_NAME = "gpt-4"  # Default model for token counting if not specified


class MemoryManager:
    """Manages context history, summaries, and embeddings with progressive eviction strategy."""

    def __init__(self, config: Dict[str, Any], embedding_client: Optional[EmbeddingClient] = None, 
                 file_tool: Optional[FileTool] = None, llm_client: Optional[Any] = None):
        """Initialize the memory manager.
        
        Args:
            config: Configuration dictionary
            embedding_client: Optional embedding client instance. If None, attempts to create one.
            file_tool: Optional file tool instance. If None, creates a new instance.
            llm_client: Optional LLM client. If None, uses router agent when needed.
        """
        self.config = config
        self.embedding_client = embedding_client
        self.file_tool = file_tool or FileTool()
        self.llm_client = llm_client
        self.workspace_path = Path(config.get("workspace_path", ".")).resolve()
        self.store_path_base = self.workspace_path / CACHE_DIR_NAME
        self.memory_state_path = self.store_path_base / MEMORY_STATE_FILE
        self.access_log_path = self.store_path_base / "embedding_access_log.json"

        # Set up checkpoint and manifest paths
        self.checkpoint_dir = self.store_path_base / 'checkpoints'
        self.checkpoint_dir.mkdir(exist_ok=True)
        self.manifest_path = self.store_path_base / 'cache_manifest.json'

        # Async executor and batch queue for embedding updates
        from concurrent.futures import ThreadPoolExecutor
        self._executor = ThreadPoolExecutor(max_workers=4)
        self._batch_queue: Set[str] = set()
        self._batch_lock = threading.Lock()
        # Lock for protecting file writes and shared state updates
        self._lock = threading.RLock()
        self._batch_timer: Optional[threading.Timer] = None
        self.batch_delay = config.get('cache_debounce_delay', 0.2)

        # Configure progressive eviction parameters
        self.max_embeddings = config.get("max_embeddings", DEFAULT_MAX_EMBEDDINGS)
        self.eviction_batch_size = config.get("eviction_batch_size", DEFAULT_EVICTION_BATCH_SIZE)
        self.access_threshold_days = config.get("embedding_cold_threshold_days", DEFAULT_ACCESS_THRESHOLD)

        # Configure LLM summarization parameters
        self.min_size_for_llm_summarization = config.get("MIN_SIZE_FOR_LLM_SUMMARIZATION", 1000)
        self.enable_llm_summarization = config.get("ENABLE_LLM_SUMMARIZATION", True)
        self.summary_cache_max_size = config.get("SUMMARY_CACHE_MAX_SIZE", 100)
        
        # Initialize LRU cache for summaries
        from collections import OrderedDict
        self._summary_cache: OrderedDict[str, str] = OrderedDict()
        self._summary_cache_hits = 0
        self._summary_cache_misses = 0
        
        # Initialize router agent for specialized LLM roles
        self.router_agent = None
        # We'll use the router_agent passed from Coordinator if provided
        # or lazily initialize it when needed in the _summarize_with_llm method

        # Dictionary to track embedding access: {file_path: {"last_access": timestamp, "access_count": count}}
        self.embedding_access_log = {}
        # Counter for prefix-aware eviction occurrences
        self.prefix_evictions = 0

        # Ensure cache directory exists
        self.store_path_base.mkdir(exist_ok=True)

        # Initialize state
        self.context_history: List[Dict[str, Any]] = []
        self.summaries: Dict[str, str] = {}  # file_path -> summary
        self.token_limit = config.get('context_token_limit', 4096)

        # Initialize SummarizationPromptGenerator
        self.prompt_generator = SummarizationPromptGenerator()

        self._load_memory()
        self._load_embedding_access_log()
        # Verify manifest integrity before normal operations
        self._verify_manifest()
        # After loading, update manifest with current checksums
        self._update_manifest()

    def _load_memory(self):
        """Load memory state (history, summaries) from disk."""
        if self.memory_state_path.exists():
            try:
                # Auto-detect gzip magic
                with open(self.memory_state_path, 'rb') as hf:
                    sig = hf.read(2)
                if sig == b"\x1f\x8b":
                    f_open = gzip.open
                    mode = 'rt'
                else:
                    f_open = open
                    mode = 'r'
                with f_open(self.memory_state_path, mode, encoding='utf-8') as f:
                    state = json.load(f)
                self.context_history = state.get('context_history', [])
                self.summaries = state.get('summaries', {})
                logger.info(f"Loaded memory state from {self.memory_state_path}")
            except (json.JSONDecodeError, OSError) as e:
                logger.error(f"Error loading memory state from {self.memory_state_path}: {e}. Initializing empty state.")
                self.context_history = []
                self.summaries = {}
        else:
            logger.info(f"Memory state file not found at {self.memory_state_path}. Initializing empty state.")
            self.context_history = []
            self.summaries = {}

    def _save_memory(self):
        """Save memory state (history, summaries) to disk atomically with checkpoint retention."""
        with self._lock:
            # Ensure cache directory exists
            self.store_path_base.mkdir(exist_ok=True)

            state = {
                'context_history': self.context_history,
                'summaries': self.summaries
            }
            try:
                # Write compressed JSON atomically
                temp_path = self.memory_state_path.with_suffix(self.memory_state_path.suffix + ".tmp")
                with gzip.open(temp_path, 'wt', encoding='utf-8') as f:
                    json.dump(state, f, indent=2)
                shutil.move(str(temp_path), str(self.memory_state_path))
                logger.info(f"Saved memory state to {self.memory_state_path}")
                # Create checkpoint after save
                ts = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
                cp_name = f'memory_state_{ts}.json.gz'
                try:
                    shutil.copy2(self.memory_state_path, self.checkpoint_dir / cp_name)
                    # Prune old checkpoints, keep last 3
                    cps = sorted(self.checkpoint_dir.iterdir(), key=lambda p: p.stat().st_mtime)
                    for old in cps[:-3]:
                        old.unlink()
                except Exception as e:
                    logger.error(f"Error creating memory checkpoint: {e}")
            except (OSError, TypeError) as e:
                logger.error(f"Error saving memory state to {self.memory_state_path}: {e}")

    def save_state(self) -> None:
        """Public wrapper to persist memory state to disk."""
        self._save_memory()

    def _load_embedding_access_log(self):
        """Load embedding access log from disk."""
        if self.access_log_path.exists():
            try:
                with open(self.access_log_path, 'r', encoding='utf-8') as f:
                    self.embedding_access_log = json.load(f)
                    logger.info(f"Loaded embedding access log from {self.access_log_path}")
            except (json.JSONDecodeError, OSError) as e:
                logger.error(f"Error loading embedding access log: {e}. Initializing empty log.")
                self.embedding_access_log = {}
        else:
            logger.info("Embedding access log not found. Initializing empty log.")
            self.embedding_access_log = {}

    def _save_embedding_access_log(self):
        """Save embedding access log to disk atomically."""
        with self._lock:
            try:
                temp_path = self.access_log_path.with_suffix(self.access_log_path.suffix + ".tmp")
                with open(temp_path, 'w', encoding='utf-8') as f:
                    json.dump(self.embedding_access_log, f, indent=2)
                shutil.move(str(temp_path), str(self.access_log_path))
                logger.debug(f"Saved embedding access log to {self.access_log_path}")
            except (OSError, TypeError) as e:
                logger.error(f"Error saving embedding access log: {e}")

    def _record_embedding_access(self, file_path: str):
        """Record access to an embedding for a specific file."""
        abs_path = str(Path(file_path).resolve())
        current_time = time.time()

        with self._lock:
            if abs_path in self.embedding_access_log:
                # Update existing record
                self.embedding_access_log[abs_path]["last_access"] = current_time
                self.embedding_access_log[abs_path]["access_count"] += 1
            else:
                # Create new record
                self.embedding_access_log[abs_path] = {
                    "last_access": current_time,
                    "access_count": 1,
                    "created": current_time
                }

            # Save periodically (e.g., every 10 accesses)
            if sum(record.get("access_count", 0) % 10 == 0 for record in self.embedding_access_log.values()) > 0:
                self._save_embedding_access_log()

    def _clean_deleted_files_from_logs(self):
        """Remove entries from access logs for files that no longer exist."""
        with self._lock:
            to_remove = []
            for file_path in list(self.embedding_access_log):
                if not Path(file_path).is_file():
                    to_remove.append(file_path)

            if to_remove:
                for file_path in to_remove:
                    del self.embedding_access_log[file_path]
                logger.info(f"Removed {len(to_remove)} deleted files from embedding access log")
                self._save_embedding_access_log()

    def apply_progressive_eviction(self, force=False):
        """
        Apply progressive embedding eviction strategy based on access patterns.
        
        Args:
            force: If True, run eviction even if below threshold
            
        Returns:
            Number of embeddings evicted
        """
        with self._lock:
            # Get current embedding count
            try:
                if self.embedding_client is not None and hasattr(self.embedding_client, 'get_embedding_count'):
                    current_count = self.embedding_client.get_embedding_count()
                else:
                    # Estimate if not available
                    current_count = len(self.embedding_access_log)
            except Exception as e:
                logger.error(f"Error getting embedding count: {e}")
                current_count = 0

            # Clean up deleted files first
            self._clean_deleted_files_from_logs()

            # Check if we need to evict
            if not force and current_count < self.max_embeddings:
                logger.debug(f"No eviction needed: {current_count}/{self.max_embeddings} embeddings used")
                return 0

            logger.info(
                f"Starting progressive embedding eviction: {current_count}/{self.max_embeddings} embeddings used"
            )

            # Determine how many embeddings to evict
            to_evict = min(
                self.eviction_batch_size,
                max(0, current_count - self.max_embeddings + self.eviction_batch_size // 2),
            )
            if force:
                to_evict = max(to_evict, self.eviction_batch_size)

            evicted_count = 0

            # Prefix-aware eviction strategy
            now = time.time()
            max_idle_seconds = self.access_threshold_days * 86400
            prefix_groups: Dict[str, List[Dict[str, Any]]] = {}

            for fp, rec in self.embedding_access_log.items():
                prefix = str(Path(fp).parent)
                last_access = rec.get("last_access", now)
                idle_factor = (
                    min(1.0, (now - last_access) / max_idle_seconds)
                    if max_idle_seconds > 0
                    else 0.5
                )
                access_factor = 1.0 / (rec.get("access_count", 0) + 1)
                age_factor = (
                    min(1.0, (now - rec.get("created", last_access)) / (max_idle_seconds / 2))
                    if max_idle_seconds > 0
                    else 0.5
                )
                score = (0.6 * idle_factor) + (0.3 * access_factor) + (0.1 * age_factor)
                prefix_groups.setdefault(prefix, []).append({"file_path": fp, "score": score})

            group_scores: List[Tuple[str, float, List[str]]] = []
            for prefix, files in prefix_groups.items():
                avg_score = sum(f["score"] for f in files) / len(files)
                paths = [f["file_path"] for f in files]
                group_scores.append((prefix, avg_score, paths))

            group_scores.sort(key=lambda x: x[1], reverse=True)

            for _, _, paths in group_scores:
                for fp in paths:
                    if evicted_count >= to_evict:
                        break
                    try:
                        if self.remove_embedding(fp, record_removal=True):
                            evicted_count += 1
                    except Exception as e:  # pragma: no cover - ignore during tests
                        logger.error(f"Error evicting embedding for {fp}: {e}")
                if evicted_count >= to_evict:
                    break

            if evicted_count > 0:
                self.prefix_evictions += evicted_count

            logger.info(f"Progressive eviction complete: {evicted_count} embeddings evicted")
            self._save_embedding_access_log()
            return evicted_count

    def add_to_history(self, entry: Dict[str, Any]):
        """Add an entry to the context history and save."""
        self.context_history.append(entry)
        self._save_memory()

    def get_history(self) -> List[Dict[str, Any]]:
        """Get the current context history."""
        return self.context_history

    def update_embedding(self, file_path: str):
        """Update embedding for a file immediately and add to embedding client."""
        # Read file content
        content = self.file_tool.read_file(file_path)
        if content is None:
            return
        # Generate embedding
        embedding = self.embedding_client.generate_embedding(content)
        if embedding is None:
            return
        # Prepare array for embedding client: always wrap embedding in a numpy array
        arr = np.array([embedding])
        # Prepare metadata
        stat = Path(file_path).stat()
        metadata = [{
            'file_path': str(Path(file_path).resolve()),
            'last_modified': stat.st_mtime
        }]
        # Add embeddings synchronously
        self.embedding_client.add_embeddings(arr, metadata)

    def remove_embedding(self, file_path: str, record_removal: bool = False):
        """
        Remove the embedding for a specific file.
        
        Args:
            file_path: Path to the file
            record_removal: Whether to record this as deliberate removal
            
        Returns:
            True if embedding was removed, False otherwise
        """
        abs_path_str = str(Path(file_path).resolve())
        try:
            removed_count = self.embedding_client.remove_embeddings_by_metadata({'file_path': abs_path_str})
            if removed_count > 0:
                logger.info(f"Removed {removed_count} embedding(s) for file: {file_path}")
                
                # Also remove from access log if it was a deliberate removal
                if record_removal and abs_path_str in self.embedding_access_log:
                    del self.embedding_access_log[abs_path_str]
                
                if abs_path_str in self.summaries:
                    del self.summaries[abs_path_str]
                    logger.info(f"Removed summary for file: {file_path}")
                    self._save_memory()
                    
                return True
            else:
                logger.debug(f"No embedding found to remove for file: {file_path}")
                return False

        except Exception as e:
            logger.error(f"Error removing embedding for {file_path}: {e}")
            return False

    def _detect_language(self, file_path: Optional[str]) -> str:
        """
        Detects the programming language or content type based on file extension. Defaults to 'text'.
        """
        if not file_path:
            return 'text'
        _, ext = os.path.splitext(file_path)
        ext = ext.lower()
        LANG_MAP = {
            '.py': 'python',
            '.js': 'javascript', '.jsx': 'javascript', '.mjs': 'javascript', '.cjs': 'javascript',
            '.ts': 'typescript', '.tsx': 'typescript',
            '.php': 'php', '.phtml': 'php',
            '.java': 'java',
            '.rb': 'ruby',
            '.go': 'go',
            '.rs': 'rust',
            '.cpp': 'cpp', '.cc': 'cpp', '.cxx': 'cpp', '.hpp': 'cpp', '.h': 'cpp', '.c': 'cpp',
            '.cs': 'csharp',
            '.swift': 'swift',
            '.kt': 'kotlin', '.kts': 'kotlin',
            '.scala': 'scala',
            '.sh': 'shell', '.bash': 'shell',
            '.html': 'html', '.htm': 'html',
            '.css': 'css', '.scss': 'css', '.sass': 'css', '.less': 'css',
            '.md': 'markdown',
            '.json': 'json',
            '.yml': 'yaml', '.yaml': 'yaml',
            '.txt': 'text',
        }
        return LANG_MAP.get(ext, 'text')

    def summarize_file(self, file_path: str, content: Optional[str] = None):
        """Schedule summarization in background thread."""
        self._executor.submit(self._do_summarize_file, file_path, content)

    def _do_summarize_file(self, file_path: str, content: Optional[str]):
        """Internal summarization logic using AST-guided pipeline."""
        if content is None:
            try:
                content = self.file_tool.read_file(file_path)
                if content is None:
                    logger.error(f"Cannot summarize, failed to read file: {file_path}")
                    return
            except Exception as e:
                logger.error(f"Error reading file for summarization {file_path}: {e}")
                return
        try:
            from agent_s3.ast_tools.python_units import extract_units
            from agent_s3.ast_tools.summariser import summarise_unit, merge_summaries
            # Detect language and use existing prompt generator
            language = self._detect_language(file_path)
            prompt_generator = self.prompt_generator
            # Extract units and summarize each unit with language and prompt generator
            units = extract_units(content, language=language)
            unit_summaries = []
            for unit in units:
                summary = summarise_unit(
                    self.llm_client or self.router_agent,
                    unit['kind'],
                    unit['name'],
                    unit['code'],
                    language,
                    prompt_generator
                )
                unit_summaries.append(summary)
            # Merge summaries with language and prompt generator
            merged_summary = merge_summaries(
                self.llm_client or self.router_agent,
                file_path,
                unit_summaries,
                language,
                prompt_generator
            )
            self.summaries[file_path] = merged_summary
            self._save_memory()
        except Exception as e:
            logger.error(f"Error during summarization for {file_path}: {e}")

    def hierarchical_summarize(self, content: str, language: str = None, max_tokens: int = None, preserve_sections: bool = False):
        """Summarize content with validation and refinement."""
        if not content.strip():
            return {"summary": "", "was_summarized": False, "validation": None}
        validator = SummaryValidator()
        refinement_manager = SummaryRefinementManager(self.router_agent)

        # Chunk content by token count for hierarchical summarization
        encoding = tiktoken.get_encoding("cl100k_base")
        max_tokens = max_tokens or DEFAULT_CHUNK_SIZE
        tokens = encoding.encode(content)
        chunks = [
            encoding.decode(tokens[i : i + max_tokens])
            for i in range(0, len(tokens), max_tokens)
        ]
        chunk_summaries = []
        for chunk in chunks:
            summary = self._generate_summary(chunk, language)
            validation_result = validator.validate(chunk, summary, language)
            if not validation_result["passed"]:
                refinement_result = refinement_manager.refine_summary(
                    source=chunk,
                    summary=summary,
                    validation_result=validation_result,
                    language=language
                )
                summary = refinement_result["summary"]
                validation_result = refinement_result["validation"]
            chunk_summaries.append({
                "summary": summary,
                "validation": validation_result
            })
        if len(chunk_summaries) == 1:
            return {
                "summary": chunk_summaries[0]["summary"],
                "was_summarized": True,
                "validation": chunk_summaries[0]["validation"]
            }
        merged_content = "\n\n".join([cs["summary"] for cs in chunk_summaries])
        if len(merged_content) > (max_tokens or 3000):
            return self.hierarchical_summarize(merged_content, language, max_tokens, False)
        final_summary = self._generate_summary(merged_content, language)
        final_validation = validator.validate(content, final_summary, language)
        if not final_validation["passed"]:
            final_refinement = refinement_manager.refine_summary(
                source=content,
                summary=final_summary,
                validation_result=final_validation,
                language=language
            )
            final_summary = final_refinement["summary"]
            final_validation = final_refinement["validation"]
        return {
            "summary": final_summary,
            "was_summarized": True,
            "validation": final_validation
        }

    def _generate_summary(self, content: str, language: str = None) -> str:
        system_prompt = self.prompt_generator.create_system_prompt(language)
        user_prompt = self.prompt_generator.create_user_prompt(content, language)
        return self.router_agent.call_llm_by_role(
            role="summarizer",
            system_prompt=system_prompt,
            user_prompt=user_prompt
        )

    def _verify_manifest(self) -> None:
        """Ensure the cache manifest exists and is valid JSON."""
        if not self.manifest_path.exists():
            try:
                self.manifest_path.parent.mkdir(exist_ok=True)
                with open(self.manifest_path, "w", encoding="utf-8") as f:
                    json.dump({}, f)
            except OSError as e:
                logger.error(f"Error creating manifest file: {e}")
            return
        try:
            with open(self.manifest_path, "r", encoding="utf-8") as f:
                json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Manifest file corrupted: {e}. Resetting.")
            try:
                with open(self.manifest_path, "w", encoding="utf-8") as f:
                    json.dump({}, f)
            except OSError as e2:
                logger.error(f"Error resetting manifest file: {e2}")

    def _update_manifest(self) -> None:
        """Update manifest timestamp."""
        data = {}
        if self.manifest_path.exists():
            try:
                with open(self.manifest_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (json.JSONDecodeError, OSError):
                data = {}
        data["last_updated"] = datetime.now(timezone.utc).isoformat()
        try:
            with open(self.manifest_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except OSError as e:
            logger.error(f"Error updating manifest: {e}")
