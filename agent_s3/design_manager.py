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
import logging
from typing import Dict, Any, Tuple

from agent_s3.tools.file_tool import FileTool
from agent_s3.router_agent import RouterAgent

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
        
        # Append any additional context if needed in the future
        
        # Call LLM for response
        response = self.llm.call_llm_agent("designer", self.conversation_history)
        
        # Add response to conversation history
        if response:
            self.conversation_history.append({"role": "assistant", "content": response})
        
        
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
        # Write conversation history to design file in a simple format
        content = f"# System Design: {self.design_objective}\n\n"
        content += "## Conversation\n\n"
        for msg in self.conversation_history:
            content += f"{msg['role']}: {msg['content']}\n"

        design_path = os.path.join(os.getcwd(), "design.txt")
        success, message = self.file_tool.write_file(design_path, content)

        if success:
            return True, "Design written to design.txt."
        return False, f"Failed to write design: {message}"
    
    
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
            print("Implementation phase selected.")
            if self.coordinator and hasattr(self.coordinator, "start_pre_planning_from_design"):
                self.coordinator.start_pre_planning_from_design("design.txt")
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

