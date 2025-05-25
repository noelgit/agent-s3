"""Deployment Manager for local deployment integration.

This module manages the deployment of applications based on design specifications,
handling configuration, database setup, and application deployment with environment
variable management.
"""

import os
import logging
import json
import re
from .pattern_constants import DEV_MODE_PATTERN, START_DEPLOYMENT_PATTERN
import secrets
import string
from typing import Dict, Any, List, Optional, Tuple
from urllib.parse import quote_plus
from datetime import datetime

logger = logging.getLogger(__name__)


class DatabaseConfig:
    """Configuration for database deployments."""

    def __init__(
        self,
        db_type: str = "sqlite",
        host: str = "localhost",
        port: Optional[int] = None,
        username: str = "",
        password: str = "",
        database: str = "",
        ssl_mode: str = "disable"
    ):
        """Initialize database configuration.

        Args:
            db_type: Database type (sqlite, postgresql, mysql)
            host: Database host
            port: Database port
            username: Database username
            password: Database password
            database: Database name
            ssl_mode: SSL mode for PostgreSQL
        """
        self.db_type = db_type.lower()
        self.host = host

        # Set default ports based on database type
        if port is None:
            if self.db_type == "postgresql":
                self.port = 5432
            elif self.db_type == "mysql":
                self.port = 3306
            else:
                self.port = 0  # No port for SQLite
        else:
            self.port = port

        self.username = username
        self.password = password
        self.database = database
        self.ssl_mode = ssl_mode

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "type": self.db_type,
            "host": self.host,
            "port": self.port,
            "username": self.username,
            "password": self.password,
            "database": self.database,
            "ssl_mode": self.ssl_mode
        }

    def get_connection_string(self) -> str:
        """Generate database connection string based on type."""
        if self.db_type == "sqlite":
            return f"sqlite:///{self.database}"
        elif self.db_type == "postgresql":
            password = quote_plus(self.password) if self.password else ""
            return f"postgresql://{self.username}:{password}@{self.host}:{self.port}/{self.database}?sslmode={self.ssl_mode}"
        elif self.db_type == "mysql":
            password = quote_plus(self.password) if self.password else ""
            return (
                f"mysql+pymysql://{self.username}:{password}@{self.host}:{self.port}/{self.database}"
            )
        else:
            raise ValueError(f"Unsupported database type: {self.db_type}")

    def get_environment_vars(self) -> Dict[str, str]:
        """Get environment variables for this database configuration."""
        prefix = "DATABASE_"

        env_vars = {
            f"{prefix}URL": self.get_connection_string(),
            f"{prefix}TYPE": self.db_type,
        }

        # Add additional vars for non-sqlite databases
        if self.db_type != "sqlite":
            env_vars.update({
                f"{prefix}HOST": self.host,
                f"{prefix}PORT": str(self.port),
                f"{prefix}USER": self.username,
                f"{prefix}PASSWORD": self.password,
                f"{prefix}NAME": self.database,
            })

            # Add SSL mode for PostgreSQL
            if self.db_type == "postgresql":
                env_vars[f"{prefix}SSLMODE"] = self.ssl_mode

        return env_vars


class DeploymentConfig:
    """Configuration for application deployment."""

    def __init__(
        self,
        app_name: str,
        app_type: str,
        host: str = "localhost",
        port: int = 8000,
        debug_mode: bool = False,
        database_config: Optional[DatabaseConfig] = None,
        extra_env_vars: Optional[Dict[str, str]] = None,
        static_dir: Optional[str] = None,
        log_level: str = "info",
        requirements_file: str = "requirements.txt",
        entry_point: str = "app.py",
    ):
        """Initialize deployment configuration.

        Args:
            app_name: Application name
            app_type: Application type (flask, django, express, etc.)
            host: Host to bind to
            port: Port to bind to
            debug_mode: Whether to enable debug mode
            database_config: Database configuration
            extra_env_vars: Additional environment variables
            static_dir: Static files directory
            log_level: Logging level
            requirements_file: Requirements file path
            entry_point: Application entry point
        """
        self.app_name = app_name
        self.app_type = app_type.lower()
        self.host = host
        self.port = port
        self.debug_mode = debug_mode
        self.database_config = database_config
        self.extra_env_vars = extra_env_vars or {}
        self.static_dir = static_dir
        self.log_level = log_level
        self.requirements_file = requirements_file
        self.entry_point = entry_point

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        result = {
            "app_name": self.app_name,
            "app_type": self.app_type,
            "host": self.host,
            "port": self.port,
            "debug_mode": self.debug_mode,
            "extra_env_vars": self.extra_env_vars,
            "static_dir": self.static_dir,
            "log_level": self.log_level,
            "requirements_file": self.requirements_file,
            "entry_point": self.entry_point,
        }

        if self.database_config:
            result["database_config"] = self.database_config.to_dict()

        return result

    def get_environment_vars(self) -> Dict[str, str]:
        """Get all environment variables for this deployment."""
        env_vars = {
            "APP_NAME": self.app_name,
            "APP_HOST": self.host,
            "APP_PORT": str(self.port),
            "DEBUG": "true" if self.debug_mode else "false",
            "LOG_LEVEL": self.log_level.upper(),
        }

        # Add static directory if specified
        if self.static_dir:
            env_vars["STATIC_DIR"] = self.static_dir

        # Add database environment variables if configured
        if self.database_config:
            env_vars.update(self.database_config.get_environment_vars())

        # Add extra environment variables
        env_vars.update(self.extra_env_vars)

        return env_vars


