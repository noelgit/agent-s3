# Dependencies Documentation

This document provides a comprehensive overview of all dependencies used in the Agent-S3 project.

## Overview

The Agent-S3 project is a multi-component system that includes:
- Python backend with AI/ML capabilities
- TypeScript VSCode extension
- React-based webview UI
- FastAPI web server
- Multiple database integrations

## Python Dependencies

### Core Runtime Dependencies (`requirements.txt`)

#### Core Framework Dependencies
- `requests>=2.25.0` - HTTP client library for API calls
- `pydantic>=2.0.0` - Data validation and serialization
- `sqlalchemy>=2.0.0` - SQL toolkit and ORM
- `jsonschema>=4.0.0` - JSON schema validation
- `cryptography>=41.0.0` - Cryptographic operations
- `python-dotenv>=1.0.0` - Environment variable management
- `psutil>=5.9.0` - System and process utilities
- `toml>=0.10.2` - TOML parser
- `pyyaml>=6.0` - YAML parser
- `libcst>=0.4.0` - Concrete syntax tree library for Python

#### Tree-sitter Parser Dependencies
- `tree-sitter>=0.22.0` - Parser generator toolkit
- `tree-sitter-python>=0.21.0` - Python language parser
- `tree-sitter-javascript>=0.21.0` - JavaScript language parser
- `tree-sitter-typescript>=0.21.0` - TypeScript language parser
- `tree-sitter-php>=0.22.0` - PHP language parser

#### AI/ML Dependencies
- `gptcache>=0.1.44` - GPT response caching
- `faiss-cpu>=1.7.0` - Vector similarity search
- `numpy>=1.24.0` - Numerical computing
- `tiktoken>=0.5.0` - Token counting for OpenAI models
- `rank-bm25>=0.2` - BM25 ranking algorithm

#### Web Framework Dependencies
- `fastapi>=0.95.0` - Modern web framework
- `uvicorn>=0.22.0` - ASGI server
- `websockets>=11.0` - WebSocket support
- `flask>=2.3.0` - Lightweight web framework

#### Cloud and Integration Dependencies
- `boto3>=1.24.0` - AWS SDK
- `botocore>=1.27.0` - AWS core library
- `PyGithub>=2.1.1` - GitHub API client
- `PyJWT>=2.6.0` - JSON Web Token library

#### Utility Dependencies
- `watchdog>=3.0.0` - File system monitoring
- `pytest>=6.2.0` - Testing framework

#### Database Adapters
- `psycopg2-binary>=2.9.0` - PostgreSQL adapter
- `pymysql>=1.0.0` - MySQL adapter

#### Legacy Support
- `phply>=0.9.1` - PHP parser (legacy support)

### Development Dependencies (`requirements-dev.txt`)

#### Testing Framework
- `pytest>=8.0` - Advanced testing framework
- `pytest-cov>=4.0.0` - Coverage reporting
- `pytest-asyncio>=0.21.0` - Async testing support
- `pytest-mock>=3.10.0` - Mocking framework

#### Code Quality Tools
- `mypy>=1.8` - Static type checker
- `ruff>=0.2` - Fast Python linter
- `black>=23.0.0` - Code formatter
- `isort>=5.12.0` - Import sorter

#### Documentation Tools
- `sphinx>=6.0.0` - Documentation generator
- `sphinx-rtd-theme>=1.2.0` - Read the Docs theme

#### Development Tools
- `pre-commit>=3.0.0` - Git hooks framework
- `tox>=4.0.0` - Testing automation

#### Testing and Development Support
- `websockets>=11.0` - WebSocket testing
- `aiohttp>=3.8.0` - Async HTTP client for testing

#### Profiling and Analysis
- `coverage>=7.0.0` - Code coverage analysis
- `line-profiler>=4.0.0` - Line-by-line profiling

#### Security Tools
- `safety>=2.3.0` - Dependency vulnerability scanner
- `bandit>=1.7.0` - Security issue scanner

## JavaScript/TypeScript Dependencies

### VSCode Extension (`vscode/package.json`)

#### Runtime Dependencies
- `@types/ws>=8.18.1` - WebSocket type definitions
- `react>=18.2.0` - React library (for webview)
- `react-dom>=18.2.0` - React DOM library
- `ws>=8.18.2` - WebSocket client

