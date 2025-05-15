"""
Enhanced Scratchpad Manager for Agent-S3 with Chain of Thought Integration.

This module provides comprehensive logging with structured Chain of Thought (CoT)
sections, session management, and utilities for extracting relevant debugging context.
"""

import os
import re
import json
import time
import glob
import shutil
import logging
from enum import Enum, auto
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional, Dict, Any, List, Iterator, Set, Tuple, Union
from pathlib import Path
import hashlib

from agent_s3.config import Config


class LogLevel(Enum):
    """Log levels for enhanced scratchpad entries."""
    DEBUG = auto()
    INFO = auto()
    WARNING = auto()
    ERROR = auto()
    CRITICAL = auto()


class Section(Enum):
    """Section types for structured CoT logging."""
    PLANNING = auto()
    GENERATION = auto()
    DEBUGGING = auto()
    TESTING = auto()
    ANALYSIS = auto()
    IMPLEMENTATION = auto()
    ERROR = auto()
    REASONING = auto()
    DECISION = auto()
    METADATA = auto()
    USER_INTERACTION = auto()


@dataclass
class LogEntry:
    """Structured log entry with metadata and content."""
    timestamp: str
    role: str
    level: LogLevel = LogLevel.INFO
    section: Optional[Section] = None
    message: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: Set[str] = field(default_factory=set)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert entry to dictionary for serialization."""
        result = asdict(self)
        result['level'] = self.level.name
        if self.section:
            result['section'] = self.section.name
        result['tags'] = list(self.tags)
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LogEntry':
        """Create LogEntry from dictionary."""
        level_name = data.get('level', 'INFO')
        section_name = data.get('section')
        
        # Convert level and section strings to enums
        try:
            level = LogLevel[level_name]
        except (KeyError, TypeError):
            level = LogLevel.INFO
            
        section = None
        if section_name:
            try:
                section = Section[section_name]
            except (KeyError, TypeError):
                pass
                
        tags = set(data.get('tags', []))
        
        return cls(
            timestamp=data.get('timestamp', ''),
            role=data.get('role', ''),
            level=level,
            section=section,
            message=data.get('message', ''),
            metadata=data.get('metadata', {}),
            tags=tags
        )


class EnhancedScratchpadManager:
    """
    Enhanced scratchpad manager with session management, structured logging,
    and Chain of Thought extraction capabilities.
    """

    # Constants for configuration
    DEFAULT_MAX_SESSIONS = 5
    DEFAULT_MAX_FILE_SIZE_MB = 50
    DEFAULT_LOG_DIR = "logs/scratchpad"
    
    # Section markers for structured logging
    SECTION_START = "===== BEGIN {section} ====="
    SECTION_END = "===== END {section} ====="
    
    def __init__(self, config: Config):
        """
        Initialize the enhanced scratchpad manager.
        
        Args:
            config: The loaded configuration
        """
        self.config = config
        
        # Get configuration values with defaults
        self.max_sessions = config.config.get('scratchpad_max_sessions', self.DEFAULT_MAX_SESSIONS)
        self.max_file_size_mb = config.config.get('scratchpad_max_file_size_mb', self.DEFAULT_MAX_FILE_SIZE_MB)
        self.log_dir = config.config.get('scratchpad_log_dir', self.DEFAULT_LOG_DIR)
        self.enable_encryption = config.config.get('scratchpad_enable_encryption', False)
        
        # Create log directory if it doesn't exist
        self.log_dir_path = Path(os.getcwd()) / self.log_dir
        self.log_dir_path.mkdir(parents=True, exist_ok=True)
        
        # Initialize session
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.current_log_file = self._get_session_log_file()
        self.current_part = 1
        
        # Initialize statistics
        self.entry_count = 0
        self.section_stack = []
        
        # Store last LLM interaction for explanation
        self._last_llm_interaction: Optional[Dict[str, Any]] = None
        
        # Cache of recent entries for quick access
        self._recent_entries: List[LogEntry] = []
        self._max_recent_entries = 100
        
        # Initialize session
        self._initialize_session()
        
        # Set up structured logger
        self._setup_logging()
        
    def _setup_logging(self) -> None:
        """Configure Python logging integration."""
        self.logger = logging.getLogger("enhanced_scratchpad")
        self.logger.setLevel(logging.DEBUG)
        
        # Create a handler that forwards to our log method
        class ScratchpadHandler(logging.Handler):
            def __init__(self, manager):
                super().__init__()
                self.manager = manager
                
            def emit(self, record):
                # Map logging levels to our levels
                level_map = {
                    logging.DEBUG: LogLevel.DEBUG,
                    logging.INFO: LogLevel.INFO,
                    logging.WARNING: LogLevel.WARNING,
                    logging.ERROR: LogLevel.ERROR,
                    logging.CRITICAL: LogLevel.CRITICAL
                }
                level = level_map.get(record.levelno, LogLevel.INFO)
                
                # Extract role from record if available, otherwise use logger name
                role = getattr(record, 'role', record.name)
                
                # Log the message with appropriate level
                self.manager.log(role, record.getMessage(), level=level)
                
        handler = ScratchpadHandler(self)
        self.logger.addHandler(handler)
        
    def _initialize_session(self) -> None:
        """Initialize a new logging session with metadata header."""
        # Clean up old sessions if needed
        self._cleanup_old_sessions()
        
        # Start with session metadata
        metadata = {
            "session_id": self.session_id,
            "start_time": datetime.now().isoformat(),
            "agent_version": self.config.config.get("version", "unknown"),
            "config_hash": self._hash_config(),
            "platform": os.name,
            "max_file_size_mb": self.max_file_size_mb,
            "encryption_enabled": self.enable_encryption
        }
        
        # Log session start with metadata
        self.log(
            "SessionManager", 
            f"Session {self.session_id} started", 
            level=LogLevel.INFO,
            section=Section.METADATA,
            metadata=metadata
        )
        
    def _hash_config(self) -> str:
        """Create a hash of the configuration for tracking."""
        try:
            config_str = json.dumps(self.config.config, sort_keys=True)
            return hashlib.md5(config_str.encode()).hexdigest()
        except Exception:
            return "unknown"
        
    def _get_session_log_file(self, part: int = 1) -> Path:
        """Get the log file path for the current session and part."""
        filename = f"scratchpad_{self.session_id}_part{part}.log"
        return self.log_dir_path / filename
        
    def _cleanup_old_sessions(self) -> None:
        """Clean up old session logs based on max_sessions configuration."""
        try:
            # Get all session directories sorted by creation time
            pattern = str(self.log_dir_path / "scratchpad_*.log")
            session_files = sorted(glob.glob(pattern), key=os.path.getctime)
            
            # Remove oldest sessions if we exceed the maximum
            if len(session_files) >= self.max_sessions:
                # Group files by session_id
                sessions = {}
                for file in session_files:
                    # Extract session ID from filename pattern scratchpad_YYYYMMDD_HHMMSS_part*.log
                    match = re.search(r'scratchpad_(\d{8}_\d{6})_part\d+\.log', os.path.basename(file))
                    if match:
                        session_id = match.group(1)
                        if session_id not in sessions:
                            sessions[session_id] = []
                        sessions[session_id].append(file)
                
                # Sort sessions by their oldest file's creation time
                sorted_sessions = sorted(sessions.keys(), 
                                        key=lambda s: min(os.path.getctime(f) for f in sessions[s]))
                
                # Delete oldest sessions to stay under the limit
                sessions_to_remove = len(sorted_sessions) - self.max_sessions + 1
                if sessions_to_remove > 0:
                    for session_id in sorted_sessions[:sessions_to_remove]:
                        for file in sessions[session_id]:
                            os.remove(file)
                            
        except Exception as e:
            # Don't fail if cleanup has issues
            print(f"Warning: Error cleaning up old scratchpad sessions: {e}")
            
    def _check_and_rotate_log(self) -> None:
        """Check if log file size limit is reached and rotate if needed."""
        try:
            if self.current_log_file.exists():
                size_mb = self.current_log_file.stat().st_size / (1024 * 1024)
                if size_mb >= self.max_file_size_mb:
                    self.current_part += 1
                    self.current_log_file = self._get_session_log_file(self.current_part)
                    
                    # Log rotation event to new file
                    new_entry = LogEntry(
                        timestamp=datetime.now().isoformat(),
                        role="SessionManager",
                        level=LogLevel.INFO,
                        section=Section.METADATA,
                        message=f"Log rotation - continuing in part {self.current_part}",
                        metadata={"previous_part": self.current_part - 1, "part": self.current_part}
                    )
                    self._write_entry(new_entry)
                    
        except Exception as e:
            # Don't fail if rotation has issues
            print(f"Warning: Error rotating scratchpad log: {e}")
            
    def _format_entry(self, entry: LogEntry) -> str:
        """Format a log entry for writing to file."""
        # Basic entry formatting
        ts_formatted = entry.timestamp
        header = f"[{entry.role} • {ts_formatted} • {entry.level.name}]"
        
        # Add section if applicable
        if entry.section:
            header += f" [{entry.section.name}]"
            
        # Add tags if present
        if entry.tags:
            tags_str = " ".join([f"#{tag}" for tag in sorted(entry.tags)])
            header += f" {tags_str}"
            
        # Format metadata if present
        metadata_str = ""
        if entry.metadata:
            try:
                metadata_json = json.dumps(entry.metadata, indent=2)
                metadata_lines = metadata_json.split("\n")
                metadata_str = "\n".join([f"    {line}" for line in metadata_lines])
                metadata_str = f"\n  METADATA:\n{metadata_str}"
            except Exception:
                # Fall back to simple string representation if JSON fails
                metadata_str = f"\n  METADATA: {str(entry.metadata)}"
                
        # Format the full entry
        message_lines = entry.message.split("\n")
        if len(message_lines) == 1:
            # Single line message
            formatted = f"{header} {entry.message}{metadata_str}"
        else:
            # Multi-line message
            indented_message = "\n  ".join(message_lines)
            formatted = f"{header}\n  {indented_message}{metadata_str}"
            
        return formatted
    
    def _encrypt_content(self, content: str) -> str:
        """Encrypt log content if encryption is enabled."""
        if not self.enable_encryption:
            return content
            
        # Simple XOR encryption with config-based key for demo
        # In production, use proper encryption libraries
        key = self.config.config.get("encryption_key", "default_key")
        key_bytes = key.encode()
        content_bytes = content.encode()
        
        # XOR encryption
        encrypted_bytes = bytearray()
        for i, byte in enumerate(content_bytes):
            key_byte = key_bytes[i % len(key_bytes)]
            encrypted_bytes.append(byte ^ key_byte)
            
        # Return base64 encoded encrypted content
        import base64
        return base64.b64encode(encrypted_bytes).decode()
    
    def _decrypt_content(self, encrypted: str) -> str:
        """Decrypt log content if encryption is enabled."""
        if not self.enable_encryption:
            return encrypted
            
        # Simple XOR decryption (inverse of encryption)
        import base64
        
        try:
            key = self.config.config.get("encryption_key", "default_key")
            key_bytes = key.encode()
            
            # Decode base64
            encrypted_bytes = base64.b64decode(encrypted)
            
            # XOR decryption
            decrypted_bytes = bytearray()
            for i, byte in enumerate(encrypted_bytes):
                key_byte = key_bytes[i % len(key_bytes)]
                decrypted_bytes.append(byte ^ key_byte)
                
            return decrypted_bytes.decode()
        except Exception:
            return f"[Error decrypting content]"
    
    def _write_entry(self, entry: LogEntry) -> None:
        """Write a log entry to the current log file."""
        try:
            # Format the entry
            formatted_entry = self._format_entry(entry)
            
            # Apply encryption if enabled
            if self.enable_encryption:
                formatted_entry = self._encrypt_content(formatted_entry)
                
            # Ensure the entry ends with a newline
            if not formatted_entry.endswith("\n"):
                formatted_entry += "\n"
                
            # Write to file
            with open(self.current_log_file, 'a', encoding='utf-8') as f:
                f.write(formatted_entry)
                
            # Update statistics
            self.entry_count += 1
            
            # Add to recent entries cache
            self._recent_entries.append(entry)
            if len(self._recent_entries) > self._max_recent_entries:
                self._recent_entries.pop(0)
                
        except Exception as e:
            # Log to standard error if file writing fails
            print(f"Error writing to scratchpad log: {e}")
    
    def log(self, 
            role: str, 
            message: str, 
            level: Union[LogLevel, str] = LogLevel.INFO,
            section: Optional[Section] = None,
            metadata: Optional[Dict[str, Any]] = None,
            tags: Optional[Set[str]] = None) -> None:
        """
        Log a message to the enhanced scratchpad.
        
        Args:
            role: The role/component that is logging
            message: The message to log
            level: Log level for the entry (LogLevel enum or string: "info", "warning", "error")
            section: Optional section categorization
            metadata: Optional structured metadata
            tags: Optional tags for filtering
        """
        # Convert string level to LogLevel enum for backward compatibility
        if isinstance(level, str):
            level_map = {
                "debug": LogLevel.DEBUG,
                "info": LogLevel.INFO,
                "warning": LogLevel.WARNING,
                "warn": LogLevel.WARNING,
                "error": LogLevel.ERROR,
                "critical": LogLevel.CRITICAL
            }
            level = level_map.get(level.lower(), LogLevel.INFO)
            
        # Check if we need to rotate the log
        self._check_and_rotate_log()
        
        # Create the log entry
        entry = LogEntry(
            timestamp=datetime.now().isoformat(),
            role=role,
            level=level,
            section=section,
            message=message,
            metadata=metadata or {},
            tags=tags or set()
        )
        
        # Write the entry to the log file
        self._write_entry(entry)
    
    def start_section(self, 
                     section: Section, 
                     role: str = "SectionManager",
                     metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        Start a new logical section in the log.
        
        Args:
            section: The section type to start
            role: The role/component starting the section
            metadata: Optional metadata for the section
        """
        # Push section onto stack
        self.section_stack.append(section)
        
        # Log section start
        start_marker = self.SECTION_START.format(section=section.name)
        self.log(
            role=role,
            message=start_marker,
            section=section,
            metadata=metadata or {
                "section": section.name,
                "action": "start",
                "depth": len(self.section_stack)
            }
        )
    
    def end_section(self, 
                   section: Optional[Section] = None, 
                   role: str = "SectionManager",
                   metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        End the current logical section in the log.
        
        Args:
            section: Optional specific section to end (must match current)
            role: The role/component ending the section
            metadata: Optional metadata for the section end
        """
        if not self.section_stack:
            # No sections to end
            self.log(
                role=role,
                message="Warning: Attempted to end section but none are active",
                level=LogLevel.WARNING
            )
            return
            
        # Get the current section
        current_section = self.section_stack[-1]
        
        # If a specific section was requested, verify it matches
        if section is not None and current_section != section:
            self.log(
                role=role,
                message=f"Warning: Attempted to end {section.name} but {current_section.name} is active",
                level=LogLevel.WARNING
            )
            return
            
        # Pop the section from the stack
        self.section_stack.pop()
        
        # Log section end
        end_marker = self.SECTION_END.format(section=current_section.name)
        self.log(
            role=role,
            message=end_marker,
            section=current_section,
            metadata=metadata or {
                "section": current_section.name,
                "action": "end",
                "depth": len(self.section_stack)
            }
        )
    
    def log_last_llm_interaction(
        self, 
        model: str, 
        prompt: str, 
        response: str, 
        prompt_summary: str = "",
        used_fallback: bool = False,
        error: Optional[str] = None
    ) -> None:
        """
        Store information about the last LLM interaction with enhanced metadata.
        
        Args:
            model: The name/role of the LLM model (e.g., "planner", "generator")
            prompt: The prompt sent to the LLM
            response: The response received from the LLM
            prompt_summary: A short summary of the prompt for display
            used_fallback: Whether a fallback strategy was used
            error: Optional error message if the interaction failed
        """
        # Get truncation limits from config
        prompt_max_len = self.config.config.get('llm_explain_prompt_max_len', 1000)
        response_max_len = self.config.config.get('llm_explain_response_max_len', 1000)
        
        # Truncate prompt and response
        truncated_prompt = prompt[:prompt_max_len]
        if len(prompt) > prompt_max_len:
            truncated_prompt += f"... [truncated, {len(prompt) - prompt_max_len} chars omitted]"
            
        truncated_response = response[:response_max_len]
        if len(response) > response_max_len:
            truncated_response += f"... [truncated, {len(response) - response_max_len} chars omitted]"
        
        # Determine status
        status = "success"
        if error:
            status = "error"
        elif used_fallback:
            status = "fallback_success"
            
        # Store the interaction
        self._last_llm_interaction = {
            'role': model,
            'prompt': truncated_prompt,
            'response': truncated_response,
            'status': status,
            'prompt_summary': prompt_summary,
            'used_fallback': used_fallback,
            'error': error,
            'timestamp': datetime.now().isoformat()
        }
        
        # Enhanced metadata for logging
        metadata = {
            'model': model,
            'prompt_length': len(prompt),
            'response_length': len(response),
            'status': status,
            'used_fallback': used_fallback
        }
        
        if error:
            metadata['error'] = error
        
        # Log the interaction
        section = Section.ERROR if error else None
        level = LogLevel.ERROR if error else LogLevel.INFO
        
        message = f"LLM Interaction with {model}: {status}"
        if prompt_summary:
            message += f" - {prompt_summary}"
        
        self.log(
            role="LLM Interaction",
            message=message,
            level=level,
            section=section,
            metadata=metadata
        )
        
    def get_last_llm_interaction(self) -> Optional[Dict[str, Any]]:
        """
        Retrieve information about the last LLM interaction.
        
        Returns:
            A dictionary containing information about the last LLM interaction,
            or None if no interaction has been logged yet.
        """
        return self._last_llm_interaction
    
    def get_recent_entries(self, 
                          count: int = 10, 
                          level: Optional[LogLevel] = None,
                          section: Optional[Section] = None,
                          role: Optional[str] = None,
                          tags: Optional[Set[str]] = None) -> List[LogEntry]:
        """
        Get recent log entries with optional filtering.
        
        Args:
            count: Maximum number of entries to return
            level: Optional filter by log level
            section: Optional filter by section
            role: Optional filter by role
            tags: Optional filter by tags (entries must have ALL specified tags)
            
        Returns:
            List of matching log entries, most recent first
        """
        # Start with all recent entries
        entries = self._recent_entries.copy()
        
        # Apply filters
        if level is not None:
            entries = [e for e in entries if e.level == level]
            
        if section is not None:
            entries = [e for e in entries if e.section == section]
            
        if role is not None:
            entries = [e for e in entries if e.role == role]
            
        if tags is not None:
            entries = [e for e in entries if all(tag in e.tags for tag in tags)]
            
        # Return the most recent entries first, limited by count
        return list(reversed(entries))[-count:]
    
    def extract_section_content(self, 
                               section: Section, 
                               max_entries: int = 100,
                               include_metadata: bool = False) -> List[Dict[str, Any]]:
        """
        Extract content from a specific section type across log files.
        
        Args:
            section: The section type to extract
            max_entries: Maximum number of entries to extract
            include_metadata: Whether to include entry metadata
            
        Returns:
            List of dictionaries containing extracted content
        """
        entries = []
        count = 0
        
        # Get all log files for this session
        log_files = sorted(self.log_dir_path.glob(f"scratchpad_{self.session_id}_*.log"))
        
        # Extract patternsstart
        section_start_pattern = self.SECTION_START.format(section=section.name)
        section_end_pattern = self.SECTION_END.format(section=section.name)
        
        # Process each file
        in_section = False
        section_entries = []
        
        for log_file in log_files:
            if count >= max_entries:
                break
                
            with open(log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    # Handle encrypted content if needed
                    if self.enable_encryption:
                        line = self._decrypt_content(line)
                        
                    # Check for section markers
                    if section_start_pattern in line:
                        in_section = True
                        section_entries = []
                        continue
                        
                    if section_end_pattern in line:
                        if in_section and section_entries:
                            # Process the complete section
                            processed_entries = self._process_section_entries(section_entries, include_metadata)
                            entries.extend(processed_entries)
                            count += len(processed_entries)
                            
                            if count >= max_entries:
                                break
                                
                        in_section = False
                        continue
                        
                    # Collect entries within the section
                    if in_section:
                        section_entries.append(line)
        
        return entries[:max_entries]
    
    def _process_section_entries(self, 
                               entries: List[str], 
                               include_metadata: bool) -> List[Dict[str, Any]]:
        """Process raw section entries into structured data."""
        processed = []
        current_entry = None
        
        # Basic entry pattern
        entry_pattern = r'\[(.*?) • (.*?) • (.*?)\](?:\s+\[(.*?)\])?\s+(.*)'
        
        for line in entries:
            # Try to match the start of a new entry
            match = re.match(entry_pattern, line)
            
            if match:
                # If we have a previous entry, finalize it
                if current_entry:
                    processed.append(current_entry)
                    
                # Extract components
                role, timestamp, level = match.group(1), match.group(2), match.group(3)
                section_name = match.group(4) if match.group(4) else None
                content = match.group(5)
                
                # Create new entry
                current_entry = {
                    "role": role,
                    "timestamp": timestamp,
                    "content": content
                }
                
                # Include optional details if requested
                if include_metadata:
                    current_entry["level"] = level
                    if section_name:
                        current_entry["section"] = section_name
            elif current_entry:
                # Continue previous entry with this line
                current_entry["content"] += "\n" + line.strip()
        
        # Add the last entry if any
        if current_entry:
            processed.append(current_entry)
            
        return processed
    
    def extract_cot_for_debugging(self, 
                                 error_context: str, 
                                 max_entries: int = 20,
                                 relevance_threshold: float = 0.5) -> List[Dict[str, Any]]:
        """
        Extract Chain of Thought entries relevant to a specific error context.
        
        Args:
            error_context: The error context to find relevant CoT for
            max_entries: Maximum number of entries to extract
            relevance_threshold: Minimum relevance score (0-1) for inclusion
            
        Returns:
            List of relevant CoT entries with relevance scores
        """
        # Extract REASONING sections first
        reasoning_entries = self.extract_section_content(
            section=Section.REASONING,
            max_entries=max_entries * 2,  # Get more entries than needed for filtering
            include_metadata=True
        )
        
        # Also get DEBUGGING sections
        debugging_entries = self.extract_section_content(
            section=Section.DEBUGGING,
            max_entries=max_entries,
            include_metadata=True
        )
        
        # Combine entries
        all_entries = reasoning_entries + debugging_entries
        
        # Score entries by relevance to the error context
        scored_entries = []
        for entry in all_entries:
            score = self._calculate_relevance_score(entry, error_context)
            if score >= relevance_threshold:
                entry["relevance_score"] = score
                scored_entries.append(entry)
                
        # Sort by relevance score (descending)
        scored_entries.sort(key=lambda e: e["relevance_score"], reverse=True)
        
        return scored_entries[:max_entries]
    
    def _calculate_relevance_score(self, entry: Dict[str, Any], context: str) -> float:
        """Calculate relevance score between entry and context."""
        content = entry.get("content", "").lower()
        context = context.lower()
        
        # Simple keyword matching for demonstration
        # In real implementation, use embeddings-based similarity
        
        # Extract key terms from context
        import re
        terms = re.findall(r'\b\w+\b', context)
        terms = [t for t in terms if len(t) > 3]  # Filter out short words
        
        if not terms:
            return 0.0
            
        # Count matches
        matches = sum(1 for term in terms if term in content)
        
        # Calculate score as portion of matching terms
        return matches / len(terms)
    
    def close(self) -> None:
        """Close the current session and finalize logs."""
        # Log session end
        self.log(
            "SessionManager",
            f"Session {self.session_id} closing - {self.entry_count} entries logged",
            metadata={
                "session_id": self.session_id,
                "end_time": datetime.now().isoformat(),
                "total_entries": self.entry_count,
                "parts": self.current_part
            }
        )
        
        # Close any open sections
        while self.section_stack:
            self.end_section()