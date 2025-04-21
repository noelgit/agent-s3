"""Database tool for secure database operations with fallback to shell commands.

Provides an abstraction layer for database access using SQLAlchemy with a fallback
to BashTool for resilience when native database access fails.
"""

import os
import json
import logging
import re
from typing import Dict, Any, List, Optional, Tuple, Union, Set
from contextlib import contextmanager
from urllib.parse import quote_plus

try:
    import sqlalchemy
    from sqlalchemy import create_engine, text
    from sqlalchemy.exc import SQLAlchemyError
    from sqlalchemy.orm import sessionmaker
    SQLALCHEMY_AVAILABLE = True
except ImportError:
    SQLALCHEMY_AVAILABLE = False

from agent_s3.tools.bash_tool import BashTool

logger = logging.getLogger(__name__)


class DatabaseTool:
    """Tool for secure database operations with fallback to shell commands."""
    
    # Explicitly list supported database types
    SUPPORTED_TYPES = ["postgresql", "mysql", "sqlite"]
    
    # Map database types to CLI clients
    DB_CLIENTS = {
        "postgresql": "psql",
        "mysql": "mysql",
        "sqlite": "sqlite3"
    }
    
    # Map database types to connection parameter formats for CLI
    DB_CLI_ARGS = {
        "postgresql": "-h {host} -p {port} -U {username} -d {database}",
        "mysql": "-h{host} -P{port} -u{username} -p{password} {database}",
        "sqlite": "{database}"
    }
    
    def __init__(self, config, bash_tool: Optional[BashTool] = None):
        """Initialize database tool with configuration.
        
        Args:
            config: The agent configuration object
            bash_tool: Optional BashTool instance for fallback operations
        """
        self.config = config
        self.connections = {}
        self.active_db_types: Set[str] = set()
        self.use_sqlalchemy = SQLALCHEMY_AVAILABLE
        
        # Initialize or use provided BashTool for fallbacks
        self.bash_tool = bash_tool or BashTool(
            sandbox=config.config.get("sandbox_environment", True),
            env_vars=self._get_db_env_vars()
        )
        
        if not self.use_sqlalchemy:
            logger.warning("SQLAlchemy not available. Using BashTool fallback for all database operations.")
        
        # Initialize connections
        self._setup_connections()
        
        # Log active database types
        if self.active_db_types:
            logger.info(f"DatabaseTool initialized with support for: {', '.join(self.active_db_types)}")
        else:
            logger.warning("DatabaseTool initialized but no databases are configured")
    
    def _get_db_env_vars(self) -> Dict[str, str]:
        """Extract database environment variables for BashTool."""
        env_vars = {}
        for var_name, var_value in os.environ.items():
            if var_name.startswith("DB_") or var_name.endswith("_PASSWORD"):
                env_vars[var_name] = var_value
        return env_vars
    
    def _setup_connections(self) -> None:
        """Set up database connections based on configuration."""
        if not self.use_sqlalchemy:
            return  # Skip SQLAlchemy setup if not available
            
        db_configs = self.config.config.get("databases", {})
        for db_name, db_config in db_configs.items():
            db_type = db_config.get("type", "postgresql").lower()
            
            if db_type not in self.SUPPORTED_TYPES:
                logger.warning(f"Unsupported database type '{db_type}' for '{db_name}'. "
                              f"Supported types are: {', '.join(self.SUPPORTED_TYPES)}")
                continue
            
            try:
                connection_string = self._build_connection_string(db_config)
                engine = create_engine(
                    connection_string,
                    pool_size=db_config.get("pool_size", 5),
                    max_overflow=db_config.get("max_overflow", 10),
                    pool_timeout=db_config.get("timeout", 30),
                    pool_recycle=db_config.get("recycle", 3600),
                )
                
                # Test connection
                with engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                    
                self.connections[db_name] = engine
                self.active_db_types.add(db_type)
                logger.info(f"Successfully connected to {db_type} database '{db_name}'")
                
            except Exception as e:
                logger.error(f"Error connecting to {db_type} database '{db_name}': {e}")
                logger.info(f"Will use BashTool fallback for database '{db_name}'")
                # We'll fall back to BashTool for this database when needed
    
    def _build_connection_string(self, db_config: Dict[str, Any]) -> str:
        """Build database connection string from configuration.
        
        Args:
            db_config: Database configuration dictionary
            
        Returns:
            SQLAlchemy connection string
        """
        db_type = db_config.get("type", "postgresql").lower()
        
        if db_type == "sqlite":
            # SQLite uses a file path rather than host/port
            db_path = db_config.get("path", ":memory:")
            return f"sqlite:///{db_path}"
            
        # For other database types (PostgreSQL, MySQL)
        host = db_config.get("host", "localhost")
        port = db_config.get("port", 5432 if db_type == "postgresql" else 3306)
        database = db_config.get("database", "")
        
        # Get credentials securely from environment variables if possible
        db_name = db_config.get("name", "default").upper()
        username = os.environ.get(f"DB_{db_name}_USER") or db_config.get("username", "")
        password = os.environ.get(f"DB_{db_name}_PASSWORD") or db_config.get("password", "")
        
        # URL encode password for special characters
        password_encoded = quote_plus(password)
        
        return f"{db_type}://{username}:{password_encoded}@{host}:{port}/{database}"
    
    @contextmanager
    def get_connection(self, db_name: str = "default"):
        """Get a database connection with automatic transaction management.
        
        Args:
            db_name: The name of the database configuration to use
            
        Yields:
            An active SQLAlchemy connection
            
        Raises:
            ValueError: If the database is not configured or SQLAlchemy is unavailable
        """
        if not self.use_sqlalchemy:
            raise ValueError("SQLAlchemy is not available. Use execute_query with fallback instead.")
            
        if db_name not in self.connections:
            raise ValueError(f"Database '{db_name}' not configured or connection failed")
        
        engine = self.connections[db_name]
        connection = engine.connect()
        transaction = connection.begin()
        
        try:
            yield connection
            transaction.commit()
        except Exception as e:
            transaction.rollback()
            logger.error(f"Database error in transaction: {e}")
            raise
        finally:
            connection.close()
    
    def execute_query(self, query: str, params: Optional[Dict[str, Any]] = None, 
                     db_name: str = "default", force_fallback: bool = False) -> Dict[str, Any]:
        """Execute a database query with optional parameters.
        
        Uses SQLAlchemy if available, falls back to BashTool if necessary.
        
        Args:
            query: SQL query to execute
            params: Optional query parameters for parameterized queries
            db_name: The name of the database configuration to use
            force_fallback: Force using the BashTool fallback
            
        Returns:
            Dictionary with results, success status, and execution info
        """
        if not query:
            return {"success": False, "error": "Query cannot be empty", "results": []}
            
        params = params or {}
        db_configs = self.config.config.get("databases", {})
        
        if db_name not in db_configs:
            return {"success": False, "error": f"Database '{db_name}' not configured", "results": []}
            
        # Basic security validation regardless of execution method
        validation_result = self._validate_query(query)
        if not validation_result["valid"]:
            return {
                "success": False, 
                "error": f"Query validation failed: {validation_result['reason']}", 
                "results": []
            }
        
        # Try SQLAlchemy first if available and not forced to use fallback
        if self.use_sqlalchemy and not force_fallback and db_name in self.connections:
            try:
                return self._execute_with_sqlalchemy(query, params, db_name)
            except Exception as e:
                logger.warning(f"SQLAlchemy query failed: {e}. Falling back to BashTool.")
                # Fall through to BashTool
        
        # Fallback to BashTool
        try:
            return self._execute_with_bash_tool(query, params, db_name)
        except Exception as e:
            error_msg = f"Database query failed with both native and fallback methods: {e}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg, "results": []}
    
    def _execute_with_sqlalchemy(self, query: str, params: Dict[str, Any], db_name: str) -> Dict[str, Any]:
        """Execute query using SQLAlchemy.
        
        Args:
            query: SQL query to execute
            params: Query parameters
            db_name: Database configuration name
            
        Returns:
            Dictionary with results and success status
        """
        results = []
        with self.get_connection(db_name) as conn:
            result = conn.execute(text(query), params)
            
            if result.returns_rows:
                columns = result.keys()
                results = [dict(zip(columns, row)) for row in result.fetchall()]
            
            rowcount = result.rowcount if hasattr(result, "rowcount") else None
            
            return {
                "success": True,
                "method": "sqlalchemy",
                "rowcount": rowcount,
                "results": results
            }
    
    def _execute_with_bash_tool(self, query: str, params: Dict[str, Any], db_name: str) -> Dict[str, Any]:
        """Execute query using BashTool as a fallback.
        
        Args:
            query: SQL query to execute
            params: Query parameters (will be injected carefully)
            db_name: Database configuration name
            
        Returns:
            Dictionary with results and success status
        """
        db_config = self.config.config.get("databases", {}).get(db_name)
        if not db_config:
            raise ValueError(f"Database '{db_name}' not configured")
            
        db_type = db_config.get("type", "postgresql").lower()
        if db_type not in self.SUPPORTED_TYPES:
            raise ValueError(f"Unsupported database type: {db_type}")
            
        client = self.DB_CLIENTS.get(db_type)
        if not client:
            raise ValueError(f"No CLI client configured for database type: {db_type}")
        
        # Apply parameters to the query before execution
        # This is less secure than using prepared statements but necessary for the CLI
        # We'll do our best to sanitize parameters
        if params:
            # Simple parameter replacement - more sophisticated sanitization would be needed
            # in a production environment
            for key, value in params.items():
                if isinstance(value, str):
                    # Escape quotes in string values
                    value = value.replace("'", "''")
                    value = f"'{value}'"
                elif value is None:
                    value = "NULL"
                # Replace parameter placeholders, considering different formats
                query = query.replace(f":{key}", str(value))
                query = query.replace(f"%({key})s", str(value))
        
        # Build command based on database type
        command = self._build_db_command(db_config, query)
        
        # Execute command
        exit_code, output = self.bash_tool.run_command(command, timeout=30)
        
        # Parse output based on database type
        if exit_code == 0:
            results = self._parse_cli_output(output, db_type)
            return {
                "success": True,
                "method": "bash_tool",
                "results": results,
                "raw_output": output
            }
        else:
            return {
                "success": False,
                "method": "bash_tool",
                "error": f"Command failed with exit code {exit_code}",
                "raw_output": output,
                "results": []
            }
    
    def _build_db_command(self, db_config: Dict[str, Any], query: str) -> str:
        """Build a database CLI command for the given configuration and query.
        
        Args:
            db_config: Database configuration
            query: SQL query to execute
            
        Returns:
            Formatted command string
        """
        db_type = db_config.get("type", "postgresql").lower()
        client = self.DB_CLIENTS.get(db_type, "")
        
        # Sanitize inputs for command line safety
        query = query.replace('"', '\\"')  # Escape double quotes
        
        if db_type == "sqlite":
            db_path = db_config.get("path", "db.sqlite")
            return f"{client} {db_path} \".mode json\" \".headers on\" \"{query}\""
            
        # For PostgreSQL/MySQL
        host = db_config.get("host", "localhost")
        port = db_config.get("port", 5432 if db_type == "postgresql" else 3306)
        database = db_config.get("database", "")
        
        # Get credentials - prefer environment variables
        db_name = db_config.get("name", "default").upper()
        username = os.environ.get(f"DB_{db_name}_USER") or db_config.get("username", "")
        password = os.environ.get(f"DB_{db_name}_PASSWORD") or db_config.get("password", "")
        
        # Build arguments based on database type
        if db_type == "postgresql":
            # Set PGPASSWORD environment variable instead of passing it on command line
            os.environ["PGPASSWORD"] = password
            cmd_args = self.DB_CLI_ARGS[db_type].format(
                host=host, port=port, username=username, database=database
            )
            return f"{client} {cmd_args} -t -A -F, -c \"{query}\""
        elif db_type == "mysql":
            # For MySQL, we use -p followed directly by the password (no space)
            cmd_args = self.DB_CLI_ARGS[db_type].format(
                host=host, port=port, username=username, 
                # Empty password in format string - handled by separate -p argument if present
                password="",
                database=database
            )
            password_arg = f"-p{password}" if password else ""
            return f"{client} {cmd_args} {password_arg} --batch --raw -e \"{query}\""
            
        # Fallback - should not reach here given previous validation
        return f"{client} -e \"{query}\""
    
    def _parse_cli_output(self, output: str, db_type: str) -> List[Dict[str, Any]]:
        """Parse CLI output into a structured format.
        
        Args:
            output: Command output string
            db_type: Database type
            
        Returns:
            List of dictionaries representing rows
        """
        # Remove any control characters, warnings, and empty lines
        clean_lines = []
        for line in output.split('\n'):
            line = line.strip()
            if line and not line.startswith('Warning:') and not line.startswith('NOTE:'):
                clean_lines.append(line)
                
        if not clean_lines:
            return []
            
        try:
            if db_type == "sqlite" and clean_lines[0].startswith('[') and clean_lines[-1].endswith(']'):
                # SQLite with JSON output
                json_text = '\n'.join(clean_lines)
                return json.loads(json_text)
                
            elif db_type == "postgresql":
                # PostgreSQL with comma-separated output
                results = []
                if len(clean_lines) >= 2:  # At least header row and one data row
                    headers = clean_lines[0].split(',')
                    for data_line in clean_lines[1:]:
                        values = data_line.split(',')
                        if len(values) == len(headers):
                            results.append(dict(zip(headers, values)))
                return results
                
            elif db_type == "mysql":
                # MySQL with tab-separated output
                results = []
                if len(clean_lines) >= 1:
                    headers = clean_lines[0].split('\t')
                    for data_line in clean_lines[1:]:
                        values = data_line.split('\t')
                        if len(values) == len(headers):
                            results.append(dict(zip(headers, values)))
                return results
                
            # Fallback: return the raw output as a single record
            return [{"output": '\n'.join(clean_lines)}]
                
        except json.JSONDecodeError:
            # If JSON parsing fails, return raw output
            return [{"raw_output": '\n'.join(clean_lines)}]
    
    def _validate_query(self, query: str) -> Dict[str, Any]:
        """Validate a SQL query for basic security concerns.
        
        Args:
            query: SQL query to validate
            
        Returns:
            Dictionary with validation result and reason if invalid
        """
        query_lower = query.lower()
        
        # Check for potentially dangerous operations
        dangerous_ops = {
            "drop table": "table dropping",
            "drop database": "database dropping",
            "truncate table": "table truncation",
            "delete from": "bulk data deletion",
            "grant": "privilege modifications",
            "revoke": "privilege modifications",
            "create user": "user creation",
            "alter user": "user modification",
            "drop user": "user deletion"
        }
        
        for op, description in dangerous_ops.items():
            if op in query_lower:
                return {"valid": False, "reason": f"Potentially unsafe operation: {description}"}
        
        # For UPDATE/DELETE, ensure there's a limiting clause (WHERE)
        if ("update " in query_lower or "delete from" in query_lower) and "where" not in query_lower:
            return {"valid": False, "reason": "UPDATE or DELETE without WHERE clause is not allowed"}
            
        # Check for potential SQL injection patterns
        injection_patterns = [
            "--",            # SQL comment
            ";",             # Command separator
            "/*",            # Block comment
            "waitfor delay", # Time-based injection
            "benchmark(",    # Time-based injection
            "sleep("         # Time-based injection
        ]
        
        for pattern in injection_patterns:
            if pattern in query_lower:
                return {"valid": False, "reason": f"Potential SQL injection pattern detected: {pattern}"}
                
        return {"valid": True}
    
    def execute_script(self, script_path: str, db_name: str = "default") -> Dict[str, Any]:
        """Execute a SQL script file.
        
        Args:
            script_path: Path to the SQL script file
            db_name: The name of the database configuration to use
            
        Returns:
            Dictionary with execution results
        """
        try:
            if not os.path.exists(script_path):
                return {"success": False, "error": f"Script file not found: {script_path}"}
                
            with open(script_path, 'r') as f:
                script_content = f.read()
                
            # Split script into individual queries
            # This is a simplified approach; a proper SQL parser would be better
            queries = re.split(r';(?![^\(]*\))', script_content)
            results = []
            
            for query in queries:
                query = query.strip()
                if query:  # Skip empty queries
                    result = self.execute_query(query, db_name=db_name)
                    results.append(result)
                    
                    # Stop on first error
                    if not result["success"]:
                        return {
                            "success": False,
                            "error": f"Script execution failed: {result.get('error', 'Unknown error')}",
                            "partial_results": results
                        }
            
            return {
                "success": True,
                "results": results,
                "queries_executed": len(results)
            }
            
        except Exception as e:
            return {"success": False, "error": f"Error executing script: {str(e)}"}
    
    def get_schema_info(self, db_name: str = "default") -> Dict[str, Any]:
        """Get database schema information.
        
        Args:
            db_name: The name of the database configuration to use
            
        Returns:
            Dictionary with schema information
        """
        db_configs = self.config.config.get("databases", {})
        if db_name not in db_configs:
            return {"success": False, "error": f"Database '{db_name}' not configured"}
            
        db_config = db_configs[db_name]
        db_type = db_config.get("type", "postgresql").lower()
        
        # Query to get table information - customize based on database type
        if db_type == "postgresql":
            query = """
                SELECT 
                    table_name, 
                    column_name, 
                    data_type, 
                    is_nullable 
                FROM 
                    information_schema.columns 
                WHERE 
                    table_schema = 'public' 
                ORDER BY 
                    table_name, ordinal_position;
            """
        elif db_type == "mysql":
            database = db_config.get("database", "")
            query = f"""
                SELECT 
                    table_name, 
                    column_name, 
                    data_type, 
                    is_nullable 
                FROM 
                    information_schema.columns 
                WHERE 
                    table_schema = '{database}' 
                ORDER BY 
                    table_name, ordinal_position;
            """
        elif db_type == "sqlite":
            query = """
                SELECT 
                    m.name AS table_name, 
                    p.name AS column_name,
                    p.type AS data_type,
                    CASE WHEN p.\"notnull\" = 0 THEN 'YES' ELSE 'NO' END AS is_nullable
                FROM 
                    sqlite_master m
                JOIN 
                    pragma_table_info(m.name) p
                WHERE 
                    m.type = 'table' AND
                    m.name NOT LIKE 'sqlite_%'
                ORDER BY 
                    m.name, p.cid;
            """
        else:
            return {
                "success": False, 
                "error": f"Schema information not supported for database type: {db_type}"
            }
            
        return self.execute_query(query, db_name=db_name)
    
    def test_connection(self, db_name: str = "default") -> Dict[str, bool]:
        """Test database connection.
        
        Args:
            db_name: The name of the database configuration to use
            
        Returns:
            Dictionary with connection test results
        """
        # Try SQLAlchemy first if available
        if self.use_sqlalchemy and db_name in self.connections:
            try:
                with self.get_connection(db_name) as conn:
                    conn.execute(text("SELECT 1"))
                return {
                    "success": True, 
                    "method": "sqlalchemy", 
                    "message": "Connection successful"
                }
            except Exception as e:
                logger.warning(f"SQLAlchemy connection test failed: {e}")
                # Fall through to BashTool
                
        # Fallback to BashTool
        try:
            result = self.execute_query("SELECT 1", db_name=db_name, force_fallback=True)
            if result["success"]:
                return {
                    "success": True, 
                    "method": "bash_tool", 
                    "message": "Connection successful using fallback method"
                }
            else:
                return {
                    "success": False, 
                    "method": "bash_tool", 
                    "error": result.get("error", "Unknown error")
                }
        except Exception as e:
            return {
                "success": False, 
                "error": f"Connection test failed: {str(e)}"
            }