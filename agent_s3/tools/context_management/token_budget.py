"""
Token Budget Allocation for Agent-S3.

This module provides tools for analyzing and optimizing token usage in context,
allowing for dynamic allocation based on task requirements and content complexity.
It uses tiktoken for accurate token counting with support for multiple models.
"""

import re
import math
import logging
import tiktoken
import os
import ast
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Set, Tuple, Union, Callable
from collections import defaultdict

logger = logging.getLogger(__name__)

# Approximate token count for different programming languages (per line)
TOKEN_ESTIMATES = {
    "python": 8,    # Python tends to be more concise
    "javascript": 10,
    "typescript": 12,  # TS has type annotations
    "java": 15,
    "csharp": 14,
    "cpp": 12,
    "go": 10,
    "ruby": 7,
    "php": 11,
    "html": 5,
    "css": 6,
    "markdown": 4,
    "json": 5,
    "yaml": 4,
    "text": 6,     # Default for unknown file types
}

# File extension to language mapping
EXTENSION_TO_LANGUAGE = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".java": "java",
    ".cs": "csharp",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".go": "go",
    ".rb": "ruby",
    ".php": "php",
    ".html": "html",
    ".htm": "html",
    ".css": "css",
    ".md": "markdown",
    ".json": "json",
    ".yml": "yaml",
    ".yaml": "yaml",
}


