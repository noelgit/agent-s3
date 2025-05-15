import os
import re
import time
import json
import logging

class ErrorContextManager:
    """Manages error context collection and caching for the debugger role.
    
    This class provides specialized context management for debugging:
    1. Prioritizes stack traces and error messages
    2. Caches and recognizes common error patterns
    3. Structures context hierarchically with error location in highest detail
    """
    
    def __init__(self, coordinator=None):
        """Initialize the error context manager.

        Args:
            coordinator: The coordinator instance that provides access to tools
        """
        self.coordinator = coordinator
        self.file_tool = coordinator.file_tool if coordinator else None
        self.code_analysis_tool = coordinator.code_analysis_tool if coordinator else None
        self.memory_manager = coordinator.memory_manager if coordinator else None
        self.scratchpad = coordinator.scratchpad if coordinator else None
        # Use the context_manager if available
        self.context_manager = coordinator.context_manager if coordinator and hasattr(coordinator, 'context_manager') else None

        # Cache for error patterns
        self._error_pattern_cache = {}
        # Cache for recently debugged files
        self._recently_debugged_files = {}
        # Error pattern similarity threshold
        self.similarity_threshold = 0.85
        # Error patterns for specialized handling
        self.error_patterns = []

    def collect_error_context(self, error_message, stack_trace=None, failed_file=None, max_token_count=4000):
        """Collect context around an error with improved error type detection and recovery hints.

        Args:
            error_message: The error message string
            stack_trace: Optional stack trace string
            failed_file: Optional path to file where error occurred
            max_token_count: Maximum tokens for context

        Returns:
            Dict with error context and recovery suggestions
        """
        error_info = self._parse_error(error_message, stack_trace)

        # Try to match against known error patterns
        similar_pattern = None
        similarity_score = 0

        if self.error_patterns:
            similar_pattern, similarity_score = self._find_similar_error_pattern(error_info)
            if similarity_score > self.similarity_threshold:
                if self.scratchpad:
                    self.scratchpad.log("ErrorContextManager",
                                    f"Found similar error pattern in cache (score: {similarity_score:.2f})")
                # Use the cached pattern's solutions as additional context
                error_info["similar_error"] = similar_pattern
                error_info["suggested_fixes"] = similar_pattern.get("solutions", [])

        # Enhanced error type detection
        error_type = self._detect_error_type(error_info)
        error_info["error_type"] = error_type

        # Get specialized context based on error type
        specialized_context = self._get_specialized_context(error_type, error_info, failed_file)
        if specialized_context:
            error_info.update(specialized_context)

        # Build the base context with hierarchical detail levels
        context = {
            "error_message": error_message,
            "stack_trace": stack_trace,
            "parsed_error": error_info,
            "error_type": error_type,
            "recovery_suggestions": self._generate_recovery_suggestions(error_type, error_info),
            "similar_pattern": similar_pattern if similar_pattern and similarity_score > self.similarity_threshold else None,
        }

        # Use the context management system if available, otherwise fall back to direct file reading
        if self.context_manager:
            self._log("Using context management system for error context gathering")
            context = self._gather_context_using_context_manager(context, error_info, max_token_count)
        else:
            self._log("Using direct file access for error context gathering (context manager not available)")
            # Allocate tokens for different context components with dynamic weighting
            token_budgets = self._allocate_token_budgets(max_token_count, error_info, len(error_info.get("file_paths", [])))
            # Add code context with hierarchical detail levels
            context["relevant_code"] = self._add_code_context(error_info, token_budgets)

        # Track error frequency and update patterns
        self._update_error_patterns(error_info, context)

        return context

    def _gather_context_using_context_manager(self, context, error_info, max_token_count):
        """Use the context management system to gather code context.

        Args:
            context: The base context dictionary
            error_info: The parsed error information
            max_token_count: Maximum token count for the context

        Returns:
            The updated context dictionary with code context added
        """
        # Get file paths from error info
        file_paths = error_info.get("file_paths", [])
        if not file_paths:
            return context

        # Identify the primary error file
        primary_file = file_paths[0] if file_paths else None

        try:
            # Use the context manager to get relevant file contents
            if primary_file and hasattr(self.context_manager, '_refine_current_context'):
                # Use available methods to get relevant context
                self.context_manager._refine_current_context(file_paths, max_tokens=max_token_count)

                # Get current context with files
                with self.context_manager._context_lock:
                    context_files = self.context_manager.current_context.get("files", {})

                # Add to our context
                context["relevant_code"] = context_files

            elif hasattr(self.context_manager, 'get_context'):
                # Alternative approach - get current context
                cm_context = self.context_manager.get_context()
                if cm_context and "files" in cm_context:
                    # Just get files that match our error paths
                    relevant_files = {}
                    for file_path in file_paths:
                        if file_path in cm_context["files"]:
                            relevant_files[file_path] = cm_context["files"][file_path]

                    # If we didn't find anything, try to load directly
                    if not relevant_files and hasattr(self.context_manager, 'read_file'):
                        for file_path in file_paths:
                            try:
                                content = self.context_manager.read_file(file_path)
                                if content:
                                    relevant_files[file_path] = content
                            except Exception as e:
                                self._log(f"Error reading file {file_path} via context manager: {e}", level="error")

                    # Add what we found
                    context["relevant_code"] = relevant_files

            else:
                # Fall back to manual context gathering if context manager lacks required methods
                token_budgets = self._allocate_token_budgets(max_token_count, error_info, len(file_paths))
                context["relevant_code"] = self._add_code_context(error_info, token_budgets)

        except Exception as e:
            self._log(f"Error using context manager: {e}", level="error")
            # Fall back to manual context gathering if there's an exception
            token_budgets = self._allocate_token_budgets(max_token_count, error_info, len(file_paths))
            context["relevant_code"] = self._add_code_context(error_info, token_budgets)

        return context

    def _log(self, message, level="info"):
        """Log a message using the scratchpad if available.

        Args:
            message: The message to log
            level: The log level (info, warning, error)
        """
        if self.scratchpad and hasattr(self.scratchpad, 'log'):
            self.scratchpad.log("ErrorContextManager", message, level=level)
        else:
            logger = logging.getLogger(__name__)
            if level == "error":
                logger.error(message)
            elif level == "warning":
                logger.warning(message)
            else:
                logger.info(message)

    def get_context_for_error(self, file_path, line_number, error_message):
        """Get context information for an error.

        This method uses the context management system if available, otherwise falls back
        to direct file access methods.

        Args:
            file_path: Path to the file where the error occurred
            line_number: Line number where the error occurred
            error_message: The error message

        Returns:
            Dictionary with context information
        """
        self._log(f"Getting context for error in {file_path}:{line_number}")

        # Use the context management system if available
        if self.context_manager:
            return self._get_context_using_context_manager(file_path, line_number, error_message)
        else:
            return self._get_context_using_direct_access(file_path, line_number, error_message)

    def _get_context_using_context_manager(self, file_path, line_number, error_message):
        """Get context information using the context management system.

        Args:
            file_path: Path to the file where the error occurred
            line_number: Line number where the error occurred
            error_message: The error message

        Returns:
            Dictionary with context information
        """
        context = {}
        try:
            # Try to get file content from context manager
            if hasattr(self.context_manager, 'read_file'):
                content = self.context_manager.read_file(file_path)
            elif hasattr(self.context_manager, 'get_file_content'):
                content = self.context_manager.get_file_content(file_path)
            else:
                # Fall back to file_tool
                content = self.file_tool.read_file(file_path) if self.file_tool else ""

            if content:
                # Extract code snippet around the error line
                lines = content.split('\n')
                start_line = max(0, line_number - 5)
                end_line = min(len(lines), line_number + 5)

                code_snippet = []
                for i in range(start_line, end_line):
                    prefix = "-> " if i == line_number - 1 else "   "
                    code_snippet.append(f"{i+1}: {prefix}{lines[i]}")

                context["code_snippet"] = "\n".join(code_snippet)

            # Try to get variables from context
            if hasattr(self.context_manager, 'get_context'):
                cm_context = self.context_manager.get_context()
                if cm_context and "variables" in cm_context:
                    context["variables"] = cm_context["variables"]

            # Try to get dependency information
            if hasattr(self.context_manager, 'get_file_dependencies'):
                dependencies = self.context_manager.get_file_dependencies(file_path)
                if dependencies:
                    context["dependencies"] = dependencies

            # Try to get dependent files information
            if hasattr(self.context_manager, 'get_dependent_files'):
                dependents = self.context_manager.get_dependent_files(file_path)
                if dependents:
                    context["dependents"] = dependents
        except Exception as e:
            self._log(f"Error getting context using context manager: {e}", level="error")

        return context

    def _get_context_using_direct_access(self, file_path, line_number, error_message):
        """Get context information using direct file access.

        Args:
            file_path: Path to the file where the error occurred
            line_number: Line number where the error occurred
            error_message: The error message

        Returns:
            Dictionary with context information
        """
        context = {}

        try:
            # Read the file content
            if self.file_tool:
                content = self.file_tool.read_file(file_path)
                if content:
                    # Extract code snippet around the error line
                    lines = content.split('\n')
                    start_line = max(0, line_number - 5)
                    end_line = min(len(lines), line_number + 5)

                    code_snippet = []
                    for i in range(start_line, end_line):
                        prefix = "-> " if i == line_number - 1 else "   "
                        code_snippet.append(f"{i+1}: {prefix}{lines[i]}")

                    context["code_snippet"] = "\n".join(code_snippet)

            # Try to get related files based on imports
            if self.code_analysis_tool and hasattr(self.code_analysis_tool, 'get_file_imports'):
                try:
                    imports = self.code_analysis_tool.get_file_imports(file_path)
                    if imports:
                        context["imports"] = imports
                except Exception as e:
                    self._log(f"Error getting imports: {e}", level="warning")
        except Exception as e:
            self._log(f"Error getting context using direct access: {e}", level="error")

        return context

    def attempt_automated_recovery(self, error_info, context):
        """
        Attempt an automated recovery for the given error context.
        Supports shell commands, file reverts, patch application, dependency installation, permission fixes, and database migrations.
        Returns a tuple (recovery_attempted: bool, recovery_result: str)
        """
        import subprocess
        import shutil
        import stat
        # 1. Try known pattern-based fixes first
        similar_pattern, score = self._find_similar_error_pattern(error_info)
        if similar_pattern and score > 0.9:
            fixes = similar_pattern.get("automated_fixes", [])
            for fix in fixes:
                if fix.get("type") == "shell_command":
                    try:
                        result = subprocess.run(fix["command"], shell=True, capture_output=True, text=True, timeout=30)
                        if result.returncode == 0:
                            return True, f"Automated fix applied: {fix['command']}\nOutput: {result.stdout}"
                        else:
                            return True, f"Automated fix failed: {fix['command']}\nError: {result.stderr}"
                    except Exception as e:
                        return True, f"Automated fix exception: {e}"
                elif fix.get("type") == "revert_file":
                    file_path = fix.get("file_path")
                    backup_path = fix.get("backup_path")
                    if file_path and backup_path and os.path.isfile(backup_path):
                        try:
                            shutil.copy2(backup_path, file_path)
                            return True, f"Reverted file {file_path} from backup."
                        except Exception as e:
                            return True, f"Failed to revert file {file_path}: {e}"
                elif fix.get("type") == "patch_file":
                    file_path = fix.get("file_path")
                    patch_content = fix.get("patch_content")
                    if file_path and patch_content:
                        try:
                            with open(file_path, 'r+') as f:
                                original = f.read()
                                # Simple patch: replace old with new (for demo, real patching should use difflib or patch)
                                if fix.get("old") and fix.get("new"):
                                    patched = original.replace(fix["old"], fix["new"])
                                    f.seek(0)
                                    f.write(patched)
                                    f.truncate()
                                    return True, f"Patched file {file_path} with provided patch."
                        except Exception as e:
                            return True, f"Failed to patch file {file_path}: {e}"
                elif fix.get("type") == "install_dependency":
                    package = fix.get("package")
                    if package:
                        try:
                            result = subprocess.run(f"pip install {package}", shell=True, capture_output=True, text=True, timeout=60)
                            if result.returncode == 0:
                                return True, f"Installed dependency: {package}\nOutput: {result.stdout}"
                            else:
                                return True, f"Failed to install dependency: {package}\nError: {result.stderr}"
                        except Exception as e:
                            return True, f"Dependency install exception: {e}"
                elif fix.get("type") == "fix_permissions":
                    file_path = fix.get("file_path")
                    mode = fix.get("mode")
                    if file_path and mode:
                        try:
                            os.chmod(file_path, int(mode, 8))
                            return True, f"Permissions for {file_path} set to {mode}."
                        except Exception as e:
                            return True, f"Failed to set permissions for {file_path}: {e}"
                elif fix.get("type") == "run_db_migration":
                    migration_cmd = fix.get("command")
                    if migration_cmd:
                        try:
                            result = subprocess.run(migration_cmd, shell=True, capture_output=True, text=True, timeout=60)
                            if result.returncode == 0:
                                return True, f"Database migration succeeded.\nOutput: {result.stdout}"
                            else:
                                return True, f"Database migration failed.\nError: {result.stderr}"
                        except Exception as e:
                            return True, f"Database migration exception: {e}"
            return False, "No actionable automated fix found for this error pattern."

        # 2. Generalize: try common fixes for error types even if not in a known pattern
        error_type = error_info.get("error_type") or self._detect_error_type(error_info)
        message = error_info.get("message", "")
        # ImportError: try pip install for missing package
        if error_type == "import":
            match = re.search(r"No module named ['\"]([a-zA-Z0-9_\-]+)['\"]", message)
            if match:
                package = match.group(1)
                try:
                    result = subprocess.run(f"pip install {package}", shell=True, capture_output=True, text=True, timeout=60)
                    if result.returncode == 0:
                        return True, f"Automated recovery: Installed missing package '{package}'.\nOutput: {result.stdout}"
                    else:
                        return True, f"Automated recovery failed: Could not install '{package}'.\nError: {result.stderr}"
                except Exception as e:
                    return True, f"Automated recovery exception during pip install: {e}"
        # PermissionError: try chmod 644
        if error_type == "permission":
            file_paths = error_info.get("file_paths", [])
            for file_path in file_paths:
                try:
                    os.chmod(file_path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)
                    return True, f"Automated recovery: Set permissions to 644 for {file_path}."
                except Exception as e:
                    return True, f"Automated recovery exception during chmod: {e}"
        # DatabaseError: try running migration if command is available in context
        if error_type == "database":
            migration_cmd = context.get("db_migration_command")
            if migration_cmd:
                try:
                    result = subprocess.run(migration_cmd, shell=True, capture_output=True, text=True, timeout=60)
                    if result.returncode == 0:
                        return True, f"Automated recovery: Ran DB migration.\nOutput: {result.stdout}"
                    else:
                        return True, f"Automated recovery failed: DB migration.\nError: {result.stderr}"
                except Exception as e:
                    return True, f"Automated recovery exception during DB migration: {e}"
        # Add more general recovery strategies as needed
        return False, "No automated recovery strategy succeeded or applicable."

    def _detect_error_type(self, error_info):
        """Detect the type of error with more granular categorization."""
        error_type = "unknown"
        error_msg = error_info.get("message", "").lower()
        error_class = error_info.get("type", "").lower()
        
        # Syntax errors
        if "syntaxerror" in error_class or "syntax error" in error_msg:
            error_type = "syntax"
        # Type errors
        elif "typeerror" in error_class or "type error" in error_msg:
            error_type = "type"
        # Import errors
        elif "importerror" in error_class or "modulenotfounderror" in error_class:
            error_type = "import"
        # Attribute errors
        elif "attributeerror" in error_class:
            error_type = "attribute"
        # Name errors
        elif "nameerror" in error_class:
            error_type = "name"
        # Index errors
        elif "indexerror" in error_class or "keyerror" in error_class:
            error_type = "index"
        # Value errors
        elif "valueerror" in error_class:
            error_type = "value"
        # Runtime errors
        elif "runtimeerror" in error_class:
            error_type = "runtime"
        # Memory errors
        elif "memoryerror" in error_class:
            error_type = "memory"
        # Permission errors
        elif "permissionerror" in error_class or "oserror" in error_class:
            error_type = "permission"
        # Assertion errors
        elif "assertionerror" in error_class:
            error_type = "assertion"
        # HTTP/Network errors
        elif any(x in error_msg for x in ["http", "network", "connection", "timeout"]):
            error_type = "network"
        # Database errors
        elif any(x in error_msg.lower() for x in ["sql", "database", "db"]):
            error_type = "database"
        
        return error_type

    def _get_specialized_context(self, error_type, error_info, failed_file):
        """Get specialized context based on error type."""
        context = {}
        
        if error_type == "import":
            # Check Python path and package dependencies
            context["python_path"] = os.environ.get("PYTHONPATH", "")
            if failed_file:
                context["package_info"] = self._get_package_info(failed_file)
                
        elif error_type == "permission":
            # Check file permissions
            if failed_file:
                context["file_permissions"] = self._get_file_permissions(failed_file)
                
        elif error_type == "memory":
            # Get memory usage stats
            import psutil
            context["memory_info"] = {
                "available": psutil.virtual_memory().available,
                "percent": psutil.virtual_memory().percent
            }
            
        elif error_type == "network":
            # Check network connectivity
            context["network_info"] = self._check_network_status()
            
        elif error_type == "database":
            # Get database connection info (sanitized)
            context["db_info"] = self._get_sanitized_db_info()
        
        return context

    def _generate_recovery_suggestions(self, error_type, error_info):
        """Generate targeted recovery suggestions based on error type."""
        suggestions = []
        
        if error_type == "syntax":
            suggestions.extend([
                "Check for missing parentheses, brackets, or quotes",
                "Verify proper indentation",
                "Look for invalid Python syntax"
            ])
        elif error_type == "type":
            suggestions.extend([
                "Verify variable types match expected types",
                "Add type conversion if needed",
                "Check function parameter types"
            ])
        elif error_type == "import":
            suggestions.extend([
                "Verify package is installed",
                "Check import path is correct",
                "Update PYTHONPATH if needed"
            ])
        elif error_type == "attribute":
            suggestions.extend([
                "Verify object has the referenced attribute",
                "Check for typos in attribute name",
                "Ensure object is properly initialized"
            ])
        elif error_type == "network":
            suggestions.extend([
                "Check network connectivity",
                "Verify endpoint URLs",
                "Add retry logic for transient failures"
            ])
        elif error_type == "database":
            suggestions.extend([
                "Verify database connection settings",
                "Check SQL query syntax",
                "Ensure database is running"
            ])
        
        # Add error-specific suggestions
        if error_info.get("similar_error"):
            suggestions.extend(error_info["similar_error"].get("solutions", []))
        
        return suggestions

    def _update_error_patterns(self, error_info, context):
        """Update error patterns cache with new error information."""
        if not self.error_patterns:
            self.error_patterns = []
            
        # Create pattern from current error
        pattern = {
            "type": error_info.get("type"),
            "message_pattern": error_info.get("message_pattern"),
            "context": {
                "error_type": context.get("error_type")
            },
            "solutions": context.get("recovery_suggestions", []),
            "frequency": 1,
            "last_seen": time.time()
        }
        
        # Check if similar pattern exists
        similar_found = False
        for existing in self.error_patterns:
            if (existing.get("type") == pattern["type"] and 
                existing.get("message_pattern") == pattern["message_pattern"]):
                # Update existing pattern
                existing["frequency"] += 1
                existing["last_seen"] = pattern["last_seen"]
                # Merge solutions without duplicates
                existing["solutions"] = list(set(existing["solutions"] + pattern["solutions"]))
                similar_found = True
                break
                
        # Add new pattern if no similar one exists
        if not similar_found:
            self.error_patterns.append(pattern)
            
        # Prune old patterns
        self._prune_error_patterns()

    def _prune_error_patterns(self):
        """Remove old or infrequent error patterns."""
        if not self.error_patterns:
            return
            
        current_time = time.time()
        retention_period = 7 * 24 * 60 * 60  # 7 days
        
        # Keep patterns that are either:
        # 1. Recent (within retention period)
        # 2. Frequently occurring (more than 5 times)
        self.error_patterns = [
            pattern for pattern in self.error_patterns
            if (current_time - pattern.get("last_seen", 0) <= retention_period or
                pattern.get("frequency", 0) > 5)
        ]

    def _parse_error(self, error_message, stack_trace=None):
        """Parse error message and stack trace to extract key information.
        
        Args:
            error_message: The error message
            stack_trace: Optional stack trace
            
        Returns:
            Dict with parsed error information
        """
        info = {
            "type": None,
            "message": error_message,
            "message_pattern": None,
            "file_paths": [],
            "line_numbers": [],
            "function_names": [],
            "modules": [],
        }
        
        # Extract error type
        error_type_match = re.search(r'([A-Za-z]+Error|Exception):', error_message)
        if error_type_match:
            info["type"] = error_type_match.group(1)
        
        # Create message pattern (replace specific values with placeholders)
        if error_message:
            pattern = re.sub(r'\'[^\']+\'', "'VALUE'", error_message)
            pattern = re.sub(r'"[^"]+"', '"VALUE"', pattern)
            pattern = re.sub(r'\d+', 'NUM', pattern)
            info["message_pattern"] = pattern
        
        # Parse stack trace if available
        if stack_trace:
            # Extract file paths
            file_paths = re.findall(r'File \"([^\"]+)\"', stack_trace)
            info["file_paths"] = file_paths
            
            # Extract line numbers
            line_numbers = re.findall(r'line (\d+)', stack_trace)
            info["line_numbers"] = [int(num) for num in line_numbers]
            
            # Extract function names
            func_matches = re.findall(r'in ([A-Za-z_][A-Za-z0-9_]*)', stack_trace)
            info["function_names"] = func_matches
            
            # Extract modules
            if file_paths:
                modules = []
                for path in file_paths:
                    if path.endswith('.py'):
                        module = os.path.basename(path)[:-3]
                        modules.append(module)
                info["modules"] = modules
        
        return info
    
    def _find_similar_error_pattern(self, error_info):
        """Find similar error patterns in the cache.
        
        Uses both exact matching and fuzzy matching for error message patterns.
        """
        if not error_info or not self.error_patterns:
            return None, 0
            
        error_type = error_info.get("type")
        message_pattern = error_info.get("message_pattern")
        
        if not error_type or not message_pattern:
            return None, 0
            
        best_match = None
        best_score = 0
        
        for pattern in self.error_patterns:
            # Same error type is required for similarity
            if pattern.get("type") != error_type:
                continue
                
            pattern_msg = pattern.get("message_pattern", "")
            if not pattern_msg:
                continue
                
            # Calculate similarity score
            score = self._calculate_pattern_similarity(message_pattern, pattern_msg)
            
            if score > best_score:
                best_score = score
                best_match = pattern
                
        return best_match, best_score

    def _calculate_pattern_similarity(self, pattern1, pattern2):
        """Calculate similarity between two error message patterns."""
        if not pattern1 or not pattern2:
            return 0
            
        # Convert patterns to sets of words
        words1 = set(pattern1.lower().split())
        words2 = set(pattern2.lower().split())
        
        if not words1 or not words2:
            return 0
            
        # Calculate Jaccard similarity
        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))
        
        if union == 0:
            return 0
            
        similarity = intersection / union
        
        # Boost score if patterns have similar structure
        if abs(len(pattern1) - len(pattern2)) / max(len(pattern1), len(pattern2)) < 0.2:
            similarity *= 1.2
            
        return min(1.0, similarity)

    def _create_error_fingerprint(self, error_info):
        """Create a fingerprint for an error pattern.
        
        Args:
            error_info: The parsed error information
            
        Returns:
            A string fingerprint
        """
        error_type = error_info.get("type", "unknown")
        msg_pattern = error_info.get("message_pattern", "")
        
        if not msg_pattern:
            return f"{error_type}:generic"
            
        # Use a shortened version of the message pattern
        shortened_pattern = msg_pattern[:100]
        
        return f"{error_type}:{shortened_pattern}"
    
    def _allocate_token_budgets(self, max_token_count, error_info, file_count):
        """Allocate token budget for different context components.
        
        Args:
            max_token_count: Maximum token count for all context
            error_info: The parsed error information containing file paths
            file_count: Number of files from error info to process
            
        Returns:
            Dict with token budgets for each context component
        """
        # Base allocation
        budgets = {
            "error_message": int(max_token_count * 0.05),  # 5%
            "stack_trace": int(max_token_count * 0.10),    # 10%
            "error_location": int(max_token_count * 0.25), # 25% for error location
            "related_files": int(max_token_count * 0.50),  # 50% for related files
            "similar_pattern": int(max_token_count * 0.10) # 10% for similar pattern
        }
        
        # If we have an error location, prioritize it
        if error_info.get("file_paths") and error_info.get("line_numbers"):
            primary_file = error_info["file_paths"][0]
            primary_line = error_info["line_numbers"][0]
            
            # Allocate more tokens to error location if it exists
            budgets["error_location"] = int(max_token_count * 0.3)
        else:
            # If no specific error location, reallocate its budget
            budgets["error_location"] = 0
            budgets["related_files"] = int(max_token_count * 0.75)
        
        # If we have many files, limit tokens per file
        if file_count > 0:
            tokens_per_file = budgets["related_files"] // file_count
            budgets["per_file"] = tokens_per_file
        else:
            budgets["per_file"] = 0
        
        return budgets
    
    def _add_code_context(self, error_info, token_budgets):
        """Add code context for files mentioned in error info with hierarchical detail.
        
        Args:
            error_info: The parsed error information containing file paths
            token_budgets: Dict with token budgets for context allocation
            
        Returns:
            Dict with file paths to code context
        """
        if not self.file_tool or not error_info.get("file_paths"):
            return {}
            
        code_context = {}
        
        # Track primary error location
        primary_file = None
        primary_line = None
        if error_info.get("file_paths") and error_info.get("line_numbers"):
            primary_file = error_info["file_paths"][0]
            primary_line = error_info["line_numbers"][0]
        
        # Process files from error info
        file_paths = error_info["file_paths"]
        
        # Check if we have a memory manager for summarization
        have_mm = bool(self.memory_manager)
        
        for file_path in file_paths:
            try:
                # Read file content
                if not os.path.isfile(file_path):
                    continue
                    
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Skip empty files
                if not content:
                    continue
                
                # Check if this is the primary error file
                is_primary = file_path == primary_file
                
                if is_primary and primary_line is not None:
                    # For primary error file, focus on the error location
                    lines = content.split('\n')
                    
                    # Adjust if line number is out of range
                    if primary_line >= len(lines):
                        primary_line = len(lines) - 1
                    
                    # Get content around error line
                    context_start = max(0, primary_line - 10)
                    context_end = min(len(lines), primary_line + 10)
                    
                    # Create content with line markers
                    error_context = []
                    for i in range(context_start, context_end):
                        line_marker = "-> " if i == primary_line else "   "
                        error_context.append(f"{i+1}: {line_marker}{lines[i]}")
                    
                    error_location_content = "\n".join(error_context)
                    
                    # Use hierarchical summarization for the rest of the file if it's large
                    if have_mm and len(lines) > 50:
                        # Upper part of file
                        upper_content = "\n".join(lines[:context_start])
                        upper_tokens = token_budgets["per_file"] // 4
                        if upper_content and upper_tokens > 100:
                            upper_summary = self.memory_manager.hierarchical_summarize(
                                upper_content, 
                                target_tokens=upper_tokens
                            )
                            upper_content = f"[BEFORE ERROR]:\n{upper_summary}"
                        else:
                            upper_content = ""
                        
                        # Lower part of file
                        lower_content = "\n".join(lines[context_end:])
                        lower_tokens = token_budgets["per_file"] // 4
                        if lower_content and lower_tokens > 100:
                            lower_summary = self.memory_manager.hierarchical_summarize(
                                lower_content, 
                                target_tokens=lower_tokens
                            )
                            lower_content = f"[AFTER ERROR]:\n{lower_summary}"
                        else:
                            lower_content = ""
                        
                        # Combine all parts
                        combined_content = []
                        if upper_content:
                            combined_content.append(upper_content)
                        combined_content.append("[ERROR LOCATION]:\n" + error_location_content)
                        if lower_content:
                            combined_content.append(lower_content)
                        
                        code_context[file_path] = "\n\n".join(combined_content)
                    else:
                        # Just use the error location if file is small
                        code_context[file_path] = error_location_content
                else:
                    # For other files, use regular (or hierarchical) summarization
                    tokens_for_file = token_budgets["per_file"]
                    tokens_for_file = max(tokens_for_file, 500)  # Minimum useful summary
                    
                    if have_mm and self.memory_manager.estimate_token_count(content) > tokens_for_file:
                        # Apply hierarchical summarization
                        summary = self.memory_manager.hierarchical_summarize(
                            content, 
                            target_tokens=tokens_for_file
                        )
                        code_context[file_path] = f"[SUMMARY]:\n{summary}"
                    else:
                        # Use full content for small files
                        code_context[file_path] = content
            except Exception as e:
                if self.scratchpad:
                    self.scratchpad.log("ErrorContextManager", f"Error processing file {file_path}: {e}")
                continue
        
        return code_context

    def _get_package_info(self, file_path):
        """Get package information for import errors."""
        try:
            # Get directory containing the file
            dir_path = os.path.dirname(os.path.abspath(file_path))
            
            # Look for requirements.txt
            req_file = None
            current_dir = dir_path
            while current_dir != '/':
                potential_req = os.path.join(current_dir, 'requirements.txt')
                if os.path.exists(potential_req):
                    req_file = potential_req
                    break
                current_dir = os.path.dirname(current_dir)
            
            info = {
                "file_dir": dir_path,
                "requirements_file": req_file,
                "python_path": os.environ.get("PYTHONPATH", "").split(os.pathsep),
                "site_packages": None
            }
            
            # Try to get site-packages location
            try:
                import site
                info["site_packages"] = site.getsitepackages()
            except Exception:
                pass
                
            return info
        except Exception as e:
            if self.scratchpad:
                self.scratchpad.log("ErrorContextManager", f"Error getting package info: {e}")
            return {}

    def _get_file_permissions(self, file_path):
        """Get file permission information."""
        try:
            st = os.stat(file_path)
            return {
                "mode": oct(st.st_mode)[-3:],  # Last 3 digits of octal mode
                "owner": st.st_uid,
                "group": st.st_gid,
                "readable": os.access(file_path, os.R_OK),
                "writable": os.access(file_path, os.W_OK),
                "executable": os.access(file_path, os.X_OK)
            }
        except Exception as e:
            if self.scratchpad:
                self.scratchpad.log("ErrorContextManager", f"Error getting file permissions: {e}")
            return {}

    def _check_network_status(self):
        """Check network connectivity status including DNS, HTTP, and HTTPS."""
        import socket
        import urllib.request
        
        def can_connect(host, port):
            try:
                socket.create_connection((host, port), timeout=2)
                return True
            except OSError:
                return False
        
        # Initialize status dict 
        status = {
            "dns_lookup": True,
            "http_access": False,
            "https_access": False,
            "dns_servers_reachable": False
        }
        
        # Check DNS resolution
        try:
            socket.gethostbyname("www.google.com")
        except socket.error:
            status["dns_lookup"] = False
            
        # Check DNS servers connectivity
        status["dns_servers_reachable"] = (
            can_connect("8.8.8.8", 53) or  # Google DNS
            can_connect("1.1.1.1", 53)     # Cloudflare DNS
        )
        
        # Check HTTP access
        try:
            urllib.request.urlopen("http://example.com", timeout=5)
            status["http_access"] = True
        except:
            # Keep http_access as False
            pass
            
        # Check HTTPS access
        try:
            urllib.request.urlopen("https://example.com", timeout=5)
            status["https_access"] = True
        except:
            # Keep https_access as False
            pass
            
        if self.scratchpad:
            self.scratchpad.log("ErrorContextManager", f"Network status check: {status}")
            
        return status

    def _get_sanitized_db_info(self):
        """Get sanitized database connection information."""
        import os
        
        # Look for common database environment variables
        db_vars = {
            "host": os.environ.get("DB_HOST", ""),
            "port": os.environ.get("DB_PORT", ""),
            "name": os.environ.get("DB_NAME", ""),
            "user": "REDACTED" if "DB_USER" in os.environ else "",
            "password": "REDACTED" if "DB_PASSWORD" in os.environ else ""
        }
        
        # Remove empty values
        return {k: v for k, v in db_vars.items() if v}
