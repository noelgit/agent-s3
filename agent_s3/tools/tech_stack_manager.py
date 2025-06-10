import re
import json
import logging
import sys
from typing import Dict, Any
import subprocess
from pathlib import Path

class TechStackManager:
    """Manages the detection, enhancement, and structuring of tech stack information."""

    def __init__(self, workspace_path=None):
        """Initialize tech stack manager with workspace path."""
        self.workspace_path = Path(workspace_path) if workspace_path else Path.cwd()
        self.tech_stack = {
            "languages": set(),
            "frameworks": set(),
            "libraries": set(),
            "tools": set(),
            "versions": {},
            "meta": {}
        }
        self.best_practices = {}
        
        # Directories to exclude from file scanning for performance
        self.excluded_dirs = {
            'node_modules',
            '__pycache__',
            '.git',
            'coverage_html',
            '.pytest_cache',
            'dist',
            'build',
            'out',
            '.vscode',
            '.idea',
            'target',
            'vendor',
            '.venv',
            'venv',
            'env',
            '.env',
            'htmlcov',
            '.coverage',
            '.mypy_cache',
            '.tox',
            '.cache',
            'bower_components',
            'jspm_packages'
        }

    def _find_files_with_extension(self, extension: str, limit: int = 5) -> bool:
        """
        Efficiently find files with given extension, excluding common large directories.
        Returns True if any files found, False otherwise.
        Uses a limit to avoid scanning entire large codebases.
        """
        count = 0
        try:
            for path in self.workspace_path.rglob(f"*.{extension}"):
                # Check if any parent directory is in excluded list
                if any(part in self.excluded_dirs for part in path.parts):
                    continue
                count += 1
                if count >= limit:
                    return True
            return count > 0
        except Exception as e:
            logging.warning(f"Error scanning for .{extension} files: {e}")
            return False

    def _find_specific_files(self, filenames: list, limit: int = 5) -> bool:
        """
        Efficiently find specific filenames, excluding common large directories.
        Returns True if any files found, False otherwise.
        """
        count = 0
        try:
            for filename in filenames:
                for path in self.workspace_path.rglob(filename):
                    # Check if any parent directory is in excluded list
                    if any(part in self.excluded_dirs for part in path.parts):
                        continue
                    count += 1
                    if count >= limit:
                        return True
            return count > 0
        except Exception as e:
            logging.warning(f"Error scanning for specific files {filenames}: {e}")
            return False

    def _find_specific_files(self, filenames: list, limit: int = 5) -> bool:
        """
        Efficiently find specific files by name, excluding common large directories.
        Returns True if any files found, False otherwise.
        """
        count = 0
        try:
            for filename in filenames:
                for path in self.workspace_path.rglob(filename):
                    # Check if any parent directory is in excluded list
                    if any(part in self.excluded_dirs for part in path.parts):
                        continue
                    count += 1
                    if count >= limit:
                        return True
            return count > 0
        except Exception as e:
            logging.warning(f"Error scanning for specific files {filenames}: {e}")
            return False
        
        # Directories to exclude from file scanning for performance
        self.excluded_dirs = {
            'node_modules',
            '__pycache__',
            '.git',
            'coverage_html',
            '.pytest_cache',
            'dist',
            'build',
            'out',
            '.vscode',
            '.idea',
            'target',
            'vendor',
            '.venv',
            'venv',
            'env',
            '.env',
            'htmlcov',
            '.coverage',
            '.mypy_cache',
            '.tox',
            '.cache',
            'bower_components',
            'jspm_packages'
        }

    def detect_tech_stack(self) -> Dict[str, Any]:
        """Detects the tech stack in the workspace with enhanced version detection."""
        # Reset tech stack for fresh detection
        self.tech_stack = {
            "languages": set(),
            "frameworks": set(),
            "libraries": set(),
            "tools": set(),
            "versions": {},
            "meta": {}
        }

        # Detect programming languages
        self._detect_languages()

        # Detect package managers and dependencies
        self._detect_package_managers()

        # Detect build systems and configuration
        self._detect_build_systems()

        # Detect version control
        self._detect_version_control()

        # Detect IDEs and editor configurations
        self._detect_ide_config()

        # Detect frameworks and versions
        self._detect_frameworks_and_versions()

        # Add best practices for detected stack
        self._add_best_practices()

        # Convert sets to lists for JSON serialization
        result = {
            "languages": list(self.tech_stack["languages"]),
            "frameworks": list(self.tech_stack["frameworks"]),
            "libraries": list(self.tech_stack["libraries"]),
            "tools": list(self.tech_stack["tools"]),
            "versions": self.tech_stack["versions"],
            "meta": self.tech_stack["meta"]
        }

        return result

    def _detect_languages(self):
        """Detect programming languages used in the project."""
        # Python
        if self._find_files_with_extension("py"):
            self.tech_stack["languages"].add("Python")
            # Get Python version
            try:
                python_version = subprocess.check_output([sys.executable, "--version"],
                                                        stderr=subprocess.STDOUT,
                                                        timeout=5).decode().strip()
                self.tech_stack["versions"]["python"] = python_version.replace("Python ", "")
            except (subprocess.TimeoutExpired, subprocess.CalledProcessError, OSError) as e:
                logging.warning(f"Failed to get Python version: {e}")
                # Fallback to sys.version_info
                try:
                    version_info = sys.version_info
                    self.tech_stack["versions"]["python"] = f"{version_info.major}.{version_info.minor}.{version_info.micro}"
                except Exception:
                    pass

        # JavaScript/TypeScript
        if self._find_files_with_extension("js"):
            self.tech_stack["languages"].add("JavaScript")

        if self._find_files_with_extension("ts"):
            self.tech_stack["languages"].add("TypeScript")
            # Check for TypeScript version in package.json
            if (self.workspace_path / "package.json").exists():
                try:
                    with open(self.workspace_path / "package.json", "r") as f:
                        package_data = json.load(f)
                    dev_deps = package_data.get("devDependencies", {})
                    if "typescript" in dev_deps:
                        self.tech_stack["versions"]["typescript"] = dev_deps["typescript"].replace("^", "").replace("~", "")
                except Exception:
                    pass

        # PHP
        if self._find_files_with_extension("php"):
            self.tech_stack["languages"].add("PHP")
            # Get PHP version
            try:
                php_version = subprocess.check_output(["php", "--version"],
                                                    stderr=subprocess.STDOUT,
                                                    timeout=5).decode().strip()
                # Extract version from output like "PHP 8.2.0 (cli) ..."
                php_match = re.search(r'PHP\s+(\d+\.\d+\.\d+)', php_version)
                if php_match:
                    self.tech_stack["versions"]["php"] = php_match.group(1)
            except (subprocess.TimeoutExpired, subprocess.CalledProcessError, OSError) as e:
                logging.warning(f"Failed to get PHP version: {e}")
                pass

        # Rust
        if self._find_files_with_extension("rs") or (self.workspace_path / "Cargo.toml").exists():
            self.tech_stack["languages"].add("Rust")
            if (self.workspace_path / "Cargo.toml").exists():
                try:
                    with open(self.workspace_path / "Cargo.toml", "r") as f:
                        cargo_content = f.read()
                        if "edition =" in cargo_content:
                            edition_match = re.search(r'edition\s*=\s*"(20\d\d)"', cargo_content)
                            if edition_match:
                                self.tech_stack["versions"]["rust_edition"] = edition_match.group(1)
                except Exception:
                    pass

        # Go
        if self._find_files_with_extension("go") or (self.workspace_path / "go.mod").exists():
            self.tech_stack["languages"].add("Go")
            if (self.workspace_path / "go.mod").exists():
                try:
                    with open(self.workspace_path / "go.mod", "r") as f:
                        go_mod = f.read()
                        go_version_match = re.search(r'go\s+(\d+\.\d+)', go_mod)
                        if go_version_match:
                            self.tech_stack["versions"]["go"] = go_version_match.group(1)
                except Exception:
                    pass

        # Java
        if self._find_files_with_extension("java"):
            self.tech_stack["languages"].add("Java")

        # C#
        if self._find_files_with_extension("cs"):
            self.tech_stack["languages"].add("C#")
            # Check for .NET version in .csproj files
            try:
                for csproj in self.workspace_path.rglob("*.csproj"):
                    # Skip if in excluded directory
                    if any(part in self.excluded_dirs for part in csproj.parts):
                        continue
                    try:
                        with open(csproj, "r") as f:
                            content = f.read()
                            target_match = re.search(r'<TargetFramework>(.*?)</TargetFramework>', content)
                            if target_match:
                                self.tech_stack["versions"]["dotnet"] = target_match.group(1)
                                break
                    except Exception:
                        continue
            except Exception:
                pass

    def _detect_package_managers(self):
        """Detect package managers and dependencies."""
        # Python packages
        if (self.workspace_path / "requirements.txt").exists():
            self.tech_stack["tools"].add("pip")
            try:
                with open(self.workspace_path / "requirements.txt", "r") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#"):
                            # Extract package name and version if available
                            package_info = re.match(r'^([a-zA-Z0-9_.-]+)(?:[=<>!]+([0-9a-zA-Z.-]+))?', line)
                            if package_info:
                                package, version = package_info.groups()
                                if package:
                                    if self._is_library(package):
                                        self.tech_stack["libraries"].add(package)
                                    if self._is_framework(package):
                                        self.tech_stack["frameworks"].add(package)
                                    if version:
                                        self.tech_stack["versions"][package] = version
            except Exception as e:
                logging.warning(f"Could not parse requirements.txt: {e}")

        # Poetry
        if (self.workspace_path / "pyproject.toml").exists():
            try:
                import toml
                with open(self.workspace_path / "pyproject.toml", "r") as f:
                    pyproject = toml.load(f)

                # Check tool.poetry section
                if "tool" in pyproject and "poetry" in pyproject["tool"]:
                    self.tech_stack["tools"].add("poetry")

                    if "dependencies" in pyproject["tool"]["poetry"]:
                        deps = pyproject["tool"]["poetry"]["dependencies"]
                        for package, info in deps.items():
                            if package != "python":
                                if self._is_library(package):
                                    self.tech_stack["libraries"].add(package)
                                if self._is_framework(package):
                                    self.tech_stack["frameworks"].add(package)
                                # Extract version
                                if isinstance(info, str):
                                    self.tech_stack["versions"][package] = info
                                elif isinstance(info, dict) and "version" in info:
                                    self.tech_stack["versions"][package] = info["version"]
            except ImportError:
                # toml module not available
                pass
            except Exception as e:
                logging.warning(f"Could not parse pyproject.toml: {e}")

        # NPM/Yarn
        if (self.workspace_path / "package.json").exists():
            self.tech_stack["tools"].add("npm")
            try:
                with open(self.workspace_path / "package.json", "r") as f:
                    package_data = json.load(f)

                # Check if using Yarn
                if (self.workspace_path / "yarn.lock").exists():
                    self.tech_stack["tools"].add("yarn")

                # Add dependencies
                dependencies = package_data.get("dependencies", {})
                devDependencies = package_data.get("devDependencies", {})

                for dep_dict in [dependencies, devDependencies]:
                    for package, version in dep_dict.items():
                        # Remove version prefix for storage
                        clean_version = version.replace("^", "").replace("~", "").replace(">=", "")

                        # Categorize packages
                        if self._is_js_framework(package):
                            self.tech_stack["frameworks"].add(package)
                            self.tech_stack["versions"][package] = clean_version
                        elif not package.startswith("@types/"):  # Skip type definitions
                            self.tech_stack["libraries"].add(package)
                            self.tech_stack["versions"][package] = clean_version
            except Exception as e:
                logging.warning(f"Could not parse package.json: {e}")

        # PHP Composer
        if (self.workspace_path / "composer.json").exists():
            self.tech_stack["tools"].add("composer")
            try:
                with open(self.workspace_path / "composer.json", "r") as f:
                    composer_data = json.load(f)

                # Check for PHP version requirement
                if "require" in composer_data and "php" in composer_data["require"]:
                    php_version = composer_data["require"]["php"]
                    # Clean version constraints like "^8.0" -> "8.0"
                    clean_version = re.sub(r'[^0-9.]', '', php_version.split('|')[0])
                    if clean_version:
                        self.tech_stack["versions"]["php_min"] = clean_version

                # Add dependencies from require and require-dev
                require = composer_data.get("require", {})
                require_dev = composer_data.get("require-dev", {})

                for dep_dict in [require, require_dev]:
                    for package, version in dep_dict.items():
                        if package == "php":  # Skip PHP version requirement
                            continue
                        
                        # Clean version
                        clean_version = re.sub(r'[^0-9.]', '', version.split('|')[0])
                        
                        # Categorize PHP packages
                        if self._is_php_framework(package):
                            self.tech_stack["frameworks"].add(package)
                            if clean_version:
                                self.tech_stack["versions"][package] = clean_version
                        else:
                            self.tech_stack["libraries"].add(package)
                            if clean_version:
                                self.tech_stack["versions"][package] = clean_version
            except Exception as e:
                logging.warning(f"Could not parse composer.json: {e}")

    def _detect_build_systems(self):
        """Detect build systems and tools."""
        # Check for Webpack
        if (self.workspace_path / "webpack.config.js").exists():
            self.tech_stack["tools"].add("webpack")

        # Check for Vite
        if (self.workspace_path / "vite.config.js").exists() or (self.workspace_path / "vite.config.ts").exists():
            self.tech_stack["tools"].add("vite")

        # Check for Babel
        if (self.workspace_path / ".babelrc").exists() or (self.workspace_path / "babel.config.js").exists():
            self.tech_stack["tools"].add("babel")

        # Check for ESLint
        if (self.workspace_path / ".eslintrc.js").exists() or (self.workspace_path / ".eslintrc.json").exists():
            self.tech_stack["tools"].add("eslint")

        # Check for tox (Python)
        if (self.workspace_path / "tox.ini").exists():
            self.tech_stack["tools"].add("tox")

        # Check for Make
        if (self.workspace_path / "Makefile").exists():
            self.tech_stack["tools"].add("make")

    def _detect_version_control(self):
        """Detect version control systems."""
        # Git
        if (self.workspace_path / ".git").exists():
            self.tech_stack["tools"].add("git")

            # Check if using GitHub Actions
            if (self.workspace_path / ".github" / "workflows").exists():
                self.tech_stack["tools"].add("github-actions")
                self.tech_stack["meta"]["ci_cd"] = "GitHub Actions"

    def _detect_ide_config(self):
        """Detect IDE configurations."""
        # VS Code
        if (self.workspace_path / ".vscode").exists():
            self.tech_stack["tools"].add("vscode")

            # Check if it's a VS Code Extension
            if self._find_specific_files(["extension.ts", "extension.js"]):
                self.tech_stack["frameworks"].add("vscode-extension")

                # Try to get extension version
                if (self.workspace_path / "package.json").exists():
                    try:
                        with open(self.workspace_path / "package.json", "r") as f:
                            pkg = json.load(f)
                            if "version" in pkg:
                                self.tech_stack["versions"]["vscode-extension"] = pkg["version"]
                    except Exception:
                        pass
                        pass

    def _detect_frameworks_and_versions(self):
        """Detect frameworks and their versions."""
        # Check for specific framework files

        # FastAPI
        if "fastapi" in self.tech_stack["frameworks"]:
            # FastAPI is detected in dependencies, enhance with additional metadata
            self.tech_stack["meta"]["api_style"] = "RESTful"
            self.tech_stack["meta"]["api_framework"] = "FastAPI"

        # Django
        if self._find_specific_files(["settings.py"]) and self._find_specific_files(["urls.py"]):
            self.tech_stack["frameworks"].add("django")
            self.tech_stack["meta"]["web_framework"] = "Django"

            # Try to find Django version
            try:
                import importlib.metadata
                django_version = importlib.metadata.version("django")
                self.tech_stack["versions"]["django"] = django_version
            except Exception:
                pass

        # Flask
        if "flask" in self.tech_stack["frameworks"] or self._find_specific_files(["app.py"]):
            if "flask" not in self.tech_stack["frameworks"]:
                self.tech_stack["frameworks"].add("flask")
            self.tech_stack["meta"]["web_framework"] = "Flask"

        # React
        if "react" in self.tech_stack["frameworks"] or self._find_specific_files(["App.jsx", "App.tsx"]):
            if "react" not in self.tech_stack["frameworks"]:
                self.tech_stack["frameworks"].add("react")
            self.tech_stack["meta"]["ui_framework"] = "React"

        # Next.js
        if "next" in self.tech_stack["frameworks"] or (self.workspace_path / "next.config.js").exists():
            if "next" not in self.tech_stack["frameworks"]:
                self.tech_stack["frameworks"].add("next.js")
            self.tech_stack["meta"]["ui_framework"] = "Next.js"
            self.tech_stack["meta"]["rendering"] = "Hybrid (SSR/SSG)"

        # Vue.js
        if "vue" in self.tech_stack["frameworks"] or self._find_specific_files(["App.vue"]):
            if "vue" not in self.tech_stack["frameworks"]:
                self.tech_stack["frameworks"].add("vue.js")
            self.tech_stack["meta"]["ui_framework"] = "Vue.js"

        # Angular
        if "angular" in self.tech_stack["frameworks"] or (self.workspace_path / "angular.json").exists():
            if "angular" not in self.tech_stack["frameworks"]:
                self.tech_stack["frameworks"].add("angular")
            self.tech_stack["meta"]["ui_framework"] = "Angular"

        # Laravel
        if "laravel" in self.tech_stack["frameworks"] or self._detect_laravel():
            if "laravel" not in self.tech_stack["frameworks"]:
                self.tech_stack["frameworks"].add("laravel")
            self.tech_stack["meta"]["web_framework"] = "Laravel"
            self.tech_stack["meta"]["language"] = "PHP"

        # Symfony
        if "symfony" in self.tech_stack["frameworks"] or self._detect_symfony():
            if "symfony" not in self.tech_stack["frameworks"]:
                self.tech_stack["frameworks"].add("symfony")
            self.tech_stack["meta"]["web_framework"] = "Symfony"
            self.tech_stack["meta"]["language"] = "PHP"

        # CodeIgniter
        if "codeigniter" in self.tech_stack["frameworks"] or self._detect_codeigniter():
            if "codeigniter" not in self.tech_stack["frameworks"]:
                self.tech_stack["frameworks"].add("codeigniter")
            self.tech_stack["meta"]["web_framework"] = "CodeIgniter"
            self.tech_stack["meta"]["language"] = "PHP"

        # WordPress
        if "wordpress" in self.tech_stack["frameworks"] or self._detect_wordpress():
            if "wordpress" not in self.tech_stack["frameworks"]:
                self.tech_stack["frameworks"].add("wordpress")
            self.tech_stack["meta"]["cms"] = "WordPress"
            self.tech_stack["meta"]["language"] = "PHP"

    def _add_best_practices(self):
        """Add best practices for the detected frameworks and languages."""
        self.best_practices = {}

        # Add Python best practices
        if "Python" in self.tech_stack["languages"]:
            self.best_practices["Python"] = [
                "Use type hints for better IDE support and runtime validation",
                "Follow PEP 8 style guide for consistent code formatting",
                "Use virtual environments for dependency isolation",
                "Implement error handling with try/except blocks and proper logging",
                "Use context managers (with statement) for resource management"
            ]

            # Add FastAPI best practices
            if "fastapi" in self.tech_stack["frameworks"]:
                self.best_practices["FastAPI"] = [
                    "Use Pydantic models for request/response validation",
                    "Implement proper dependency injection for modularity",
                    "Use appropriate HTTP status codes for all responses",
                    "Set up proper error handling with FastAPI's HTTPException",
                    "Implement middleware for auth, logging, and metrics",
                    "Use async endpoints for I/O-bound operations"
                ]

            # Add Django best practices
            if "django" in self.tech_stack["frameworks"]:
                self.best_practices["Django"] = [
                    "Follow the MTV (Model-Template-View) architecture",
                    "Use Django ORM for database operations",
                    "Implement proper form validation",
                    "Use Django's built-in security features",
                    "Create reusable apps for modularity",
                    "Use Django REST Framework for API development"
                ]

            # Add Flask best practices
            if "flask" in self.tech_stack["frameworks"]:
                self.best_practices["Flask"] = [
                    "Use Flask Blueprints for modular application structure",
                    "Implement proper error handling and custom error pages",
                    "Use Flask-SQLAlchemy for ORM functionality",
                    "Set up Flask-Login for authentication",
                    "Use Flask-WTF for form validation",
                    "Implement proper app factory pattern and configuration"
                ]

        # Add JavaScript/TypeScript best practices
        if "JavaScript" in self.tech_stack["languages"] or "TypeScript" in self.tech_stack["languages"]:
            js_practices = [
                "Use const and let instead of var",
                "Implement error handling with try/catch blocks",
                "Use modern ES6+ features like arrow functions, destructuring, and spread operators",
                "Avoid callback hell with Promises or async/await",
                "Use modules for code organization"
            ]

            if "TypeScript" in self.tech_stack["languages"]:
                self.best_practices["TypeScript"] = js_practices + [
                    "Use strict typing with proper interfaces and type definitions",
                    "Enable strict mode in tsconfig.json",
                    "Use enums for values with semantic meaning",
                    "Use generics for reusable components",
                    "Implement proper error handling with custom error types"
                ]
            else:
                self.best_practices["JavaScript"] = js_practices

            # Add React best practices
            if "react" in self.tech_stack["frameworks"]:
                self.best_practices["React"] = [
                    "Use functional components with hooks instead of class components",
                    "Implement proper state management with useContext and useReducer",
                    "Use React.memo for performance optimization",
                    "Create reusable, single-responsibility components",
                    "Implement proper error boundaries",
                    "Use proper key props in lists"
                ]

            # Add Vue.js best practices
            if "vue.js" in self.tech_stack["frameworks"]:
                self.best_practices["Vue.js"] = [
                    "Follow the Vue Style Guide conventions",
                    "Use single-file components for organization",
                    "Implement state management with Pinia or Vuex",
                    "Use computed properties for derived state",
                    "Implement proper component composition"
                ]

            # Add Next.js best practices
            if "next.js" in self.tech_stack["frameworks"]:
                self.best_practices["Next.js"] = [
                    "Use getStaticProps and getStaticPaths for static generation",
                    "Implement proper data fetching strategies based on use case",
                    "Use Next.js Image component for optimized images",
                    "Implement correct routing strategies with dynamic routes",
                    "Use ISR (Incremental Static Regeneration) for dynamic content"
                ]

            # Add Angular best practices
            if "angular" in self.tech_stack["frameworks"]:
                self.best_practices["Angular"] = [
                    "Follow Angular style guide and naming conventions",
                    "Use proper component hierarchy and composition",
                    "Implement lazy loading for better performance",
                    "Use Angular services for shared functionality",
                    "Implement reactive forms for complex validation"
                ]

        # Add VS Code Extension best practices
        if "vscode-extension" in self.tech_stack["frameworks"]:
            self.best_practices["VS Code Extension"] = [
                "Use activation events appropriately to minimize startup impact",
                "Implement proper extension contribution points (commands, views, menus)",
                "Use WebviewPanel for rich UI with proper message passing",
                "Follow VS Code theming guidelines for UI consistency",
                "Properly dispose of resources and event listeners to prevent memory leaks"
            ]

    def _is_framework(self, package: str) -> bool:
        """Determine if a Python package is a framework."""
        frameworks = {
            "django", "flask", "fastapi", "tornado", "pyramid", "sanic",
            "starlette", "falcon", "quart", "responder", "bottle", "cherrypy",
            "aiohttp", "dash", "hug", "streamlit", "web2py", "masonite",
            "scikit-learn", "keras", "tensorflow", "pytorch", "pandas"
        }
        return package.lower() in frameworks

    def _is_library(self, package: str) -> bool:
        """Determine if a Python package is a library (not a framework)."""
        return not self._is_framework(package)

    def _is_js_framework(self, package: str) -> bool:
        """Determine if a JavaScript package is a framework."""
        frameworks = {
            "react", "vue", "angular", "next", "nuxt", "svelte", "express",
            "koa", "hapi", "meteor", "nestjs", "gatsby", "ember", "aurelia",
            "backbone", "jquery", "bootstrap", "material-ui", "@mui/material",
            "tailwindcss", "bulma", "chakra-ui", "@chakra-ui/react", "redux"
        }
        return package.lower() in frameworks

    def _is_php_framework(self, package: str) -> bool:
        """Determine if a PHP package is a framework."""
        frameworks = {
            "laravel/framework", "laravel/laravel", "symfony/symfony", "symfony/framework-bundle",
            "codeigniter4/framework", "codeigniter/framework", "cakephp/cakephp", "cake/cake",
            "zendframework/zendframework", "laminas/laminas-mvc", "slim/slim", "phalcon/cphalcon",
            "yiisoft/yii2", "yiisoft/yii", "drupal/core", "wordpress/wordpress",
            "magento/magento2ce", "prestashop/prestashop", "phpunit/phpunit", "pestphp/pest",
            "doctrine/orm", "twig/twig", "swiftmailer/swiftmailer", "guzzlehttp/guzzle"
        }
        # Check full package name and base name
        return package.lower() in frameworks or package.lower().split('/')[-1] in {f.split('/')[-1] for f in frameworks}

    def get_formatted_tech_stack(self) -> str:
        """Return well-formatted tech stack information for LLM consumption."""
        output = []

        # Add languages with versions
        if self.tech_stack["languages"]:
            languages = []
            for lang in sorted(self.tech_stack["languages"]):
                version = self.tech_stack["versions"].get(lang.lower(), "")
                if version:
                    languages.append(f"{lang} {version}")
                else:
                    languages.append(lang)
            output.append(f"Languages: {', '.join(languages)}")

        # Add frameworks with versions
        if self.tech_stack["frameworks"]:
            frameworks = []
            for fw in sorted(self.tech_stack["frameworks"]):
                version = self.tech_stack["versions"].get(fw.lower(), "")
                if version:
                    frameworks.append(f"{fw} {version}")
                else:
                    frameworks.append(fw)
            output.append(f"Frameworks: {', '.join(frameworks)}")

        # Add important libraries
        if self.tech_stack["libraries"]:
            # Limit to 10 most important libraries to avoid overwhelming
            top_libs = sorted(self.tech_stack["libraries"])[:10]
            libraries = []
            for lib in top_libs:
                version = self.tech_stack["versions"].get(lib.lower(), "")
                if version:
                    libraries.append(f"{lib} {version}")
                else:
                    libraries.append(lib)
            output.append(f"Libraries: {', '.join(libraries)}")

        # Add tools
        if self.tech_stack["tools"]:
            output.append(f"Tools: {', '.join(sorted(self.tech_stack['tools']))}")

        # Add metadata if available
        if self.tech_stack["meta"]:
            meta_items = []
            for key, value in self.tech_stack["meta"].items():
                meta_items.append(f"{key.replace('_', ' ').title()}: {value}")
            output.append(f"Architecture: {', '.join(meta_items)}")

        # Add best practices if available
        if self.best_practices:
            output.append("\nRecommended Best Practices:")
            for tech, practices in self.best_practices.items():
                output.append(f"\n{tech}:")
                for i, practice in enumerate(practices[:5]):  # Limit to 5 practices per tech
                    output.append(f"  {i+1}. {practice}")

        return "\n".join(output)

    def get_structured_tech_stack(self) -> Dict[str, Any]:
        """Return structured tech stack data for programmatic use."""
        result = {
            "languages": list(self.tech_stack["languages"]),
            "frameworks": list(self.tech_stack["frameworks"]),
            "libraries": list(self.tech_stack["libraries"]),
            "tools": list(self.tech_stack["tools"]),
            "versions": self.tech_stack["versions"],
            "meta": self.tech_stack["meta"],
            "best_practices": self.best_practices
        }
        return result

    def _detect_laravel(self) -> bool:
        """Detect Laravel framework."""
        # Check for Laravel specific files and directories
        laravel_indicators = [
            (self.workspace_path / "artisan").exists(),
            (self.workspace_path / "app" / "Http" / "Kernel.php").exists(),
            (self.workspace_path / "bootstrap" / "app.php").exists(),
            self._find_specific_files(["web.php", "api.php"]),  # routes
            # Check composer.json for Laravel
            self._check_composer_for_package("laravel/framework")
        ]
        return any(laravel_indicators)

    def _detect_symfony(self) -> bool:
        """Detect Symfony framework."""
        symfony_indicators = [
            (self.workspace_path / "bin" / "console").exists(),
            (self.workspace_path / "config" / "bundles.php").exists(),
            (self.workspace_path / "src" / "Kernel.php").exists(),
            self._check_composer_for_package("symfony/framework-bundle")
        ]
        return any(symfony_indicators)

    def _detect_codeigniter(self) -> bool:
        """Detect CodeIgniter framework."""
        ci_indicators = [
            (self.workspace_path / "system" / "CodeIgniter.php").exists(),
            (self.workspace_path / "application" / "config" / "config.php").exists(),
            self._find_specific_files(["index.php"]) and self._find_specific_files(["Config.php"]),
            self._check_composer_for_package("codeigniter4/framework")
        ]
        return any(ci_indicators)

    def _detect_wordpress(self) -> bool:
        """Detect WordPress."""
        wp_indicators = [
            (self.workspace_path / "wp-config.php").exists(),
            (self.workspace_path / "wp-content").exists(),
            (self.workspace_path / "wp-includes").exists(),
            self._find_specific_files(["functions.php", "style.css"]) and 
            self._find_specific_files(["index.php"])
        ]
        return any(wp_indicators)

    def _check_composer_for_package(self, package_name: str) -> bool:
        """Check if a specific package exists in composer.json."""
        composer_path = self.workspace_path / "composer.json"
        if not composer_path.exists():
            return False
        
        try:
            with open(composer_path, "r") as f:
                composer_data = json.load(f)
            
            # Check both require and require-dev
            require = composer_data.get("require", {})
            require_dev = composer_data.get("require-dev", {})
            
            return package_name in require or package_name in require_dev
        except Exception:
            return False