#### Development Dependencies
- `@types/node>=22.14.1` - Node.js type definitions
- `@types/react>=18.0.28` - React type definitions
- `@types/react-dom>=18.0.11` - React DOM type definitions
- `@types/vscode>=1.99.1` - VSCode API type definitions
- `@typescript-eslint/eslint-plugin>=4.22.0` - TypeScript ESLint plugin
- `@typescript-eslint/parser>=4.22.0` - TypeScript ESLint parser
- `eslint>=7.24.0` - JavaScript/TypeScript linter
- `typescript>=4.2.4` - TypeScript compiler

### Webview UI (`vscode/webview-ui/package.json`)

#### Runtime Dependencies
- `react>=18.2.0` - React library
- `react-dom>=18.2.0` - React DOM library
- `react-scripts>=5.0.1` - Create React App scripts
- `marked>=12.0.0` - Markdown parser
- `highlight.js>=11.9.0` - Syntax highlighting
- `dompurify>=3.0.9` - DOM sanitization

#### Development Dependencies
- `@types/node>=16.18.11` - Node.js type definitions
- `@types/react>=18.3.21` - React type definitions
- `@types/react-dom>=18.3.7` - React DOM type definitions
- `@types/dompurify>=3.0.2` - DOMPurify type definitions
- `typescript>=4.9.5` - TypeScript compiler

## Main Project Configuration

### Root Package.json
Contains project metadata and development dependencies for the entire project including:
- TypeScript and ESLint configuration
- Testing and documentation tools
- Build and development scripts

### Python Project Configuration

#### pyproject.toml
- Contains the same dependencies as requirements.txt in structured TOML format
- Includes project metadata and build configuration
- Used by modern Python package managers

## Installation Instructions

### Python Environment Setup
```bash
# Install runtime dependencies
pip install -r requirements.txt

# Install development dependencies
pip install -r requirements-dev.txt
```

### Node.js Environment Setup
```bash
# Install main project dependencies
npm install

# Install VSCode extension dependencies
cd vscode && npm install

# Install webview UI dependencies
cd vscode/webview-ui && npm install
```

### Building the Project
```bash
# Compile VSCode extension
cd vscode && npm run compile

# Build webview UI
cd vscode && npm run build-webview

# Run linting
npm run lint
```

## Dependency Management Best Practices

### Version Constraints
- All dependencies use minimum version constraints (`>=`) to ensure compatibility
- Major version boundaries are respected to avoid breaking changes
- Security-critical packages are kept up to date

### Security Considerations
- Regular dependency audits are performed using `npm audit` and `safety`
- Known vulnerabilities are addressed promptly
- Transitive dependencies are monitored for security issues

### Development vs Production
- Development dependencies are clearly separated from runtime dependencies
- Testing and development tools are not included in production builds
- Optional dependencies are marked appropriately

### Tree-sitter Language Support
The project supports multiple programming languages through tree-sitter parsers:
- Python
- JavaScript
- TypeScript
- PHP

Additional language support can be added by installing the corresponding tree-sitter parser packages.

## Troubleshooting

### Common Issues
1. **Node.js Version Compatibility**: Ensure Node.js version >= 16.x for React 18 support
2. **Python Version**: Requires Python >= 3.8 for modern typing features
3. **Platform-specific Dependencies**: Some packages (like `psycopg2-binary`) may require platform-specific builds

### Dependency Conflicts
If you encounter dependency conflicts:
1. Clear package caches: `npm cache clean --force` and `pip cache purge`
2. Delete node_modules and reinstall: `rm -rf node_modules && npm install`
3. Use virtual environments for Python to isolate dependencies

### Security Vulnerabilities
To check for and fix security vulnerabilities:
```bash
# Node.js dependencies
npm audit
npm audit fix

# Python dependencies
safety check
bandit -r agent_s3/
```

## Recent Dependency Management Updates

### Major Overhaul Completed (2025-05-23)
- **Restructured requirements.txt**: Organized from 34 unorganized entries to 40+ categorized dependencies
- **Enhanced requirements-dev.txt**: Expanded from 4 to 20+ development-specific dependencies  
- **Security Improvements**: Fixed 8 high/moderate security vulnerabilities in webview-ui
- **Build System Validation**: All dependencies verified across Python, Node.js, and tree-sitter ecosystems
- **Documentation**: Created comprehensive dependency tracking and validation tools

### Key Achievements
- ✅ All dependencies properly catalogued and managed
- ✅ Build systems working across all components  
- ✅ Security vulnerabilities resolved
- ✅ Automated validation tools in place

## Update Schedule

Dependencies should be reviewed and updated regularly:
- Security updates: Immediately upon discovery
- Minor version updates: Monthly review cycle
- Major version updates: Quarterly review with testing
- Development dependencies: Updated more frequently for latest tooling features
