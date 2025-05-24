import os
import re
import shlex

from agent_s3.tools.error_context.cache import update_error_patterns
from agent_s3.tools.error_context.hierarchy import ContextHierarchyManager
from agent_s3.tools.error_context.patterns import (
    detect_error_type,
    find_similar_error_pattern,
    parse_error,
)

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

        # Error patterns and similarity threshold
        self.similarity_threshold = 0.85
        self.error_patterns: list[dict] = []

        # Initialize context hierarchy helper
        self.context_hierarchy = ContextHierarchyManager(
            file_tool=self.file_tool,
            code_analysis_tool=self.code_analysis_tool,
            memory_manager=self.memory_manager,
            context_manager=self.context_manager,
            scratchpad=self.scratchpad,
        )

    def collect_error_context(
        self,
        error_message,
        stack_trace=None,
        failed_file=None,
        max_token_count=4000,
    ) -> dict:
        """Collect context around an error with improved error type detection and recovery hints.

        Args:
            error_message: The error message string
            stack_trace: Optional stack trace string
            failed_file: Optional path to file where error occurred
            max_token_count: Maximum tokens for context

        Returns:
            Dict with error context and recovery suggestions
        """
        error_info = parse_error(error_message, stack_trace)

        # Try to match against known error patterns
        similar_pattern = None
        similarity_score = 0

        if self.error_patterns:
            similar_pattern, similarity_score = find_similar_error_pattern(error_info, self.error_patterns)
            if similarity_score > self.similarity_threshold:
                if self.scratchpad:
                    self.scratchpad.log(
                        "ErrorContextManager",
                        f"Found similar error pattern in cache (score: {similarity_score:.2f})",
                    )
                # Use the cached pattern's solutions as additional context
                error_info["similar_error"] = similar_pattern
                error_info["suggested_fixes"] = similar_pattern.get("solutions", [])

        # Enhanced error type detection
        error_type = detect_error_type(error_info)
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
            self.context_hierarchy._log("Using context management system for error context gathering")
            context = self.context_hierarchy.gather_context_using_context_manager(
                context, error_info, max_token_count
            )
        else:
            self.context_hierarchy._log(
                "Using direct file access for error context gathering (context manager not available)"
            )
            token_budgets = self.context_hierarchy.allocate_token_budgets(
                max_token_count, error_info, len(error_info.get("file_paths", []))
            )
            context["relevant_code"] = self.context_hierarchy.add_code_context(error_info, token_budgets)

        # Track error frequency and update patterns
        update_error_patterns(self.error_patterns, error_info, context)

        return context


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
        self.context_hierarchy._log(f"Getting context for error in {file_path}:{line_number}")

        if self.context_manager:
            return self.context_hierarchy.get_context_using_context_manager(
                file_path, line_number, error_message
            )
        return self.context_hierarchy.get_context_using_direct_access(
            file_path, line_number, error_message
        )


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
        similar_pattern, score = find_similar_error_pattern(error_info, self.error_patterns)
        if similar_pattern and score > 0.9:
            fixes = similar_pattern.get("automated_fixes", [])
            for fix in fixes:
                if fix.get("type") == "shell_command":
                    try:
                        cmd_list = shlex.split(fix["command"])
                        result = subprocess.run(cmd_list, capture_output=True, text=True, timeout=30)
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
                            if re.match(r"^[a-zA-Z0-9._-]+$", package):
                                result = subprocess.run(["pip", "install", package], capture_output=True, text=True, timeout=60)
                            else:
                                return True, f"Invalid package name: {package}"
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
                            cmd_list = shlex.split(migration_cmd)
                            result = subprocess.run(cmd_list, capture_output=True, text=True, timeout=60)
                            if result.returncode == 0:
                                return True, f"Database migration succeeded.\nOutput: {result.stdout}"
                            else:
                                return True, f"Database migration failed.\nError: {result.stderr}"
                        except Exception as e:
                            return True, f"Database migration exception: {e}"
            return False, "No actionable automated fix found for this error pattern."

        # 2. Generalize: try common fixes for error types even if not in a known pattern
        error_type = error_info.get("error_type") or detect_error_type(error_info)
        message = error_info.get("message", "")
        # ImportError: try pip install for missing package
        if error_type == "import":
            match = re.search(r"No module named ['\"]([^'\"]+)['\"]", message)
            if match:
                package = match.group(1)
                try:
                    if re.match(r"^[a-zA-Z0-9._-]+$", package):
                        result = subprocess.run(["pip", "install", package], capture_output=True, text=True, timeout=60)
                    else:
                        return True, f"Invalid package name: {package}"
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
                    cmd_list = shlex.split(migration_cmd)
                    result = subprocess.run(cmd_list, capture_output=True, text=True, timeout=60)
                    if result.returncode == 0:
                        return True, f"Automated recovery: Ran DB migration.\nOutput: {result.stdout}"
                    else:
                        return True, f"Automated recovery failed: DB migration.\nError: {result.stderr}"
                except Exception as e:
                    return True, f"Automated recovery exception during DB migration: {e}"
        # Add more general recovery strategies as needed
        return False, "No automated recovery strategy succeeded or applicable."

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
        except Exception:
            # Keep http_access as False
            pass

        # Check HTTPS access
        try:
            urllib.request.urlopen("https://example.com", timeout=5)
            status["https_access"] = True
        except Exception:
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
