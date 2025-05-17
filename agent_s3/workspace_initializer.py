"""Workspace Initializer component for Agent-S3.

Responsible for initializing, validating, and managing workspace files.
"""

import os
import logging
from pathlib import Path
from typing import Tuple, Dict, Any, Optional

class WorkspaceInitializer:
    """Handles workspace initialization, validation, and essential file management."""

    def __init__(self, config, file_tool=None, scratchpad=None, prompt_moderator=None, tech_stack=None):
        """Initialize the workspace initializer.
        
        Args:
            config: Configuration object
            file_tool: Optional FileTool instance
            scratchpad: Optional EnhancedScratchpadManager for logging
            prompt_moderator: Optional PromptModerator for user notifications
            tech_stack: Optional dictionary with tech stack information
        """
        self.config = config
        self.file_tool = file_tool
        self.scratchpad = scratchpad
        self.prompt_moderator = prompt_moderator
        self.tech_stack = tech_stack
        self.workspace_path = Path.cwd()
        self.github_dir = self.workspace_path / ".github"
        self.guidelines_file = self.github_dir / "copilot-instructions.md"
        self.readme_file = self.workspace_path / "README.md"
        self.llm_json_file = self.workspace_path / "llm.json"
        self.is_workspace_valid = False
        self.validation_failure_reason = None
    
    def initialize_workspace(self) -> bool:
        """Initialize the workspace by checking essential files and creating defaults if necessary.
        
        Returns:
            Boolean indicating if workspace is valid
        """
        logging.info("Initializing workspace...")
        self._log("Initializing workspace...")
        
        # Create required directories
        self.github_dir.mkdir(exist_ok=True)
        
        # Validate README.md
        if not self.readme_file.exists():
            self.validation_failure_reason = "README.md not found"
            self._notify_user("WARNING: README.md not found. Creating essential files but some features may be limited.", level="warning")
            self.is_workspace_valid = False
        else:
            # Optional LLM-based README.md structure validation
            if hasattr(self, '_validate_workspace_files'):
                try:
                    valid = self._validate_workspace_files()
                    if not valid:
                        self.validation_failure_reason = "README.md structure validation failed"
                        self._notify_user("README.md structure validation failed.", level="error")
                        self.is_workspace_valid = False
                        # We continue with initialization even with invalid README.md
                    else:
                        self.is_workspace_valid = True
                except Exception as e:
                    self._log(f"Error validating README.md: {e}")
                    self.validation_failure_reason = f"Error validating README.md: {str(e)}"
                    self._notify_user("Error validating README.md structure.", level="error")
                    self.is_workspace_valid = False
                    # We continue with initialization even with README.md validation error
            else:
                # If no validation method exists, consider workspace valid with README.md present
                self.is_workspace_valid = True
        
        # Create personas.md if it doesn't exist
        personas_path = self.workspace_path / "personas.md"
        if not personas_path.exists():
            try:
                self._log("Creating personas.md...")
                personas_result = self.execute_personas_command()
                self._log(personas_result)
            except Exception as e:
                self._log(f"Error creating personas.md: {e}", level="error")
        
        # Create copilot-instructions.md if it doesn't exist
        if not self.guidelines_file.exists():
            try:
                self._log("Creating copilot-instructions.md...")
                guidelines_result = self.execute_guidelines_command()
                self._log(guidelines_result)
            except Exception as e:
                self._log(f"Error creating copilot-instructions.md: {e}", level="error")
        
        # Create llm.json if it doesn't exist
        if not self.llm_json_file.exists():
            try:
                self._log("Creating llm.json...")
                llm_status, llm_msg = self._ensure_llm_config()
                self._log(llm_msg)
            except Exception as e:
                self._log(f"Error creating llm.json: {e}", level="error")
        
        # Log initialization status
        if self.is_workspace_valid:
            self._log("Core workspace initialization successful.")
            logging.info("Core workspace initialization completed successfully.")
        else:
            self._log(f"Core workspace validation failed: {self.validation_failure_reason}", level="warning")
            logging.warning(f"Core workspace validation failed: {self.validation_failure_reason}")
        
        return self.is_workspace_valid
    
    def execute_personas_command(self) -> str:
        """Creates the personas.md file with default content.
        
        Returns:
            A string indicating success or failure message
        """
        try:
            personas_path = Path(self.config.config.get("workspace_path", ".")) / "personas.md"
            
            # Fallback to hardcoded default content
            content = """**Note:** These four personas will have a structured debate until they all agree on a final prompt for the AI coding agent. The prompt will contain a summary of the feature, a function-level step by step execution plan. It will ensure that unit and integration tests are created and executed after code generation. They should cover the happy path scenarios and corner cases. Logical consistency check fo the final feature is done.

## Business Development Manager
**Background & Expertise:**
- 8 years in SaaS product strategy and go‑to‑market
- Deep network of end‑user interviews and market‑research data
- Fluent in articulating ROI, competitive positioning, and customer pain points

**Primary Goal:**
Clarify **why** we're building this feature, whom it serves, and what real‑world scenarios it must cover.

**Contributions:**
- Frames user stories and acceptance criteria
- Resolves any ambiguity around business value or use cases
- Prioritizes sub‑features against revenue impact and roadmap

---

## Expert Coder
**Background & Expertise:**
- Senior Software Engineer with 10+ years of full‑stack experience (Node JS, React, Python)
- Skilled at breaking high‑level requirements into concrete implementation steps
- Passionate about scalable architectures and clean API design

**Primary Goal:**
Define **how** the feature will be built—step by step, with tech choices, data models, integration points, and up to file/module breakdown—without writing full implementation code during the discussion.

**Contributions:**
- Drafts an end‑to‑end implementation plan, including module and file‑level breakdown
- Proposes database schema changes, API contracts, and component/class outlines
- Estimates effort, flags dependencies, and suggests any necessary tooling
- Provides enough detail to guide precise code development later, but stops short of full code snippets during brainstorming

---

## Reviewer
**Background & Expertise:**
- 7 years reviewing production codebases in agile teams
- Expert in detecting logical gaps, edge cases, and architectural anti‑patterns
- Champions maintainability, readability, and test coverage

**Primary Goal:**
Ensure the proposed solution is **logically consistent** and covers all functional scenarios, from high‑level flows down to file/module level structure—without expecting full code at this phase.

**Contributions:**
- Critically examines data flows, error‑handling paths, and concurrency concerns
- Suggests unit/integration test cases to validate each behavior
- Verifies that every requirement is traceable to code tasks and mapped to specific files or modules
- Validates that the plan includes both high‑level architecture and file/function‑level breakdown without full code implementations

---

## Validator
**Background & Expertise:**
- 5 years in QA, security auditing, and accessibility compliance
- Deep knowledge of OWASP Top 10, WCAG accessibility standards, and internal style guides
- Advocates for automated linting, CI/CD checks, and deploy‑gate rules

**Primary Goal:**
Confirm the solution adheres to **best practices** and organizational guidelines in security, performance, accessibility, and internal policy.

**Contributions:**
- Reviews API specifications against security checklist (input validation, auth, rate limits)
- Checks UI/UX mockups for accessibility (contrast, keyboard nav, ARIA roles)
- Ensures compliance with company guidelines in `.github/copilot-instructions.md`
- Verifies alignment with feature definitions and constraints in `README.md`, unless modifications are explicitly requested
- Enforces security standards (OWASP Top 10), performance goals, and maintainability
"""
            
            # Write the file using file_tool or direct file operation
            if self.file_tool:
                self.file_tool.write_file(str(personas_path), content)
            else:
                with open(personas_path, "w", encoding="utf-8") as f:
                    f.write(content)
            
            self._log(f"Created personas.md at {personas_path}")
            return f"Successfully created personas.md at {personas_path}"
        
        except Exception as e:
            error_msg = f"Error creating personas.md: {str(e)}"
            self._log(error_msg, level="error")
            return error_msg
    
    def execute_guidelines_command(self) -> str:
        """Creates the copilot-instructions.md file with default content.
        
        Returns:
            A string indicating success or failure message
        """
        try:
            # Use existing functionality to get guidelines content
            guidelines_content = self._get_default_guidelines()
            guidelines_path = self.github_dir / "copilot-instructions.md"
            
            # Analyze tech stack to enhance guidelines if available
            if self.tech_stack:
                # Enhance default guidelines with tech stack-specific recommendations
                enhanced_content = self._enhance_guidelines_with_tech_stack(guidelines_content)
                if enhanced_content:
                    guidelines_content = enhanced_content
            
            # Write the file using file_tool or direct file operation
            if self.file_tool:
                self.file_tool.write_file(str(guidelines_path), guidelines_content)
            else:
                with open(guidelines_path, "w", encoding="utf-8") as f:
                    f.write(guidelines_content)
            
            self._log(f"Created copilot-instructions.md at {guidelines_path}")
            return f"Successfully created copilot-instructions.md at {guidelines_path}"
        
        except Exception as e:
            error_msg = f"Error creating copilot-instructions.md: {str(e)}"
            self._log(error_msg, level="error")
            return error_msg
    
    def _ensure_llm_config(self) -> Tuple[bool, str]:
        """Ensures the llm.json file exists with proper content.
        
        Returns:
            Tuple of (success_status, message)
        """
        try:
            if not self.llm_json_file.exists():
                # Get default content
                content = self._get_llm_json_content()
                
                # Write file
                if self.file_tool:
                    self.file_tool.write_file(str(self.llm_json_file), content)
                else:
                    with open(self.llm_json_file, "w", encoding="utf-8") as f:
                        f.write(content)
                
                return True, f"Created default LLM configuration at {self.llm_json_file}"
            else:
                return True, f"LLM configuration already exists at {self.llm_json_file}"
        except Exception as e:
            return False, f"Error creating LLM configuration: {str(e)}"
    
    def _get_default_guidelines(self) -> str:
        """Returns the default coding guidelines content."""
        return """# GitHub Copilot Instructions

You are an AI assistant for development projects. Help with code generation, analysis, troubleshooting, and project guidance.

## Core Development Criteria

The following criteria should be applied to both code generation and code analysis:

### Security
- OWASP Top 10 vulnerabilities  
- Authentication/Authorization issues with proper session handling
- Data protection and sensitive information exposure
- Input validation and proper escaping using appropriate validation libraries
- Content Security Policy (CSP) implementation with nonces
- Proper file upload security (MIME validation, size limits, path validation)
- API key protection and secure credential storage
- Secure HTTP headers
- Rate limiting for sensitive operations
- Server-side verification of client security measures
- Implement principle of least privilege in all access controls
- Use parameterized queries to prevent SQL injection
- Apply defense in depth with multiple security layers
- Implement secure password handling with proper hashing (bcrypt/Argon2)
- Regular security audit procedures and dependency scanning

### Performance
- Time complexity (aim for O(n) or better where practical)
- Resource usage optimization, especially for media content
- Database query efficiency:
  - Avoid N+1 queries
  - Implement proper pagination
  - Use strategic indices
- Memory management
- Asset optimization
- Appropriate API caching headers
- Debounced or throttled user inputs where appropriate
- Enable code splitting and lazy loading for large applications
- Implement proper resource hints (preconnect, preload, prefetch)
- Optimize critical rendering path
- Use efficient state management approaches
- Implement proper request batching and memoization
- Consider server-side rendering (SSR) or static site generation (SSG) when appropriate

### Code Quality
- SOLID principles for modularity
- Clean code practices with clear naming conventions
- Comprehensive error handling with recovery strategies
- Thorough documentation for all exported functions
- Adherence to project-specific guidelines
- Alignment with defined user stories and acceptance criteria
- No fallback data for failed operations
- Testable code structure
- Apply DRY (Don't Repeat Yourself) principle while avoiding premature abstraction
- Use consistent code formatting with automated tools
- Implement proper versioning for APIs
- Follow semantic versioning for packages
- Use meaningful commit messages with conventional commits format
- Apply continuous integration best practices
- Prioritize immutability when appropriate

### Accessibility
- WCAG 2.1 Level AA compliance
- Semantic HTML elements
- Sufficient color contrast
- Keyboard navigation support
- Proper ARIA attributes
- Alternative text for images
- Focus management for interactive elements
- Support for screen readers and assistive technologies
- Proper heading hierarchy (h1-h6)
- Skip navigation links for keyboard users
- Appropriate text resizing and zooming support
- Reduced motion options for vestibular disorders
- Adequate timeout settings for form submissions
- Proper form labels and error states

## Assistance Categories

### 1. Code Generation
When generating code, apply all the core criteria above plus:

- Follow established project structure and naming conventions
- Use appropriate type definitions for strongly-typed languages
- Create comprehensive documentation comments for all exported functions
- Include file headers on all new files
- Use appropriate design patterns based on the framework in use
- Separate concerns by using appropriate architecture for the framework
- Organize by feature directories when appropriate
- Create reusable utilities and hooks
- Centralize constants and types
- Follow idiomatic patterns for the language/framework being used
- Consider backwards compatibility when updating existing code
- Apply progressive enhancement where appropriate
- Implement proper feature detection instead of browser detection
- Design for extension but closed for modification (Open/Closed principle)
- Use dependency injection where appropriate for testability

### 2. Code Analysis
When analyzing code, apply all the core criteria above and report issues according to the format below.

### 3. Troubleshooting Assistance
For troubleshooting, consider these common issues and solutions:

- Database connectivity issues
- Server connectivity issues
- Build errors and dependency problems
- Network and API connection issues
- Environment configuration problems
- Browser compatibility issues
- Memory leaks and performance degradation
- Version conflicts between dependencies
- Cross-origin resource sharing (CORS) issues
- Caching problems
- Asynchronous timing issues
- Environment-specific behavior differences
"""
    
    def _get_llm_json_content(self) -> str:
        """Get the llm.json content exactly as specified in instructions.md."""
        return """[
  {
    "model": "gpt-4o-mini",
    "role": "scaffolder",
    "context_window": 128000,
    "capabilities": ["fast chat","file scaffolding","simple Q&A","documentation generation","code formatting","template creation"],
    "pricing_per_million": {"input":0.15,"output":0.60},
    "api": {"endpoint":"POST https://api.openai.com/v1/chat/completions","auth_header":"Authorization: Bearer $OPENAI_KEY"},
    "example_call": "curl https://api.openai.com/v1/chat/completions \\\\n  -H \\"Authorization: Bearer $OPENAI_KEY\\" \\\\n  -H \\"Content-Type: application/json\\" \\\\n  -d '{\\\"model\\\":\\\"gpt-4o-mini\\\",\\\"messages\\\":[{\\\"role\\\":\\\"user\\\",\\\"content\\\":\\\"Generate a Python CLI project scaffold with pyproject.toml and README\\\"}]}'",
    "use_cases": ["Generate file/project scaffolds","Format or lint code snippets","Quick dev Q&A","Boilerplate tests","Doc stubs"]
  },
  {
    "model": "mistral-7b-instruct",
    "role": "planner",
    "context_window": 32000,
    "capabilities": ["chain-of-thought planning","summarization","error analysis","dependency mapping","refactoring strategy"],
    "pricing_per_million": {"input":0.25,"output":0.25},
    "api": {"endpoint":"POST https://api.mistral.ai/v1/chat/completions","auth_header":"Authorization: Bearer $MISTRAL_KEY"},
    "example_call": "curl https://api.mistral.ai/v1/chat/completions \\\\n  -H \\"Authorization: Bearer $MISTRAL_KEY\\" \\\\n  -H \\"Content-Type: application/json\\" \\\\n  -d '{\\\"model\\\":\\\"mistral-7b-instruct\\\",\\\"messages\\\":[{\\\"role\\\":\\\"user\\\",\\\"content\\\":\\\"Plan a multi-file refactor to extract common utilities into a separate module\\\"}]}'",
    "use_cases": ["Analyze error logs","Generate refactoring plans","Summarize code","Map dependencies","Outline DB migrations"]
  },
  {
    "model": "gemini-2.5-pro",
    "role": "generator",
    "context_window": 1000000,
    "capabilities": ["multi-file code synthesis","function calling","multi-modal inputs","complex algorithm implementation","external API integration"],
    "pricing_per_million": {"free_tier_limit":200000,"paid":{"input":2.50,"output":15.00}},
    "api": {"rest_endpoint":"POST https://us-central1-aiplatform.googleapis.com/v1/projects/PROJECT/locations/LOCATION/publishers/google/models/gemini-2.5-pro:predict"},
    "example_call": "curl -X POST \\\\n  -H \\"Authorization: Bearer $GEMINI_KEY\\" \\\\n  -H \\"Content-Type: application/json\\" \\\\n  https://us-central1-aiplatform.googleapis.com/v1/projects/PROJECT/locations/LOCATION/publishers/google/models/gemini-2.5-pro:predict \\\\n  -d '{\\\"instances\\\":[{\\\"content\\\":\\\"Generate a patch to integrate OAuth2 login across all Flask routes\\\"}]}'",
    "use_cases": ["Generate multi-file patches","Implement complex features","Write end-to-end tests","Refactor large modules","Translate code between languages"]
  }
]"""
    
    def _enhance_guidelines_with_tech_stack(self, base_guidelines: str) -> str:
        """Enhances the default guidelines with tech stack-specific recommendations.
        
        Args:
            base_guidelines: The base guidelines content to enhance
            
        Returns:
            Enhanced guidelines with tech stack-specific recommendations
        """
        try:
            # Skip if tech stack info is not available
            if not self.tech_stack:
                return base_guidelines
                
            # Add tech stack specific sections based on detected technologies
            techs = []
            if 'languages' in self.tech_stack:
                techs.extend(self.tech_stack['languages'])
            if 'frameworks' in self.tech_stack:
                techs.extend(self.tech_stack['frameworks'])
            
            # Don't modify if no technologies detected
            if not techs:
                return base_guidelines
                
            # Basic enhancement: Add tech stack section
            tech_section = "\n\n## Tech Stack Best Practices\n\n"
            for tech in techs:
                tech_name = tech.get('name', '') if isinstance(tech, dict) else tech
                if tech_name:
                    tech_section += f"### {tech_name}\n"
                    tech_section += "- Follow best practices for this technology\n"
                    tech_section += "- Apply proper structure and patterns\n"
                    tech_section += "- Implement appropriate error handling\n\n"
            
            # Append the tech section to the base guidelines
            return base_guidelines + tech_section
        except Exception as e:
            self._log(f"Error enhancing guidelines: {str(e)}", level="error")
            return base_guidelines
    
    def _log(self, message: str, level: str = "info") -> None:
        """Log a message using the scratchpad or default logger.
        
        Args:
            message: The message to log
            level: The log level (info, warning, error)
        """
        if self.scratchpad and hasattr(self.scratchpad, 'log'):
            self.scratchpad.log("WorkspaceInitializer", message, level=level)
        else:
            if level.lower() == "error":
                logging.error(message)
            elif level.lower() == "warning":
                logging.warning(message)
            else:
                logging.info(message)
    
    def _notify_user(self, message: str, level: str = "info") -> None:
        """Notify the user through prompt_moderator if available, otherwise print.
        
        Args:
            message: The message to notify the user with
            level: The notification level (info, warning, error)
        """
        if self.prompt_moderator and hasattr(self.prompt_moderator, 'notify_user'):
            self.prompt_moderator.notify_user(message, level=level)
        else:
            print(message)