class TokenEstimator:
    """
    Estimates token count for various content types using tiktoken.
    """
    
    def __init__(self, model_name: str = "gpt-4"):
        """
        Initialize the token estimator with the specified model.
        
        Args:
            model_name: Name of the model to use for token counting
        """
        try:
            self.encoding = tiktoken.encoding_for_model(model_name)
        except KeyError:
            # Fallback to cl100k_base encoding (used by gpt-4, gpt-3.5-turbo)
            logger.warning(f"Model {model_name} not found. Using cl100k_base encoding.")
            self.encoding = tiktoken.get_encoding("cl100k_base")
        
        # Default language-specific modifiers (to account for code density)
        self.language_modifiers = {
            "python": 1.0,      # Base reference
            "javascript": 1.1,  # Slightly more verbose than Python
            "typescript": 1.15, # More verbose due to type annotations
            "java": 1.25,       # Significantly more verbose
            "csharp": 1.2,      # More verbose than Python
            "go": 1.1,          # About 10% more verbose than Python
            "cpp": 1.2,         # More verbose with templates, etc.
            "text": 1.0,        # Default text
            "markdown": 0.9,    # More efficient token usage for plain text
            "json": 1.1,        # Lots of quotes and braces
            "yaml": 0.95        # Efficient format
        }
    
    def estimate_tokens_for_text(self, text: str, language: Optional[str] = None) -> int:
        """
        Estimate the number of tokens in a text string.
        
        Args:
            text: The text to estimate
            language: Optional programming language for more accurate estimates
            
        Returns:
            Estimated token count
        """
        if not text:
            return 0
        
        # Get accurate token count using tiktoken
        tokens = self.encoding.encode(text)
        token_count = len(tokens)
        
        # Apply language-specific modifier if provided
        if language:
            language = language.lower()
            modifier = self.language_modifiers.get(language, 1.0)
            token_count = int(token_count * modifier)
        
        return token_count
    
    def estimate_tokens_for_file(
        self, 
        file_path: str, 
        content: Optional[str] = None
    ) -> int:
        """
        Estimate the number of tokens in a file.
        
        Args:
            file_path: Path to the file
            content: Optional pre-loaded content of the file
            
        Returns:
            Estimated token count
        """
        # Determine language from file extension
        ext = "." + file_path.split('.')[-1].lower() if '.' in file_path else ""
        language = EXTENSION_TO_LANGUAGE.get(ext, "text")
        
        # If content is provided, use it
        if content is not None:
            return self.estimate_tokens_for_text(content, language)
        
        # Try to read the file if it exists
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                return self.estimate_tokens_for_text(content, language)
            except Exception as e:
                logger.warning(f"Failed to read file {file_path}: {e}")
        
        # Fallback: estimate based on typical file sizes for that language
        avg_tokens_per_file = {
            "python": 1500,
            "javascript": 2000,
            "typescript": 2200,
            "java": 2500,
            "csharp": 2200,
            "go": 1800,
            "cpp": 2000,
            "text": 1000,
            "markdown": 800,
            "json": 1200,
            "yaml": 1000
        }
        
        return avg_tokens_per_file.get(language, 1000)
    
    def estimate_tokens_for_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Estimate token usage for different parts of a context dictionary.
        
        Args:
            context: The context dictionary
            
        Returns:
            Dictionary mapping context sections to token counts
        """
        estimates = {}
        
        # Estimate code_context tokens
        if "code_context" in context:
            code_estimates = {}
            total_code_tokens = 0
            
            for file_path, content in context["code_context"].items():
                file_tokens = self.estimate_tokens_for_file(file_path, content)
                code_estimates[file_path] = file_tokens
                total_code_tokens += file_tokens
            
            estimates["code_context"] = {
                "total": total_code_tokens,
                "files": code_estimates
            }
        
        # Estimate metadata tokens
        if "metadata" in context:
            metadata_str = str(context["metadata"])
            metadata_tokens = self.estimate_tokens_for_text(metadata_str)
            estimates["metadata"] = metadata_tokens
        
        # Estimate framework_structures tokens
        if "framework_structures" in context:
            framework_str = str(context["framework_structures"])
            framework_tokens = self.estimate_tokens_for_text(framework_str)
            estimates["framework_structures"] = framework_tokens
        
        # Estimate historical context tokens
        if "historical_context" in context:
            historical_str = str(context["historical_context"])
            historical_tokens = self.estimate_tokens_for_text(historical_str)
            estimates["historical_context"] = historical_tokens
        
        # Estimate file metadata tokens
        if "file_metadata" in context:
            file_metadata_str = str(context["file_metadata"])
            file_metadata_tokens = self.estimate_tokens_for_text(file_metadata_str)
            estimates["file_metadata"] = file_metadata_tokens
        
        # Estimate related features tokens
        if "related_features" in context:
            related_features_str = str(context["related_features"])
            related_features_tokens = self.estimate_tokens_for_text(related_features_str)
            estimates["related_features"] = related_features_tokens
        
        # Handle any other context sections
        for section, content in context.items():
            if section not in ["code_context", "metadata", "framework_structures", 
                              "historical_context", "file_metadata", "related_features"]:
                section_str = str(content)
                section_tokens = self.estimate_tokens_for_text(section_str)
                estimates[section] = section_tokens
        
        # Calculate total tokens
        total_tokens = sum(
            estimates[k] if isinstance(estimates[k], int) else estimates[k]["total"] 
            for k in estimates
        )
        
        estimates["total"] = total_tokens
        
        return estimates


class TokenBudgetAnalyzer:
    """
    Analyzes context and determines optimal token allocation.
    """
    
    def __init__(
        self, 
        max_tokens: int = 16000,
        reserved_tokens: int = 2000,
        importance_scorers: Optional[Dict[str, Callable]] = None,
        model_name: str = "gpt-4"
    ):
        """
        Initialize the token budget analyzer.
        
        Args:
            max_tokens: Maximum number of tokens available for context
            reserved_tokens: Tokens reserved for system message and other needs
            importance_scorers: Optional functions to score importance of content
            model_name: Model name for token counting
        """
        self.max_tokens = max_tokens
        self.reserved_tokens = reserved_tokens
        self.available_tokens = max_tokens - reserved_tokens
        self.estimator = TokenEstimator(model_name=model_name)
        self.importance_scorers = importance_scorers or {}
        
        # Known important code patterns by language
        self.important_patterns = {
            "python": {
                # Primary API definitions
                "class_def": (r'class\s+(\w+)', 1.5),
                "function_def": (r'def\s+(\w+)\s*\(', 1.3),
                "method_def": (r'^\s+def\s+(\w+)', 1.2),
                "import": (r'import\s+(.+?)$', 1.2),
                "from_import": (r'from\s+(.+?)\s+import', 1.2),
                "decorator": (r'@(\w+)', 1.4),
                # Error handling
                "exception": (r'except|raise\s+\w+', 1.3),
                # Documentation
                "docstring": (r'"""(.+?)"""', 1.4),
                "comment": (r'#\s*(.+?)$', 1.2),
            },
            "javascript": {
                "function_def": (r'function\s+(\w+)', 1.3),
                "arrow_function": (r'const\s+(\w+)\s*=\s*\(.*?\)\s*=>', 1.3),
                "class_def": (r'class\s+(\w+)', 1.5),
                "method_def": (r'(\w+)\s*\(.*?\)\s*{', 1.2),
                "import": (r'import\s+(.+?)\s+from', 1.2),
                "export": (r'export\s+(.+?)$', 1.4),
                "try_catch": (r'try\s*{|catch\s*\(', 1.3),
                "jsdoc": (r'/\*\*(.+?)\*/', 1.4),
            },
            "typescript": {
                "interface": (r'interface\s+(\w+)', 1.6),
                "type_def": (r'type\s+(\w+)', 1.5),
                "function_def": (r'function\s+(\w+)', 1.3),
                "class_def": (r'class\s+(\w+)', 1.5),
                "method_def": (r'(\w+)\s*\(.*?\)\s*:\s*\w+', 1.3),
                "import": (r'import\s+(.+?)\s+from', 1.2),
                "export": (r'export\s+(.+?)$', 1.4),
            },
        }
        
        # Common important identifiers across languages
        self.important_identifiers = {
            "main", "init", "start", "run", "process", "handle", "create", 
            "build", "setup", "configure", "get", "set", "update", "delete",
            "add", "remove", "find", "search", "validate", "execute", "parse",
            "convert", "transform", "generate", "load", "save", "read", "write",
            "open", "close", "connect", "disconnect", "send", "receive",
            "route", "controller", "service", "repository", "manager", "helper",
            "util", "store", "reducer", "action", "component", "model", "view"
        }
    
    def analyze_code_structure(self, content: str, language: str) -> Dict[str, Any]:
        """
        Analyze code structure to identify important elements.
        
        Args:
            content: The code content
            language: Programming language
            
        Returns:
            Dictionary with structural analysis
        """
        analysis = {
            "functions": [],
            "classes": [],
            "imports": [],
            "patterns": {},
            "complexity_metrics": {}
        }
        
        # Extract code structure based on language
        if language == "python":
            try:
                # Use AST to parse Python code
                tree = ast.parse(content)
                
                # Extract functions and classes
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        analysis["functions"].append({
                            "name": node.name,
                            "line": node.lineno,
                            "decorators": [d.id if hasattr(d, 'id') else str(d) for d in node.decorator_list],
                            "args": len(node.args.args)
                        })
                    elif isinstance(node, ast.ClassDef):
                        analysis["classes"].append({
                            "name": node.name,
                            "line": node.lineno,
                            "bases": len(node.bases),
                            "methods": sum(1 for child in node.body if isinstance(child, ast.FunctionDef))
                        })
                    elif isinstance(node, ast.ImportFrom):
                        if node.module:
                            analysis["imports"].append(f"{node.module} ({', '.join(n.name for n in node.names)})")
                    elif isinstance(node, ast.Import):
                        analysis["imports"].extend(n.name for n in node.names)
                
                # Calculate complexity metrics
                analysis["complexity_metrics"] = {
                    "num_functions": len(analysis["functions"]),
                    "num_classes": len(analysis["classes"]),
                    "num_imports": len(analysis["imports"]),
                    "lines": content.count('\n') + 1,
                    "avg_line_length": len(content) / (content.count('\n') + 1) if content else 0,
                }
            except SyntaxError:
                # Fallback to regex patterns if AST parsing fails
                pass
        
        # Check for important patterns using regex
        if language in self.important_patterns:
            for pattern_name, (regex, _) in self.important_patterns[language].items():
                matches = re.findall(regex, content, re.MULTILINE)
                if matches:
                    analysis["patterns"][pattern_name] = matches
        
        return analysis
    
    def analyze_content_complexity(self, code_context: Dict[str, str]) -> Dict[str, float]:
        """
        Analyze the complexity and importance of code content.
        
        Args:
            code_context: Dictionary mapping file paths to content
            
        Returns:
            Dictionary mapping file paths to complexity/importance scores
        """
        complexity_scores = {}
        file_analyses = {}
        
        for file_path, content in code_context.items():
            # Calculate basic metrics
            lines = content.count('\n') + 1
            avg_line_length = len(content) / lines if lines > 0 else 0
            
            # Calculate language-specific complexity
            ext = "." + file_path.split('.')[-1].lower() if '.' in file_path else ""
            language = EXTENSION_TO_LANGUAGE.get(ext, "text")
            
            # Get patterns for this language
            language_patterns = self.important_patterns.get(language.lower(), 
                                                          self.important_patterns.get("python", {}))
            
            # Base complexity/importance score
            score = 1.0
            
            # Analyze code structure when possible
            analysis = self.analyze_code_structure(content, language)
            file_analyses[file_path] = analysis
            
            # Score based on defined entities (functions, classes, etc.)
            entity_count = len(analysis.get("functions", [])) + len(analysis.get("classes", []))
            if entity_count > 0:
                score *= (1 + min(1.0, entity_count / 20))  # Cap at doubling the score
            
            # Score based on entity importance
            important_entity_bonus = 0
            for entity_type in ["functions", "classes"]:
                for entity in analysis.get(entity_type, []):
                    name = entity["name"]
                    # Check if name is in list of important identifiers
                    if name.lower() in self.important_identifiers:
                        important_entity_bonus += 0.2
                    # Check for common patterns indicating importance
                    if name.startswith("main") or name.endswith("Controller") or name.endswith("Service"):
                        important_entity_bonus += 0.3
            
            # Apply important entity bonus (cap at doubling)
            score *= (1 + min(1.0, important_entity_bonus))
            
            # Apply language-specific adjustments
            if language in ["python", "ruby"]:
                # These tend to be more concise and important
                score *= 1.1
            elif language in ["java", "csharp"]:
                # These tend to be more verbose but often core functionality
                score *= 1.2
            
            # Check for important code patterns using regex
            pattern_importance = 0
            for pattern_name, (pattern, importance) in language_patterns.items():
                matches = re.findall(pattern, content)
                if matches:
                    # Weight by number of occurrences but with diminishing returns
                    pattern_importance += importance * min(3, len(matches)/3)
                    
                    # Check if matched identifiers are in the important list
                    for match in matches:
                        if isinstance(match, str) and match.lower() in self.important_identifiers:
                            pattern_importance += 0.1
            
            # Apply pattern importance bonus (cap at tripling)
            score *= (1 + min(2.0, pattern_importance / 10))
            
            # Adjust based on filename relevance
            filename = os.path.basename(file_path).lower()
            if any(keyword in filename for keyword in ["main", "app", "index", "core", "base", "config", "util"]):
                score *= 1.3
            
            # Normalize score to reasonable range (0.5 - 3.0)
            score = max(0.5, min(3.0, score))
            
            complexity_scores[file_path] = score
        
        return complexity_scores
    
    def calculate_importance_scores(
        self, 
        context: Dict[str, Any], 
        task_type: Optional[str] = None,
        task_keywords: Optional[List[str]] = None  # New parameter
    ) -> Dict[str, float]:
        """
        Calculate importance scores for different parts of the context.

        Args:
            context: The context dictionary
            task_type: Optional task type to influence scoring
            task_keywords: Optional list of keywords from the task description
                           to boost relevance.

        Returns:
            Dictionary mapping context items to importance scores
        """
        importance_scores = {}

        # Process code_context
        if "code_context" in context:
            file_scores = {}

            # Get complexity scores
            complexity_scores = self.analyze_content_complexity(context["code_context"])

            for file_path, complexity in complexity_scores.items():
                score = complexity  # Base score is the complexity

                # Apply custom scorers if available
                for scorer_name, scorer_fn in self.importance_scorers.items():
                    try:
                        content = context["code_context"][file_path]
                        custom_score = scorer_fn(file_path, content, task_type)
                        score *= custom_score
                    except Exception as e:
                        logger.warning(f"Error in custom scorer {scorer_name}: {e}")

                # Task-specific scoring
                if task_type:
                    task_type = task_type.lower()

                    # For debugging tasks, prioritize test files and error handling
                    if task_type == "debugging":
                        if "test" in file_path or "spec" in file_path:
                            score *= 1.3
                        if "error" in file_path or "exception" in file_path:
                            score *= 1.4

                    # For feature implementation tasks, prioritize related components
                    elif task_type == "implementation":
                        if "component" in file_path or "model" in file_path:
                            score *= 1.3

                    # For refactoring tasks, prioritize code quality files
                    elif task_type == "refactoring":
                        if "util" in file_path or "helper" in file_path:
                            score *= 1.2
                
                # Boost score if task_keywords are present in the file content
                if task_keywords and file_path in context.get("code_context", {}):
                    content = context["code_context"][file_path].lower()
                    keyword_bonus = 0.0
                    for keyword in task_keywords:
                        if keyword.lower() in content:
                            keyword_bonus += 0.2 # Add a bonus for each keyword found
                    
                    if keyword_bonus > 0:
                        score *= (1 + min(keyword_bonus, 1.0)) # Cap bonus at doubling the score

                file_scores[file_path] = score

            importance_scores["code_context"] = file_scores

        # Process other context sections
        for section in context:
            if section != "code_context" and section not in importance_scores:
                # Default importance for other sections
                importance_scores[section] = 1.0
                
                # Adjust based on task type
                if task_type:
                    task_type = task_type.lower()
                    
                    if section == "framework_structures":
                        if task_type == "implementation":
                            importance_scores[section] = 1.4
                        elif task_type == "debugging":
                            importance_scores[section] = 1.2
                    
                    elif section == "metadata":
                        if task_type == "documentation":
                            importance_scores[section] = 1.5
        
        return importance_scores
    
    def allocate_tokens(
        self, 
        context: Dict[str, Any], 
        task_type: Optional[str] = None,
        task_keywords: Optional[List[str]] = None,  # New parameter
        force_optimization: bool = False
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Allocate tokens to different parts of the context based on importance.

        Args:
            context: The context dictionary
            task_type: Optional task type to influence allocation
            task_keywords: Optional list of keywords from the task description.
            force_optimization: Force optimization even if token count is low (for testing)

        Returns:
            Tuple: (Dictionary with token allocation information and optimized context, importance_scores)
                - The first element is a dictionary with keys 'optimized_context' and 'allocation_report'.
                - The second element is the full importance_scores map (including task-keyword-boosted scores).
        """
        # Estimate token usage
        token_estimates = self.estimator.estimate_tokens_for_context(context)

        # Calculate importance scores
        importance_scores = self.calculate_importance_scores(context, task_type, task_keywords)  # Pass keywords

        # Calculate available tokens
        total_estimated_tokens = token_estimates.get("total", 0)
        
        # Skip test for large_file.py
        
        # If we have more tokens than available, we need to optimize
        if total_estimated_tokens > self.available_tokens or force_optimization:
            # Create new optimized context
            optimized_context = context.copy()
            
            # Optimize code_context based on importance
            if "code_context" in context and "code_context" in importance_scores:
                optimized_code_context = {}
                code_files = list(context["code_context"].keys())
                
                # Sort files by importance score (highest first)
                code_files.sort(
                    key=lambda f: importance_scores["code_context"].get(f, 0), 
                    reverse=True
                )
                
                # Allocate tokens to files based on importance
                allocated_tokens = 0
                
                # Calculate total code budget (proportional to original share)
                code_budget = int(
                    self.available_tokens * 
                    token_estimates["code_context"]["total"] / total_estimated_tokens
                )
                
                # Ensure we don't use more than available tokens
                code_budget = min(code_budget, int(self.available_tokens * 0.8))
                
                for file_path in code_files:
                    file_tokens = token_estimates["code_context"]["files"].get(file_path, 0)
                    
                    # If adding this file would exceed budget, skip or truncate
                    if allocated_tokens + file_tokens > code_budget:
                        # If this is a high-importance file, include a truncated version
                        importance = importance_scores["code_context"].get(file_path, 0)
                        if importance > 1.5 and allocated_tokens < code_budget:
                            # Determine how many tokens we can still allocate
                            remaining_tokens = code_budget - allocated_tokens
                            
                            # Truncate file content to fit remaining tokens
                            content = context["code_context"][file_path]
                            lines = content.split('\n')
                            
                            # Use tiktoken for more accurate token counting
                            ext = "." + file_path.split('.')[-1].lower() if '.' in file_path else ""
                            language = EXTENSION_TO_LANGUAGE.get(ext, "text")
                            
                            # Calculate tokens more accurately using tiktoken
                            tokens_per_line = []
                            for line in lines:
                                # Get token count for each line
                                line_tokens = len(self.estimator.encoding.encode(line))
                                tokens_per_line.append(line_tokens)
                                
                            # Calculate how many lines we can include based on actual token counts
                            lines_to_include = 0
                            tokens_used = 0
                            
                            for i, line_token_count in enumerate(tokens_per_line):
                                if tokens_used + line_token_count <= remaining_tokens:
                                    lines_to_include += 1
                                    tokens_used += line_token_count
                                else:
                                    break
                            
                            # Include important parts (beginning and end)
                            if lines_to_include < len(lines) and lines_to_include > 10:
                                # Take half from beginning and half from end
                                half = lines_to_include // 2
                                truncated_content = '\n'.join(
                                    lines[:half] + 
                                    [f"... [truncated {len(lines) - lines_to_include} lines] ..."] + 
                                    lines[-half:]
                                )
                            else:
                                # Just take from beginning
                                truncated_content = '\n'.join(
                                    lines[:lines_to_include] + 
                                    [f"... [truncated {len(lines) - lines_to_include} lines]"]
                                )
                            
                            optimized_code_context[file_path] = truncated_content
                            allocated_tokens += tokens_used
                        continue
                    
                    # Otherwise include the full file
                    optimized_code_context[file_path] = context["code_context"][file_path]
                    allocated_tokens += file_tokens
                
                # Update the context with optimized code_context
                optimized_context["code_context"] = optimized_code_context
                
                # Calculate tokens for other sections
                other_allocated_tokens = 0
                for section in token_estimates:
                    if section != "code_context" and section != "total":
                        section_tokens = token_estimates[section]
                        if isinstance(section_tokens, dict):
                            section_tokens = section_tokens.get("total", 0)
                        other_allocated_tokens += section_tokens
                
                # Calculate total allocated tokens
                allocated_tokens = allocated_tokens + other_allocated_tokens
                
                # Create allocation report
                allocation_report = {
                    "original_tokens": total_estimated_tokens,
                    "available_tokens": self.available_tokens,
                    "allocated_tokens": allocated_tokens,
                    "code_context_tokens": allocated_tokens - other_allocated_tokens,
                    "other_tokens": other_allocated_tokens,
                    "optimization_applied": True
                }
                
                # Include file-level allocation
                if "code_context" in token_estimates:
                    allocation_report["file_allocations"] = {}
                    for file_path in optimized_context["code_context"]:
                        content = optimized_context["code_context"][file_path]
                        allocated_file_tokens = self.estimator.estimate_tokens_for_text(
                            content, 
                            language=EXTENSION_TO_LANGUAGE.get(
                                "." + file_path.split('.')[-1].lower() if '.' in file_path else "",
                                "text"
                            )
                        )
                        allocation_report["file_allocations"][file_path] = {
                            "allocated_tokens": allocated_file_tokens,
                            "importance_score": importance_scores["code_context"].get(file_path, 0)
                        }
                
                return {
                    "optimized_context": optimized_context,
                    "allocation_report": allocation_report
                }, importance_scores
            
        # If no optimization needed, return original context
        return {
            "optimized_context": context,
            "allocation_report": {
                "original_tokens": total_estimated_tokens,
                "available_tokens": self.available_tokens,
                "allocated_tokens": total_estimated_tokens,
                "optimization_applied": False
            }
        }, importance_scores
    
    def get_total_token_count(self, context: Dict[str, Any]) -> int:
        """
        Returns the total estimated token count for the given context.
        """
        token_estimates = self.estimator.estimate_tokens_for_context(context)
        return token_estimates.get("total", 0)
    
    def get_token_count(self, text: str, language: Optional[str] = None) -> int:
        """
        Returns the estimated token count for a given text and optional language.
        """
        return self.estimator.estimate_tokens_for_text(text, language=language)


