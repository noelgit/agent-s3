"""Terminal Output Parser for Agent-S3 UI Flow.

This module provides functionality to parse and categorize terminal output
for appropriate rendering in the VS Code UI.
"""

import re
import json
from typing import Tuple, Dict, Any, List, Optional, Set, Union, Match
from .message_protocol import OutputCategory


class TerminalOutputParser:
    """Parser for categorizing terminal output into structured data."""
    
    def __init__(self):
        """Initialize the terminal output parser with regex patterns."""
        self.patterns = {
            OutputCategory.APPROVAL_PROMPT: [
                r"Do you (approve|want to proceed|agree).*\? \[(yes|no|y|n|edit)\]",
                r"Create a GitHub issue for this plan\?",
                r"Do you approve this plan\?",
                r"Do you approve these changes\?"
            ],
            OutputCategory.DIFF_CONTENT: [
                r"^diff --git",
                r"^@@ -\d+,\d+ \+\d+,\d+ @@",
                r"^File: .+\n-+\n(\+|-| ).*"
            ],
            OutputCategory.LOG_MESSAGE: [
                r"^\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\]",
                r"^INFO |^WARNING |^ERROR |^DEBUG ",
                r"^ℹ️ INFO: |^⚠️ WARNING: |^❌ ERROR: |^✅ SUCCESS: "
            ],
            OutputCategory.DEBATE_SECTION: [
                r"^## [A-Za-z ]+ Perspective:",
                r"^## Final Consensus:",
                r"^PERSONA DEBATE DISCUSSION:",
                r"^## [A-Za-z ]+ Round \d+:"
            ],
            OutputCategory.PROGRESS_INFO: [
                r"Phase: [a-z_]+, Status: [a-z_]+",
                r"\|█+░*\| \d+%",
                r"^Step \d+/\d+: ",
                r"^Running tests\.\.\."
            ],
            OutputCategory.ERROR_MESSAGE: [
                r"Error: ",
                r"Exception: ",
                r"Failed to ",
                r"❌ ERROR:",
                r"^Traceback \(most recent call last\):"
            ],
            OutputCategory.CODE_SNIPPET: [
                r"```[a-z]*\n",
                r"^[a-zA-Z_]+\(\) {",
                r"^class [A-Za-z_]+ {",
                r"^class [A-Za-z_]+\([A-Za-z_]+\):",
                r"^def [a-zA-Z_]+\("
            ]
        }
        
        # Enhanced detection patterns for interactive UI elements
        self.enhanced_patterns = {
            "interactive_diff": r"^DIFF: ([a-zA-Z0-9_\-\.]+)(\s+\(NEW\))?\s*\n",
            "interactive_approval": r"^APPROVAL REQUIRED: (.+?)\n\[(.+?)\]",
            "progress_indicator": r"^PROGRESS: ([a-zA-Z0-9_\-\. ]+?): (\d+)%",
            "task_breakdown": r"^TASK BREAKDOWN:\s*\n(.*?)(?:\n\n|\Z)",
            "file_tree": r"^FILE STRUCTURE:\s*\n(.*?)(?:\n\n|\Z)"
        }
        
    def categorize_output(self, text: str) -> Tuple[OutputCategory, Dict[str, Any]]:
        """Categorize terminal output and extract structured data.
        
        Args:
            text: The terminal output text to categorize
            
        Returns:
            Tuple of (category, extracted_data)
        """
        # First check for enhanced patterns that map to interactive UI elements
        for pattern_name, pattern in self.enhanced_patterns.items():
            match = re.search(pattern, text, re.MULTILINE | re.DOTALL)
            if match:
                extracted_data = self._extract_enhanced_data(pattern_name, text, match)
                # Return with original category but with enhanced structured data
                if pattern_name == "interactive_diff":
                    return OutputCategory.DIFF_CONTENT, extracted_data
                elif pattern_name == "interactive_approval":
                    return OutputCategory.APPROVAL_PROMPT, extracted_data
                elif pattern_name == "progress_indicator":
                    return OutputCategory.PROGRESS_INFO, extracted_data
                        
        # Then check for regular categories
        for category, patterns in self.patterns.items():
            for pattern in patterns:
                if re.search(pattern, text, re.MULTILINE):
                    return category, self._extract_data(category, text)
                    
        return OutputCategory.GENERAL, {"text": text}
    
    def _extract_enhanced_data(self, pattern_name: str, text: str, match: Match) -> Dict[str, Any]:
        """Extract structured data from enhanced patterns.
        
        Args:
            pattern_name: The pattern name that matched
            text: The full text that was matched
            match: The regex match object
            
        Returns:
            Dictionary of extracted data
        """
        if pattern_name == "interactive_diff":
            filename = match.group(1)
            is_new = bool(match.group(2))
            
            # Try to extract the before/after content from a diff block
            diff_parts = text.split("===== BEFORE =====")
            if len(diff_parts) > 1:
                before_after = diff_parts[1].split("===== AFTER =====")
                if len(before_after) > 1:
                    before = before_after[0].strip()
                    after = before_after[1].strip()
                    
                    return {
                        "text": text,
                        "interactive": True,
                        "file": filename,
                        "is_new": is_new,
                        "before": before if not is_new else "",
                        "after": after
                    }
            
            # Fallback to regular diff extraction if enhanced format not found
            return {
                "text": text,
                "files": self._extract_diff_files(text)
            }
            
        elif pattern_name == "interactive_approval":
            title = match.group(1)
            options_str = match.group(2)
            options = [opt.strip() for opt in options_str.split('/')]
            
            # Extract description - all content between title and options
            description_match = re.search(r"^APPROVAL REQUIRED: .+?\n(.*?)\n\[", 
                                          text, re.MULTILINE | re.DOTALL)
            description = description_match.group(1).strip() if description_match else ""
            
            return {
                "text": text,
                "interactive": True,
                "title": title,
                "description": description,
                "options": options,
                "prompt_type": "approval"
            }
            
        elif pattern_name == "progress_indicator":
            title = match.group(1)
            percentage = int(match.group(2))
            
            # Try to extract steps if present
            steps = []
            steps_match = re.search(r"Steps:\s*\n(.*?)(?:\n\n|\Z)", 
                                    text, re.MULTILINE | re.DOTALL)
            if steps_match:
                steps_text = steps_match.group(1)
                step_lines = steps_text.strip().split("\n")
                for line in step_lines:
                    step_match = re.match(r"\[(.*?)\] (.*)", line)
                    if step_match:
                        status = step_match.group(1)  # e.g., "DONE", "IN_PROGRESS", "PENDING"
                        name = step_match.group(2)
                        steps.append({
                            "name": name,
                            "status": status.lower()
                        })
            
            return {
                "text": text,
                "interactive": True,
                "title": title,
                "percentage": percentage,
                "steps": steps
            }
            
        elif pattern_name == "task_breakdown":
            breakdown = match.group(1)
            tasks = []
            
            for line in breakdown.strip().split("\n"):
                task_match = re.match(r"(\d+)\. \[(.*?)\] (.*)", line)
                if task_match:
                    task_id = int(task_match.group(1))
                    status = task_match.group(2)  # e.g., "DONE", "TODO"
                    description = task_match.group(3)
                    
                    tasks.append({
                        "id": task_id,
                        "status": status.lower(),
                        "description": description
                    })
            
            return {
                "text": text,
                "interactive": True,
                "tasks": tasks
            }
            
        elif pattern_name == "file_tree":
            tree_text = match.group(1)
            return {
                "text": text,
                "interactive": True,
                "tree": self._parse_file_tree(tree_text)
            }
            
        # Default fallback
        return {"text": text}
    
    def _parse_file_tree(self, tree_text: str) -> Dict[str, Any]:
        """Parse a textual file tree into a nested structure.
        
        Args:
            tree_text: The text representation of the file tree
            
        Returns:
            Dictionary representing the file tree
        """
        root = {"name": "root", "type": "directory", "children": []}
        path_stack = [root]
        current_indent = 0
        indent_size = None
        
        for line in tree_text.strip().split("\n"):
            if not line.strip():
                continue
                
            # Calculate indent level
            indent = len(line) - len(line.lstrip())
            if indent_size is None and indent > 0:
                indent_size = indent
                
            if indent_size:
                current_level = indent // indent_size
            else:
                current_level = 0
                
            # Adjust path stack based on indent level
            while len(path_stack) > current_level + 1:
                path_stack.pop()
                
            # Create node
            clean_name = line.strip().rstrip("/")
            is_dir = line.strip().endswith("/")
            node = {
                "name": clean_name,
                "type": "directory" if is_dir else "file"
            }
            
            if is_dir:
                node["children"] = []
                
            # Add to parent
            parent = path_stack[-1]
            if "children" in parent:
                parent["children"].append(node)
                
            # If directory, add to stack
            if is_dir:
                path_stack.append(node)
                
        return root
        
    def _extract_data(self, category: OutputCategory, text: str) -> Dict[str, Any]:
        """Extract structured data based on the category.
        
        Args:
            category: The output category
            text: The terminal output text
            
        Returns:
            Dictionary of extracted data
        """
        if category == OutputCategory.APPROVAL_PROMPT:
            return {
                "text": text,
                "options": self._extract_options(text),
                "prompt_type": "approval"
            }
        elif category == OutputCategory.DIFF_CONTENT:
            return {
                "text": text,
                "files": self._extract_diff_files(text)
            }
        elif category == OutputCategory.DEBATE_SECTION:
            return {
                "text": text
            }
        elif category == OutputCategory.PROGRESS_INFO:
            return {
                "text": text,
                "percentage": self._extract_percentage(text)
            }
        elif category == OutputCategory.CODE_SNIPPET:
            return {
                "text": text,
                "language": self._extract_language(text)
            }
            
        return {"text": text}
    
    def _extract_options(self, text: str) -> List[str]:
        """Extract options from an approval prompt.
        
        Args:
            text: The approval prompt text
            
        Returns:
            List of option strings
        """
        if "yes/no/edit" in text.lower() or "y/n/edit" in text.lower() or "y/n/e" in text.lower():
            return ["yes", "no", "edit"]
        elif "yes/no" in text.lower() or "y/n" in text.lower():
            return ["yes", "no"]
        
        # Try to extract options from format like [option1/option2/option3]
        brackets_match = re.search(r'\[(.*?)\]', text)
        if brackets_match:
            options_str = brackets_match.group(1)
            return [opt.strip() for opt in options_str.split('/')]
            
        return ["yes", "no"]  # Default fallback
    
    def _extract_diff_files(self, text: str) -> List[Dict[str, Any]]:
        """Extract file diffs from diff content.
        
        Args:
            text: The diff content
            
        Returns:
            List of dictionaries with file info and diff content
        """
        files = []
        current_file = None
        lines = text.split('\n')
        
        # First look for the enhanced format (with before/after sections)
        file_match = re.search(r"^DIFF: ([a-zA-Z0-9_\-\.]+)(\s+\(NEW\))?\s*\n", text, re.MULTILINE)
        if file_match:
            filename = file_match.group(1)
            is_new = bool(file_match.group(2))
            
            # Try to extract the before/after content
            parts = text.split("===== BEFORE =====")
            if len(parts) > 1:
                before_after = parts[1].split("===== AFTER =====")
                if len(before_after) > 1:
                    before = before_after[0].strip()
                    after = before_after[1].strip()
                    
                    files.append({
                        "filename": filename,
                        "content": text,  # Include the whole formatted diff
                        "is_new": is_new,
                        "before": before if not is_new else "",
                        "after": after,
                        "enhanced": True
                    })
                    
                    return files
        
        # Fall back to the traditional git diff format
        for i, line in enumerate(lines):
            git_diff_match = re.match(r'diff --git a/(.*) b/(.*)', line)
            if git_diff_match:
                if current_file is not None:
                    files.append(current_file)
                    
                current_file = {
                    "filename": git_diff_match.group(1),
                    "content": line + "\n",
                    "is_new": False,
                    "enhanced": False
                }
                continue
                
            # Also check the File: format
            file_header_match = re.match(r'File: (.+)', line)
            if file_header_match:
                if current_file is not None:
                    files.append(current_file)
                    
                current_file = {
                    "filename": file_header_match.group(1),
                    "content": line + "\n",
                    "is_new": False,
                    "enhanced": False
                }
                
                # Check if it's a new file
                if i+1 < len(lines) and "(NEW FILE)" in lines[i+1]:
                    current_file["is_new"] = True
                continue
                
            # If we have a current file, append the line to its content
            if current_file is not None:
                current_file["content"] += line + "\n"
                
                # Check for "new file mode" line which indicates a new file in git diff
                if "new file mode" in line:
                    current_file["is_new"] = True
        
        # Add the last file if there is one
        if current_file is not None:
            files.append(current_file)
            
        return files
    
    def _extract_percentage(self, text: str) -> int:
        """Extract percentage from progress info.
        
        Args:
            text: The progress info text
            
        Returns:
            Percentage as integer
        """
        # Check for the enhanced format first
        enhanced_match = re.search(r"^PROGRESS: .+?: (\d+)%", text, re.MULTILINE)
        if enhanced_match:
            return int(enhanced_match.group(1))
            
        # Fall back to regular percentage extraction
        percentage_match = re.search(r'(\d+)%', text)
        if percentage_match:
            return int(percentage_match.group(1))
            
        # Try to extract progress from progress bar
        progress_bar_match = re.search(r'\|(█+)(░*)\| (\d+)%', text)
        if progress_bar_match:
            return int(progress_bar_match.group(3))
            
        return 0
    
    def _extract_language(self, text: str) -> str:
        """Extract programming language from code snippet.
        
        Args:
            text: The code snippet
            
        Returns:
            Identified language or empty string
        """
        language_match = re.match(r'```([a-z]*)\n', text)
        if language_match:
            lang = language_match.group(1)
            return lang if lang else "text"  # Default to "text" for empty language
            
        # Try to guess language from content
        if "function " in text or "const " in text or "let " in text or "=> {" in text:
            return "javascript"
        elif "def " in text or "class " in text and ":" in text:
            return "python"
        elif "<html" in text or "<div" in text:
            return "html"
        elif "interface " in text or "export class" in text or ": string" in text:
            return "typescript"
            
        return "text"  # Default
