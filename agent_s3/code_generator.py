"""Code Generator module for producing code changes from plans."""

import os
import json
import logging
import traceback
import re
import time
from typing import Dict, Optional, Any, List, Union, Tuple

import openai
from openai import OpenAI

from agent_s3.router_agent import RouterAgent, _load_llm_config

logger = logging.getLogger(__name__)

# Initialize models_by_role at module level to avoid undefined global variable
_models_by_role = {}

class CodeGenerator:
    """Handles code generation with optimized context management.
    
    Applies token budget allocation strategies, selective code context based on
    planned modifications, and progressive refinement for better code generation
    with minimal token usage.
    """
    
    def __init__(self, coordinator=None):
        """Initialize the code generator.
        
        Args:
            coordinator: The coordinator instance for access to tools
        """
        self.coordinator = coordinator
        self.llm = coordinator.llm if coordinator else None
        self.scratchpad = coordinator.scratchpad if coordinator else None
        self.file_tool = coordinator.file_tool if coordinator else None
        self.memory_manager = coordinator.memory_manager if coordinator else None
        
        # Track generations for progressive refinement
        self._generation_attempts = {}
    
    def generate_code(self, task, plan=None, tech_stack=None, max_token_count=6000):
        """Generate code for the given task with optimized token usage.
        
        Args:
            task: Task description
            plan: Optional plan from planner
            tech_stack: Optional tech stack information
            max_token_count: Maximum token count for context
            
        Returns:
            Generated code with metadata
        """
        # Log the generation attempt
        task_id = self._create_task_id(task)
        
        self.scratchpad.log("CodeGenerator", f"Generating code for task: {task[:100]}...")
        
        # Track generation attempts
        if task_id in self._generation_attempts:
            self._generation_attempts[task_id]["attempt_count"] += 1
        else:
            self._generation_attempts[task_id] = {
                "attempt_count": 1,
                "failed_attempts": []
            }
        
        # Determine token budget allocation based on complexity and attempt number
        token_budgets = self._allocate_token_budget(
            max_token_count, 
            plan=plan, 
            tech_stack=tech_stack,
            attempt_num=self._generation_attempts[task_id]["attempt_count"]
        )
        
        # For first attempt, use minimal context
        if self._generation_attempts[task_id]["attempt_count"] == 1:
            # Start with minimal context (progressive refinement)
            context = self._gather_minimal_context(task, plan, tech_stack, token_budgets)
        else:
            # Add more context for subsequent attempts
            context = self._gather_full_context(
                task, 
                plan, 
                tech_stack, 
                token_budgets,
                self._generation_attempts[task_id].get("failed_attempts", [])
            )
        
        # Log context composition
        if self.memory_manager:
            context_tokens = {
                k: self.memory_manager.estimate_token_count(v) if isinstance(v, str) else 0
                for k, v in context.items()
            }
            total_tokens = sum(context_tokens.values())
            
            self.scratchpad.log("CodeGenerator", 
                f"Context composition: " +
                f"task={context_tokens.get('task', 0)} tokens, " +
                f"plan={context_tokens.get('plan', 0)} tokens, " +
                f"code_files={context_tokens.get('code_context', 0)} tokens, " +
                f"tech_stack={context_tokens.get('tech_stack', 0)} tokens, " +
                f"total={total_tokens} tokens"
            )
        
        # Generate code using the LLM
        try:
            # Prepare prompt with allocated context
            prompt = self._create_generation_prompt(context)
            
            # Generate code
            response = self.llm.generate(prompt, max_tokens=2048)
            
            # Extract code from response
            generated_code = self._extract_code(response)
            
            # If code generation failed, record the failure for future attempts
            if not generated_code:
                self._generation_attempts[task_id]["failed_attempts"].append({
                    "context": context,
                    "response": response
                })
                self.scratchpad.log("CodeGenerator", "Failed to extract code from response")
                return None
            
            # Return the generated code
            return {
                "code": generated_code,
                "task": task,
                "plan": plan,
                "token_count": len(prompt.split()) + len(response.split()),
                "attempt_num": self._generation_attempts[task_id]["attempt_count"]
            }
            
        except Exception as e:
            self.scratchpad.log("CodeGenerator", f"Error generating code: {e}")
            return None
    
    def _allocate_token_budget(self, max_token_count, plan=None, tech_stack=None, attempt_num=1):
        """Allocate token budget for different context components.
        
        Adjusts allocations based on attempt number for progressive refinement.
        
        Args:
            max_token_count: Maximum token count for context
            plan: Optional plan from planner
            tech_stack: Optional tech stack information
            attempt_num: Generation attempt number
            
        Returns:
            Dict with token budgets for each component
        """
        # Base allocation for first attempt (minimal context)
        if attempt_num == 1:
            return {
                "task": int(max_token_count * 0.2),        # 20%
                "plan": int(max_token_count * 0.3),        # 30%
                "code_context": int(max_token_count * 0.4), # 40%
                "tech_stack": int(max_token_count * 0.1)    # 10%
            }
        
        # Second attempt - more code context
        elif attempt_num == 2:
            return {
                "task": int(max_token_count * 0.15),       # 15%
                "plan": int(max_token_count * 0.25),       # 25%
                "code_context": int(max_token_count * 0.5), # 50%
                "tech_stack": int(max_token_count * 0.1)    # 10%
            }
        
        # Third+ attempt - much more code context
        else:
            return {
                "task": int(max_token_count * 0.1),        # 10%
                "plan": int(max_token_count * 0.2),        # 20%
                "code_context": int(max_token_count * 0.6), # 60%
                "tech_stack": int(max_token_count * 0.1)    # 10%
            }
    
    def _gather_minimal_context(self, task, plan, tech_stack, token_budgets):
        """Gather minimal context for first generation attempt.
        
        Args:
            task: Task description
            plan: Optional plan from planner
            tech_stack: Optional tech stack information
            token_budgets: Token budget allocations
            
        Returns:
            Context dict with minimal information
        """
        context = {
            "task": task[:token_budgets["task"]],
            "plan": None,
            "code_context": {},
            "tech_stack": None
        }
        
        # Include plan summary if available
        if plan:
            if self.memory_manager and self.memory_manager.estimate_token_count(plan) > token_budgets["plan"]:
                context["plan"] = self.memory_manager.summarize(plan, target_tokens=token_budgets["plan"])
            else:
                context["plan"] = plan
        
        # Include minimal tech stack info if available
        if tech_stack:
            if isinstance(tech_stack, dict):
                # Extract just the main frameworks/languages
                minimal_stack = {
                    "languages": tech_stack.get("languages", []),
                    "frameworks": tech_stack.get("frameworks", [])
                }
                context["tech_stack"] = minimal_stack
            else:
                # If it's a string, truncate to fit budget
                ts_budget = token_budgets["tech_stack"]
                if self.memory_manager and self.memory_manager.estimate_token_count(tech_stack) > ts_budget:
                    context["tech_stack"] = tech_stack[:ts_budget]
                else:
                    context["tech_stack"] = tech_stack
        
        # Extract files to be modified from plan
        files_to_modify = self._extract_files_from_plan(plan) if plan else []
        
        # Get minimal context for files to be modified - just one most relevant file
        if files_to_modify and self.file_tool:
            most_relevant = files_to_modify[0]
            try:
                if os.path.isfile(most_relevant):
                    with open(most_relevant, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Truncate or summarize if needed
                    cc_budget = token_budgets["code_context"]
                    if self.memory_manager and self.memory_manager.estimate_token_count(content) > cc_budget:
                        summary = self.memory_manager.summarize(content, target_tokens=cc_budget)
                        context["code_context"][most_relevant] = f"[SUMMARY] {summary}"
                    else:
                        context["code_context"][most_relevant] = content
            except Exception as e:
                self.scratchpad.log("CodeGenerator", f"Error reading file {most_relevant}: {e}")
        
        return context
    
    def _gather_full_context(self, task, plan, tech_stack, token_budgets, failed_attempts=None):
        """Gather comprehensive context for subsequent generation attempts.
        
        Args:
            task: Task description
            plan: Optional plan from planner
            tech_stack: Optional tech stack information
            token_budgets: Token budget allocations
            failed_attempts: Previous failed generation attempts
            
        Returns:
            Context dict with comprehensive information
        """
        context = {
            "task": task[:token_budgets["task"]],
            "plan": None,
            "code_context": {},
            "tech_stack": None,
            "previous_attempts": []
        }
        
        # Include full plan if available
        if plan:
            if self.memory_manager and self.memory_manager.estimate_token_count(plan) > token_budgets["plan"]:
                context["plan"] = self.memory_manager.summarize(plan, target_tokens=token_budgets["plan"])
            else:
                context["plan"] = plan
        
        # Include full tech stack info if available
        if tech_stack:
            ts_budget = token_budgets["tech_stack"]
            if isinstance(tech_stack, dict):
                # If dict, use all fields but potentially summarize large values
                processed_stack = {}
                for k, v in tech_stack.items():
                    if isinstance(v, str) and self.memory_manager:
                        if self.memory_manager.estimate_token_count(v) > ts_budget // 4:
                            processed_stack[k] = v[:ts_budget // 4]  # Simple truncation
                        else:
                            processed_stack[k] = v
                    else:
                        processed_stack[k] = v
                context["tech_stack"] = processed_stack
            else:
                # If string, summarize if needed
                if self.memory_manager and self.memory_manager.estimate_token_count(tech_stack) > ts_budget:
                    context["tech_stack"] = self.memory_manager.summarize(tech_stack, target_tokens=ts_budget)
                else:
                    context["tech_stack"] = tech_stack
        
        # Extract files to be modified from plan
        files_to_modify = self._extract_files_from_plan(plan) if plan else []
        
        # Include context from previous failures
        if failed_attempts:
            # Extract issues from previous attempts
            issues = []
            for attempt in failed_attempts[-2:]:  # Just use the latest 2 attempts
                if "response" in attempt:
                    issues.append(attempt["response"][-200:])  # Last part of response often has error info
            
            if issues:
                context["previous_attempts"] = issues
        
        # Get context for all files to be modified
        cc_budget = token_budgets["code_context"]
        if files_to_modify and self.file_tool:
            # Allocate budget per file
            per_file_budget = cc_budget // min(len(files_to_modify), 8)  # Cap at 8 files
            
            # Process files in batches to stay within budget
            processed_files = 0
            used_budget = 0
            
            for file_path in files_to_modify:
                try:
                    if not os.path.isfile(file_path) or used_budget >= cc_budget:
                        continue
                        
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Skip empty files
                    if not content:
                        continue
                    
                    # Apply hierarchical summarization for large files
                    file_budget = min(per_file_budget, cc_budget - used_budget)
                    
                    if self.memory_manager and self.memory_manager.estimate_token_count(content) > file_budget:
                        summary = self.memory_manager.hierarchical_summarize(
                            content, 
                            target_tokens=file_budget
                        )
                        context["code_context"][file_path] = f"[SUMMARY] {summary}"
                    else:
                        context["code_context"][file_path] = content
                    
                    # Track budget usage
                    used_budget += self.memory_manager.estimate_token_count(context["code_context"][file_path])
                    processed_files += 1
                    
                    # Stop if we've processed enough files
                    if processed_files >= 8:  # Cap at 8 files for practical context
                        break
                        
                except Exception as e:
                    self.scratchpad.log("CodeGenerator", f"Error reading file {file_path}: {e}")
        
        return context
    
    def _extract_files_from_plan(self, plan):
        """Extract files to be modified from the plan.
        
        Args:
            plan: The plan text
            
        Returns:
            List of file paths
        """
        if not plan:
            return []
            
        # Common patterns for file paths in plans
        file_patterns = [
            r'(?:create|modify|update|edit|in|file:)\s+`?([^`\s]+\.[a-zA-Z0-9]+)`?',
            r'(?:Create|Modify|Update|Edit)\s+`?([^`\s]+\.[a-zA-Z0-9]+)`?',
            r'(?:create|modify|update|edit|in)\s+file\s+`?([^`\s]+\.[a-zA-Z0-9]+)`?',
            r'File:\s+`?([^`\s]+\.[a-zA-Z0-9]+)`?',
            r'`([^`\s]+\.[a-zA-Z0-9]+)`'
        ]
        
        files = []
        for pattern in file_patterns:
            matches = re.findall(pattern, plan)
            files.extend(matches)
        
        # Remove duplicates
        unique_files = list(dict.fromkeys(files))
        
        # Resolve full paths if needed
        resolved_files = []
        for file in unique_files:
            # Check if it's a relative path
            if not os.path.isabs(file) and self.coordinator:
                # Try to resolve against project root
                if hasattr(self.coordinator, 'project_root'):
                    full_path = os.path.join(self.coordinator.project_root, file)
                    resolved_files.append(full_path)
                else:
                    # Just use as is
                    resolved_files.append(file)
            else:
                resolved_files.append(file)
        
        return resolved_files
    
    def _create_generation_prompt(self, context):
        """Create a prompt for code generation with the context.
        
        Args:
            context: The context dict
            
        Returns:
            Prompt string
        """
        prompt = f"# Task\n{context['task']}\n\n"
        
        # Add plan if available
        if context.get('plan'):
            prompt += f"# Plan\n{context['plan']}\n\n"
        
        # Add code context if available
        if context.get('code_context'):
            prompt += "# Relevant Code Files\n"
            for file_path, content in context['code_context'].items():
                prompt += f"## {os.path.basename(file_path)}\n```\n{content}\n```\n\n"
        
        # Add tech stack if available
        if context.get('tech_stack'):
            prompt += "# Tech Stack\n"
            if isinstance(context['tech_stack'], dict):
                for key, value in context['tech_stack'].items():
                    prompt += f"## {key}\n{value}\n\n"
            else:
                prompt += f"{context['tech_stack']}\n\n"
        
        # Add previous attempts if available
        if context.get('previous_attempts'):
            prompt += "# Issues from Previous Attempts\n"
            for i, issue in enumerate(context['previous_attempts']):
                prompt += f"Attempt {i+1}: {issue}\n\n"
        
        # Add final instruction
        prompt += "# Instructions\nGenerate code to fulfill the task. Include all necessary files and code snippets. Each file should be in a markdown code block with the filename as the language specifier.\n"
        
        return prompt
    
    def _extract_code(self, response):
        """Extract code from the LLM response.
        
        Args:
            response: The LLM response text
            
        Returns:
            Dict mapping filenames to code content
        """
        # Pattern for code blocks with filename in language specifier
        pattern = r'```([^\n]+)\n(.*?)```'
        matches = re.findall(pattern, response, re.DOTALL)
        
        code_files = {}
        for lang_spec, code in matches:
            # Extract filename from language specifier
            if '.' in lang_spec:
                # Assume the language specifier is or contains the filename
                filename = lang_spec.strip()
            else:
                # Check if there's a filename comment at the start of the code
                filename_match = re.match(r'^\s*#\s*([^\n]+\.[a-zA-Z0-9]+)', code)
                if filename_match:
                    filename = filename_match.group(1).strip()
                else:
                    # No filename found, use a generic name with the language
                    filename = f"generated_code.{lang_spec}"
            
            code_files[filename] = code
        
        return code_files
    
    def _create_task_id(self, task):
        """Create a task ID for tracking generation attempts.
        
        Args:
            task: The task description
            
        Returns:
            Task ID string
        """
        # Use first 100 chars as fingerprint
        task_prefix = task[:100].strip().lower()
        
        import hashlib
        return hashlib.md5(task_prefix.encode()).hexdigest()
