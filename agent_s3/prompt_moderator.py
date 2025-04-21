"""Prompt Moderator module for handling user interactions."""

import os
import sys
import re
from typing import Dict, Optional, Union, List, Tuple, Any, Set, Literal

class PromptModerator:
    """Handles user interactions, presents plans, and manages approvals."""

    def __init__(self, coordinator=None):
        """Initialize the moderator.

        Args:
            coordinator: Optional coordinator instance that provides access to tools
        """
        self.coordinator = coordinator
        self.scratchpad = coordinator.scratchpad if coordinator else None

    def notify_user(self, message: str, level: str = "info") -> None:
        """Notify the user with a formatted message.
        
        Args:
            message: The message to display
            level: The level of the message (info, warning, error, success)
        """
        prefix_map = {
            "info": "ℹ️ INFO: ",
            "warning": "⚠️ WARNING: ",
            "error": "❌ ERROR: ",
            "success": "✅ SUCCESS: "
        }
        prefix = prefix_map.get(level.lower(), prefix_map["info"])
        print(f"\n{prefix}{message}")
        
        if self.scratchpad:
            self.scratchpad.log("Moderator", f"[{level.upper()}] {message}")

    def present_plan(self, plan: str, summary: str) -> Tuple[bool, str]:
        """Present the execution plan to the user for approval.
        
        Args:
            plan: The detailed execution plan
            summary: A summary of the plan
            
        Returns:
            Tuple of (approved, final_prompt)
        """
        if self.scratchpad:
            self.scratchpad.log("Moderator", "Presenting plan to user for approval")
        
        print("\n" + "="*80)
        print(f"EXECUTION PLAN SUMMARY:")
        print("-"*80)
        print(summary)
        print("\n" + "="*80)
        print("DETAILED PLAN:")
        print("-"*80)
        print(plan)
        print("="*80)
        
        while True:
            user_input = input("\nDo you approve this plan? (y/n/edit): ").strip().lower()
            
            if user_input in ["y", "yes"]:
                if self.scratchpad:
                    self.scratchpad.log("Moderator", "User approved the plan")
                return True, plan
            elif user_input in ["n", "no"]:
                if self.scratchpad:
                    self.scratchpad.log("Moderator", "User rejected the plan")
                return False, plan
            elif user_input in ["e", "edit"]:
                print("\nEnter your modified plan (type 'DONE' on a new line when finished):")
                lines = []
                while True:
                    line = input()
                    if line.strip() == "DONE":
                        break
                    lines.append(line)
                    
                modified_plan = "\n".join(lines)
                if self.scratchpad:
                    self.scratchpad.log("Moderator", "User modified the plan")
                    
                return True, modified_plan
            else:
                print("Invalid input. Please enter 'y', 'n', or 'edit'.")

    def present_patch_with_diff(self, changes: Dict[str, str], iteration: int = 1) -> bool:
        """Present the generated patch with diff for user approval.
        
        Args:
            changes: Dictionary mapping file paths to their new contents
            iteration: The current iteration number
            
        Returns:
            True if the user approves the patch, False otherwise
        """
        if self.scratchpad:
            self.scratchpad.log("Moderator", f"Presenting patch for iteration {iteration}")
            
        if not changes:
            self.notify_user("No changes were generated.", level="warning")
            return False
            
        # Compute diffs for each file
        diffs = self._compute_diffs(changes)
        
        # Display the patch
        print(f"\n{'='*80}")
        print(f"CODE CHANGES (ITERATION {iteration}):")
        print(f"{'-'*80}")
        
        for file_path, diff in diffs.items():
            print(f"\nFile: {file_path}")
            print(f"{'-'*40}")
            print(diff)
            
        print(f"{'='*80}")
        
        # Ask for approval
        while True:
            user_input = input("\nDo you approve these changes? (y/n): ").strip().lower()
            
            if user_input in ["y", "yes"]:
                if self.scratchpad:
                    self.scratchpad.log("Moderator", f"User approved changes for iteration {iteration}")
                return True
            elif user_input in ["n", "no"]:
                if self.scratchpad:
                    self.scratchpad.log("Moderator", f"User rejected changes for iteration {iteration}")
                return False
            else:
                print("Invalid input. Please enter 'y' or 'n'.")

    def _compute_diffs(self, changes: Dict[str, str]) -> Dict[str, str]:
        """Compute diffs between current files and the proposed changes.
        
        Args:
            changes: Dictionary mapping file paths to their new contents
            
        Returns:
            Dictionary mapping file paths to their computed diffs
        """
        diffs = {}
        
        for file_path, new_content in changes.items():
            full_path = os.path.join(self.coordinator.config.config.get('project_root', os.getcwd()), file_path)
            is_new_file = not os.path.exists(full_path)
            
            if is_new_file:
                # For new files, just show the whole content with "+" prefixes
                diff_lines = [f"+{line}" for line in new_content.split("\n")]
                diffs[file_path] = f"(NEW FILE)\n{'-'*10}\n" + "\n".join(diff_lines)
            else:
                # For existing files, compute a proper diff
                try:
                    with open(full_path, 'r') as f:
                        old_content = f.read()
                    
                    # Use the proper diff tool if available
                    if hasattr(self.coordinator, 'code_analysis_tool') and hasattr(self.coordinator.code_analysis_tool, 'compute_diff'):
                        diff = self.coordinator.code_analysis_tool.compute_diff(old_content, new_content)
                        diffs[file_path] = diff
                    else:
                        # Simplified diff: uses a basic line-by-line comparison
                        old_lines = old_content.split("\n")
                        new_lines = new_content.split("\n")
                        
                        # Simple diff implementation
                        diff_lines = []
                        for i, (old_line, new_line) in enumerate(zip(old_lines, new_lines)):
                            if old_line != new_line:
                                diff_lines.append(f"-{old_line}")
                                diff_lines.append(f"+{new_line}")
                            else:
                                diff_lines.append(f" {old_line}")
                                
                        # Handle different line counts
                        if len(old_lines) > len(new_lines):
                            for i in range(len(new_lines), len(old_lines)):
                                diff_lines.append(f"-{old_lines[i]}")
                        elif len(new_lines) > len(old_lines):
                            for i in range(len(old_lines), len(new_lines)):
                                diff_lines.append(f"+{new_lines[i]}")
                                
                        diffs[file_path] = "\n".join(diff_lines)
                        
                except Exception as e:
                    if self.scratchpad:
                        self.scratchpad.log("Moderator", f"Error computing diff for {file_path}: {e}")
                    diffs[file_path] = f"(ERROR COMPUTING DIFF: {e})\n{new_content}"
                    
        return diffs

    def ask_binary_question(self, question: str) -> bool:
        """Ask the user a binary yes/no question.

        Args:
            question: The question to ask the user

        Returns:
            True if the user answers 'yes', False otherwise
        """
        while True:
            # Use 'y'/'n' for brevity as requested in original function
            user_input = input(f"{question} (y/n): ").strip().lower()

            if user_input in ["y", "yes"]:
                return True
            elif user_input in ["n", "no"]:
                return False
            else:
                print("Invalid input. Please enter 'y' or 'n'.")

    def ask_ternary_question(self, question: str) -> Literal["yes", "no", "modify"]:
        """Ask the user a question with three possible answers: yes, no, or modify.

        Args:
            question: The question to ask the user.

        Returns:
            'yes', 'no', or 'modify' based on user input.
        """
        while True:
            user_input = input(f"{question} (yes/no/modify): ").strip().lower()

            if user_input in ["y", "yes"]:
                return "yes"
            elif user_input in ["n", "no"]:
                return "no"
            elif user_input in ["m", "modify"]:
                return "modify"
            else:
                print("Invalid input. Please enter 'yes', 'no', or 'modify'.")

    def ask_for_input(self, prompt: str) -> str:
        """Ask the user for free-form input.
        
        Args:
            prompt: The prompt to display to the user
            
        Returns:
            The user's input
        """
        return input(f"{prompt}: ").strip()

    def ask_for_modification(self, prompt: str) -> str:
        """Ask the user for modifications to the plan."""
        print(f"\n{prompt}")
        print("(Type 'DONE' on a new line when finished)")
        lines = []
        while True:
            try:
                line = input()
                if line.strip().upper() == "DONE":
                    break
                lines.append(line)
            except EOFError: # Handle Ctrl+D or similar EOF signals
                break
        return "\n".join(lines)

    def show_code_snippet(self, snippet: str, title: str = "Code Snippet") -> None:
        """Display a code snippet with proper formatting.
        
        Args:
            snippet: The code snippet to display
            title: Optional title for the snippet
        """
        print(f"\n{title}:")
        print("-" * len(title))
        print(snippet)
        print()

    def present_choices(self, prompt: str, choices: List[str]) -> int:
        """Present a list of choices to the user and return their selection.
        
        Args:
            prompt: The prompt to display to the user
            choices: List of choices to present
            
        Returns:
            The index of the selected choice
        """
        print(f"\n{prompt}")
        for i, choice in enumerate(choices):
            print(f"{i+1}. {choice}")
            
        while True:
            try:
                selection = int(input("\nEnter your choice (number): "))
                if 1 <= selection <= len(choices):
                    return selection - 1
                else:
                    print(f"Please enter a number between 1 and {len(choices)}.")
            except ValueError:
                print("Please enter a valid number.")

    def show_progress(self, message: str, progress: float) -> None:
        """Show a progress indicator.
        
        Args:
            message: The message to display
            progress: Progress value between 0.0 and 1.0
        """
        bar_length = 40
        filled_length = int(bar_length * progress)
        bar = '█' * filled_length + '░' * (bar_length - filled_length)
        percent = int(progress * 100)
        print(f"\r{message} |{bar}| {percent}%", end='')
        sys.stdout.flush()
        
        if progress >= 1.0:
            print()  # Newline after completion
            
        if self.scratchpad:
            self.scratchpad.log("Moderator", f"{message}: {percent}%")

    def format_error(self, error_message: str, stack_trace: Optional[str] = None) -> str:
        """Format an error message for display.
        
        Args:
            error_message: The error message to display
            stack_trace: Optional stack trace
            
        Returns:
            Formatted error message
        """
        formatted = f"\n❌ ERROR: {error_message}"
        
        if stack_trace:
            formatted += f"\n\nStack Trace:\n{stack_trace}"
            
        return formatted

    # Fix missing placeholder f-string issue
    def display_validation_error(self, message: str, file_path: Optional[str] = None) -> None:
        """Display a validation error message.
        
        Args:
            message: The error message to display
            file_path: Optional path to the file with the error
        """
        error_prefix = "Validation Error"
        if file_path:
            error_prefix = f"Validation Error in {file_path}"
            
        print(f"\n❌ {error_prefix}: {message}")
        
        if self.scratchpad:
            self.scratchpad.log("Moderator", f"[VALIDATION] {error_prefix}: {message}")

    # Fix missing placeholder f-string issue
    def prompt_file_selection(self, file_list: List[str], prompt_text: str = "Select a file") -> Optional[str]:
        """Prompt the user to select a file from a list.
        
        Args:
            file_list: List of files to choose from
            prompt_text: Text to display as the prompt
            
        Returns:
            The selected file path, or None if selection was canceled
        """
        if not file_list:
            print("No files available for selection.")
            return None
            
        print(f"\n{prompt_text}:")
        for i, file_path in enumerate(file_list):
            print(f"{i+1}. {file_path}")
        print(f"0. Cancel")
        
        while True:
            try:
                selection = int(input("\nEnter your choice (number): "))
                if selection == 0:
                    return None
                elif 1 <= selection <= len(file_list):
                    selected_file = file_list[selection-1]
                    print(f"Selected: {selected_file}")
                    return selected_file
                else:
                    print(f"Please enter a number between 0 and {len(file_list)}.")
            except ValueError:
                print("Please enter a valid number.")

    def request_confirmation(self, message: str) -> bool:
        """Request confirmation from the user with a custom message.
        
        Args:
            message: The message to display
            
        Returns:
            True if confirmed, False otherwise
        """
        confirmation = input(f"{message} (y/n): ").strip().lower()
        return confirmation in ["y", "yes"]

    def display_execution_result(self, success: bool, message: str) -> None:
        """Display the result of an execution.
        
        Args:
            success: Whether the execution was successful
            message: The message to display
        """
        if success:
            print(f"\n✅ {message}")
        else:
            print(f"\n❌ {message}")
            
        if self.scratchpad:
            status = "SUCCESS" if success else "FAILURE"
            self.scratchpad.log("Moderator", f"[{status}] {message}")

    # Fix missing placeholder f-string issue
    def show_file_content(self, file_path: str, content: str, highlight_lines: Optional[Set[int]] = None) -> None:
        """Show file content with optional line highlighting.
        
        Args:
            file_path: Path to the file
            content: Content of the file
            highlight_lines: Optional set of line numbers to highlight
        """
        print(f"\nFile: {file_path}")
        print("-" * (len(file_path) + 6))
        
        if highlight_lines is None:
            highlight_lines = set()
            
        for i, line in enumerate(content.split("\n"), 1):
            if i in highlight_lines:
                # Highlight the line
                print(f"{i:4d} | \033[93m{line}\033[0m")
            else:
                print(f"{i:4d} | {line}")
        print()

    def display_discussion_and_plan(self, discussion: str, plan: str) -> None:
        """Display the discussion transcript and the implementation plan to the user."""
        if self.scratchpad:
            self.scratchpad.log("Moderator", "Displaying discussion and plan")

        print("\n" + "="*80)
        print("PERSONA DEBATE DISCUSSION:")
        print("-"*80)
        print(discussion)

        print("\n" + "="*80)
        print("IMPLEMENTATION PLAN:")
        print("-"*80)
        print(plan)
        print("="*80)
