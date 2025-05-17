"""Design Manager for handling system design conversations and feature decomposition.

This module provides functionality for:
1. Analyzing design objectives based on industry best practices
2. Facilitating clarification questions for ambiguous requirements
3. Decomposing systems into distinct, single-concern features
4. Managing the design conversation flow and termination
5. Writing the final design to a structured file
6. Transitioning to local deployment of the designed system
"""

import os
import json
import logging
import time
from typing import List, Dict, Any, Tuple, Optional
from pathlib import Path

from agent_s3.tools.file_tool import FileTool
from agent_s3.router_agent import RouterAgent
from agent_s3.code_generator import CodeGenerator
from agent_s3.deployment_manager import DeploymentManager

logger = logging.getLogger(__name__)


class DesignManager:
    """Manages system design conversations, analysis, and feature decomposition."""

    def __init__(self, coordinator=None):
        """Initialize the DesignManager.

        Args:
            coordinator: The parent coordinator instance
        """
        self.coordinator = coordinator
        self.conversation_history = []
        self.design_objective = ""
        self.llm = RouterAgent()
        self.file_tool = FileTool()
        
        # Initialize termination signal detection variables
        self.consecutive_feature_messages = 0
        self.features_identified = False
        self.user_explicitly_requested_completion = False
        self.clarification_count = 0
        self.max_clarifications = 5  # Maximum number of clarification rounds before suggesting completion

    def start_design_conversation(self, design_objective: str) -> str:
        """Initiate a design conversation with the specified objective.
        
        Args:
            design_objective: The user's design objective/request
            
        Returns:
            The LLM's initial response
        """
        self.design_objective = design_objective
        self.conversation_history = []
        
        # Create the initial prompt
        system_prompt = self._get_system_prompt()
        user_prompt = f"Design Objective: {design_objective}\n\nAnalyze this design objective and enhance it based on industry best practices. Ask clarification questions if there are missing details or ambiguities."
        
        # Add to conversation history
        self.conversation_history.append({"role": "system", "content": system_prompt})
        self.conversation_history.append({"role": "user", "content": user_prompt})
        
        # Call LLM to get initial response
        response = self.llm.call_llm_agent("designer", self.conversation_history)
        
        # Add response to conversation history
        if response:
            self.conversation_history.append({"role": "assistant", "content": response})
        
        return response

    def continue_conversation(self, user_message: str) -> Tuple[str, bool]:
        """Continue the design conversation with a user message.
        
        Args:
            user_message: The user's message
            
        Returns:
            Tuple of (LLM response, is_design_complete)
        """
        # Check for explicit completion request
        if "/finalize-design" in user_message.lower():
            self.user_explicitly_requested_completion = True
            response = "I'll finalize the design now and create the design.txt file with the distinct, single-concern features we've discussed."
            self.conversation_history.append({"role": "user", "content": user_message})
            self.conversation_history.append({"role": "assistant", "content": response})
            return response, True
        
        # Add user message to conversation history
        self.conversation_history.append({"role": "user", "content": user_message})
        
        # Update clarification count if this appears to be a response to a question
        if self._is_clarification(user_message):
            self.clarification_count += 1
        
        # Create a contextual prompt based on conversation state
        contextual_prompt = self._create_contextual_prompt()
        if contextual_prompt:
            self.conversation_history.append({"role": "system", "content": contextual_prompt})
        
        # Call LLM for response
        response = self.llm.call_llm_agent("designer", self.conversation_history)
        
        # Add response to conversation history
        if response:
            self.conversation_history.append({"role": "assistant", "content": response})
        
        # Check if we should suggest completion after many clarification rounds
        if self.clarification_count >= self.max_clarifications and "feature" in response.lower():
            suggest_completion = "Based on our discussion so far, I think I have enough information to finalize the design. Would you like me to create the design.txt file with the distinct features we've discussed? If not, we can continue refining the design further."
            self.conversation_history.append({"role": "assistant", "content": suggest_completion})
            response += f"\n\n{suggest_completion}"
        
        # Check if design conversation appears complete
        is_complete = self.detect_design_completion()
        
        return response, is_complete

    def detect_design_completion(self) -> bool:
        """Detect if the design conversation is complete based on heuristics.
        
        Returns:
            True if design appears complete, False otherwise
        """
        # If user explicitly requested completion
        if self.user_explicitly_requested_completion:
            return True
        
        # Check last few messages for feature listing patterns
        if len(self.conversation_history) >= 3:
            last_ai_message = next((msg["content"] for msg in reversed(self.conversation_history) 
                                 if msg["role"] == "assistant"), "")
            
            # Check for feature listing patterns
            feature_indicators = [
                "Feature 1:", "1. Feature:", "Feature #1", 
                "Component 1:", "Module 1:", "Service 1:",
                "Here are the distinct features:", "The system can be decomposed into:"
            ]
            
            if any(indicator in last_ai_message for indicator in feature_indicators):
                self.features_identified = True
                self.consecutive_feature_messages += 1
            elif self.features_identified:
                # If we previously identified features but this message doesn't contain them,
                # check if it's a summary/conclusion type message
                conclusion_indicators = [
                    "In conclusion", "To summarize", "These features", "This design",
                    "Would you like me to create", "Would you like to implement",
                    "Should I finalize", "Ready to finalize"
                ]
                if any(indicator in last_ai_message for indicator in conclusion_indicators):
                    return True
            
            # If we've had consecutive messages with feature listings, likely finished
            if self.consecutive_feature_messages >= 2:
                return True
            
            # Check if the last user response indicates completion
            last_user_message = next((msg["content"] for msg in reversed(self.conversation_history) 
                                   if msg["role"] == "user"), "")
            
            user_confirmation_indicators = [
                "looks good", "that's good", "finalize", "proceed", "complete",
                "ready", "finished", "done", "create design.txt", "write the design"
            ]
            
            if self.features_identified and any(indicator in last_user_message.lower() 
                                             for indicator in user_confirmation_indicators):
                return True
        
        return False

    def write_design_to_file(self) -> Tuple[bool, str]:
        """Extract design features from conversation and write to design.txt.
        
        Returns:
            Tuple of (success_flag, message)
        """
        # Extract features from conversation
        features = self._extract_features_from_conversation()
        
        if not features:
            return False, "Could not extract features from the design conversation."
        
        # Format design content with hierarchical tasks
        content = f"# System Design: {self.design_objective}\n\n"
        content += "## Features\n\n"
        
        # Convert features to hierarchical tasks
        hierarchical_tasks = self._extract_hierarchical_tasks(features)
        content += self._format_tasks_hierarchically(hierarchical_tasks)
        
        # Write to design.txt
        design_path = os.path.join(os.getcwd(), "design.txt")
        success, message = self.file_tool.write_file(design_path, content)
        
        # Initialize progress tracker
        if success:
            self._initialize_progress_tracker(design_path, hierarchical_tasks)
            return True, f"Design written to design.txt with {len(features)} features."
        else:
            return False, f"Failed to write design: {message}"
    
    def _extract_hierarchical_tasks(self, features: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract hierarchical tasks from features.
        
        Args:
            features: List of feature dictionaries
            
        Returns:
            List of hierarchical task dictionaries
        """
        tasks = []
        
        for i, feature in enumerate(features, 1):
            # Add main feature as top-level task
            feature_task = {
                "id": str(i),
                "description": feature['name'],
                "details": feature.get('description', ''),
                "subtasks": []
            }
            
            # Add components as subtasks
            for j, component in enumerate(feature.get('components', []), 1):
                subtask = {
                    "id": f"{i}.{j}",
                    "description": component,
                    "details": "",
                    "subtasks": []
                }
                feature_task["subtasks"].append(subtask)
            
            tasks.append(feature_task)
        
        return tasks
    
    def _format_tasks_hierarchically(self, tasks: List[Dict[str, Any]]) -> str:
        """Format tasks in hierarchical structure.
        
        Args:
            tasks: List of hierarchical task dictionaries
            
        Returns:
            Formatted string for design.txt
        """
        content = ""
        
        for task in tasks:
            content += f"{task['id']}. {task['description']}\n"
            if task.get('details'):
                content += f"   {task['details']}\n\n"
            else:
                content += "\n"
            
            for subtask in task.get('subtasks', []):
                content += f"   {subtask['id']}. {subtask['description']}\n"
                if subtask.get('details'):
                    content += f"      {subtask['details']}\n\n"
                else:
                    content += "\n"
                
                for subsubtask in subtask.get('subtasks', []):
                    content += f"      {subsubtask['id']}. {subsubtask['description']}\n"
                    if subsubtask.get('details'):
                        content += f"         {subsubtask['details']}\n\n"
                    else:
                        content += "\n"
        
        return content
    
    def _initialize_progress_tracker(self, design_file: str, tasks: List[Dict[str, Any]]) -> bool:
        """Initialize the implementation progress tracker.
        
        Args:
            design_file: Path to the design file
            tasks: List of hierarchical task dictionaries
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Create a flat list of all tasks and subtasks
            flat_tasks = []
            
            for task in tasks:
                flat_tasks.append({
                    "id": task['id'],
                    "description": task['description'],
                    "status": "pending"
                })
                
                for subtask in task.get('subtasks', []):
                    flat_tasks.append({
                        "id": subtask['id'],
                        "description": subtask['description'],
                        "status": "pending"
                    })
                    
                    for subsubtask in subtask.get('subtasks', []):
                        flat_tasks.append({
                            "id": subsubtask['id'],
                            "description": subsubtask['description'],
                            "status": "pending"
                        })
            
            # Create progress tracker
            progress = {
                "design_objective": self.design_objective,
                "design_file": design_file,
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "last_updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "tasks": flat_tasks
            }
            
            # Write to implementation_progress.json
            progress_path = os.path.join(os.getcwd(), "implementation_progress.json")
            with open(progress_path, 'w') as f:
                json.dump(progress, f, indent=2)
            
            return True
        except Exception as e:
            logger.error(f"Error initializing progress tracker: {e}")
            return False
    
    def prompt_for_implementation(self) -> Dict[str, Any]:
        """Prompt the user if they want to proceed with implementation or deployment.
        
        This method will directly transition to pre-planning if implementation is chosen.
        The pre-planning phase will then guide the user through code generation.
        
        Returns:
            Dictionary with user choices and transition status
        """
        # Prepare the implementation message for the user
        impl_message = (
            "The design has been written to design.txt.\n"
            "Would you like to proceed with implementation? "
            "This will transition to code generation. (yes/no): "
        )
        
        # If we have access to coordinator's scratchpad, use that to prompt
        if self.coordinator and hasattr(self.coordinator, 'scratchpad'):
            self.coordinator.scratchpad.log("DesignManager", impl_message)
            impl_response = input(impl_message).strip().lower()
        else:
            # Fallback to direct input
            impl_response = input(impl_message).strip().lower()
        
        impl_choice = impl_response in ["yes", "y", "true", "1"]
        deploy_choice = False
        
        if impl_choice:
            # User wants to implement, transition to pre-planning
            print("Starting transition to code implementation phase...")
            success = self._transition_to_pre_planning()
            if not success:
                print("Failed to transition to implementation phase. See logs for details.")
                # If implementation transition fails, offer deployment as fallback
                deploy_message = (
                    "Would you like to deploy the application locally instead? (yes/no): "
                )
                if self.coordinator and hasattr(self.coordinator, 'scratchpad'):
                    self.coordinator.scratchpad.log("DesignManager", deploy_message)
                    deploy_response = input(deploy_message).strip().lower()
                    deploy_choice = deploy_response in ["yes", "y", "true", "1"]
                else:
                    deploy_response = input(deploy_message).strip().lower()
                    deploy_choice = deploy_response in ["yes", "y", "true", "1"]
        else:
            # If user doesn't want implementation, ask about deployment
            deploy_message = (
                "Would you like to deploy the application locally instead? (yes/no): "
            )
            
            if self.coordinator and hasattr(self.coordinator, 'scratchpad'):
                self.coordinator.scratchpad.log("DesignManager", deploy_message)
                deploy_response = input(deploy_message).strip().lower()
            else:
                # Fallback to direct input
                deploy_response = input(deploy_message).strip().lower()
            
            deploy_choice = deploy_response in ["yes", "y", "true", "1"]
        
        return {
            "implementation": impl_choice,
            "deployment": deploy_choice
        }

    def _extract_features_from_conversation(self) -> List[Dict[str, Any]]:
        """Extract structured feature information from conversation history.
        
        Returns:
            List of feature dictionaries with name, description, and components
        """
        features = []
        
        # Collect all assistant messages
        assistant_messages = [msg["content"] for msg in self.conversation_history 
                             if msg["role"] == "assistant"]
        
        # Request a structured format from the LLM
        system_prompt = """
        Extract the distinct, single-concern features from our design conversation. 
        Format each feature with:
        1. A concise name/title
        2. A brief description
        3. Key components or capabilities
        
        Return in a structured JSON format with an array of features.
        """
        
        conversation_text = "\n\n".join(assistant_messages)
        extraction_prompt = f"Based on our design conversation, extract and structure the distinct features we've identified:\n\n{conversation_text}"
        
        # Create a temporary conversation for feature extraction
        extraction_conversation = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": extraction_prompt}
        ]
        
        # Call LLM for extraction
        extraction_result = self.llm.call_llm_agent("designer", extraction_conversation)
        
        if not extraction_result:
            logger.error("Failed to extract features: No response from LLM")
            return []
        
        # Try to extract JSON from the response
        try:
            # Look for JSON block in the response
            json_start = extraction_result.find('{')
            json_end = extraction_result.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = extraction_result[json_start:json_end]
                data = json.loads(json_str)
                
                if isinstance(data, dict) and 'features' in data and isinstance(data['features'], list):
                    features = data['features']
                elif isinstance(data, list):
                    features = data
            
            # If JSON parsing failed, try a regex-based approach
            if not features:
                import re
                feature_blocks = re.split(r'(?:Feature\s+\d+|^\d+\.)\s*:', extraction_result, flags=re.MULTILINE)
                if len(feature_blocks) > 1:  # First element is often empty or intro text
                    feature_blocks = feature_blocks[1:]
                    for block in feature_blocks:
                        lines = block.strip().split('\n')
                        if lines:
                            name = lines[0].strip()
                            description = "\n".join([l for l in lines[1:] if l.strip()]) if len(lines) > 1 else ""
                            features.append({
                                "name": name,
                                "description": description,
                                "components": []
                            })
        
        except Exception as e:
            logger.error(f"Error extracting features from LLM response: {e}")
            # If JSON extraction fails, try a fallback approach
            # Find feature blocks with common patterns
            current_feature = None
            for msg in assistant_messages:
                lines = msg.split('\n')
                for line in lines:
                    line = line.strip()
                    # Look for feature headers
                    import re
                    feature_match = re.search(r'(?:Feature|Component|Module|Service)\s*(?:\d+|#\d+)?\s*:?\s*(.*)', line)
                    if feature_match:
                        if current_feature and current_feature["name"]:
                            features.append(current_feature)
                        current_feature = {"name": feature_match.group(1).strip(), "description": "", "components": []}
                    elif current_feature and line and not line.startswith('-') and not line.startswith('*'):
                        # Add to description
                        current_feature["description"] += line + " "
                    elif current_feature and (line.startswith('-') or line.startswith('*')):
                        # Add as component
                        component = line[1:].strip()
                        if component:
                            current_feature["components"].append(component)
            
            # Add the last feature if any
            if current_feature and current_feature["name"]:
                features.append(current_feature)
                
        # Filter out empty features
        features = [f for f in features if f.get('name')]
        
        return features

    def _get_system_prompt(self) -> str:
        """Get the system prompt for the design conversation.
        
        Returns:
            System prompt string
        """
        return """
        You are an expert system designer tasked with helping the user design a software system.
        
        Your responsibilities:
        1. Analyze the design objective and enhance it based on industry best practices
        2. Ask clarification questions if there are missing details or ambiguities
        3. Decompose the system into distinct, single-concern features
        
        Follow these guidelines:
        - Focus on high-level architecture and component design, not implementation details
        - Apply relevant design patterns and principles (SOLID, microservices, etc.)
        - Consider scalability, maintainability, and security in your design
        - Break down complex systems into coherent, single-responsibility components
        - Identify data flows and key interfaces between components
        - Consider error handling, logging, and monitoring requirements
        
        When the design is complete, you'll enumerate the distinct, single-concern features
        that can be implemented iteratively. Each feature should be self-contained enough
        to be implemented and tested independently.
        """

    def _create_contextual_prompt(self) -> str:
        """Create a contextual system prompt based on conversation state.
        
        Returns:
            Contextual prompt string or empty string if not needed
        """
        # Get latest messages
        latest_assistant_msg = next((msg["content"] for msg in reversed(self.conversation_history) 
                                  if msg["role"] == "assistant"), "")
        latest_user_msg = next((msg["content"] for msg in reversed(self.conversation_history) 
                             if msg["role"] == "user"), "")
        
        # Check conversation state
        if self.features_identified:
            # If we're already in feature definition mode, guide towards completion
            return """
            Continue refining the feature definitions. Make sure each feature:
            1. Has a clear, descriptive name
            2. Addresses a single responsibility/concern
            3. Can be implemented and tested independently
            
            When you've finished defining all features, ask the user if they're ready to finalize the design.
            """
        elif "?" in latest_assistant_msg and self._is_clarification(latest_user_msg):
            # If we just got a clarification answer, move towards feature definition
            return """
            Thank the user for the clarification. Based on all information gathered so far,
            start decomposing the system into distinct, single-concern features.
            
            For each feature:
            1. Provide a clear name
            2. Give a brief description
            3. List key components or capabilities
            
            Format the features in a numbered list for clarity.
            """
        elif self.clarification_count >= 3 and "feature" not in latest_assistant_msg.lower():
            # If we've had several clarification rounds but no feature discussion yet
            return """
            Based on the information gathered so far, begin decomposing the system into
            distinct, single-concern features. It's time to move from clarification to
            concrete design elements.
            """
        
        # Default: no special contextual prompt needed
        return ""

    def _is_clarification(self, message: str) -> bool:
        """Check if a message appears to be answering a clarification question.
        
        Args:
            message: The message to check
            
        Returns:
            True if it appears to be a clarification answer, False otherwise
        """
        # Look for question marks in previous assistant message
        prev_assistant_msg = ""
        for i in range(len(self.conversation_history) - 1, -1, -1):
            if self.conversation_history[i]["role"] == "assistant":
                prev_assistant_msg = self.conversation_history[i]["content"]
                break
        
        # If previous message had questions and this message is relatively short, likely a clarification
        if "?" in prev_assistant_msg and len(message.split()) < 100:
            return True
            
        # If message directly references a question
        clarification_indicators = [
            "yes", "no", "correct", "that's right", "to clarify",
            "to answer your question", "regarding your question"
        ]
        
        if any(indicator in message.lower() for indicator in clarification_indicators):
            return True
            
        return False

    def _transition_to_pre_planning(self) -> bool:
        """Convert design tasks to planning format and transition to pre-planning phase.
        
        This creates a structured format from the design features that can be used
        by the pre-planning phase for implementation.
        
        Returns:
            True if transition was successful, False otherwise
        """
        try:
            # Get the path to design.txt
            design_path = os.path.join(os.getcwd(), "design.txt")
            
            if not os.path.exists(design_path):
                logger.error("Design file not found. Cannot transition to pre-planning.")
                return False
                
            # Load hierarchical tasks from the progress tracker
            progress_path = os.path.join(os.getcwd(), "implementation_progress.json")
            if not os.path.exists(progress_path):
                logger.error("Progress file not found. Cannot transition to pre-planning.")
                return False
                
            with open(progress_path, 'r') as f:
                progress_data = json.load(f)
            
            # Create feature groups from the tasks for pre-planning
            feature_groups = self._convert_tasks_to_feature_groups(progress_data.get('tasks', []))
            
            if not feature_groups:
                logger.error("Failed to convert design tasks to feature groups.")
                return False
            
            # Create the pre-planning input
            pre_planning_input = {
                "original_request": self.design_objective,
                "feature_groups": feature_groups,
                "from_design": True,  # Explicit flag for tracking
                "design_file": design_path
            }
            
            # Log the transition
            if self.coordinator and hasattr(self.coordinator, 'scratchpad'):
                self.coordinator.scratchpad.log(
                    "DesignManager", 
                    "Transitioning from design to pre-planning phase..."
                )
            
            # Initialize the pre-planning phase with our input
            if self.coordinator:
                if hasattr(self.coordinator, 'run_task'):
                    # Standardize on directly using run_task with from_design=True
                    self.coordinator.run_task(
                        task=self.design_objective,
                        pre_planning_input=pre_planning_input,
                        from_design=True
                    )
                    return True
            
            # If we reach here, we couldn't call the method
            logger.error("Coordinator doesn't support transitioning to pre-planning from design.")
            return False
                
        except Exception as e:
            logger.error(f"Error transitioning to pre-planning: {e}")
            return False
    
    def _convert_tasks_to_feature_groups(self, tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Convert hierarchical tasks to feature groups for pre-planning.
        
        This method transforms the hierarchical task structure from the design phase
        into the format required by the pre-planning phase. It preserves the task hierarchy
        while adding necessary metadata for implementation planning.
        
        Args:
            tasks: List of tasks from implementation_progress.json
            
        Returns:
            List of feature groups in pre-planning format
        """
        # Group tasks by their parent feature (first-level tasks)
        task_groups = {}
        subtask_details = {}  # Cache for storing details about subtasks
        
        # First pass: categorize tasks and gather details
        for task in tasks:
            task_id = task.get('id', '')
            task_desc = task.get('description', '')
            task_details = task.get('details', '')
            task_status = task.get('status', 'pending')
            
            # Check if this is a top-level task (no decimal in ID)
            if '.' not in task_id:
                # Create a new feature group for this top-level task
                task_groups[task_id] = {
                    "group_name": task_desc,
                    "group_description": task_details,
                    "group_id": task_id,
                    "status": task_status,
                    "features": [],
                    "subtasks": []
                }
            else:
                # This is a subtask
                parts = task_id.split('.')
                parent_id = parts[0]
                
                # Store detailed info about this subtask
                subtask_details[task_id] = {
                    "id": task_id,
                    "description": task_desc,
                    "details": task_details,
                    "status": task_status,
                    "depth": len(parts) - 1  # How deep in the hierarchy
                }
                
                # Add to parent's subtasks
                if parent_id in task_groups:
                    task_groups[parent_id]["subtasks"].append(task)
        
        # Convert task groups to feature groups
        feature_groups = []
        for task_id, group_data in task_groups.items():
            # Create features from the subtasks
            features = []
            
            # Group subtasks by their immediate parent (level 2 tasks)
            level2_tasks = {}
            for subtask in group_data["subtasks"]:
                subtask_id = subtask.get('id', '')
                if subtask_id.count('.') == 1:  # Level 2 task (e.g. "1.1")
                    level2_tasks[subtask_id] = {
                        "task": subtask,
                        "children": []
                    }
                elif subtask_id.count('.') > 1:  # Level 3+ task (e.g. "1.1.1")
                    parent_prefix = '.'.join(subtask_id.split('.')[:2])  # Get "1.1" from "1.1.1"
                    if parent_prefix in level2_tasks:
                        level2_tasks[parent_prefix]["children"].append(subtask)
            
            # Create a feature for each level 2 task
            for level2_id, level2_data in level2_tasks.items():
                level2_task = level2_data["task"]
                
                # Extract system design elements from children
                code_elements = []
                interfaces = []
                data_flows = []
                
                # Process children to extract code elements and other design info
                for child in level2_data["children"]:
                    child_desc = child.get('description', '').lower()
                    
                    # Try to identify what kind of component this is
                    if any(keyword in child_desc for keyword in ['class', 'function', 'method', 'component']):
                        code_elements.append({
                            "name": child.get('description', ''),
                            "type": "class" if "class" in child_desc else 
                                   "function" if "function" in child_desc else
                                   "method" if "method" in child_desc else
                                   "component",
                            "description": child.get('details', ''),
                            "id": child.get('id', '')
                        })
                    elif any(keyword in child_desc for keyword in ['api', 'endpoint', 'interface', 'route']):
                        interfaces.append({
                            "name": child.get('description', ''),
                            "description": child.get('details', ''),
                            "id": child.get('id', '')
                        })
                    elif any(keyword in child_desc for keyword in ['data', 'flow', 'store', 'model']):
                        data_flows.append({
                            "name": child.get('description', ''),
                            "description": child.get('details', ''),
                            "id": child.get('id', '')
                        })
                
                # Create the feature from the level 2 task
                feature = {
                    "name": level2_task.get('description', f"Feature {level2_task.get('id', 'unknown')}"),
                    "description": level2_task.get('details', ''),
                    "task_id": level2_task.get('id', ''),
                    "files_affected": [],
                    "test_requirements": {
                        "unit_tests": [],
                        "integration_tests": []
                    },
                    "dependencies": {
                        "external_libraries": [],
                        "internal_modules": []
                    },
                    "risk_assessment": {
                        "complexity": "medium",
                        "security_concerns": [],
                        "backwards_compatibility": True
                    },
                    "system_design": {
                        "code_elements": code_elements,
                        "data_flow": data_flows,
                        "interfaces": interfaces
                    }
                }
                features.append(feature)
            
            # If no level 2 tasks, create a single feature from the main task
            if not features:
                features = [{
                    "name": group_data.get("group_name", f"Feature {task_id}"),
                    "description": group_data.get("group_description", ""),
                    "task_id": task_id,
                    "files_affected": [],
                    "test_requirements": {
                        "unit_tests": [],
                        "integration_tests": []
                    },
                    "dependencies": {
                        "external_libraries": [],
                        "internal_modules": []
                    },
                    "risk_assessment": {
                        "complexity": "medium",
                        "security_concerns": [],
                        "backwards_compatibility": True
                    },
                    "system_design": {
                        "code_elements": [],
                        "data_flow": [],
                        "interfaces": []
                    }
                }]
            
            # Add the feature group
            feature_group = {
                "group_name": group_data.get("group_name", f"Feature Group {task_id}"),
                "group_description": group_data.get("group_description", ""),
                "group_id": task_id,
                "features": features
            }
            feature_groups.append(feature_group)
        
        return feature_groups