class DynamicAllocationStrategy(ABC):
    """
    Abstract base class for dynamic token allocation strategies.
    """
    
    @abstractmethod
    def allocate(
        self, 
        context: Dict[str, Any], 
        task_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Allocate tokens based on a specific strategy.
        
        Args:
            context: The context dictionary
            task_type: Optional task type to influence allocation
            
        Returns:
            Dictionary with token allocation information and optimized context
        """
        pass


class PriorityBasedAllocation(DynamicAllocationStrategy):
    """
    Allocates tokens based on predefined priorities for different context elements.
    """
    
    def __init__(
        self, 
        max_tokens: int = 16000,
        reserved_tokens: int = 2000,
        priorities: Optional[Dict[str, float]] = None,
        model_name: str = "gpt-4"
    ):
        """
        Initialize the priority-based allocation strategy.
        
        Args:
            max_tokens: Maximum number of tokens available for context
            reserved_tokens: Tokens reserved for system message and other needs
            priorities: Optional dictionary of section priorities
            model_name: Name of the model for token counting
        """
        self.analyzer = TokenBudgetAnalyzer(
            max_tokens=max_tokens,
            reserved_tokens=reserved_tokens,
            model_name=model_name
        )
        self.priorities = priorities or {
            "code_context": 1.0,
            "framework_structures": 0.8,
            "metadata": 0.5
        }
    
    def allocate(
        self, 
        context: Dict[str, Any], 
        task_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Allocate tokens based on predefined priorities.
        
        Args:
            context: The context dictionary
            task_type: Optional task type to influence allocation
            
        Returns:
            Dictionary with token allocation information and optimized context
        """
        # Adjust analyzer's importance scorers based on priorities
        custom_scorers = {}
        
        for section, priority in self.priorities.items():
            if section == "code_context":
                # Create a custom scorer that applies this priority
                def priority_scorer(file_path, content, task_type, priority=priority):
                    return priority
                
                custom_scorers["priority_scorer"] = priority_scorer
        
        self.analyzer.importance_scorers = custom_scorers
        
        # Run the allocation
        return self.analyzer.allocate_tokens(context, task_type)


class TaskAdaptiveAllocation(DynamicAllocationStrategy):
    """
    Allocates tokens adaptively based on the type of task being performed.
    """
    
    def __init__(
        self, 
        max_tokens: int = 16000,
        reserved_tokens: int = 2000,
        model_name: str = "gpt-4"
    ):
        """
        Initialize the task-adaptive allocation strategy.
        
        Args:
            max_tokens: Maximum number of tokens available for context
            reserved_tokens: Tokens reserved for system message and other needs
            model_name: Name of the model for token counting
        """
        self.analyzer = TokenBudgetAnalyzer(
            max_tokens=max_tokens,
            reserved_tokens=reserved_tokens,
            model_name=model_name
        )
        
        # Define task-specific priorities
        self.task_priorities = {
            "debugging": {
                "code_context": 1.2,
                "framework_structures": 0.7,
                "metadata": 0.5
            },
            "implementation": {
                "code_context": 1.0,
                "framework_structures": 1.0,
                "metadata": 0.6
            },
            "documentation": {
                "code_context": 0.8,
                "framework_structures": 0.5,
                "metadata": 1.2
            },
            "refactoring": {
                "code_context": 1.3,
                "framework_structures": 0.6,
                "metadata": 0.4
            }
        }
        
        # Custom scorers for different task types
        self.task_scorers = {
            "debugging": {
                "test_files": lambda file_path, content, _: 1.5 if "test" in file_path else 1.0,
                "error_handling": lambda file_path, content, _: 1.3 if "try" in content and "catch" in content else 1.0
            },
            "implementation": {
                "interface_files": lambda file_path, content, _: 1.4 if "interface" in file_path or "types" in file_path else 1.0,
                "core_files": lambda file_path, content, _: 1.3 if "core" in file_path or "main" in file_path else 1.0
            },
            "documentation": {
                "doc_comments": lambda file_path, content, _: 1.5 if "/**" in content or "'''" in content else 1.0
            },
            "refactoring": {
                "complexity": lambda file_path, content, _: 1.4 if content.count(")") > 100 else 1.0
            }
        }
    
    def allocate(
        self, 
        context: Dict[str, Any], 
        task_type: Optional[str] = None,
        task_keywords: Optional[List[str]] = None  # New parameter
    ) -> Dict[str, Any]:
        """
        Allocate tokens adaptively based on task type.

        Args:
            context: The context dictionary
            task_type: Optional task type to influence allocation
            task_keywords: Optional list of keywords from the task description.

        Returns:
            Dictionary with token allocation information and optimized context
        """
        # Default to implementation if no task type is provided
        task_type = task_type or "implementation"
        task_type = task_type.lower()

        # Get priorities for this task type, or use default
        priorities = self.task_priorities.get(task_type, self.task_priorities["implementation"])

        # Get scorers for this task type
        scorers = self.task_scorers.get(task_type, {})

        # Create a priority scorer
        def priority_scorer(file_path, content, task_type, priorities=priorities, task_keywords=task_keywords):  # Pass keywords
            score = priorities.get("code_context", 1.0)
            # Apply any task-specific scorers
            for scorer_name, scorer_fn in scorers.items():
                score *= scorer_fn(file_path, content, task_type)
            
            # Apply keyword bonus if keywords are provided
            if task_keywords and file_path in context.get("code_context", {}):  # Check if file_path is in code_context
                file_content_lower = content.lower()  # content is already available
                keyword_bonus = 0.0
                for keyword in task_keywords:
                    if keyword.lower() in file_content_lower:
                        keyword_bonus += 0.2 
                if keyword_bonus > 0:
                    score *= (1 + min(keyword_bonus, 1.0))
            return score

        # Set the analyzer's scorers
        self.analyzer.importance_scorers = {"task_scorer": priority_scorer}

        # Run the allocation, passing task_keywords
        return self.analyzer.allocate_tokens(context, task_type, task_keywords)
