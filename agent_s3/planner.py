"""Planner module for generating implementation plans from user requests."""

import os
import json
import logging
import traceback
from typing import Dict, List, Tuple, Any, Optional, Literal
from datetime import datetime
import re
import time  # Import time module for circuit breaker functionality

try:
    from agent_s3.router_agent import RouterAgent, _load_llm_config
except ImportError:
    print("Warning: Could not import RouterAgent or _load_llm_config from agent_s3.router_agent")
    class RouterAgent:
        def call_llm_by_role(self, **kwargs):
            print("Dummy RouterAgent called")
            return json.dumps({"discussion": "Dummy discussion", "plan": "Dummy plan"})
    def _load_llm_config(): return {}

from agent_s3.prompt_moderator import PromptModerator

logger = logging.getLogger(__name__)

_models_by_role = {}

class Planner:
    """
    The Planner class is responsible for creating plans for tasks using an LLM.
    Implements optimized context management strategies:
    1. Uses file metadata (modification frequency and recency)
    2. Caches embeddings by query theme
    3. Applies hierarchical summarization to context
    """
    
    def __init__(self, coordinator=None):
        """Initialize the planner with a coordinator for access to tools."""
        self.coordinator = coordinator
        self.llm = coordinator.llm if coordinator else None
        self.code_analysis_tool = coordinator.code_analysis_tool if coordinator else None
        self.memory_manager = coordinator.memory_manager if coordinator else None
        self.file_tool = coordinator.file_tool if coordinator else None
        self.scratchpad = coordinator.scratchpad if coordinator else None
        
        # Cache for query themes
        self._query_theme_cache = {}
        # Mapping of task types to query themes
        self._task_to_theme_mapping = {
            "refactor": "code-architecture-design-patterns",
            "implement": "implementation-features-functionality",
            "bugfix": "debugging-bug-fixes-error-handling",
            "performance": "optimization-performance-improvements",
            "testing": "testing-frameworks-test-patterns"
        }
        # File metadata tracking
        self._file_metadata = {}
        # Last update time for file metadata
        self._last_metadata_update = 0
    
    def create_plan(self, task, max_token_count=6000):
        """
        Create a plan for the given task using the LLM.
        
        Args:
            task: The task description
            max_token_count: Maximum token count for context
            
        Returns:
            A plan string
        """
        if self.scratchpad:
            self.scratchpad.log("Planner", f"Creating plan for task: {task[:100]}...")
        
        # Update file metadata if needed (once per 30 minutes)
        current_time = time.time()
        if current_time - self._last_metadata_update > 1800:  # 30 minutes
            self._update_file_metadata()
            self._last_metadata_update = current_time
        
        # Determine task type and corresponding query theme
        task_type = self._determine_task_type(task)
        query_theme = self._task_to_theme_mapping.get(task_type, "general-development")
        
        # Add some randomness to avoid overspecialization
        import random
        if random.random() < 0.2:  # 20% chance to use general theme
            query_theme = "general-development"
        
        # Gather context for planning
        context = self._gather_context(task, query_theme, max_token_count)
        
        # Log context statistics
        if self.memory_manager:
            context_size = {}
            for section, content in context.items():
                if isinstance(content, str):
                    context_size[section] = self.memory_manager.estimate_token_count(content)
                elif isinstance(content, dict):
                    context_size[section] = sum(
                        self.memory_manager.estimate_token_count(v) 
                        for v in content.values() if isinstance(v, str)
                    )
            
            total_tokens = sum(context_size.values())
            if self.scratchpad:
                self.scratchpad.log("Planner", 
                    f"Context size: {total_tokens} tokens " +
                    f"({', '.join(f'{k}={v}' for k, v in context_size.items())})"
                )
        
        # Create planning prompt
        prompt = self._create_planning_prompt(task, context)
        
        try:
            # Generate plan
            plan = self.llm.generate(prompt, max_tokens=2048)
            return plan
        except Exception as e:
            logging.error(f"Error creating plan: {e}")
            return f"Error creating plan: {e}"
    
    def _determine_task_type(self, task):
        """
        Determine the type of task to select an appropriate query theme.
        
        Args:
            task: The task description
            
        Returns:
            Task type string
        """
        task_lower = task.lower()
        
        # Check for refactoring tasks
        if any(word in task_lower for word in ["refactor", "restructure", "redesign", "clean up"]):
            return "refactor"
        
        # Check for implementation tasks
        if any(word in task_lower for word in ["implement", "create", "add", "build", "develop"]):
            return "implement"
        
        # Check for bug fixing
        if any(word in task_lower for word in ["fix", "bug", "issue", "problem", "error", "crash"]):
            return "bugfix"
        
        # Check for performance tasks
        if any(word in task_lower for word in ["optimize", "performance", "speed", "slow", "faster"]):
            return "performance"
        
        # Check for testing tasks
        if any(word in task_lower for word in ["test", "unit test", "integration test", "testing"]):
            return "testing"
        
        # Default to implementation
        return "implement"
    
    def _gather_context(self, task, query_theme, max_token_count):
        """
        Gather context for planning with optimized token usage and relevance-aware pruning.
        
        Args:
            task: The task description
            query_theme: The query theme for code search
            max_token_count: Maximum token count for context
            
        Returns:
            Context dictionary
        """
        # Allocate token budget
        token_budgets = self._allocate_token_budget(max_token_count)
        
        # Prepare context container
        context = {
            "task": task,
            "relevant_files": {},
            "file_metadata": {},
            "project_structure": None,
            "tech_stack": None,
        }
        
        # Generate query for code search
        query = self._generate_search_query(task, query_theme)
        
        # Create cached query ID from theme and key words from task
        query_id = f"{query_theme}-{self._create_task_fingerprint(task)}"
        
        # Find relevant files using the query (with caching)
        file_results = []
        if self.code_analysis_tool:
            try:
                # Get more results initially since we'll use relevance pruning
                initial_results = self.code_analysis_tool.find_relevant_files(
                    query=query, 
                    top_n=15,  # Increased from 10 to get more candidates for relevance pruning
                    query_theme=query_id,
                    use_hybrid=True  # Enable hybrid search for better results
                )
                
                # Apply relevance-aware pruning if the code analysis tool supports it
                if hasattr(self.code_analysis_tool, 'prune_context_by_relevance'):
                    if self.scratchpad:
                        self.scratchpad.log("Planner", "Applying relevance-aware pruning to context")
                    
                    # Prune results based on relevance to the task
                    file_results = self.code_analysis_tool.prune_context_by_relevance(
                        context_chunks=initial_results,
                        query=task,
                        target_token_count=token_budgets["relevant_files"],
                        llm_client=self.llm
                    )
                else:
                    # Fall back to original top_n results if pruning not available
                    file_results = initial_results
            except Exception as e:
                if self.scratchpad:
                    self.scratchpad.log("Planner", f"Error finding relevant files: {e}")
        
        # Calculate tokens used so far
        used_tokens = self.memory_manager.estimate_token_count(task) if self.memory_manager else len(task.split())
        
        # Track added file paths to avoid duplicates
        added_files = set()
        
        # Process file results and add to context
        for file_result in file_results:
            file_path = file_result.get("file_path")
            content = file_result.get("content")
            score = file_result.get("score", 0)
            relevance_score = file_result.get("relevance_score", 0)
            
            if not file_path or not content or file_path in added_files:
                continue
            
            # Get file metadata if available
            file_meta = self._get_file_metadata(file_path)
            
            # Check if this file needs truncation (as indicated by relevance pruning)
            if file_result.get("needs_truncation") and self.memory_manager:
                target_tokens = file_result.get("target_tokens", token_budgets["relevant_files"])
                content = self.memory_manager.hierarchical_summarize(
                    content, target_tokens=target_tokens
                )
            
            # Estimate tokens for this file's content
            file_tokens = self.memory_manager.estimate_token_count(content) if self.memory_manager else len(content.split())
            
            # Check if adding this file would exceed the budget
            remaining_tokens = token_budgets["relevant_files"] - used_tokens
            
            if file_tokens > remaining_tokens:
                # Apply hierarchical summarization if the file is too large
                if self.memory_manager:
                    summary_tokens = min(remaining_tokens, 1000)  # Cap at 1000 tokens per file
                    if summary_tokens >= 200:  # Only summarize if we can allocate at least 200 tokens
                        content_summary = self.memory_manager.hierarchical_summarize(
                            content, target_tokens=summary_tokens
                        )
                        context["relevant_files"][file_path] = content_summary
                        used_tokens += self.memory_manager.estimate_token_count(content_summary)
                        added_files.add(file_path)
                        
                        # Add file metadata
                        if file_meta:
                            context["file_metadata"][file_path] = file_meta
            else:
                # File fits within budget, add full content
                context["relevant_files"][file_path] = content
                used_tokens += file_tokens
                added_files.add(file_path)
                
                # Add file metadata with relevance score if available
                if file_meta:
                    if relevance_score:
                        file_meta["relevance_score"] = relevance_score
                    context["file_metadata"][file_path] = file_meta
            
            # Stop if we've hit the token budget
            if used_tokens >= token_budgets["relevant_files"]:
                break
        
        # Add project structure if we have a coordinator
        if self.coordinator and hasattr(self.coordinator, "get_project_structure"):
            try:
                project_structure = self.coordinator.get_project_structure()
                
                # Check if we need to summarize the project structure
                if self.memory_manager:
                    structure_tokens = self.memory_manager.estimate_token_count(project_structure)
                    
                    if structure_tokens > token_budgets["project_structure"]:
                        # Summarize project structure
                        context["project_structure"] = self.memory_manager.summarize(
                            project_structure, 
                            target_tokens=token_budgets["project_structure"]
                        )
                    else:
                        context["project_structure"] = project_structure
                else:
                    context["project_structure"] = project_structure
            except Exception as e:
                if self.scratchpad:
                    self.scratchpad.log("Planner", f"Error getting project structure: {e}")
        
        # Add tech stack information if available
        if self.coordinator and hasattr(self.coordinator, "tech_stack_manager"):
            try:
                tech_stack = self.coordinator.tech_stack_manager.get_tech_stack()
                
                if tech_stack:
                    # Format tech stack as string if it's a dict
                    if isinstance(tech_stack, dict):
                        tech_stack_str = json.dumps(tech_stack, indent=2)
                    else:
                        tech_stack_str = str(tech_stack)
                    
                    # Check if we need to summarize
                    if self.memory_manager:
                        tech_stack_tokens = self.memory_manager.estimate_token_count(tech_stack_str)
                        
                        if tech_stack_tokens > token_budgets["tech_stack"]:
                            # Summarize tech stack
                            context["tech_stack"] = self.memory_manager.summarize(
                                tech_stack_str,
                                target_tokens=token_budgets["tech_stack"]
                            )
                        else:
                            context["tech_stack"] = tech_stack_str
                    else:
                        context["tech_stack"] = tech_stack_str
            except Exception as e:
                if self.scratchpad:
                    self.scratchpad.log("Planner", f"Error getting tech stack: {e}")
        
        return context
    
    def _allocate_token_budget(self, max_token_count):
        """
        Allocate token budget for different context components.
        
        Args:
            max_token_count: Maximum token count for all context
            
        Returns:
            Dict with token budgets for each component
        """
        return {
            "relevant_files": int(max_token_count * 0.7),     # 70% for code files
            "project_structure": int(max_token_count * 0.15), # 15% for project structure
            "tech_stack": int(max_token_count * 0.15)         # 15% for tech stack info
        }
    
    def _generate_search_query(self, task, query_theme):
        """
        Generate a search query from the task and theme.
        
        Args:
            task: The task description
            query_theme: The query theme
            
        Returns:
            Search query string
        """
        # Extract key terms from the task
        task_lower = task.lower()
        
        # Extract file names
        file_pattern = r'(?:file[s]?|in)\s+[`\'"]?([a-zA-Z0-9_\-./]+\.[a-zA-Z0-9]+)[`\'"]?'
        file_matches = re.findall(file_pattern, task)
        
        # Extract function/class names
        code_entity_pattern = r'(?:function|method|class|component)\s+[`\'"]?([a-zA-Z0-9_]+)[`\'"]?'
        entity_matches = re.findall(code_entity_pattern, task)
        
        # Extract quoted terms
        quoted_pattern = r'[`\'"]([^`\'"]+)[`\'"]'
        quoted_matches = re.findall(quoted_pattern, task)
        
        # Combine all specific terms
        specific_terms = file_matches + entity_matches + quoted_matches
        
        # Generate the query
        if specific_terms:
            # Use the specific terms extracted from the task
            query = " ".join(specific_terms)
            
            # Add some keywords from the task
            words = task_lower.split()
            keywords = [w for w in words if len(w) > 4 and w not in ["implement", "create", "update", "modify", "function", "method", "class", "component"]]
            
            # Add up to 5 keywords
            if keywords:
                query += " " + " ".join(keywords[:5])
        else:
            # If no specific terms found, use the task description directly
            # but filter out common words
            query = task
        
        # Add some theme-specific terms
        theme_terms = {
            "code-architecture-design-patterns": "design pattern architecture structure",
            "implementation-features-functionality": "implementation feature function method",
            "debugging-bug-fixes-error-handling": "bug error exception handling",
            "optimization-performance-improvements": "optimize performance speed efficient",
            "testing-frameworks-test-patterns": "test unittest pytest assert mock"
        }
        
        theme_keywords = theme_terms.get(query_theme, "")
        if theme_keywords:
            query += f" {theme_keywords}"
        
        return query
    
    def _create_planning_prompt(self, task, context):
        """
        Create a prompt for planning with the gathered context.
        
        Args:
            task: The task description
            context: The context dictionary
            
        Returns:
            Prompt string
        """
        prompt = f"# Task\n{task}\n\n"
        
        # Add relevant files
        if context.get("relevant_files"):
            prompt += "# Relevant Files\n"
            
            for file_path, content in context["relevant_files"].items():
                file_name = os.path.basename(file_path)
                prompt += f"## {file_name} ({file_path})\n"
                
                # Add file metadata if available
                if file_path in context.get("file_metadata", {}):
                    metadata = context["file_metadata"][file_path]
                    prompt += f"Modification frequency: {metadata.get('mod_frequency', 'unknown')}, "
                    prompt += f"Last modified: {metadata.get('last_modified_relative', 'unknown')}\n"
                
                prompt += f"```\n{content}\n```\n\n"
        
        # Add project structure
        if context.get("project_structure"):
            prompt += f"# Project Structure\n{context['project_structure']}\n\n"
        
        # Add tech stack info
        if context.get("tech_stack"):
            prompt += f"# Tech Stack\n{context['tech_stack']}\n\n"
        
        # Add planning instructions
        prompt += """# Planning Instructions
Create a detailed, step-by-step plan for implementing the task. The plan should:
1. Break down the task into logical steps
2. Identify specific files to modify or create
3. Reference existing code patterns and architecture when appropriate
4. Consider potential challenges and how to address them
5. Include appropriate error handling and testing steps

Format your plan as a numbered list, with each step being specific and actionable.
"""
        
        return prompt
    
    def _update_file_metadata(self):
        """Update metadata for all files in the project."""
        if not self.file_tool or not hasattr(self.file_tool, "list_files"):
            return
        
        try:
            # Get all code files
            all_files = self.file_tool.list_files(
                extensions=[".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".c", ".cpp", ".h", ".cs", ".go", ".rb"]
            )
            
            current_time = time.time()
            
            # Track file access and modification
            for file_path in all_files:
                if os.path.isfile(file_path):
                    stats = os.stat(file_path)
                    last_modified = stats.st_mtime
                    
                    # Initialize if new file
                    if file_path not in self._file_metadata:
                        self._file_metadata[file_path] = {
                            "creation_time": stats.st_ctime,
                            "modification_times": [last_modified],
                            "last_modified": last_modified,
                            "mod_count": 1,
                            "mod_frequency": "new"
                        }
                    else:
                        # Update existing file metadata
                        metadata = self._file_metadata[file_path]
                        
                        # Check if this is a new modification
                        if last_modified > metadata["last_modified"]:
                            metadata["modification_times"].append(last_modified)
                            metadata["last_modified"] = last_modified
                            metadata["mod_count"] += 1
                            
                            # Keep only the last 10 modification times
                            if len(metadata["modification_times"]) > 10:
                                metadata["modification_times"] = metadata["modification_times"][-10:]
                        
                        # Calculate modification frequency
                        mod_times = metadata["modification_times"]
                        if len(mod_times) >= 3:
                            # Calculate average time between modifications
                            time_diffs = [mod_times[i] - mod_times[i-1] for i in range(1, len(mod_times))]
                            avg_time_diff = sum(time_diffs) / len(time_diffs)
                            
                            # Classify frequency
                            if avg_time_diff < 3600:  # Less than 1 hour
                                metadata["mod_frequency"] = "very frequent"
                            elif avg_time_diff < 86400:  # Less than 1 day
                                metadata["mod_frequency"] = "frequent"
                            elif avg_time_diff < 604800:  # Less than 1 week
                                metadata["mod_frequency"] = "regular"
                            elif avg_time_diff < 2592000:  # Less than 1 month
                                metadata["mod_frequency"] = "occasional"
                            else:
                                metadata["mod_frequency"] = "rare"
                        elif len(mod_times) == 1:
                            metadata["mod_frequency"] = "new"
                        else:
                            metadata["mod_frequency"] = "infrequent"
                        
                        # Add relative time description
                        time_diff = current_time - last_modified
                        if time_diff < 3600:
                            metadata["last_modified_relative"] = f"{int(time_diff / 60)} minutes ago"
                        elif time_diff < 86400:
                            metadata["last_modified_relative"] = f"{int(time_diff / 3600)} hours ago"
                        elif time_diff < 604800:
                            metadata["last_modified_relative"] = f"{int(time_diff / 86400)} days ago"
                        elif time_diff < 2592000:
                            metadata["last_modified_relative"] = f"{int(time_diff / 604800)} weeks ago"
                        else:
                            metadata["last_modified_relative"] = f"{int(time_diff / 2592000)} months ago"
        except Exception as e:
            logging.error(f"Error updating file metadata: {e}")
    
    def _get_file_metadata(self, file_path):
        """
        Get metadata for a specific file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Metadata dict or None
        """
        if file_path in self._file_metadata:
            return self._file_metadata[file_path]
        
        # If we don't have metadata, try to create it now
        if os.path.isfile(file_path):
            try:
                stats = os.stat(file_path)
                current_time = time.time()
                last_modified = stats.st_mtime
                time_diff = current_time - last_modified
                
                # Create relative time description
                if time_diff < 3600:
                    last_modified_relative = f"{int(time_diff / 60)} minutes ago"
                elif time_diff < 86400:
                    last_modified_relative = f"{int(time_diff / 3600)} hours ago"
                elif time_diff < 604800:
                    last_modified_relative = f"{int(time_diff / 86400)} days ago"
                elif time_diff < 2592000:
                    last_modified_relative = f"{int(time_diff / 604800)} weeks ago"
                else:
                    last_modified_relative = f"{int(time_diff / 2592000)} months ago"
                
                return {
                    "creation_time": stats.st_ctime,
                    "last_modified": last_modified,
                    "last_modified_relative": last_modified_relative,
                    "mod_frequency": "unknown"
                }
            except Exception:
                return None
        
        return None
    
    def _create_task_fingerprint(self, task):
        """Create a fingerprint for a task to use in cache keys.
        
        Args:
            task: The task description
            
        Returns:
            A short fingerprint string
        """
        # Use first 50 chars and strip whitespace/lowercase
        task_prefix = task[:50].strip().lower()
        
        # Create MD5 hash and use first 8 chars
        import hashlib
        return hashlib.md5(task_prefix.encode()).hexdigest()[:8]
