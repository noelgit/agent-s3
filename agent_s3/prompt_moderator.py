"""Prompt Moderator module for handling user interactions."""

import os
import sys
import tempfile
import subprocess
import shlex
import json
from typing import Dict, Optional, List, Tuple, Any, Set, Literal

from .communication.vscode_bridge import VSCodeBridge

class PromptModerator:
    """Handles user interactions, presents plans, and manages approvals.
    
    Provides methods for both terminal-based and VS Code Chat UI-based interaction.
    """

    def __init__(self, coordinator=None):
        """Initialize the moderator.

        Args:
            coordinator: Optional coordinator instance that provides access to tools
        """
        self.coordinator = coordinator
        self.scratchpad = coordinator.scratchpad if coordinator else None
        self.ui_mode = "terminal"  # Default to terminal UI mode
        self.vscode_bridge = None  # Will be set by set_vscode_bridge
        self.max_plan_iterations = 5  # Maximum number of plan modification iterations
        
    def set_vscode_bridge(self, vscode_bridge: VSCodeBridge):
        """Set the VS Code bridge integration for chat UI communication.
        
        Args:
            vscode_bridge: VS Code bridge instance
        """
        self.ui_mode = "vscode"
        self.vscode_bridge = vscode_bridge
        if self.scratchpad:
            self.scratchpad.log("Moderator", "VS Code Chat UI integration enabled")

    def is_vscode_mode(self):
        """Check if VS Code integration is active and preferred."""
        return (
            self.vscode_bridge and 
            self.vscode_bridge.connection_active and 
            self.vscode_bridge.config.prefer_ui
        )
        
    def _get_preferred_editor(self) -> str:
        """Determine the user's preferred text editor.
        
        Returns:
            Command to open the preferred editor
        """
        if hasattr(self, '_preferred_editor') and self._preferred_editor:
            return self._preferred_editor
            
        # Try to determine preferred editor
        editor = os.environ.get('EDITOR')
        if not editor:
            if sys.platform.startswith('win'):
                editor = 'notepad'
            elif sys.platform == 'darwin':
                editor = 'open -a TextEdit'
            else:
                # Try common Linux editors
                for ed in ['nano', 'vim', 'vi', 'emacs']:
                    try:
                        subprocess.run(['which', ed], check=True, stdout=subprocess.PIPE)
                        editor = ed
                        break
                    except subprocess.CalledProcessError:
                        continue
                
                if not editor:
                    editor = 'nano'  # Default to nano if nothing else is found
        
        self._preferred_editor = editor
        return editor
        
    def _open_in_editor(self, file_path: str) -> None:
        """Open a file in the user's preferred editor.
        
        Args:
            file_path: Path to the file to edit
        """
        editor = self._get_preferred_editor()
        
        # Open the file
        try:
            if ' ' in editor:
                # Split editor command safely to avoid shell=True
                command = shlex.split(editor) + [file_path]
                subprocess.run(command, check=True)
            else:
                subprocess.run([editor, file_path], check=True)
        except subprocess.CalledProcessError as e:
            print(f"Error opening editor: {e}")
            # Fallback to basic terminal input if editor fails
            print("Editor failed. Please enter your content directly (type 'EOF' on a new line when done):")
            
            lines = []
            with open(file_path, 'r') as f:
                lines = f.readlines()
            
            print("".join(lines))
            print("\nEnter new content:")
            
            new_lines = []
            while True:
                line = input()
                if line.strip() == 'EOF':
                    break
                new_lines.append(line + '\n')
            
            with open(file_path, 'w') as f:
                f.writelines(new_lines)
                
    def confirm_test_code(self, test_data: Dict[str, Any]) -> Dict[str, Any]:
        """Present test code to user for review and modifications.
        
        Args:
            test_data: Dictionary containing test information and code
            
        Returns:
            Updated test data after user review/modifications
        """
        print("\n=== TEST REVIEW REQUIRED ===")
        print("Please review the generated tests to ensure they correctly validate the desired behavior.")
        print("This is a critical step for ensuring correct implementation.\n")
        
        # Create a temporary file with the test code for editing
        tests_to_edit = []
        
        # Organize tests for display
        for i, test_item in enumerate(test_data.get("tests", [])):
            if isinstance(test_item, dict):
                test_desc = test_item.get("description", f"Test {i+1}")
                test_code = test_item.get("test_code", "")
                test_file = test_item.get("file", f"test_{i+1}.py")
                expected = test_item.get("expected_outcome", "")
                
                print(f"\nTest {i+1}: {test_desc}")
                print(f"File: {test_file}")
                print(f"Expected Outcome: {expected}")
                print("Code:")
                print("```")
                print(test_code)
                print("```")
                
                tests_to_edit.append((i, test_item))
        
        if not tests_to_edit:
            print("No tests found to review!")
            return test_data
        
        # Ask if user wants to modify tests
        modify = self.ask_ternary_question("Do you want to proceed with these tests, modify them, or cancel?")
        
        if modify == "no":
            print("Test review cancelled.")
            return None  # Signal cancellation
        
        if modify == "yes":
            print("Tests approved without modification.")
            return test_data
        
        # User wants to modify tests
        updated_test_data = test_data.copy()
        updated_tests = updated_test_data.get("tests", []).copy()
        
        # Handle each test one by one
        for idx, test_item in tests_to_edit:
            original_test = test_item.copy()
            test_desc = original_test.get("description", f"Test {idx+1}")
            
            print(f"\nEditing Test {idx+1}: {test_desc}")
            action = input("Action (edit/skip/delete/add): ").strip().lower()
            
            if action == "edit":
                with tempfile.NamedTemporaryFile(suffix=".py", mode="w+", delete=False) as temp:
                    temp.write(original_test.get("test_code", ""))
                    temp_path = temp.name
                
                # Open in editor
                self._open_in_editor(temp_path)
                
                # Read back the edited content
                with open(temp_path, "r") as temp:
                    edited_code = temp.read()
                
                # Update the test
                updated_test = original_test.copy()
                updated_test["test_code"] = edited_code
                
                # Ask for description update
                new_desc = input(f"New description (leave empty to keep '{test_desc}'): ").strip()
                if new_desc:
                    updated_test["description"] = new_desc
                
                # Replace the test in the list
                updated_tests[idx] = updated_test
                
                # Clean up
                os.unlink(temp_path)
                
            elif action == "delete":
                confirm = input(f"Confirm deletion of Test {idx+1} (yes/no): ").strip().lower()
                if confirm in ["yes", "y"]:
                    # Mark for removal
                    updated_tests[idx] = None
                    
            elif action == "add":
                print("Please enter new test details:")
                new_test = {}
                new_test["description"] = input("Description: ").strip()
                new_test["file"] = input("File path: ").strip() or f"test_new_{len(updated_tests)}.py"
                new_test["expected_outcome"] = input("Expected outcome: ").strip()
                
                with tempfile.NamedTemporaryFile(suffix=".py", mode="w+", delete=False) as temp:
                    temp.write("# Enter new test code here\n")
                    temp_path = temp.name
                
                # Open in editor
                self._open_in_editor(temp_path)
                
                # Read back the edited content
                with open(temp_path, "r") as temp:
                    new_test["test_code"] = temp.read()
                
                # Add to the list
                updated_tests.append(new_test)
                
                # Clean up
                os.unlink(temp_path)
        
        # Remove deleted tests
        updated_tests = [test for test in updated_tests if test is not None]
        updated_test_data["tests"] = updated_tests
        
        # Ask if user wants to add more tests
        while self.ask_yes_no_question("Do you want to add another test?"):
            new_test = {}
            new_test["description"] = input("Description: ").strip()
            new_test["file"] = input("File path: ").strip() or f"test_new_{len(updated_tests)}.py"
            new_test["expected_outcome"] = input("Expected outcome: ").strip()
            
            with tempfile.NamedTemporaryFile(suffix=".py", mode="w+", delete=False) as temp:
                temp.write("# Enter new test code here\n")
                temp_path = temp.name
            
            # Open in editor
            self._open_in_editor(temp_path)
            
            # Read back the edited content
            with open(temp_path, "r") as temp:
                new_test["test_code"] = temp.read()
            
            # Add to the list
            updated_tests.append(new_test)
            
            # Clean up
            os.unlink(temp_path)
        
        # Final confirmation
        print("\n=== UPDATED TESTS ===")
        for i, test_item in enumerate(updated_tests):
            print(f"\nTest {i+1}: {test_item.get('description', '')}")
            print(f"File: {test_item.get('file', '')}")
            
        confirm = self.ask_yes_no_question("Confirm these updated tests?")
        if confirm:
            print("Tests confirmed. Proceeding with code generation.")
            updated_test_data["tests"] = updated_tests
            return updated_test_data
        else:
            print("Test updates cancelled.")
            return None  # Signal cancellation
            
    def ask_structured_modification(self, feature_groups: List[Dict[str, Any]]) -> Tuple[Dict[str, Any], str]:
        """Ask the user for structured modifications to a feature group plan.
        
        Args:
            feature_groups: List of feature group dictionaries
            
        Returns:
            Tuple of (selected feature group dict, modification text)
        """
        print("\n=== MODIFICATION REQUEST ===")
        print("Please specify which feature group and component you want to modify:")
        
        if not feature_groups:
            print("No feature groups available to modify!")
            return None, ""
        
        # Display available feature groups
        for i, group in enumerate(feature_groups):
            print(f"{i+1}. {group.get('group_name', f'Group {i+1}')}")
        
        # Get user selection
        group_idx = -1
        while group_idx < 0 or group_idx >= len(feature_groups):
            try:
                group_idx = int(input("Select feature group number: ").strip()) - 1
                if group_idx < 0 or group_idx >= len(feature_groups):
                    print(f"Please enter a number between 1 and {len(feature_groups)}")
            except ValueError:
                print("Please enter a valid number")
        
        selected_group = feature_groups[group_idx]
        print(f"\nSelected: {selected_group.get('group_name', f'Group {group_idx+1}')}")
        
        # Ask what component to modify
        components = [
            "architecture_review", 
            "implementation_plan",
            "tests", 
            "general_approach"
        ]
        
        print("\nWhich component do you want to modify?")
        for i, comp in enumerate(components):
            print(f"{i+1}. {comp}")
        
        # Get user selection
        comp_idx = -1
        while comp_idx < 0 or comp_idx >= len(components):
            try:
                comp_idx = int(input("Select component number: ").strip()) - 1
                if comp_idx < 0 or comp_idx >= len(components):
                    print(f"Please enter a number between 1 and {len(components)}")
            except ValueError:
                print("Please enter a valid number")
        
        selected_component = components[comp_idx]
        print(f"\nSelected: {selected_component}")
        
        # Get modification instructions
        print("\nPlease enter your modification instructions:")
        print(f"For '{selected_component}' in '{selected_group.get('group_name', f'Group {group_idx+1}')}'")
        print("Be specific about what should be added, removed, or changed.")
        print("Type 'done' on a new line when finished.")
        
        lines = []
        while True:
            line = input()
            if line.strip() == 'done':
                break
            lines.append(line)
        
        modification_text = f"Component: {selected_component}\n"
        modification_text += "\n".join(lines)
        
        return selected_group, modification_text
        
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
        
        # Log the message to scratchpad regardless of UI mode
        if self.scratchpad:
            self.scratchpad.log("Moderator", f"[{level.upper()}] {message}")
        
        # Display via appropriate UI
        formatted_message = f"{prefix}{message}"
        
        if self.is_vscode_mode():
            # Send to VS Code UI
            self.vscode_bridge.send_terminal_output(formatted_message)
        else:
            # Default terminal output
            print(f"\n{formatted_message}")
        
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
        
        # Format plan for display
        plan_display = "\n" + "="*80 + "\n"
        plan_display += "EXECUTION PLAN SUMMARY:\n"
        plan_display += "-"*80 + "\n"
        plan_display += summary + "\n\n"
        plan_display += "="*80 + "\n"
        plan_display += "DETAILED PLAN:\n"
        plan_display += "-"*80 + "\n"
        plan_display += plan + "\n"
        plan_display += "="*80
        
        # Display via appropriate UI
        if self.is_vscode_mode():
            # Send to VS Code UI
            self.vscode_bridge.send_terminal_output(plan_display)
            

            
            # Create enhanced interactive approval options
            approval_options = [
                {
                    "id": "yes", 
                    "label": "Approve Plan", 
                    "shortcut": "Y",
                    "description": "Proceed with the plan as written"
                },
                {
                    "id": "no", 
                    "label": "Reject Plan", 
                    "shortcut": "N",
                    "description": "Reject the plan and start over"
                },
                {
                    "id": "edit", 
                    "label": "Edit Plan", 
                    "shortcut": "E",
                    "description": "Modify aspects of the plan before proceeding"
                }
            ]
            
            # Send enhanced interactive approval request
            wait_for_response = self.vscode_bridge.send_interactive_approval(
                title="Plan Approval Required",
                description=f"Summary: {summary}\n\nPlease review the proposed plan and choose an option.",
                options=approval_options
            )
            
            if wait_for_response:
                response = wait_for_response()
                if response:
                    option_id = response.get("option_id", "").lower()
                    
                    if option_id == "yes":
                        if self.scratchpad:
                            self.scratchpad.log("Moderator", "User approved the plan via VS Code UI")
                        return True, plan
                    elif option_id == "no":
                        if self.scratchpad:
                            self.scratchpad.log("Moderator", "User rejected the plan via VS Code UI")
                        return False, plan
                    elif option_id == "edit":
                        modifications = response.get("modifications", "")
                        if modifications:
                            modified_plan = modifications
                        else:
                            # If no modifications provided in the response, ask separately
                            modified_plan = self.ask_for_modification("Enter your modifications to the plan:")
                            
                        if self.scratchpad:
                            self.scratchpad.log("Moderator", "User modified the plan via VS Code UI")
                        return True, modified_plan
                
            # Fallback to terminal if VS Code response fails or times out
            if (self.vscode_bridge.config.fallback_to_terminal):
                self.notify_user("No response from VS Code UI, falling back to terminal", level="warning")
            else:
                if self.scratchpad:
                    self.scratchpad.log("Moderator", "No response from VS Code UI, defaulting to reject")
                return False, plan
        
        # Default terminal interaction
        print(plan_display)
        
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
                modified_plan = self.ask_for_modification("Enter your modified plan:")
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
        
        # Format diffs for display
        diffs_display = f"\n{'='*80}\n"
        diffs_display += f"CODE CHANGES (ITERATION {iteration}):\n"
        diffs_display += f"{'-'*80}\n"
        
        diff_files = []
        for file_path, diff in diffs.items():
            file_diff = f"\nFile: {file_path}\n{'-'*40}\n{diff}"
            diffs_display += file_diff
            
            # Collect structured diff data for VS Code UI
            diff_files.append({
                "filename": file_path,
                "content": diff,
                "is_new": "(NEW FILE)" in diff
            })
            
        diffs_display += f"\n{'='*80}"
        
        # Display via appropriate UI
        if self.is_vscode_mode():
            # Send to VS Code UI
            self.vscode_bridge.send_terminal_output(diffs_display)
            
            # Extract before and after content for interactive diff display
            enhanced_diff_files = []
            
            for file_diff in diff_files:
                file_path = file_diff["filename"]
                content = file_diff["content"]
                is_new = file_diff["is_new"]
                
                if is_new:
                    # For new files, before is empty and after is the full content
                    before = ""
                    after = "\n".join([line.lstrip("+") for line in content.split("\n") 
                                     if line.startswith("+") and not line.startswith("+++")])
                else:
                    # For existing files, extract before/after from diff
                    before, after = self._extract_before_after_content(content)
                
                enhanced_diff_files.append({
                    "filename": file_path,
                    "before": before,
                    "after": after,
                    "is_new": is_new
                })
            
            # Send enhanced interactive diff display
            wait_for_response = self.vscode_bridge.send_interactive_diff(
                files=enhanced_diff_files,
                summary=f"Code Changes (Iteration {iteration})"
            )
            
            if wait_for_response:
                response = wait_for_response()
                if response:
                    action = response.get("response", "").lower()
                    
                    if action in ["approve", "yes", "y"]:
                        if self.scratchpad:
                            self.scratchpad.log("Moderator", "User approved changes via VS Code UI")
                        return True
                    else:
                        if self.scratchpad:
                            self.scratchpad.log("Moderator", "User rejected changes via VS Code UI")
                        return False
                
            # Fallback to terminal if VS Code response fails
            if self.vscode_bridge.config.fallback_to_terminal:
                self.notify_user("No response from VS Code UI, falling back to terminal", level="warning")
            else:
                if self.scratchpad:
                    self.scratchpad.log("Moderator", "No response from VS Code UI, defaulting to reject")
                return False
        
        # Default terminal output
        print(diffs_display)
        
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

    def explain_plan_section(self, section_data: Dict[str, Any], section_path: str) -> Optional[str]:
        """Request an explanation for a section of the generated plan.

        Args:
            section_data: The data for the section to explain
            section_path: The path to the section being explained

        Returns:
            The explanation as text, or None if the user cancels
        """
        if self.is_vscode_mode():
            # Show loading indicator in VS Code UI
            self.vscode_bridge.send_log_output(f"Generating explanation for {section_path}...", level="info")

        if not hasattr(self.coordinator, 'router_agent'):
            self.notify_user("Cannot provide explanation - router agent not available.", level="error")
            return None

        # Format section data for display
        if isinstance(section_data, (dict, list)):
            section_json = json.dumps(section_data, indent=2)
        else:
            section_json = str(section_data)

        # Create the prompt for the LLM
        system_prompt = """You are a helpful assistant tasked with explaining technical planning details.
Your explanations should be clear, concise, and focused on helping software engineers understand the rationale
behind design and implementation decisions."""

        user_prompt = f"""Please explain the following section from a software development plan:

```json
{section_json}
```

Path: {section_path}

Provide a clear explanation that covers:
1. What this component/section is meant to accomplish
2. Why it's designed this way
3. How it fits into the overall system design
4. Any critical considerations or rationale for specific design choices

Focus on explaining the "why" behind the decisions, not just describing what's in the JSON."""

        # Call the LLM
        try:
            router_agent = self.coordinator.router_agent
            response = router_agent.call_llm_by_role(
                role='explainer',
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                config={
                    "temperature": 0.3,  # Lower temperature for more factual response
                    "max_tokens": 1000   # Limit response length
                }
            )

            # Display the explanation
            if self.is_vscode_mode():
                # Show in VS Code UI
                self.vscode_bridge.send_terminal_output(f"\n=== Explanation for {section_path} ===\n")
                self.vscode_bridge.send_terminal_output(response)
            else:
                # Show in terminal
                print(f"\n=== Explanation for {section_path} ===\n")
                print(response)
                print("\n" + "="*40)

            return response

        except Exception as e:
            if self.scratchpad:
                self.scratchpad.log("Moderator", f"Error generating explanation: {e}")
            self.notify_user(f"Error generating explanation: {e}", level="error")
            return None

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

    def ask_yes_no_question(self, question: str) -> bool:
        """Ask the user a yes/no question.

        Args:
            question: The question to ask the user

        Returns:
            True if the user answers 'yes', False otherwise
        """
        # Use the VS Code UI if available
        if self.is_vscode_mode():
            # Send the question via VS Code UI
            wait_for_response = self.vscode_bridge.send_interactive_approval(
                title="Confirmation Required",
                description=question,
                options=[
                    {
                        "id": "yes", 
                        "label": "Yes", 
                        "shortcut": "Y",
                        "description": "Proceed"
                    },
                    {
                        "id": "no", 
                        "label": "No", 
                        "shortcut": "N",
                        "description": "Cancel"
                    }
                ]
            )
            
            if wait_for_response:
                response = wait_for_response()
                if response:
                    option_id = response.get("option_id", "").lower()
                    return option_id == "yes"
            
            # Fallback to terminal if VS Code response fails
            if self.vscode_bridge.config.fallback_to_terminal:
                self.notify_user("No response from VS Code UI, falling back to terminal", level="warning")
            else:
                if self.scratchpad:
                    self.scratchpad.log("Moderator", "No response from VS Code UI, defaulting to No")
                return False
                
        # Use terminal interaction
        while True:
            user_input = input(f"{question} (y/n): ").strip().lower()
            
            if user_input in ["y", "yes"]:
                if self.scratchpad:
                    self.scratchpad.log("Moderator", "User responded 'yes'")
                return True
            elif user_input in ["n", "no"]:
                if self.scratchpad:
                    self.scratchpad.log("Moderator", "User responded 'no'")
                return False
            else:
                print("Invalid input. Please enter 'y' or 'n'.")
    
    def ask_for_modification(self, prompt: str, supports_json_path: bool = False) -> str:
        """Ask the user for structured modifications to the plan.

        Args:
            prompt: The prompt text to display
            supports_json_path: Whether to show JSON path targeting instructions

        Returns:
            Structured modification text
        """
        print(f"\n{prompt}")
        print("\nPlease provide STRUCTURED modifications using one of these formats:")

        if supports_json_path:
            print("\nOption 1: Target a specific JSON path (most precise):")
            print("JSON_PATH: feature_groups[0].features[1].name")
            print("NEW_VALUE: Updated feature name")
            print("REASON: Feature name was too generic")
            print("\n--- OR ---\n")

        print("Option 2: Structured component modification:")
        print("COMPONENT: implementation_plan")
        print("LOCATION: src/database/user_repository.py")
        print("CHANGE_TYPE: add")
        print("DESCRIPTION: Add error handling for database connection failures")
        print("\nYou can provide multiple modifications by separating them with '---'")
        print("(Type 'DONE' on a new line when finished)")
        
        lines = []
        current_section = []
        
        # Track section completeness
        sections = []
        current_modification = {}
        expected_keys = ["COMPONENT", "LOCATION", "CHANGE_TYPE", "DESCRIPTION"]
        
        while True:
            try:
                line = input()
                if line.strip().upper() == "DONE":
                    # Add the last section if not empty
                    if current_section:
                        lines.extend(current_section)
                        if current_modification:
                            sections.append(current_modification)
                    break
                
                # Check for section separator
                if line.strip() == "---":
                    # Add current section to lines
                    if current_section:
                        lines.extend(current_section)
                        lines.append(line)  # Add the separator
                        if current_modification:
                            sections.append(current_modification)
                            current_modification = {}  # Reset for next section
                    current_section = []
                    continue
                
                # Add line to current section
                current_section.append(line)
                
                # Try to parse structured components
                key_value = line.split(":", 1)
                if len(key_value) == 2:
                    key = key_value[0].strip().upper()
                    value = key_value[1].strip()
                    if key in expected_keys:
                        current_modification[key] = value
                
            except EOFError:  # Handle Ctrl+D or similar EOF signals
                break
        
        # If we have structured modifications, convert to a more standardized format
        if sections:
            if self.scratchpad:
                self.scratchpad.log("Moderator", f"Received {len(sections)} structured modifications")
            
            # Create a standardized JSON-like format for easier processing
            structured_output = "STRUCTURED_MODIFICATIONS:\n"
            for i, section in enumerate(sections):
                structured_output += f"Modification {i+1}:\n"
                for key in expected_keys:
                    if key in section:
                        structured_output += f"  {key}: {section[key]}\n"
                structured_output += "\n"
            
            # Append the raw input at the end for reference
            raw_input = "\n".join(lines)
            structured_output += "RAW_INPUT:\n" + raw_input
            
            return structured_output
        else:
            # Fall back to the original format if not enough structure was provided
            if self.scratchpad:
                self.scratchpad.log("Moderator", "Free-form modification received, no apparent structure")
            return "\n".join(lines)

    def request_debugging_guidance(self, group_name: str, max_attempts: int) -> Optional[str]:
        """Request engineer guidance when automated debugging fails.

        Args:
            group_name: Name of the feature group that failed.
            max_attempts: Number of automated attempts that were made.

        Returns:
            Modification text provided by the engineer, or None to abort.
        """
        question = (
            f"Implementation for {group_name} failed after {max_attempts} attempts. "
            "Would you like to provide modifications before retrying?"
        )
        if self.ask_yes_no_question(question):
            return self.ask_for_modification("Enter your modifications:")
        return None

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
        progress_text = f"\r{message} |{bar}| {percent}%"
        
        # Print to terminal
        print(progress_text, end='')
        sys.stdout.flush()
        
        if progress >= 1.0:
            print()  # Newline after completion
            
        # Send to VS Code UI if available
        if self.is_vscode_mode():
            # Use enhanced progress indicator with step tracking
            if hasattr(self, '_progress_steps'):
                # Update the current step
                for step in self._progress_steps:
                    if step["status"] == "in_progress":
                        step["percentage"] = percent
                        break
                
                # Check if we need to advance to the next step
                if percent >= 100:
                    for i, step in enumerate(self._progress_steps):
                        if step["status"] == "in_progress":
                            step["status"] = "completed"
                            step["percentage"] = 100
                            # Move to next step if available
                            if i + 1 < len(self._progress_steps):
                                self._progress_steps[i + 1]["status"] = "in_progress"
                                self._progress_steps[i + 1]["percentage"] = 0
                            break
                
                # Send enhanced progress indicator
                self.vscode_bridge.send_progress_indicator(
                    title="Task Progress",
                    percentage=self._compute_overall_progress(),
                    description=message,
                    steps=self._progress_steps,
                    estimated_time_remaining=self._estimate_remaining_time() if hasattr(self, '_start_time') else None
                )
            else:
                # Legacy progress update
                self.vscode_bridge.send_progress_update(message, percent)
            
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
        print("0. Cancel")
        
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

    def present_consolidated_plan(self, plan: Dict[str, Any]) -> Tuple[str, Optional[str]]:
        """Present the consolidated plan to the user, grouped by feature.
        
        This method displays the plan in a structured way, highlighting architecture
        and tests for each feature group for clarity. It also handles pagination
        for large plans to manage information overload.
        
        Args:
            plan: The consolidated plan to present
            
        Returns:
            Tuple of (decision, modification_text)
        """
        if self.scratchpad:
            self.scratchpad.log("Moderator", "Presenting consolidated plan to user")
        
        if not plan:
            return "no", "No consolidated plan provided"
        
        group_name = plan.get("group_name", "Unnamed Group")
        
        # Format plan for display
        print(f"\n{'='*30}")
        print(f"FEATURE GROUP: {group_name}")
        print(f"{'='*30}")
        print(f"\nDescription: {plan.get('group_description', 'No description')}")
        
        # Show architecture review summary
        print("\nARCHITECTURE REVIEW:")
        architecture_review = plan.get("architecture_review", {})
        
        logical_gaps = architecture_review.get("logical_gaps", [])
        if logical_gaps:
            print(f"- Logical Gaps: {len(logical_gaps)}")
            for i, gap in enumerate(logical_gaps[:3], 1):
                print(f"  {i}. {gap.get('description', 'No description')}")
            if len(logical_gaps) > 3:
                print(f"  ... and {len(logical_gaps) - 3} more gaps.")
        else:
            print("- No logical gaps identified")
            
        optimizations = architecture_review.get("optimization_suggestions", [])
        if optimizations:
            print(f"- Optimization Suggestions: {len(optimizations)}")
            for i, opt in enumerate(optimizations[:3], 1):
                print(f"  {i}. {opt.get('description', 'No description')}")
            if len(optimizations) > 3:
                print(f"  ... and {len(optimizations) - 3} more suggestions.")
        else:
            print("- No optimization suggestions")
        
        # Show test summary
        print("\nTESTS:")
        tests = plan.get("tests", {})
        
        unit_tests = tests.get("unit_tests", [])
        if unit_tests:
            print(f"- Unit Tests: {len(unit_tests)}")
            for i, test in enumerate(unit_tests[:3], 1):
                print(f"  {i}. {test.get('test_name', 'Unnamed test')}")
            if len(unit_tests) > 3:
                print(f"  ... and {len(unit_tests) - 3} more unit tests.")
        else:
            print("- No unit tests")
            
        integration_tests = tests.get("integration_tests", [])
        if integration_tests:
            print(f"- Integration Tests: {len(integration_tests)}")
        
        # Show implementation summary
        print("\nIMPLEMENTATION PLAN:")
        implementation_plan = plan.get("implementation_plan", {})
        if implementation_plan:
            print(f"- Files to modify: {len(implementation_plan)}")
            for i, (file_path, funcs) in enumerate(list(implementation_plan.items())[:3], 1):
                print(f"  {i}. {file_path} ({len(funcs)} functions)")
            if len(implementation_plan) > 3:
                print(f"  ... and {len(implementation_plan) - 3} more files.")
        else:
            print("- No implementation details")
        
        # Show semantic validation results if available
        semantic_validation = plan.get("semantic_validation", {})
        if semantic_validation and "error" not in semantic_validation:
            print("\nSEMANTIC VALIDATION:")
            coherence_score = semantic_validation.get("coherence_score", 0)
            consistency_score = semantic_validation.get("technical_consistency_score", 0)
            print(f"- Coherence Score: {coherence_score:.2f}")
            print(f"- Technical Consistency Score: {consistency_score:.2f}")
            
            critical_issues = semantic_validation.get("critical_issues", [])
            if critical_issues:
                print(f"- Critical Issues: {len(critical_issues)}")
                for i, issue in enumerate(critical_issues[:3], 1):
                    print(f"  {i}. {issue.get('category', 'Issue')}: {issue.get('description', 'No description')}")
                if len(critical_issues) > 3:
                    print(f"  ... and {len(critical_issues) - 3} more issues.")
            else:
                print("- No critical issues identified")
        
        # Ask for user decision
        print("\nDECISION:")
        decision = self.ask_ternary_question(
            "Do you want to proceed with this plan? (yes/no/modify)"
        )
        
        modification_text = None
        if decision == "modify":
            modification_text = self.handle_user_modification(plan)
        
        return decision, modification_text
    
    def handle_user_modification(self, plan: Dict[str, Any]) -> str:
        """Handle user modifications to the plan in a structured way.
        
        This method parses user input for modifications, maps them to the
        corresponding JSON node or text section in the plan, and applies
        the changes to a copy of the plan.
        
        Args:
            plan: The plan to modify
            
        Returns:
            The modification text
        """
        print("\nPlease enter your modification instructions:")
        print("Be specific about what should be added, removed, or changed.")
        print("\nYou can use structured format for precise modifications:")
        print("COMPONENT: architecture_review")
        print("LOCATION: logical_gaps")
        print("CHANGE_TYPE: add")
        print("DESCRIPTION: Add a logical gap for error handling in the authentication flow")
        print("\nOr provide free-form instructions for general modifications.")
        print("Type 'done' on a new line when finished.")
        
        lines = []
        while True:
            line = input()
            if line.strip().lower() == 'done':
                break
            lines.append(line)
        
        # Process the modification text
        modification_text = "\n".join(lines)
        
        # Try to parse structured modifications
        structured_mods = self._parse_structured_modifications(modification_text)
        
        if structured_mods and self.scratchpad:
            self.scratchpad.log("Moderator", f"Parsed {len(structured_mods)} structured modifications")
            
            # Create a standardized format for easier processing
            formatted_text = "STRUCTURED_MODIFICATIONS:\n"
            for i, mod in enumerate(structured_mods):
                formatted_text += f"Modification {i+1}:\n"
                for key, value in mod.items():
                    formatted_text += f"  {key}: {value}\n"
                formatted_text += "\n"
            
            # Append the raw input for reference
            formatted_text += "RAW_INPUT:\n" + modification_text
            
            return formatted_text
        
        return modification_text
    
    def _parse_structured_modifications(self, text: str) -> List[Dict[str, str]]:
        """Parse structured modifications from text.
        
        Args:
            text: The modification text
            
        Returns:
            List of structured modifications
        """
        modifications = []
        current_mod = {}
        expected_keys = ["COMPONENT", "LOCATION", "CHANGE_TYPE", "DESCRIPTION"]
        
        # Split by lines and process
        lines = text.split('\n')
        for line in lines:
            # Check for section separator
            if line.strip() == "---":
                if current_mod:
                    modifications.append(current_mod)
                    current_mod = {}
                continue
            
            # Try to parse key-value pairs
            parts = line.split(':', 1)
            if len(parts) == 2:
                key = parts[0].strip().upper()
                value = parts[1].strip()
                
                if key in expected_keys:
                    current_mod[key] = value
        
        # Add the last modification if not empty
        if current_mod:
            modifications.append(current_mod)
        
        return modifications
    
    def display_discussion_and_plan(self, discussion: str, plan: str) -> None:
        """Display the discussion transcript and the implementation plan to the user."""
        if self.scratchpad:
            self.scratchpad.log("Moderator", "Displaying discussion and plan")

        display_text = "\n" + "="*80 + "\n"
        display_text += "DISCUSSION:\n"
        display_text += "-"*80 + "\n"
        display_text += discussion + "\n\n"
        display_text += "="*80 + "\n"
        display_text += "IMPLEMENTATION PLAN:\n"
        display_text += "-"*80 + "\n"
        display_text += plan + "\n"
        display_text += "="*80

        # Display via appropriate UI
        if self.is_vscode_mode():
            # Send only terminal output
            self.vscode_bridge.send_terminal_output(display_text)
        else:
            # Default terminal output
            print(display_text)