class DeploymentManager:
    """Manages local deployment of applications."""

    def __init__(self, coordinator=None):
        """Initialize the deployment manager.

        Args:
            coordinator: The parent coordinator instance
        """
        self.coordinator = coordinator

        # Initialize tools from coordinator if available
        self.bash_tool = coordinator.bash_tool if coordinator else None
        self.file_tool = coordinator.file_tool if coordinator else None
        self.env_tool = coordinator.env_tool if coordinator else None
        self.database_tool = coordinator.database_tool if coordinator else None
        self.llm = coordinator.router_agent if coordinator else None
        self.scratchpad = coordinator.scratchpad if coordinator else None

        # Track deployment state
        self.current_deployment = None
        self.deployment_log_file = "deployment_log.json"

    def prompt_for_deployment(self, design_file: str = "design.txt") -> bool:
        """Prompt the user if they want to proceed with deployment after design is complete.

        Args:
            design_file: Path to the design file

        Returns:
            True if user wants to proceed with deployment, False otherwise
        """
        # Prepare a message for the user
        message = (
            "The design has been written to design.txt. "
            "Would you like to proceed with local deployment? (yes/no): "
        )

        # If we have access to coordinator's scratchpad, use that to prompt
        if self.coordinator and hasattr(self.coordinator, 'scratchpad'):
            self.coordinator.scratchpad.log("DeploymentManager", message)
            response = input(message).strip().lower()
        else:
            # Fallback to direct input
            response = input(message).strip().lower()

        return response in ["yes", "y", "true", "1"]

    def start_deployment_conversation(self, design_file: str = "design.txt") -> str:
        """Start a deployment conversation based on the design file.

        Args:
            design_file: Path to the design file

        Returns:
            Initial deployment conversation response
        """
        # Read the design file
        design_content = self._read_design_file(design_file)
        if not design_content:
            return "Error: Could not read design file."

        # Log the start of deployment conversation
        if self.scratchpad:
            self.scratchpad.log("DeploymentManager", f"Starting deployment conversation for design: {design_file}")

        # Extract deployment requirements from design
        system_prompt = self._get_deployment_system_prompt()
        user_prompt = f"Design specification:\n\n{design_content}\n\nI'd like to deploy this application locally. What information do you need from me to set up the deployment environment?"

        # Create conversation history
        conversation = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        # Call LLM with deployment role
        response = self._call_llm(conversation)

        if not response:
            return "Error: Failed to start deployment conversation."

        # Save the conversation for continuation
        self._save_conversation(conversation + [{"role": "assistant", "content": response}])

        return response

    def continue_deployment_conversation(self, user_message: str) -> Tuple[str, bool]:
        """Continue the deployment conversation with a user message.

        Args:
            user_message: The user's message

        Returns:
            Tuple of (LLM response, is_deployment_ready)
        """
        # Check for explicit deployment trigger
        if START_DEPLOYMENT_PATTERN.search(user_message):
            return self._prepare_deployment_from_conversation(), True

        # Load existing conversation
        conversation = self._load_conversation()
        if not conversation:
            return "Error: No active deployment conversation. Please start a new one.", False

        # Add user message to conversation
        conversation.append({"role": "user", "content": user_message})

        # Call LLM for continuation
        response = self._call_llm(conversation)

        if not response:
            return "Error: Failed to continue deployment conversation.", False

        # Add response to conversation
        conversation.append({"role": "assistant", "content": response})

        # Save updated conversation
        self._save_conversation(conversation)

        # Check if we have enough information to deploy
        is_deployment_ready = self._check_deployment_readiness(conversation)

        if is_deployment_ready:
            suggestion = "\n\nI think I have all the information needed to start deployment. You can type '/start-deployment' when you're ready to proceed with the local deployment."
            response += suggestion

        return response, is_deployment_ready

    def execute_deployment(
        self, deployment_config: Optional[DeploymentConfig] = None
    ) -> Dict[str, Any]:
        """Execute deployment based on configuration.

        Args:
            deployment_config: Optional deployment configuration

        Returns:
            Dictionary with deployment results
        """
        if self.scratchpad:
            self.scratchpad.log("DeploymentManager", "Starting deployment execution")

        # If no config provided, generate from conversation
        if not deployment_config:
            response = self._prepare_deployment_from_conversation()
            deployment_config = self._extract_deployment_config(response)

        if not deployment_config:
            return {"success": False, "error": "Failed to create valid deployment configuration"}

        # Save current deployment
        self.current_deployment = deployment_config

        # Log the deployment start
        if self.scratchpad:
            self.scratchpad.log("DeploymentManager", f"Deploying application: {deployment_config.app_name}")

        try:
            # 1. Set up environment
            env_result = self._setup_environment(deployment_config)
            if not env_result.get("success", False):
                return {"success": False, "error": f"Environment setup failed: {env_result.get('error')}"}

            # 2. Create environment file
            env_file_result = self._create_env_file(deployment_config)
            if not env_file_result.get("success", False):
                return {"success": False, "error": f"Environment file creation failed: {env_file_result.get('error')}"}

            # 3. Set up database if configured
            if deployment_config.database_config:
                db_result = self._setup_database(deployment_config.database_config)
                if not db_result.get("success", False):
                    return {"success": False, "error": f"Database setup failed: {db_result.get('error')}"}

            # 4. Configure application
            config_result = self._configure_application(deployment_config)
            if not config_result.get("success", False):
                return {"success": False, "error": f"Application configuration failed: {config_result.get('error')}"}

            # 5. Launch application
            launch_result = self._launch_application(deployment_config)
            if not launch_result.get("success", False):
                return {"success": False, "error": f"Application launch failed: {launch_result.get('error')}"}

            # 6. Save deployment log
            self._save_deployment_log(deployment_config, "success")

            return {
                "success": True,
                "message": "Application deployed successfully",
                "deployment": deployment_config.to_dict(),
                "access_url": f"http://{deployment_config.host}:{deployment_config.port}",
                "env_file": ".env"
            }

        except Exception as e:
            error_msg = f"Deployment failed: {str(e)}"
            if self.scratchpad:
                self.scratchpad.log("DeploymentManager", error_msg, level="error")

            # Save deployment log with error
            self._save_deployment_log(deployment_config, "failed", error=str(e))

            return {"success": False, "error": error_msg}

    def _setup_environment(self, config: DeploymentConfig) -> Dict[str, Any]:
        """Set up the deployment environment.

        Args:
            config: Deployment configuration

        Returns:
            Dictionary with setup results
        """
        if self.scratchpad:
            self.scratchpad.log("DeploymentManager", "Setting up deployment environment")

        try:
            # Check for virtual environment
            venv_prefix = ""
            if self.env_tool:
                venv_prefix = self.env_tool.activate_virtual_env()

            # Install requirements
            if os.path.exists(config.requirements_file):
                cmd = f"{venv_prefix}pip install -r {config.requirements_file}"
                if self.bash_tool:
                    exit_code, output = self.bash_tool.run_command(cmd, timeout=300)  # 5 minutes
                    if exit_code != 0:
                        if self.scratchpad:
                            self.scratchpad.log("DeploymentManager", f"Package installation failed: {output}", level="error")
                        return {"success": False, "error": f"Package installation failed: {output}"}

                    if self.scratchpad:
                        self.scratchpad.log("DeploymentManager", "Package installation completed successfully")
            else:
                # Create a default requirements file based on app type
                default_requirements = self._generate_default_requirements(config)
                if self.file_tool:
                    self.file_tool.write_file(config.requirements_file, default_requirements)

                    # Install generated requirements
                    cmd = f"{venv_prefix}pip install -r {config.requirements_file}"
                    if self.bash_tool:
                        exit_code, output = self.bash_tool.run_command(cmd, timeout=300)
                        if exit_code != 0:
                            if self.scratchpad:
                                self.scratchpad.log("DeploymentManager", f"Package installation failed: {output}", level="error")
                            return {"success": False, "error": f"Package installation failed: {output}"}

                        if self.scratchpad:
                            self.scratchpad.log("DeploymentManager", "Package installation completed successfully")

            return {"success": True, "message": "Environment setup completed successfully"}
        except Exception as e:
            if self.scratchpad:
                self.scratchpad.log("DeploymentManager", f"Environment setup failed: {e}", level="error")
            return {"success": False, "error": f"Environment setup failed: {str(e)}"}

    def _create_env_file(self, config: DeploymentConfig) -> Dict[str, Any]:
        """Create a .env file with environment variables.

        Args:
            config: Deployment configuration

        Returns:
            Dictionary with creation results
        """
        if self.scratchpad:
            self.scratchpad.log("DeploymentManager", "Creating .env file")

        try:
            # Generate environment variables
            env_vars = config.get_environment_vars()

            # Add SECRET_KEY if not present
            if "SECRET_KEY" not in env_vars:
                env_vars["SECRET_KEY"] = self._generate_secret_key()

            # Format .env file content with quoting for special characters
            env_content = "\n".join([
                f"{key}={self._format_env_value(value)}" for key, value in env_vars.items()
            ])

            # Write to .env file
            if self.file_tool:
                result = self.file_tool.write_file(".env", env_content)
                if not result:
                    return {"success": False, "error": "Failed to write .env file"}

                if self.scratchpad:
                    self.scratchpad.log("DeploymentManager", "Created .env file successfully")

                return {"success": True, "message": "Created .env file successfully", "env_vars": env_vars}
            else:
                return {"success": False, "error": "File tool not available"}

        except Exception as e:
            if self.scratchpad:
                self.scratchpad.log("DeploymentManager", f"Failed to create .env file: {e}", level="error")
            return {"success": False, "error": f"Failed to create .env file: {str(e)}"}

    def _format_env_value(self, value: str) -> str:
        """Quote or escape environment variable values as needed."""
        if not isinstance(value, str):
            value = str(value)

        # Safe characters without quoting
        if re.fullmatch(r"[A-Za-z0-9_./@:+-]+", value) and " " not in value:
            return value

        # Escape backslashes and quotes, then wrap in double quotes
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'

    def _setup_database(self, db_config: DatabaseConfig) -> Dict[str, Any]:
        """Set up and initialize the database.

        Args:
            db_config: Database configuration

        Returns:
            Dictionary with setup results
        """
        if self.scratchpad:
            self.scratchpad.log("DeploymentManager", f"Setting up {db_config.db_type} database")

        try:
            if db_config.db_type == "sqlite":
                # For SQLite, just create the directory if needed
                db_dir = os.path.dirname(db_config.database)
                if db_dir and not os.path.exists(db_dir):
                    os.makedirs(db_dir, exist_ok=True)

                if self.scratchpad:
                    self.scratchpad.log("DeploymentManager", f"SQLite database path prepared: {db_config.database}")

                return {"success": True, "message": f"SQLite database path prepared: {db_config.database}"}

            elif db_config.db_type in ["postgresql", "mysql"]:
                # For PostgreSQL and MySQL, use database_tool if available
                if self.database_tool:
                    # Create a database configuration for the server
                    server_config = {
                        "name": "deployment",
                        "type": db_config.db_type,
                        "host": db_config.host,
                        "port": db_config.port,
                        "username": db_config.username,
                        "password": db_config.password,
                        "database": db_config.database
                    }

                    # Add configuration to database_tool
                    if hasattr(self.database_tool, 'config') and hasattr(self.database_tool.config, 'config'):
                        databases = self.database_tool.config.config.get("databases", {})
                        databases["deployment"] = server_config
                        self.database_tool.config.config["databases"] = databases

                        # Test connection
                        test_result = self.database_tool.test_connection("deployment")
                        if not test_result.get("success", False):
                            # Try to create the database
                            self._create_database(db_config)

                            # Test connection again
                            test_result = self.database_tool.test_connection("deployment")
                            if not test_result.get("success", False):
                                if self.scratchpad:
                                    self.scratchpad.log("DeploymentManager", f"Database connection failed: {test_result.get('error')}", level="error")
                                return {"success": False, "error": f"Database connection failed: {test_result.get('error')}"}

                        if self.scratchpad:
                            self.scratchpad.log("DeploymentManager", f"{db_config.db_type.capitalize()} database connected successfully")

                        return {"success": True, "message": f"{db_config.db_type.capitalize()} database connected successfully"}
                    else:
                        return {"success": False, "error": "Database tool configuration not available"}
                else:
                    # Fallback to manual connection check
                    return {"success": True, "message": f"Database {db_config.db_type} configured, but connection not verified"}
            else:
                return {"success": False, "error": f"Unsupported database type: {db_config.db_type}"}

        except Exception as e:
            if self.scratchpad:
                self.scratchpad.log("DeploymentManager", f"Database setup failed: {e}", level="error")
            return {"success": False, "error": f"Database setup failed: {str(e)}"}

    def _create_database(self, db_config: DatabaseConfig) -> bool:
        """Create a database if it doesn't exist.

        Args:
            db_config: Database configuration

        Returns:
            True if successful, False otherwise
        """
        try:
            if db_config.db_type == "postgresql":
                # Try to connect to 'postgres' database first
                postgres_config = db_config.to_dict()
                postgres_config["database"] = "postgres"

                # Using bash_tool as a fallback
                if self.bash_tool:
                    cmd = f"PGPASSWORD='{db_config.password}' psql -h {db_config.host} -p {db_config.port} -U {db_config.username} -d postgres -c 'CREATE DATABASE {db_config.database};'"
                    exit_code, output = self.bash_tool.run_command(cmd, timeout=30)
                    return exit_code == 0

            elif db_config.db_type == "mysql":
                # Using bash_tool as a fallback
                if self.bash_tool:
                    cmd = f"mysql -h {db_config.host} -P {db_config.port} -u {db_config.username} -p'{db_config.password}' -e 'CREATE DATABASE IF NOT EXISTS {db_config.database};'"
                    exit_code, output = self.bash_tool.run_command(cmd, timeout=30)
                    return exit_code == 0

            return False
        except Exception as e:
            if self.scratchpad:
                self.scratchpad.log("DeploymentManager", f"Database creation failed: {e}", level="error")
            return False

    def _configure_application(self, config: DeploymentConfig) -> Dict[str, Any]:
        """Configure the application based on type.

        Args:
            config: Deployment configuration

        Returns:
            Dictionary with configuration results
        """
        if self.scratchpad:
            self.scratchpad.log("DeploymentManager", f"Configuring {config.app_type} application")

        try:
            # Check if entry point exists
            if not os.path.exists(config.entry_point):
                # Create entry point based on app type
                entry_point_content = self._generate_entry_point(config)

                if self.file_tool:
                    result = self.file_tool.write_file(config.entry_point, entry_point_content)
                    if not result:
                        return {"success": False, "error": f"Failed to create entry point: {config.entry_point}"}

                    if self.scratchpad:
                        self.scratchpad.log("DeploymentManager", f"Created entry point: {config.entry_point}")
                else:
                    return {"success": False, "error": "File tool not available"}

            # Create static directory if needed
            if config.static_dir and not os.path.exists(config.static_dir):
                os.makedirs(config.static_dir, exist_ok=True)

                # Create a sample index.html file
                index_path = os.path.join(config.static_dir, "index.html")
                if not os.path.exists(index_path) and self.file_tool:
                    index_content = self._generate_index_html(config)
                    self.file_tool.write_file(index_path, index_content)

            return {"success": True, "message": f"Application configured successfully: {config.app_type}"}

        except Exception as e:
            if self.scratchpad:
                self.scratchpad.log("DeploymentManager", f"Application configuration failed: {e}", level="error")
            return {"success": False, "error": f"Application configuration failed: {str(e)}"}

    def _launch_application(self, config: DeploymentConfig) -> Dict[str, Any]:
        """Launch the application.

        Args:
            config: Deployment configuration

        Returns:
            Dictionary with launch results
        """
        if self.scratchpad:
            self.scratchpad.log("DeploymentManager", f"Launching application: {config.app_name}")

        try:
            # Determine launch command based on app type
            launch_cmd = self._generate_launch_command(config)

            # Display launch command for the user
            print(f"\nTo launch your application, run the following command in a terminal:\n\n{launch_cmd}\n")

            if self.scratchpad:
                self.scratchpad.log("DeploymentManager", f"Launch command: {launch_cmd}")

            # Return success with launch instructions
            return {
                "success": True,
                "message": "Application ready to launch",
                "launch_command": launch_cmd,
                "access_url": f"http://{config.host}:{config.port}"
            }

        except Exception as e:
            if self.scratchpad:
                self.scratchpad.log("DeploymentManager", f"Application launch failed: {e}", level="error")
            return {"success": False, "error": f"Application launch failed: {str(e)}"}

    def _generate_launch_command(self, config: DeploymentConfig) -> str:
        """Generate the command to launch the application.

        Args:
            config: Deployment configuration

        Returns:
            Launch command string
        """
        # Get virtual environment activation if available
        venv_prefix = ""
        if self.env_tool:
            venv_prefix = self.env_tool.activate_virtual_env()
            if venv_prefix:
                venv_prefix = venv_prefix.rstrip(" && ")

        # Base command with environment vars
        cmd = f"{'source .env && ' if os.path.exists('.env') else ''}"

        # Application-specific launch command
        if config.app_type == "flask":
            cmd += (
                f"{venv_prefix + (' && ' if venv_prefix else '')}"
                f"flask --app {config.entry_point.rstrip('.py')} run --host={config.host} --port={config.port} {'--debug' if config.debug_mode else ''}"
            )
        elif config.app_type == "django":
            cmd += (
                f"{venv_prefix + (' && ' if venv_prefix else '')}"
                f"python manage.py runserver {config.host}:{config.port}"
            )
        elif config.app_type == "fastapi":
            cmd += (
                f"{venv_prefix + (' && ' if venv_prefix else '')}"
                f"uvicorn {config.entry_point.rstrip('.py')}:app --host {config.host} --port {config.port} {'--reload' if config.debug_mode else ''}"
            )
        elif config.app_type in ["node", "express"]:
            cmd += f"node {config.entry_point}"
        elif config.app_type == "python":
            cmd += f"{venv_prefix + ' && ' if venv_prefix else ''}python {config.entry_point}"
        else:
            # Generic fallback
            cmd += f"{venv_prefix + ' && ' if venv_prefix else ''}python {config.entry_point}"

        return cmd

    def _generate_entry_point(self, config: DeploymentConfig) -> str:
        """Generate application entry point file content.

        Args:
            config: Deployment configuration

        Returns:
            Entry point file content
        """
        # Flask application
        if config.app_type == "flask":
            return f"""import os
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__,
            static_folder='{config.static_dir or "static"}',
            template_folder='{config.static_dir or "templates"}')

# Configure from environment
app.config['DEBUG'] = os.getenv('DEBUG', 'false').lower() == 'true'
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', '{self._generate_secret_key()}')

# Database setup (if configured)
if os.getenv('DATABASE_URL'):
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Initialize database - uncomment if using SQLAlchemy
    # from flask_sqlalchemy import SQLAlchemy
    # db = SQLAlchemy(app)

@app.route('/')
def index():
    try:
        return render_template('index.html')
    except:
        return f"<h1>{os.getenv('APP_NAME', 'Flask App')}</h1><p>Running on http://{os.getenv('APP_HOST', '127.0.0.1')}:{os.getenv('APP_PORT', '5000')}</p>"

@app.route('/api/status')
def status():
    return jsonify({{"status": "ok", "app_name": os.getenv('APP_NAME', 'Flask App')}})

if __name__ == '__main__':
    app.run(
        host=os.getenv('APP_HOST', '127.0.0.1'),
        port=int(os.getenv('APP_PORT', 5000)),
        debug=os.getenv('DEBUG', 'false').lower() == 'true'
    )
"""

        # FastAPI application
        elif config.app_type == "fastapi":
            return f"""import os
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables
load_dotenv()

app = FastAPI(
    title=os.getenv('APP_NAME', 'FastAPI App'),
    description="API generated by Agent-S3 Deployment Manager",
    version="0.1.0",
    debug=os.getenv('DEBUG', 'false').lower() == 'true'
)

# Mount static files if the directory exists
static_dir = os.getenv('STATIC_DIR', '{config.static_dir or "static"}')
if Path(static_dir).exists():
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/", response_class=HTMLResponse)
async def read_root():
    static_path = Path(static_dir) / "index.html"
    if static_path.exists():
        return HTMLResponse(content=static_path.read_text())
    else:
        return f"<h1>{{os.getenv('APP_NAME', 'FastAPI App')}}</h1><p>Running on http://{{os.getenv('APP_HOST', '127.0.0.1')}}:{{os.getenv('APP_PORT', '8000')}}</p>"

@app.get("/api/status")
async def status():
    return {{"status": "ok", "app_name": os.getenv('APP_NAME', 'FastAPI App')}}

# Database models (if using database)
# from sqlalchemy import Column, Integer, String, create_engine
# from sqlalchemy.ext.declarative import declarative_base
# from sqlalchemy.orm import sessionmaker

# Base = declarative_base()
# engine = create_engine(os.getenv('DATABASE_URL'))
# SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# class Item(Base):
#     __tablename__ = "items"
#     id = Column(Integer, primary_key=True, index=True)
#     name = Column(String, index=True)
#     description = Column(String)

# Base.metadata.create_all(bind=engine)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app:app",
        host=os.getenv('APP_HOST', '127.0.0.1'),
        port=int(os.getenv('APP_PORT', 8000)),
        reload=os.getenv('DEBUG', 'false').lower() == 'true'
    )
"""

        # Django application would be more complex with multiple files
        elif config.app_type == "django":
            # For Django, we'd need to create a more complete structure,
            # so return a minimal manage.py and suggest running django-admin
            return """#!/usr/bin/env python
import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def main():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)

if __name__ == '__main__':
    # For a new Django project, run:
    # django-admin startproject config .
    if not os.path.exists('config'):
        print("Django project structure not found.")
        print("To create it, run: django-admin startproject config .")
        sys.exit(1)
    main()
"""

        # Node/Express application
        elif config.app_type in ["node", "express"]:
            return f"""const express = require('express');
const path = require('path');
require('dotenv').config();

const app = express();
const PORT = process.env.APP_PORT || 3000;
const HOST = process.env.APP_HOST || 'localhost';

// Middleware
app.use(express.json());
app.use(express.urlencoded({{ extended: true }}));

// Static files
app.use(express.static(path.join(__dirname, '{config.static_dir or "public"}')));

// Routes
app.get('/', (req, res) => {{
    res.sendFile(path.join(__dirname, '{config.static_dir or "public"}', 'index.html'));
}});

app.get('/api/status', (req, res) => {{
    res.json({{ status: 'ok', app_name: process.env.APP_NAME || 'Express App' }});
}});

// Start server
app.listen(PORT, HOST, () => {{
    console.log(`Server running at http://${{HOST}}:${{PORT}}/`);
}});
"""

        # Generic Python application
        else:
            return f"""#!/usr/bin/env python
import os
import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class CustomHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/api/status':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(bytes('{{"status": "ok", "app_name": "' +
                 os.getenv('APP_NAME', 'Python App') + '"}}', 'utf-8'))            return
        return super().do_GET()

def run(host='127.0.0.1', port=8000):
    server_address = (host, port)
    httpd = HTTPServer(server_address, CustomHandler)
    print(f"Server running at http://{{host}}:{{port}}/")
    httpd.serve_forever()

if __name__ == '__main__':
    host = os.getenv('APP_HOST', '127.0.0.1')
    port = int(os.getenv('APP_PORT', 8000))

    # Set directory to serve files from
    static_dir = os.getenv('STATIC_DIR', '{config.static_dir or "static"}')
    if os.path.exists(static_dir):
        os.chdir(static_dir)

    run(host, port)
"""

    def _generate_index_html(self, config: DeploymentConfig) -> str:
        """Generate a sample index.html file.

        Args:
            config: Deployment configuration

        Returns:
            HTML content
        """
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{config.app_name}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
        }}
        .container {{
            border: 1px solid #ddd;
            border-radius: 5px;
            padding: 20px;
            margin-top: 40px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #0066cc;
        }}
        .status {{
            background-color: #f5f5f5;
            padding: 10px;
            border-radius: 3px;
            margin: 20px 0;
        }}
        .status.ok {{
            background-color: #d4edda;
            color: #155724;
        }}
        button {{
            background-color: #0066cc;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
            cursor: pointer;
        }}
        button:hover {{
            background-color: #0056b3;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>{config.app_name}</h1>
        <p>Your application is running successfully!</p>

        <div class="status" id="status">Checking status...</div>

        <button onclick="checkStatus()">Check Status</button>
    </div>

    <script>
        // Check the API status on page load
        window.addEventListener('DOMContentLoaded', checkStatus);

        function checkStatus() {{
            document.getElementById('status').innerHTML = 'Checking status...';
            document.getElementById('status').className = 'status';

            fetch('/api/status')
                .then(response => response.json())
                .then(data => {{
                    document.getElementById('status').innerHTML =
                        `Status: ${{data.status}}<br>App: ${{data.app_name}}`;
                    document.getElementById('status').className = 'status ok';
                }})
                .catch(error => {{
                    document.getElementById('status').innerHTML =
                        `Error connecting to API: ${{error.message}}`;
                    document.getElementById('status').className = 'status';
                }});
        }}
    </script>
</body>
</html>
"""

    def _generate_default_requirements(self, config: DeploymentConfig) -> str:
        """Generate default requirements file content based on app type.

        Args:
            config: Deployment configuration

        Returns:
            Requirements file content
        """
        common_requirements = [
            "python-dotenv",
        ]

        app_specific_requirements = {
            "flask": [
                "flask>=2.3.0",
                "flask-sqlalchemy>=3.0.0",
                "flask-migrate>=4.0.0",
                "werkzeug>=2.3.0",
            ],
            "django": [
                "django>=4.2.0",
                "djangorestframework>=3.14.0",
                "django-cors-headers>=4.0.0",
            ],
            "fastapi": [
                "fastapi>=0.95.0",
                "uvicorn>=0.22.0",
                "pydantic>=2.0.0",
                "sqlalchemy>=2.0.0",
            ],
            "python": [
                "requests>=2.28.0",
                "aiohttp>=3.8.0",
            ]
        }

        # Database requirements
        db_requirements = {
            "postgresql": ["psycopg2-binary>=2.9.0"],
            "mysql": ["pymysql>=1.0.0", "sqlalchemy-utils>=0.40.0"],
            "sqlite": [],  # SQLite is included in Python standard library
        }

        # Combine requirements
        requirements = common_requirements
        requirements.extend(app_specific_requirements.get(config.app_type, []))

        # Add database requirements if configured
        if config.database_config:
            requirements.extend(db_requirements.get(config.database_config.db_type, []))

        # Format the requirements file
        return "\n".join(requirements)

    def _generate_secret_key(self, length: int = 32) -> str:
        """Generate a secure random secret key.

        Args:
            length: Length of the secret key

        Returns:
            Random secret key string
        """
        chars = string.ascii_letters + string.digits + "!@#$%^&*()_-+=[]{}|:;<>,.?/~"
        return ''.join(secrets.choice(chars) for _ in range(length))

    def _save_deployment_log(
        self, config: DeploymentConfig, status: str, error: Optional[str] = None
    ) -> None:
        """Save deployment log to file.

        Args:
            config: Deployment configuration
            status: Deployment status
            error: Optional error message
        """
        try:
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "app_name": config.app_name,
                "app_type": config.app_type,
                "host": config.host,
                "port": config.port,
                "status": status,
            }

            if error:
                log_entry["error"] = error

            # Read existing log if it exists
            if os.path.exists(self.deployment_log_file):
                with open(self.deployment_log_file, 'r') as f:
                    try:
                        logs = json.load(f)
                    except json.JSONDecodeError:
                        logs = {"deployments": []}
            else:
                logs = {"deployments": []}

            # Add new entry
            logs["deployments"].append(log_entry)

            # Write updated log
            with open(self.deployment_log_file, 'w') as f:
                json.dump(logs, f, indent=2)

        except Exception as e:
            if self.scratchpad:
                self.scratchpad.log("DeploymentManager", f"Failed to save deployment log: {e}", level="error")

    def _read_design_file(self, design_file: str) -> str:
        """Read the design file content.

        Args:
            design_file: Path to the design file

        Returns:
            Design file content
        """
        if not os.path.exists(design_file):
            if self.scratchpad:
                self.scratchpad.log("DeploymentManager", f"Design file not found: {design_file}", level="error")
            return ""

        try:
            with open(design_file, 'r') as f:
                return f.read()
        except Exception as e:
            if self.scratchpad:
                self.scratchpad.log("DeploymentManager", f"Failed to read design file: {e}", level="error")
            return ""

    def _save_conversation(self, conversation: List[Dict[str, str]]) -> None:
        """Save deployment conversation to temporary file.

        Args:
            conversation: List of conversation messages
        """
        try:
            with open(".deployment_conversation.json", 'w') as f:
                json.dump(conversation, f, indent=2)
        except Exception as e:
            if self.scratchpad:
                self.scratchpad.log("DeploymentManager", f"Failed to save conversation: {e}", level="error")

    def _load_conversation(self) -> List[Dict[str, str]]:
        """Load deployment conversation from temporary file.

        Returns:
            List of conversation messages
        """
        if not os.path.exists(".deployment_conversation.json"):
            return []

        try:
            with open(".deployment_conversation.json", 'r') as f:
                return json.load(f)
        except Exception as e:
            if self.scratchpad:
                self.scratchpad.log("DeploymentManager", f"Failed to load conversation: {e}", level="error")
            return []

    def _call_llm(self, conversation: List[Dict[str, str]]) -> str:
        """Call LLM with the given conversation.

        Args:
            conversation: Conversation history

        Returns:
            LLM response
        """
        if not self.llm:
            if self.scratchpad:
                self.scratchpad.log("DeploymentManager", "LLM client not available", level="error")
            return ""

        try:
            # Call LLM with deployment role
            response = self.llm.call_llm_agent("deployer", conversation)
            return response
        except Exception as e:
            if self.scratchpad:
                self.scratchpad.log("DeploymentManager", f"LLM call failed: {e}", level="error")
            return ""

    def _get_deployment_system_prompt(self) -> str:
        """Get the system prompt for deployment conversation.

        Returns:
            System prompt string
        """
        return """
        You are an expert deployment engineer tasked with helping the user deploy a software application locally.

        Your responsibilities:
        1. Analyze the design specification to understand the application requirements
        2. Ask clarification questions to gather necessary information for deployment
        3. Provide guidance on setting up the local environment
        4. Help configure databases, environment variables, and application settings
        5. Provide detailed, accurate instructions for deployment

        Follow these guidelines:
        - Focus on practical, concrete steps the user can take immediately
        - Consider the appropriate local deployment strategy based on the application type
        - Ask about the user's operating system and environment to provide tailored instructions
        - Gather details about database requirements, port configuration, and dependencies
        - Explain environment variables that will be needed
        - Prefer containerization or virtual environments for isolation when appropriate

        During the conversation, gather all information needed for deployment:
        1. Application type (web, API, CLI, etc.)
        2. Framework information (e.g., Flask, Django, Express, React)
        3. Database requirements (if any)
        4. Environment variable needs
        5. Dependency requirements
        6. Port and host configuration

        When the user is ready to deploy, you will provide a comprehensive deployment plan with explicit instructions.
        """

    def _check_deployment_readiness(self, conversation: List[Dict[str, str]]) -> bool:
        """Check if we have enough information to start deployment.

        Args:
            conversation: Conversation history

        Returns:
            True if ready for deployment, False otherwise
        """
        # Extract user messages
        user_messages = [msg["content"] for msg in conversation if msg["role"] == "user"]
        assistant_messages = [msg["content"] for msg in conversation if msg["role"] == "assistant"]

        if len(user_messages) < 3 or len(assistant_messages) < 3:
            # Need more conversation to gather requirements
            return False

        # Check if we have received responses about key deployment aspects
        # This is a basic heuristic - could be made more sophisticated
        required_topics = [
            "application type",
            "framework",
            "database",
            "port",
            "environment"
        ]

        # Check for presence of required topics in the conversation
        topics_found = 0
        all_text = " ".join(user_messages + assistant_messages).lower()

        for topic in required_topics:
            if topic in all_text:
                topics_found += 1

        # Consider ready if most topics have been addressed
        return topics_found >= 3

    def _prepare_deployment_from_conversation(self) -> str:
        """Prepare deployment configuration from conversation.

        Returns:
            Deployment preparation response
        """
        # Load conversation
        conversation = self._load_conversation()
        if not conversation:
            return "Error: No active deployment conversation. Please start a new one."

        # Add system prompt to request deployment preparation
        system_prompt = """
        Based on the conversation so far, prepare a concise deployment configuration.

        Your response should be structured as follows:

        1. DEPLOYMENT SUMMARY: A brief summary of what will be deployed

        2. CONFIGURATION:
           - Application Type: (e.g., Flask, Django, Express, etc.)
           - Host: (e.g., localhost, 127.0.0.1)
           - Port: (e.g., 8000)
           - Environment Mode: (development/production)
           - Database: (type and configuration if applicable)

        3. ENVIRONMENT VARIABLES:
           List all environment variables that will be set

        4. DEPLOYMENT STEPS:
           Numbered list of steps to complete the deployment

        5. LAUNCH COMMAND:
           The exact command to start the application

        Be specific and concrete, using only the information gathered from the conversation.
        Format this as a structured report, ready for implementation.
        """

        preparation_prompt = "Based on our conversation, please prepare a deployment configuration that I can implement. Include all the details we've discussed and any recommendations for a smooth deployment."

        # Create conversation for deployment preparation
        preparation_conversation = conversation + [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": preparation_prompt}
        ]

        # Call LLM for deployment preparation
        response = self._call_llm(preparation_conversation)

        if not response:
            return "Error: Failed to prepare deployment configuration."

        return response

    def _extract_deployment_config(self, response: str) -> Optional[DeploymentConfig]:
        """Extract deployment configuration from LLM response.

        Args:
            response: LLM response with deployment configuration

        Returns:
            Extracted DeploymentConfig object or None if extraction fails
        """
        try:
            # Use regex to extract key configuration details
            app_type_match = re.search(
                r"Application Type:?\s*([a-zA-Z0-9_+\- ]+)",
                response,
                re.IGNORECASE,
            )
            app_type = (
                app_type_match.group(1).strip().lower() if app_type_match else "python"
            )

            host_match = re.search(r"Host:?\s*([a-zA-Z0-9_.\-]+)", response, re.IGNORECASE)
            host = host_match.group(1).strip() if host_match else "localhost"

            port_match = re.search(r"Port:?\s*(\d+)", response, re.IGNORECASE)
            port = int(port_match.group(1)) if port_match else 8000

            # Try to extract app name from the summary

            app_name_match = re.search(
                r"DEPLOYMENT SUMMARY.*?([a-zA-Z0-9_\- ]+)(?:application|app|service)",
                response,
                re.IGNORECASE | re.DOTALL,
            )
            app_name = (
                app_name_match.group(1).strip()
                if app_name_match
                else f"{app_type.title()} Application"
            )

            # Extract debug/environment mode
            debug_match = re.search(
                r"(?:Environment Mode|Mode):?\s*([a-zA-Z0-9_\- ]+)",
                response,
                re.IGNORECASE,
            )
            debug_mode = bool(
                debug_match and DEV_MODE_PATTERN.search(debug_match.group(1))
            )
            # Extract database configuration if present
            db_type = None
            db_config = None


            db_section = re.search(
                r"Database:?\s*([^\n]+(?:\n\s+[^\n]+)*)",
                response,
                re.IGNORECASE,
            )
            if db_section:
                db_text = db_section.group(1).lower()
                if "sqlite" in db_text:
                    db_type = "sqlite"
                    db_path_match = re.search(r"(?:path|file):?\s*([a-zA-Z0-9_.\-/\\]+)", db_text)
                    db_path = db_path_match.group(1).strip() if db_path_match else "database.sqlite"
                    db_config = DatabaseConfig(db_type=db_type, database=db_path)

                elif "postgres" in db_text:
                    db_type = "postgresql"
                    host_match = re.search(r"host:?\s*([a-zA-Z0-9_.\-]+)", db_text)
                    port_match = re.search(r"port:?\s*(\d+)", db_text)
                    user_match = re.search(r"(?:user|username):?\s*([a-zA-Z0-9_\-]+)", db_text)
                    pass_match = re.search(r"(?:pass|password):?\s*([a-zA-Z0-9_\-]+)", db_text)
                    db_match = re.search(r"(?:db|database|name):?\s*([a-zA-Z0-9_\-]+)", db_text)

                    db_config = DatabaseConfig(
                        db_type=db_type,
                        host=host_match.group(1).strip() if host_match else "localhost",
                        port=int(port_match.group(1)) if port_match else 5432,
                        username=user_match.group(1).strip() if user_match else "postgres",
                        password=pass_match.group(1).strip() if pass_match else "",
                        database=db_match.group(1).strip() if db_match else "postgres"
                    )

                elif "mysql" in db_text:
                    db_type = "mysql"
                    host_match = re.search(r"host:?\s*([a-zA-Z0-9_.\-]+)", db_text)
                    port_match = re.search(r"port:?\s*(\d+)", db_text)
                    user_match = re.search(r"(?:user|username):?\s*([a-zA-Z0-9_\-]+)", db_text)
                    pass_match = re.search(r"(?:pass|password):?\s*([a-zA-Z0-9_\-]+)", db_text)
                    db_match = re.search(r"(?:db|database|name):?\s*([a-zA-Z0-9_\-]+)", db_text)

                    db_config = DatabaseConfig(
                        db_type=db_type,
                        host=host_match.group(1).strip() if host_match else "localhost",
                        port=int(port_match.group(1)) if port_match else 3306,
                        username=user_match.group(1).strip() if user_match else "root",
                        password=pass_match.group(1).strip() if pass_match else "",
                        database=db_match.group(1).strip() if db_match else "mysql"
                    )

            # Extract environment variables

            env_vars = {}
            env_section = re.search(
                r"ENVIRONMENT VARIABLES:?\s*([^\n]+(?:\n\s+[^\n]+)*)",
                response,
                re.IGNORECASE,
            )
            if env_section:
                env_text = env_section.group(1)
                env_matches = re.findall(r"([A-Z_0-9]+):?\s*([^\n]+)", env_text)
                for key, value in env_matches:
                    env_vars[key.strip()] = value.strip()

            # Create DeploymentConfig object
            return DeploymentConfig(
                app_name=app_name,
                app_type=app_type,
                host=host,
                port=port,
                debug_mode=debug_mode,
                database_config=db_config,
                extra_env_vars=env_vars,
                static_dir="static",  # Default static dir
                log_level="info" if not debug_mode else "debug"
            )

        except Exception as e:
            if self.scratchpad:
                self.scratchpad.log("DeploymentManager", f"Failed to extract deployment config: {e}", level="error")
            return None
