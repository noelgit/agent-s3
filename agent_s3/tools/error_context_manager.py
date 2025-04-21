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
        
        # Cache for error patterns
        self._error_pattern_cache = {}
        # Cache for recently debugged files
        self._recently_debugged_files = {}
        # Error pattern similarity threshold
        self.similarity_threshold = 0.85
    
    def collect_error_context(self, error_message, stack_trace=None, failed_file=None, max_token_count=4000):
        """Collect context specialized for debugging a specific error.
        
        Args:
            error_message: The error message to debug
            stack_trace: Optional stack trace text
            failed_file: Optional path to the file that triggered the error
            max_token_count: Maximum tokens for context
            
        Returns:
            Dict with error context structured for debugging
        """
        if self.scratchpad:
            self.scratchpad.log("ErrorContextManager", f"Collecting context for error: {error_message[:100]}...")
        
        # Extract key information from error and stack trace
        error_info = self._parse_error(error_message, stack_trace)
        
        # Look for similar error patterns in cache
        similar_pattern, similarity_score = self._find_similar_error_pattern(error_info)
        
        if similar_pattern and similarity_score > self.similarity_threshold:
            if self.scratchpad:
                self.scratchpad.log("ErrorContextManager", 
                                    f"Found similar error pattern in cache (score: {similarity_score:.2f})")
            # Use the cached pattern's solutions as additional context
            error_info["similar_error"] = similar_pattern
        
        # Identify relevant files
        relevant_files = self._identify_relevant_files(error_info, failed_file)
        
        # Allocate tokens for different context components
        token_budgets = self._allocate_token_budgets(max_token_count, error_info, len(relevant_files))
        
        # Build the context
        context = {
            "error_message": error_message,
            "stack_trace": stack_trace,
            "parsed_error": error_info,
            "relevant_code": {},
            "similar_pattern": similar_pattern if similar_pattern and similarity_score > self.similarity_threshold else None,
        }
        
        # Add code context with hierarchical detail levels
        context["relevant_code"] = self._add_code_context(relevant_files, error_info, token_budgets)
        
        # Track token usage for logging
        if self.memory_manager:
            total_tokens = sum(self.memory_manager.estimate_token_count(json.dumps(v)) 
                               for v in context.values() if v)
            
            if self.scratchpad:
                self.scratchpad.log("ErrorContextManager", 
                                    f"Collected error context using {total_tokens} tokens " +
                                    f"across {len(context['relevant_code'])} files")
        
        return context
    
    def cache_error_pattern(self, error_info, solution, success=True):
        """Cache an error pattern and its solution for future reference.
        
        Args:
            error_info: Parsed error information dictionary
            solution: The solution that resolved the error
            success: Whether the solution worked
        """
        if not error_info or not error_info.get("type"):
            return
        
        # Create a fingerprint for this error type
        error_fingerprint = self._create_error_fingerprint(error_info)
        
        if error_fingerprint in self._error_pattern_cache:
            # Update existing pattern with new solution
            pattern = self._error_pattern_cache[error_fingerprint]
            if solution not in pattern["solutions"]:
                pattern["solutions"].append(solution)
            pattern["success_count"] += 1 if success else 0
            pattern["total_count"] += 1
        else:
            # Create new pattern
            self._error_pattern_cache[error_fingerprint] = {
                "type": error_info.get("type"),
                "message_pattern": error_info.get("message_pattern"),
                "solutions": [solution],
                "success_count": 1 if success else 0,
                "total_count": 1,
                "last_seen": time.time()
            }
        
        # Limit cache size (keep most recent/successful patterns)
        if len(self._error_pattern_cache) > 100:
            # Sort by success rate and recency
            patterns = list(self._error_pattern_cache.items())
            sorted_patterns = sorted(
                patterns,
                key=lambda x: (x[1]["success_count"] / max(x[1]["total_count"], 1), -x[1]["last_seen"]),
                reverse=True
            )
            # Keep top 80 patterns
            self._error_pattern_cache = dict(sorted_patterns[:80])
    
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
        """Find a similar error pattern in the cache.
        
        Args:
            error_info: The parsed error information
            
        Returns:
            Tuple of (pattern, similarity_score)
        """
        if not error_info or not error_info.get("type") or not self._error_pattern_cache:
            return None, 0
        
        # Look for exact error type and message pattern match first
        error_fingerprint = self._create_error_fingerprint(error_info)
        if error_fingerprint in self._error_pattern_cache:
            return self._error_pattern_cache[error_fingerprint], 1.0
        
        # Look for similar error types
        best_match = None
        best_score = 0
        
        for pattern in self._error_pattern_cache.values():
            # Different error types are less similar
            if pattern["type"] != error_info.get("type"):
                continue
                
            # Compare message patterns
            pattern_msg = pattern.get("message_pattern", "")
            current_msg = error_info.get("message_pattern", "")
            
            # Skip if either message is missing
            if not pattern_msg or not current_msg:
                continue
                
            # Calculate similarity (simple Jaccard for now)
            pattern_tokens = set(pattern_msg.split())
            current_tokens = set(current_msg.split())
            
            if not pattern_tokens or not current_tokens:
                continue
                
            intersection = len(pattern_tokens.intersection(current_tokens))
            union = len(pattern_tokens.union(current_tokens))
            
            if union == 0:
                continue
                
            similarity = intersection / union
            
            # Update best match
            if similarity > best_score:
                best_score = similarity
                best_match = pattern
        
        return best_match, best_score
    
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
    
    def _identify_relevant_files(self, error_info, failed_file=None):
        """Identify files relevant to the error.
        
        Args:
            error_info: The parsed error information
            failed_file: Optional known file that triggered the error
            
        Returns:
            Dict mapping file paths to relevance scores
        """
        relevant_files = {}
        
        # Add the failed file with highest priority if provided
        if failed_file and os.path.isfile(failed_file):
            relevant_files[failed_file] = 1.0
            
            # Also check if this file was recently debugged
            if failed_file in self._recently_debugged_files:
                debug_info = self._recently_debugged_files[failed_file]
                debug_info["debug_count"] += 1
                debug_info["last_debugged"] = time.time()
            else:
                self._recently_debugged_files[failed_file] = {
                    "debug_count": 1,
                    "last_debugged": time.time()
                }
        
        # Add files from stack trace with high priority
        for i, file_path in enumerate(error_info.get("file_paths", [])):
            if os.path.isfile(file_path):
                # Files earlier in the stack trace are more relevant
                pos_weight = 1.0 - (i * 0.1)
                relevance = max(0.7, pos_weight)
                relevant_files[file_path] = relevance
                
                # Track debug count
                if file_path in self._recently_debugged_files:
                    debug_info = self._recently_debugged_files[file_path]
                    debug_info["debug_count"] += 1
                    debug_info["last_debugged"] = time.time()
                else:
                    self._recently_debugged_files[file_path] = {
                        "debug_count": 1,
                        "last_debugged": time.time()
                    }
        
        # If we have a code analysis tool, find other related files
        if self.code_analysis_tool and error_info.get("type"):
            query = f"{error_info.get('type')} {' '.join(error_info.get('function_names', []))}"
            
            try:
                # Use semantic search to find related files
                search_results = self.code_analysis_tool.find_relevant_files(query, top_n=5)
                
                for result in search_results:
                    file_path = result.get("file_path")
                    
                    # Skip files already included
                    if file_path in relevant_files:
                        continue
                        
                    # Add with lower priority than files from stack trace
                    relevance = min(0.6, result.get("score", 0.5))
                    relevant_files[file_path] = relevance
            except Exception as e:
                if self.scratchpad:
                    self.scratchpad.log("ErrorContextManager", f"Error finding related files: {e}")
        
        # Limit to 10 most relevant files
        if len(relevant_files) > 10:
            sorted_files = sorted(relevant_files.items(), key=lambda x: x[1], reverse=True)
            relevant_files = dict(sorted_files[:10])
        
        return relevant_files
    
    def _allocate_token_budgets(self, max_token_count, error_info, file_count):
        """Allocate token budget for different context components.
        
        Args:
            max_token_count: Maximum token count for all context
            error_info: The parsed error information
            file_count: Number of relevant files
            
        Returns:
            Dict with token budgets for each component
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
    
    def _add_code_context(self, relevant_files, error_info, token_budgets):
        """Add code context for relevant files with hierarchical detail.
        
        Args:
            relevant_files: Dict of file paths to relevance scores
            error_info: The parsed error information
            token_budgets: Dict with token budgets
            
        Returns:
            Dict with file paths to code context
        """
        if not relevant_files or not self.file_tool:
            return {}
            
        code_context = {}
        
        # Track primary error location
        primary_file = None
        primary_line = None
        if error_info.get("file_paths") and error_info.get("line_numbers"):
            primary_file = error_info["file_paths"][0]
            primary_line = error_info["line_numbers"][0]
        
        # Process files in order of relevance
        sorted_files = sorted(relevant_files.items(), key=lambda x: x[1], reverse=True)
        
        # Check if we have a memory manager for summarization
        have_mm = bool(self.memory_manager)
        
        for file_path, relevance in sorted_files:
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