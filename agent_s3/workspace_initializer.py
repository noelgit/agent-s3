"""Workspace Initializer for Agent-S3.

This module provides functionality for:
1. Validating workspace structure and requirements
2. Creating essential workspace files and directories
3. Setting up default configuration files
4. Managing workspace-specific guidelines and documentation
"""

import logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


class WorkspaceInitializer:
    """Manages workspace initialization, validation, and essential file creation."""

    def __init__(self, config=None, file_tool=None, scratchpad=None, tech_stack=None):
        """Initialize the WorkspaceInitializer.

        Args:
            config: Configuration manager instance
            file_tool: File tool for file operations
            scratchpad: Scratchpad manager for logging
            tech_stack: Detected tech stack information
        """
        self.config = config
        self.file_tool = file_tool
        self.scratchpad = scratchpad
        self.tech_stack = tech_stack or {}
        self.prompt_moderator = None  # Set later by coordinator
        self.validation_failure_reason = None

    def initialize_workspace(self) -> bool:
        """Initialize the workspace with essential files and directories.

        Returns:
            bool: True if workspace is successfully initialized, False otherwise
        """
        try:
            self._log("Starting workspace initialization...")
            
            # Validate workspace structure
            if not self._validate_workspace():
                return False

            # Create essential directories
            self._create_essential_directories()

            # Create essential files
            self._create_essential_files()

            # Initialize context management system
            self._initialize_context_management()

            self._log("Workspace initialization completed successfully.")
            return True

        except Exception as e:
            error_msg = f"Workspace initialization failed: {e}"
            self._log(error_msg, level="error")
            self.validation_failure_reason = str(e)
            return False

    def execute_guidelines_command(self) -> str:
        """Create or update the copilot-instructions.md file with default content.

        Returns:
            str: Success message indicating guidelines file creation/update
        """
        try:
            self._log("Creating/updating copilot-instructions.md...")
            
            guidelines_path = Path(".github/copilot-instructions.md")
            
            # Create .github directory if it doesn't exist
            guidelines_path.parent.mkdir(exist_ok=True)
            
            # Generate guidelines content based on detected tech stack
            guidelines_content = self._generate_guidelines_content()
            
            # Write the guidelines file
            if self.file_tool:
                result = self.file_tool.create_file(str(guidelines_path), guidelines_content)
                if not result.get("success", False):
                    return f"Failed to create guidelines file: {result.get('error', 'Unknown error')}"
            else:
                # Fallback to direct file writing
                with open(guidelines_path, 'w', encoding='utf-8') as f:
                    f.write(guidelines_content)
            
            self._log(f"Guidelines file created/updated at {guidelines_path}")
            return f"Guidelines file created/updated successfully at {guidelines_path}"

        except Exception as e:
            error_msg = f"Failed to create guidelines file: {e}"
            self._log(error_msg, level="error")
            return error_msg

    def _validate_workspace(self) -> bool:
        """Validate that the workspace meets basic requirements.

        Returns:
            bool: True if workspace is valid, False otherwise
        """
        try:
            # Check for README.md (core validation requirement)
            readme_path = Path("README.md")
            if not readme_path.exists():
                self.validation_failure_reason = "README.md not found in workspace"
                self._log("Workspace validation failed: README.md not found", level="warning")
                return False

            # Check if we're in a git repository (optional but recommended)
            git_path = Path(".git")
            if not git_path.exists():
                self._log("Warning: No git repository detected", level="warning")

            self._log("Workspace validation passed")
            return True

        except Exception as e:
            self.validation_failure_reason = f"Validation error: {e}"
            self._log(f"Workspace validation error: {e}", level="error")
            return False

    def _create_essential_directories(self) -> None:
        """Create essential directories if they don't exist."""
        directories = [".github"]
        
        for directory in directories:
            dir_path = Path(directory)
            if not dir_path.exists():
                dir_path.mkdir(parents=True, exist_ok=True)
                self._log(f"Created directory: {directory}")

    def _create_essential_files(self) -> None:
        """Create essential files if they don't exist."""
        try:
            # Create copilot-instructions.md if missing
            guidelines_path = Path(".github/copilot-instructions.md")
            if not guidelines_path.exists():
                self.execute_guidelines_command()

            # Create llm.json if missing
            llm_config_path = Path("llm.json")
            if not llm_config_path.exists():
                self._create_default_llm_config()

        except Exception as e:
            self._log(f"Error creating essential files: {e}", level="error")

    def _create_default_llm_config(self) -> None:
        """Create default LLM configuration file."""
        try:
            import json
            
            default_config = {
                "models": {
                    "default": {
                        "provider": "openrouter",
                        "model": "anthropic/claude-3.5-sonnet",
                        "max_tokens": 8192,
                        "temperature": 0.1
                    }
                },
                "roles": {
                    "coder": "default",
                    "planner": "default",
                    "reviewer": "default"
                }
            }
            
            with open("llm.json", 'w', encoding='utf-8') as f:
                json.dump(default_config, f, indent=2)
            
            self._log("Created default llm.json configuration")

        except Exception as e:
            self._log(f"Failed to create llm.json: {e}", level="error")

    def _initialize_context_management(self) -> None:
        """Initialize the context management system for the workspace."""
        try:
            self._log("Initializing context management system...")
            
            # Detect and analyze codebase for initial context
            self._detect_and_analyze_codebase()
            
            # Set up initial context cache
            self._setup_context_cache()
            
            # Initialize indexing for faster context retrieval
            self._initialize_code_indexing()
            
            self._log("Context management system initialized successfully")
            
        except Exception as e:
            # Context management initialization is not critical for basic workspace functionality
            self._log(f"Warning: Context management initialization failed: {e}", level="warning")

    def _detect_and_analyze_codebase(self) -> None:
        """Detect and analyze the codebase structure for context management."""
        try:
            # Get workspace root
            workspace_root = Path.cwd()
            
            # Find relevant code files
            code_extensions = {'.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.cpp', '.c', '.h', '.cs', '.rb', '.go', '.rs', '.php', '.swift', '.kt'}
            config_extensions = {'.json', '.yaml', '.yml', '.toml', '.ini', '.cfg', '.conf'}
            doc_extensions = {'.md', '.rst', '.txt'}
            
            code_files = []
            config_files = []
            doc_files = []
            
            # Scan workspace for relevant files (excluding common ignore patterns)
            ignore_patterns = {
                'node_modules', '.git', '__pycache__', '.mypy_cache', '.pytest_cache',
                'dist', 'build', '.venv', 'venv', '.env', 'coverage_html'
            }
            
            for file_path in workspace_root.rglob('*'):
                if file_path.is_file() and not any(pattern in str(file_path) for pattern in ignore_patterns):
                    if file_path.suffix in code_extensions:
                        code_files.append(file_path)
                    elif file_path.suffix in config_extensions:
                        config_files.append(file_path)
                    elif file_path.suffix in doc_extensions:
                        doc_files.append(file_path)
            
            # Log discovered structure
            self._log(f"Discovered {len(code_files)} code files, {len(config_files)} config files, {len(doc_files)} documentation files")
            
            # Store file information for context system
            self._context_files = {
                'code': code_files[:100],  # Limit initial analysis to avoid overwhelming
                'config': config_files[:50],
                'docs': doc_files[:50]
            }
            
        except Exception as e:
            self._log(f"Error during codebase detection: {e}", level="warning")

    def _setup_context_cache(self) -> None:
        """Set up initial context cache directories and structure."""
        try:
            # Create context management directories
            context_dirs = [
                '.agent_s3',
                '.agent_s3/context',
                '.agent_s3/context/cache',
                '.agent_s3/context/index',
                '.agent_s3/context/embeddings'
            ]
            
            for context_dir in context_dirs:
                dir_path = Path(context_dir)
                if not dir_path.exists():
                    dir_path.mkdir(parents=True, exist_ok=True)
                    self._log(f"Created context directory: {context_dir}")
            
            # Create initial context configuration
            context_config = {
                "version": "1.0",
                "initialized": True,
                "workspace_type": self._detect_workspace_type(),
                "primary_language": self._detect_primary_language(),
                "framework": self._detect_framework(),
                "last_updated": str(datetime.now().isoformat())
            }
            
            config_path = Path('.agent_s3/context/workspace_context.json')
            with open(config_path, 'w', encoding='utf-8') as f:
                import json
                json.dump(context_config, f, indent=2)
            
            self._log("Context cache structure created")
            
        except Exception as e:
            self._log(f"Error setting up context cache: {e}", level="warning")

    def _initialize_code_indexing(self) -> None:
        """Initialize code indexing and semantic analysis for faster context retrieval."""
        try:
            # Only initialize indexing if we have code files
            if not hasattr(self, '_context_files') or not self._context_files.get('code'):
                self._log("No code files found, skipping indexing initialization")
                return
            
            # Create comprehensive index with semantic information
            index_data = {
                "version": "1.0",
                "last_indexed": str(datetime.now().isoformat()),
                "indexed_files": [],
                "file_hashes": {},
                "semantic_summaries": {},
                "api_endpoints": [],
                "data_models": [],
                "business_logic": [],
                "architectural_patterns": [],
                "ready_for_context": True
            }
            
            # Analyze code files for semantic content
            for file_path in self._context_files.get('code', [])[:20]:  # Analyze first 20 files
                try:
                    relative_path = str(file_path.relative_to(Path.cwd()))
                    file_size = file_path.stat().st_size
                    
                    # Only analyze reasonably sized files
                    if file_size < 100000:  # 100KB limit
                        # Basic file metadata
                        file_info = {
                            "path": relative_path,
                            "size": file_size,
                            "modified": str(datetime.fromtimestamp(file_path.stat().st_mtime).isoformat())
                        }
                        
                        # Generate semantic analysis
                        semantic_summary = self._analyze_file_semantics(file_path)
                        if semantic_summary:
                            file_info["semantic_analysis"] = semantic_summary
                            index_data["semantic_summaries"][relative_path] = semantic_summary
                            
                            # Extract structured information for different categories
                            self._extract_api_endpoints(semantic_summary, relative_path, index_data)
                            self._extract_data_models(semantic_summary, relative_path, index_data)
                            self._extract_business_logic(semantic_summary, relative_path, index_data)
                            self._extract_architectural_patterns(semantic_summary, relative_path, index_data)
                        
                        index_data["indexed_files"].append(file_info)
                        
                        # Simple hash for change detection
                        import hashlib
                        with open(file_path, 'rb') as f:
                            file_hash = hashlib.md5(f.read()).hexdigest()
                        index_data["file_hashes"][relative_path] = file_hash
                        
                except Exception as file_error:
                    self._log(f"Error analyzing file {file_path}: {file_error}", level="debug")
            
            # Save comprehensive index
            index_path = Path('.agent_s3/context/index/file_index.json')
            with open(index_path, 'w', encoding='utf-8') as f:
                import json
                json.dump(index_data, f, indent=2)
            
            # Save semantic summary for preplanning
            self._save_semantic_summary_for_preplanning(index_data)
            
            self._log(f"Code indexing and semantic analysis completed with {len(index_data['indexed_files'])} files")
            
        except Exception as e:
            self._log(f"Error initializing code indexing: {e}", level="warning")

    def _detect_workspace_type(self) -> str:
        """Detect the type of workspace (empty, existing project, etc.)."""
        workspace_root = Path.cwd()
        
        # Check for common project indicators
        if (workspace_root / 'package.json').exists():
            return 'nodejs'
        elif (workspace_root / 'requirements.txt').exists() or (workspace_root / 'pyproject.toml').exists():
            return 'python'
        elif (workspace_root / 'pom.xml').exists():
            return 'java'
        elif (workspace_root / 'Cargo.toml').exists():
            return 'rust'
        elif (workspace_root / 'go.mod').exists():
            return 'go'
        elif (workspace_root / 'composer.json').exists():
            return 'php'
        elif any(workspace_root.glob('*.sln')) or any(workspace_root.glob('*.csproj')):
            return 'dotnet'
        else:
            # Check if directory is empty or has minimal files
            files = [f for f in workspace_root.iterdir() if f.is_file() and not f.name.startswith('.')]
            if len(files) <= 2:
                return 'empty'
            return 'mixed'

    def _detect_primary_language(self) -> str:
        """Detect the primary programming language in the workspace."""
        if not hasattr(self, '_context_files'):
            return 'unknown'
        
        code_files = self._context_files.get('code', [])
        if not code_files:
            return 'none'
        
        # Count files by extension
        extension_counts = {}
        for file_path in code_files:
            ext = file_path.suffix.lower()
            extension_counts[ext] = extension_counts.get(ext, 0) + 1
        
        # Map extensions to languages
        extension_to_language = {
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.jsx': 'javascript',
            '.tsx': 'typescript',
            '.java': 'java',
            '.cpp': 'cpp',
            '.c': 'c',
            '.cs': 'csharp',
            '.rb': 'ruby',
            '.go': 'go',
            '.rs': 'rust',
            '.php': 'php',
            '.swift': 'swift',
            '.kt': 'kotlin'
        }
        
        # Find most common language
        language_counts = {}
        for ext, count in extension_counts.items():
            lang = extension_to_language.get(ext, 'other')
            language_counts[lang] = language_counts.get(lang, 0) + count
        
        if language_counts:
            return max(language_counts, key=language_counts.get)
        return 'mixed'

    def _detect_framework(self) -> str:
        """Detect the primary framework in the workspace."""
        workspace_root = Path.cwd()
        
        # Check for framework-specific files
        if (workspace_root / 'package.json').exists():
            try:
                import json
                with open(workspace_root / 'package.json', 'r') as f:
                    package_data = json.load(f)
                
                dependencies = {**package_data.get('dependencies', {}), **package_data.get('devDependencies', {})}
                
                if 'react' in dependencies:
                    return 'react'
                elif 'vue' in dependencies:
                    return 'vue'
                elif 'angular' in dependencies or '@angular/core' in dependencies:
                    return 'angular'
                elif 'express' in dependencies:
                    return 'express'
                elif 'next' in dependencies:
                    return 'nextjs'
                else:
                    return 'nodejs'
            except Exception:
                return 'nodejs'
        
        elif (workspace_root / 'requirements.txt').exists() or (workspace_root / 'pyproject.toml').exists():
            # Check Python frameworks
            framework_files = ['manage.py', 'app.py', 'main.py', 'wsgi.py']
            if any((workspace_root / f).exists() for f in framework_files):
                try:
                    # Try to detect Django, Flask, FastAPI
                    if (workspace_root / 'manage.py').exists():
                        return 'django'
                    elif (workspace_root / 'app.py').exists():
                        return 'flask'
                    else:
                        return 'python'
                except Exception:
                    return 'python'
            return 'python'
        
        return 'none'

    def _generate_guidelines_content(self) -> str:
        """Generate guidelines content based on detected tech stack.

        Returns:
            str: Guidelines content tailored to the detected tech stack
        """
        # Base guidelines
        guidelines = """# Copilot Instructions

This file contains guidelines for GitHub Copilot to follow when working with this codebase.

## General Guidelines

- Follow best practices for security, performance, and code quality
- Write clean, modular code with proper error handling
- Include comprehensive tests for all functionality
- Follow project-specific conventions and patterns
- Use meaningful variable and function names
- Add comments for complex logic
- Ensure code is maintainable and readable

## Code Style

- Use consistent indentation and formatting
- Follow language-specific style guides
- Organize imports properly
- Keep functions and classes focused and single-purpose

## Testing

- Write unit tests for all new functionality
- Include edge cases and error scenarios
- Maintain good test coverage
- Use appropriate testing frameworks for the language

## Security

- Validate all inputs
- Use secure coding practices
- Avoid hardcoding secrets or sensitive data
- Follow principle of least privilege

"""

        # Add tech stack specific guidelines
        if self.tech_stack:
            languages = self.tech_stack.get('languages', [])
            frameworks = self.tech_stack.get('frameworks', [])
            
            if languages:
                guidelines += f"## Detected Languages: {', '.join(languages)}\n\n"
                
                if 'python' in [lang.lower() for lang in languages]:
                    guidelines += """### Python Specific Guidelines

- Follow PEP 8 style guidelines
- Use type hints for function parameters and return values
- Use f-strings for string formatting
- Handle exceptions appropriately
- Use virtual environments for dependencies

"""
                
                if 'javascript' in [lang.lower() for lang in languages] or 'typescript' in [lang.lower() for lang in languages]:
                    guidelines += """### JavaScript/TypeScript Guidelines

- Use modern ES6+ features
- Prefer const/let over var
- Use arrow functions appropriately
- Handle promises and async operations properly
- Follow consistent naming conventions

"""

            if frameworks:
                guidelines += f"## Detected Frameworks: {', '.join(frameworks)}\n\n"

        return guidelines

    def _log(self, message: str, level: str = "info") -> None:
        """Log a message using the scratchpad or default logger.

        Args:
            message: The message to log
            level: The log level (info, warning, error)
        """
        if self.scratchpad:
            # Use scratchpad logging if available
            from agent_s3.enhanced_scratchpad_manager import LogLevel
            
            level_map = {
                "debug": LogLevel.DEBUG,
                "info": LogLevel.INFO,
                "warning": LogLevel.WARNING,
                "warn": LogLevel.WARNING,
                "error": LogLevel.ERROR,
                "critical": LogLevel.CRITICAL
            }
            log_level = level_map.get(level.lower(), LogLevel.INFO)
            self.scratchpad.log("WorkspaceInitializer", message, level=log_level)
        else:
            # Fall back to standard logging
            if level.lower() == "error":
                logger.error(message)
            elif level.lower() == "warning":
                logger.warning(message)
            else:
                logger.info(message)