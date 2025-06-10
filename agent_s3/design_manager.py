"""Design Manager for handling system design conversations and feature decomposition.

This module provides functionality for:
1. Analyzing design objectives based on industry best practices
2. Facilitating clarification questions for ambiguous requirements
3. Decomposing systems into distinct, single-concern features
4. Managing the design conversation flow and termination
5. Writing the final design to a structured file
6. Transitioning to local deployment of the designed system
7. Ensuring conversation history is reset for each new design session

Each new /design or /design-auto command automatically resets the conversation
history to ensure that design sessions do not carry over context from previous
design sessions.
"""

import os
import logging
import re
from typing import Dict, Any, Tuple, List

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
        # Use the coordinator's router_agent if available, otherwise create new one
        self.llm = coordinator.router_agent if coordinator and hasattr(coordinator, 'router_agent') else RouterAgent()
        self.file_tool = FileTool()

        # Initialize termination signal detection variables
        self.consecutive_feature_messages = 0
        self.features_identified = False
        self.user_explicitly_requested_completion = False
        
        # Get configuration for LLM calls
        self.config = self._get_llm_config()
        
        logger.info("DesignManager initialized with clean conversation state")

    def _get_llm_config(self) -> Dict[str, Any]:
        """Get LLM configuration with API keys."""
        import os
        from dotenv import load_dotenv
        
        # Load environment variables
        load_dotenv()
        
        return {
            "openrouter_key": os.getenv("OPENROUTER_KEY"),
            "openai_key": os.getenv("OPENAI_API_KEY"),
            "max_retries": 3,
            "llm_connection_timeout": 10,  # Connection timeout: 10 seconds
            "llm_read_timeout": 90,        # Read timeout: 90 seconds (shorter for design)
            "backoff_multiplier": 1.5,
            "failure_threshold": 3
        }
    
    def _create_scratchpad(self):
        """Create a simple scratchpad for logging."""
        class SimpleScratchpad:
            def log(self, category: str, message: str, level: str = "info", **kwargs):
                logger.info(f"[{category}] {message}")
        
        return SimpleScratchpad()

    def reset_conversation(self) -> None:
        """Reset conversation history and design state for a new design session.
        
        This method ensures that each new /design or /design-auto command
        starts with a clean slate, preventing conversation history from
        carrying over between different design sessions.
        """
        self.conversation_history = []
        self.design_objective = ""
        self.consecutive_feature_messages = 0
        self.features_identified = False
        self.user_explicitly_requested_completion = False
        
        logger.info("Design conversation history and state reset for new session")

    def start_design_conversation(self, design_objective: str) -> str:
        """Initiate a design conversation with the specified objective.
        
        Args:
            design_objective: The user's design objective/request
            
        Returns:
            The LLM's initial response
        """
        # Reset conversation history and state for new design session
        self.reset_conversation()
        self.design_objective = design_objective

        # Create the initial prompt
        system_prompt = self._get_system_prompt()
        user_prompt = f"Design Objective: {design_objective}\n\nAnalyze this design objective and enhance it based on industry best practices. Ask clarification questions if there are missing details or ambiguities."

        # Add to conversation history
        self.conversation_history.append({"role": "system", "content": system_prompt})
        self.conversation_history.append({"role": "user", "content": user_prompt})

        # Call LLM to get initial response
        response = self.llm.call_llm_by_role(
            role="designer",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            config=self.config,
            scratchpad=self._create_scratchpad()
        )

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
        response = self.llm.call_llm_by_role(
            role="designer",
            system_prompt="",  # System prompt already in conversation history
            user_prompt=user_message,
            config=self.config,
            scratchpad=self._create_scratchpad()
        )

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

            last_ai_message_lower = last_ai_message.lower()
            if any(indicator.lower() in last_ai_message_lower for indicator in feature_indicators):
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
                if any(indicator.lower() in last_ai_message_lower for indicator in conclusion_indicators):
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

    def _parse_feature_content(self, feature_num: str, feature_content: str) -> Dict[str, Any]:
        """Parse narrative feature content into structured JSON format.
        
        Args:
            feature_num: The feature number (e.g., "1", "2")  
            feature_content: The raw feature content from conversation
            
        Returns:
            Structured feature dictionary matching preplanning schema
        """
        # Extract feature name from the beginning of content
        name_match = re.search(r'^([^*\n]+)', feature_content.strip())
        feature_name = name_match.group(1).strip() if name_match else f"Feature {feature_num}"
        
        # Build the base feature structure
        feature = {
            "name": feature_name,
            "description": "",
            "files_affected": [],
            "test_requirements": {
                "unit_tests": [],
                "property_based_tests": [],
                "acceptance_tests": [],
                "test_strategy": {
                    "coverage_goal": "85% line coverage",
                    "ui_test_approach": "End-to-end tests for critical user flows"
                }
            },
            "dependencies": {
                "internal": [],
                "external": [],
                "feature_dependencies": []
            },
            "risk_assessment": {
                "critical_files": [],
                "potential_regressions": [],
                "backward_compatibility_concerns": [],
                "mitigation_strategies": [],
                "required_test_characteristics": {
                    "required_types": ["unit", "integration"],
                    "required_keywords": [],
                    "suggested_libraries": []
                }
            },
            "system_design": {
                "overview": f"Implementation of {feature_name}",
                "code_elements": [],
                "data_flow": "Standard data flow",
                "key_algorithms": []
            }
        }
        
        # Extract Purpose & Responsibility for description
        purpose_match = re.search(r'\*\s+\*\*Purpose & Responsibility\*\*:\s*([^*]+?)(?=\*\s+\*\*|$)', feature_content)
        if purpose_match:
            feature["description"] = purpose_match.group(1).strip()
        else:
            # Fallback to first line or basic description
            feature["description"] = f"Implementation of {feature_name}"
        
        # Extract Data Requirements to infer files_affected
        data_match = re.search(r'\*\s+\*\*Data Requirements\*\*:\s*([^*]+?)(?=\*\s+\*\*|$)', feature_content)
        if data_match:
            data_content = data_match.group(1).strip()
            # Infer likely files based on feature name and data requirements
            normalized_name = feature_name.lower().replace(' ', '_').replace('-', '_')
            feature["files_affected"] = [
                f"src/{normalized_name}.py",
                f"tests/test_{normalized_name}.py"
            ]
        else:
            # Default files for any feature
            normalized_name = feature_name.lower().replace(' ', '_').replace('-', '_')
            feature["files_affected"] = [f"src/{normalized_name}.py"]
        
        # Extract Dependencies
        deps_match = re.search(r'\*\s+\*\*Dependencies\*\*:\s*([^*]+?)(?=\*\s+\*\*|$)', feature_content)
        if deps_match:
            deps_content = deps_match.group(1).strip()
            # Parse dependencies - look for external libraries or internal components
            if "database" in deps_content.lower():
                feature["dependencies"]["external"].append("database")
            if "api" in deps_content.lower():
                feature["dependencies"]["external"].append("api_client")
        
        # Extract Functional Requirements for system design
        func_match = re.search(r'\*\s+\*\*Functional Requirements\*\*:\s*([^*]+?)(?=\*\s+\*\*|$)', feature_content, re.DOTALL)
        if func_match:
            func_content = func_match.group(1).strip()
            
            # Create basic code elements based on functional requirements
            normalized_name = feature_name.lower().replace(' ', '_').replace('-', '_')
            element_id = f"{normalized_name}_main_function"
            
            feature["system_design"]["code_elements"] = [{
                "element_type": "function",
                "name": f"{normalized_name}_handler", 
                "element_id": element_id,
                "signature": f"def {normalized_name}_handler(data: Dict[str, Any]) -> Dict[str, Any]:",
                "description": f"Main handler function for {feature_name}",
                "key_attributes_or_methods": [],
                "target_file": feature["files_affected"][0] if feature["files_affected"] else f"src/{normalized_name}.py"
            }]
            
            # Update system design overview
            feature["system_design"]["overview"] = f"Handles {feature_name.lower()} functionality through main handler function"
            
            # Basic unit test targeting the code element
            feature["test_requirements"]["unit_tests"] = [{
                "description": f"Test {normalized_name}_handler function with valid inputs",
                "target_element": f"{normalized_name}_handler",
                "target_element_id": element_id,
                "inputs": ["valid_data: Dict with required fields"],
                "expected_outcome": "Returns success response with processed data"
            }]
        
        # Extract Business Rules for risk assessment
        rules_match = re.search(r'\*\s+\*\*Business Rules\*\*:\s*([^*]+?)(?=\*\s+\*\*|$)', feature_content)
        if rules_match:
            rules_content = rules_match.group(1).strip()
            if "validation" in rules_content.lower():
                feature["risk_assessment"]["mitigation_strategies"].append("Implement comprehensive input validation")
            if "security" in rules_content.lower():
                feature["risk_assessment"]["mitigation_strategies"].append("Apply security best practices")
        
        return feature

    def _extract_features_from_conversation(self) -> List[str]:
        """Parse conversation history to extract detailed features.
        
        Returns:
            List of detailed feature descriptions
        """
        features = []
        
        # Find messages that contain feature breakdowns
        for msg in self.conversation_history:
            if msg.get("role") == "assistant":
                content = msg.get("content", "")
                
                # Look for detailed feature patterns in the content
                if "**Feature" in content and "Purpose & Responsibility" in content:
                    # Extract complete feature blocks including all details
                    # Pattern: **Feature X: Title**
                    feature_blocks = re.split(r'\*\*Feature\s+(\d+):\s+([^*]+)\*\*', content)
                    
                    # Skip the first split (content before first feature)
                    for i in range(1, len(feature_blocks), 3):
                        if i + 2 < len(feature_blocks):
                            feature_num = feature_blocks[i]
                            feature_title = feature_blocks[i + 1].strip()
                            feature_content = feature_blocks[i + 2]
                            
                            # Build the complete feature description
                            full_feature = f"**Feature {feature_num}: {feature_title}**"
                            
                            # Add all the detailed content
                            if feature_content.strip():
                                full_feature += f"\n{feature_content.strip()}"
                            
                            features.append(full_feature)
                    
                    # If we found features, return them
                    if features:
                        return features
                
                # Also try alternative patterns for different formats
                elif ("I. Core Platform" in content or "**I. Core Platform" in content) and "Purpose & Responsibility" in content:
                    # Split by major sections and then extract features within each
                    sections = re.split(r'\*\*([IVX]+\.\s+[^*]+)\*\*', content)
                    
                    for section_content in sections:
                        # Look for individual features within sections
                        if "**Feature" in section_content and "Purpose & Responsibility" in section_content:
                            individual_features = re.split(r'\*\*Feature\s+(\d+):\s+([^*]+)\*\*', section_content)
                            
                            for j in range(1, len(individual_features), 3):
                                if j + 2 < len(individual_features):
                                    feature_num = individual_features[j]
                                    feature_title = individual_features[j + 1].strip()
                                    feature_content = individual_features[j + 2]
                                    
                                    full_feature = f"**Feature {feature_num}: {feature_title}**"
                                    if feature_content.strip():
                                        full_feature += f"\n{feature_content.strip()}"
                                    
                                    features.append(full_feature)
                    
                    if features:
                        return features
        
        # Fallback: Extract basic numbered features if detailed ones not found
        patterns = [
            re.compile(r"(?:Feature|Task|Component|Module|Step)?\s*(\d+(?:\.\d+)*)[:.)\-\s]+(.+)", re.IGNORECASE),
            re.compile(r"(\d+(?:\.\d+)*)\.\s+(.+)")
        ]

        seen = set()

        for msg in self.conversation_history:
            if msg.get("role") not in {"assistant", "user"}:
                continue

            for line in msg.get("content", "").splitlines():
                line = line.strip()
                for pattern in patterns:
                    match = pattern.match(line)
                    if match:
                        description = match.group(2).strip()
                        key = description.lower()
                        if description and key not in seen:
                            features.append(description)
                            seen.add(key)
                        break

        return features

    def write_design_to_file(self) -> Tuple[bool, str]:
        """Extract design features from conversation and write to design.txt.
        
        Returns:
            Tuple of (success_flag, message)
        """
        # Write detailed features for comprehensive documentation
        content = f"# System Design: {self.design_objective}\n\n"

        features = self._extract_features_from_conversation()
        if features:
            content += "## Detailed Features\n\n"
            for idx, feature in enumerate(features, 1):
                # Add proper spacing between features for readability
                if idx > 1:
                    content += "\n---\n\n"
                content += f"{feature}\n"
            content += "\n"
        else:
            # Fallback if no features extracted
            content += "## Features\n\n"
            content += "No detailed features were extracted from the conversation.\n\n"

        content += "## Design Conversation History\n\n"
        for msg in self.conversation_history:
            role = msg.get("role", "")
            message = msg.get("content", "")
            
            # Filter out detailed feature content from conversation history to avoid duplication
            if role == "assistant" and self._contains_detailed_features(message):
                # Replace detailed features with a summary reference
                filtered_message = self._filter_detailed_features_from_message(message)
                content += f"**{role.upper()}:**\n{filtered_message}\n\n---\n\n"
            else:
                content += f"**{role.upper()}:**\n{message}\n\n---\n\n"

        design_path = os.path.join(os.getcwd(), "design.txt")
        success, message = self.file_tool.write_file(design_path, content)

        if success:
            return True, "Design written to design.txt with detailed features."
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

        if self.coordinator and hasattr(self.coordinator, 'prompt_moderator'):
            prompt_mod = self.coordinator.prompt_moderator
            impl_choice = prompt_mod.ask_yes_no_question(impl_message)
        else:
            if self.coordinator and hasattr(self.coordinator, 'scratchpad'):
                self.coordinator.scratchpad.log("DesignManager", impl_message)
            impl_choice = input(impl_message).strip().lower() in ["yes", "y", "true", "1"]

        deploy_choice = False

        if impl_choice:
            print("Implementation phase selected.")
        else:
            # If user doesn't want implementation, ask about deployment
            deploy_message = (
                "Would you like to deploy the application locally instead? (yes/no): "
            )

            if self.coordinator and hasattr(self.coordinator, 'prompt_moderator'):
                prompt_mod = self.coordinator.prompt_moderator
                deploy_choice = prompt_mod.ask_yes_no_question(deploy_message)
            else:
                if self.coordinator and hasattr(self.coordinator, 'scratchpad'):
                    self.coordinator.scratchpad.log("DesignManager", deploy_message)
                deploy_choice = input(deploy_message).strip().lower() in ["yes", "y", "true", "1"]

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
        You are an expert system designer tasked with helping the user design a comprehensive software system.
        
        Your responsibilities:
        1. Analyze the design objective and enhance it based on industry best practices
        2. Ask clarification questions if there are missing details or ambiguities
        3. Decompose the system into distinct, thoroughly detailed features that completely describe the entire system
        
        Follow these guidelines:
        - Focus on high-level architecture and component design, not implementation details or code
        - Apply relevant design patterns and principles (SOLID, microservices, etc.)
        - Consider scalability, maintainability, and security in your design
        - Break down complex systems into coherent, single-responsibility components
        - Identify data flows and key interfaces between components
        - Consider error handling, logging, and monitoring requirements
        
        CRITICAL FEATURE DESIGN REQUIREMENTS:
        When you provide the final feature breakdown, each feature must be extremely detailed and comprehensive:
        
        1. **Complete System Coverage**: The features when combined together must thoroughly and completely describe the ENTIRE system with no gaps. Every aspect of the system should be covered by at least one feature.
        
        2. **Detailed Feature Descriptions**: Each feature should include:
           - **Purpose & Responsibility**: What the feature does and why it's needed
           - **Functional Requirements**: Specific behaviors, inputs, outputs, and operations
           - **Data Requirements**: What data it handles, stores, or processes
           - **User Interactions**: How users interact with this feature (if applicable)
           - **Integration Points**: How it connects with other features/components
           - **Business Rules**: Any logic, validation, or constraints that apply
           - **Non-Functional Requirements**: Performance, security, scalability considerations
           - **Dependencies**: What other features or external systems it relies on
           - **Success Criteria**: How to know the feature is working correctly
        
        3. **Comprehensive Scope**: Include ALL necessary features such as:
           - Core business functionality
           - User authentication and authorization
           - Data persistence and management
           - User interface components
           - API endpoints and communication
           - Error handling and validation
           - Logging and monitoring
           - Configuration and settings
           - Security measures
           - Testing and quality assurance
           - Deployment and infrastructure concerns
           - Documentation and help systems
        
        4. **Granular Detail**: Provide enough detail that a developer could understand exactly what needs to be built without writing any code. Think of this as a comprehensive specification document.
        
        5. **No Implementation Details**: Describe WHAT needs to be built and HOW it should behave, but do not include actual code, specific technology choices, or implementation approaches.
        
        When the design is complete, you'll enumerate these distinct, thoroughly detailed features that can be implemented iteratively. Each feature should be self-contained enough to be implemented and tested independently while contributing to the complete system functionality.
        """

    def _contains_detailed_features(self, message: str) -> bool:
        """Check if a message contains detailed feature descriptions.
        
        Args:
            message: The message content to check
            
        Returns:
            True if message contains detailed features, False otherwise
        """
        # Look for patterns that indicate detailed feature content
        detailed_feature_indicators = [
            "**Purpose & Responsibility**:",
            "**Functional Requirements**:",
            "**Data Requirements**:",
            "**User Interactions**:",
            "**Integration Points**:",
            "**Business Rules**:",
            "**Non-Functional Requirements**:",
            "**Dependencies**:",
            "**Success Criteria**:"
        ]
        
        # Check if the message contains multiple detailed feature indicators
        indicator_count = sum(1 for indicator in detailed_feature_indicators if indicator in message)
        return indicator_count >= 3  # Consider it detailed if it has 3+ detailed sections
    
    def _filter_detailed_features_from_message(self, message: str) -> str:
        """Filter out detailed feature content from a message, keeping summary info.
        
        Args:
            message: The message content to filter
            
        Returns:
            Filtered message with detailed features replaced by summary
        """
        # Look for comprehensive feature breakdown patterns
        if "**Comprehensive Feature Breakdown:**" in message:
            # Keep the introduction but replace detailed features with a reference
            parts = message.split("**Comprehensive Feature Breakdown:**")
            if len(parts) > 1:
                intro = parts[0].strip()
                summary = "**Comprehensive Feature Breakdown:**\n\n[Detailed features moved to 'Detailed Features' section above for better organization]\n\nThis comprehensive feature breakdown covers the core functionality for the requested system with proper component separation and detailed specifications."
                return f"{intro}\n\n{summary}" if intro else summary
        
        # If it contains detailed features but not the comprehensive breakdown pattern
        if self._contains_detailed_features(message):
            # Replace detailed feature content with a summary reference
            return "[Detailed feature content moved to 'Detailed Features' section above to avoid duplication]"
        
        return message

