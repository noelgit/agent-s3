"""
Database tool for secure database operations with fallback to shell commands.

Provides an abstraction layer for database access using SQLAlchemy with a fallback
to BashTool for resilience when native database access fails. Enhanced for security,
error handling, and feature completeness.
"""

import os
import json
import logging
import re
import time # Added for timing
from typing import Dict, Any, List, Optional
from contextlib import contextmanager
from urllib.parse import quote_plus
import shlex # Added for safer command building

try:
    import sqlalchemy
    from sqlalchemy import create_engine, text, inspect
    from sqlalchemy.exc import (
        SQLAlchemyError,
        OperationalError,
        ProgrammingError,
        IntegrityError,
    )
    SQLALCHEMY_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dependency
    # Provide lightweight fallbacks when SQLAlchemy is not installed so that
    # tests which monkeypatch these objects can still run without raising
    # AttributeError. These stub classes mimic the SQLAlchemy exception
    # hierarchy used within this module.
    SQLALCHEMY_AVAILABLE = False

    class SQLAlchemyError(Exception):
        """Base class used when SQLAlchemy is unavailable."""

    class OperationalError(SQLAlchemyError):
        pass

    class ProgrammingError(SQLAlchemyError):
        pass

    class IntegrityError(SQLAlchemyError):
        pass

    sqlalchemy = None
    create_engine = None
    text = None
    inspect = None

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

    # Stricter validation patterns
    DANGEROUS_COMMANDS_REGEX = re.compile(
        r"\b(DROP\s+(TABLE|DATABASE|USER|INDEX)|TRUNCATE\s+TABLE|DELETE\s+FROM\s+
            (?!.*\bWHERE\b)|GRANT\s+|REVOKE\s+|CREATE\s+USER|ALTER\s+
                USER)\b",        re.IGNORECASE | re.MULTILINE    )
    POTENTIAL_INJECTION_REGEX = re.compile(
        r"(--|;|/\*|\*/|xp_cmdshell|WAITFOR\s+DELAY|BENCHMARK\(|SLEEP\()",
        re.IGNORECASE
    )

    def __init__(self, config, bash_tool: Optional[BashTool] = None):
        """Initialize the database tool with configuration.

        Args:
            config: Configuration object containing database settings
            bash_tool: Optional BashTool for executing shell commands
        """
        self.config = config
        self.bash_tool = bash_tool or BashTool(config)

        # Initialize connections dictionary
        self.connections = {}

        # Track if we can use SQLAlchemy
        self.use_sqlalchemy = SQLALCHEMY_AVAILABLE

        # Log SQLAlchemy availability
        if self.use_sqlalchemy:
            logger.info("SQLAlchemy is available, using for database operations")
        else:
            logger.warning("SQLAlchemy not available, falling back to shell commands for all operations")

        # Set up database connections
        self._setup_connections()

    def _get_db_env_vars(self) -> Dict[str, str]:
        """Get database environment variables for secure credential management.

        Returns:
            Dictionary of environment variables
        """
        db_env_vars = {}

        # Extract database configurations
        db_configs = self.config.config.get("databases", {})

        # Add environment variables for each database
        for db_name, db_config in db_configs.items():
            db_type = db_config.get("type", "postgresql").lower()

            # Create environment variables based on database type
            if db_type == "postgresql":
                # PostgreSQL uses PGPASSWORD
                password = db_config.get("password", "")
                if password:
                    db_env_vars["PGPASSWORD"] = password

            # Create DB_NAME_USER and DB_NAME_PASSWORD environment variables
            env_prefix = f"DB_{db_name.upper()}"
            username = db_config.get("username", "")
            password = db_config.get("password", "")

            if username:
                db_env_vars[f"{env_prefix}_USER"] = username
            if password:
                db_env_vars[f"{env_prefix}_PASSWORD"] = password

        return db_env_vars

    def _setup_connections(self) -> None:
        """Set up database connections using SQLAlchemy if available."""
        if not self.use_sqlalchemy:
            logger.warning("SQLAlchemy not available, skipping connection setup")
            return

        # Extract database configurations
        db_configs = self.config.config.get("databases", {})

        if not db_configs:
            logger.warning("No database configurations found in config")
            return

        for db_name, db_config in db_configs.items():
            try:
                # Build connection string
                connection_string = self._build_connection_string(db_config)

                # Create engine with a pool
                engine = create_engine(
                    connection_string,
                    pool_size=5,
                    max_overflow=10,
                    pool_timeout=30,
                    pool_recycle=1800,  # Recycle connections after 30 minutes
                    echo=False  # Set to True for SQL query logging
                )

                # Test connection
                with engine.connect() as conn:
                    conn.execute(text("SELECT 1"))

                # Store the engine
                self.connections[db_name] = engine
                logger.info("%s", Successfully connected to database '{db_name}')

            except Exception as e:
                logger.error("%s", Failed to connect to database '{db_name}': {e})
                # Don't store failed connections

    def _build_connection_string(self, db_config: Dict[str, Any]) -> str:
        """Build SQLAlchemy connection string from configuration.

        Args:
            db_config: Database configuration dictionary

        Returns:
            SQLAlchemy connection string

        Raises:
            ValueError: If database type is not supported
        """
        db_type = db_config.get("type", "postgresql").lower()

        if db_type not in self.SUPPORTED_TYPES:
            raise ValueError(f"Unsupported database type: {db_type}")

        # Handle SQLite separately
        if db_type == "sqlite":
            db_path = db_config.get("path", "db.sqlite")
            return f"sqlite:///{db_path}"

        # Build connection string for PostgreSQL and MySQL
        host = db_config.get("host", "localhost")
        port = db_config.get("port", 5432 if db_type == "postgresql" else 3306)
        database = db_config.get("database", "")
        username = db_config.get("username", "")
        password = db_config.get("password", "")

        # URL encode username and password for safety
        safe_username = quote_plus(username) if username else ""
        safe_password = quote_plus(password) if password else ""

        # Build authentication part
        auth_part = ""
        if safe_username:
            auth_part = safe_username
            if safe_password:
                auth_part += f":{safe_password}"
            auth_part += "@"

        # Build connection string based on database type
        if db_type == "postgresql":
            return f"postgresql://{auth_part}{host}:{port}/{database}"
        elif db_type == "mysql":
            return f"mysql+pymysql://{auth_part}{host}:{port}/{database}"

        # Fallback (shouldn't reach here due to supported types check)
        raise ValueError(f"Failed to build connection string for {db_type}")

    @contextmanager
    def get_connection(self, db_name: str = "default"):
        # ...existing code...

        engine = self.connections[db_name]
        connection = None # Initialize connection to None
        transaction = None # Initialize transaction to None
        try:
            connection = engine.connect()
            transaction = connection.begin()
            logger.debug("%s", Acquired connection and started transaction for {db_name})
            yield connection
            transaction.commit()
            logger.debug("%s", Committed transaction for {db_name})
        except SQLAlchemyError as e: # Catch specific SQLAlchemy errors
            if transaction:
                transaction.rollback()
                logger.error("%s", Database transaction rolled back for {db_name} due to error: {e})
            else:
                 logger.error("%s", Database connection failed for {db_name}: {e})
            # Re-raise the specific error for better upstream handling
            raise e
        finally:
            if connection:
                connection.close()
                logger.debug("%s", Closed connection for {db_name})

    # --- Explicit Transaction Control ---
    def begin_transaction(self, db_name: str = "default")
         -> Optional["sqlalchemy.engine.Connection"]:        """Begin a transaction manually. Returns the connection. Caller must commit/rollback and close."""
        if not self.use_sqlalchemy:
            logger.warning("Manual transactions require SQLAlchemy. Operation skipped.")
            return None
        if db_name not in self.connections:
            logger.error("%s", Database '{db_name}' not configured or connection failed)
            return None

        engine = self.connections[db_name]
        connection = None
        try:
            connection = engine.connect()
            connection.begin() # Start transaction
            logger.info("%s", Manual transaction started for {db_name})
            return connection
        except SQLAlchemyError as e:
            logger.error("%s", Failed to begin manual transaction for {db_name}: {e})
            if connection:
                connection.close()
            return None

    def commit_transaction(self, connection: "sqlalchemy.engine.Connection") -> bool:
        """Commit a manually started transaction and close the connection."""
        if not connection or connection.closed:
            logger.error("Cannot commit: Invalid or closed connection provided.")
            return False
        try:
            if connection.in_transaction():
                 connection.commit()
                 logger.info("Manual transaction committed.")
            else:
                 logger.warning("No active transaction to commit.")
            return True
        except SQLAlchemyError as e:
            logger.error("%s", Failed to commit manual transaction: {e})
            return False
        finally:
            connection.close()
            logger.debug("Manual transaction connection closed after commit attempt.")

    def rollback_transaction(self, connection: "sqlalchemy.engine.Connection") -> bool:
        """Roll back a manually started transaction and close the connection."""
        if not connection or connection.closed:
            logger.error("Cannot rollback: Invalid or closed connection provided.")
            return False
        try:
            if connection.in_transaction():
                connection.rollback()
                logger.info("Manual transaction rolled back.")
            else:
                logger.warning("No active transaction to rollback.")
            return True
        except SQLAlchemyError as e:
            logger.error("%s", Failed to rollback manual transaction: {e})
            return False
        finally:
            connection.close()
            logger.debug("Manual transaction connection closed after rollback attempt.")
    # --- End Explicit Transaction Control ---

    def execute_query(self, query: str, params: Optional[Dict[str, Any]] = None,
                     db_name: str = "default", force_fallback: bool = False) -> Dict[str, Any]:
        """Execute a database query with optional parameters.

        Uses SQLAlchemy if available, falls back to BashTool if necessary.
        Enhanced validation and error reporting.

        Args:\n            # ...existing args...
        Returns:\n            # ...existing returns...
        """
        start_time = time.time()  # Start timing
        if not query or not query.strip(): # Check for empty/whitespace query
            return {"success": False, "error": "Query cannot be empty", "results": [], "duration_ms": 0}

        params = params or {}

        # Enhanced security validation
        validation_result = self._validate_query(query)
        if not validation_result["valid"]:
            logger.warning("%s", Query validation failed: {validation_result['reason']})
            return {
                "success": False,
                "error": validation_result["reason"],
                "results": [],
                "duration_ms": (time.time() - start_time) * 1000 # Add duration
            }

        # Try SQLAlchemy first
        if self.use_sqlalchemy and not force_fallback and db_name in self.connections:
            try:
                result = self._execute_with_sqlalchemy(query, params, db_name)
                result["duration_ms"] = (time.time() - start_time) * 1000 # Add duration
                logger.info("%s", Executed query via SQLAlchemy on {db_name} in {result['duration_ms']:.2f} ms)
                return result
            except (OperationalError, ProgrammingError, IntegrityError) as e: # Catch specific, potentially recoverable errors
                 logger.warning("%s", SQLAlchemy query failed with {type(e).__name__}: {e}. Falling back to BashTool.)
                 # Fall through to BashTool
            except SQLAlchemyError as e: # Catch other SQLAlchemy errors
                 error_msg = f"SQLAlchemy query failed unexpectedly: {e}"
                 logger.error(error_msg)
                 # Decide whether to fallback or fail immediately based on error type if needed
                 # For now, we'll return the error without fallback for non-operational errors
                 return {"success": False, "error": error_msg, "results": [], "duration_ms": (time.time() - start_time) * 1000}
            except Exception as e: # Catch any other unexpected errors during SQLAlchemy execution
                 error_msg = f"Unexpected error during SQLAlchemy execution: {e}"
                 logger.exception(error_msg) # Log with traceback
                 return {"success": False, "error": error_msg, "results": [], "duration_ms": (time.time() - start_time) * 1000}

        # Fallback to BashTool
        logger.info("%s", Attempting query execution via BashTool fallback for {db_name})
        try:
            result = self._execute_with_bash_tool(query, params, db_name)
            result["duration_ms"] = (time.time() - start_time) * 1000 # Add duration
            if result["success"]:
                 logger.info("%s", Executed query via BashTool on {db_name} in {result['duration_ms']:.2f} ms)
            else:
                 logger.error("%s", BashTool query failed on {db_name}: {result.get('error', 'Unknown error)}")
            return result
        except Exception as e:
            error_msg = f"Database query failed with BashTool fallback: {e}"
            logger.exception(error_msg) # Log with traceback
            return {"success": False, "error": error_msg, "results": [], "duration_ms": (time.time() - start_time) * 1000}

    def _execute_with_sqlalchemy(self, query: str, params: Dict[str, Any], db_name: str) -> Dict[str
        , Any]:        """Execute a query using SQLAlchemy.

        Args:
            query: SQL query to execute
            params: Dictionary of query parameters
            db_name: The name of the database configuration to use

        Returns:
            Dictionary with success status, results, and error message if any
        """
        start_time = time.time() # Start timing
        try:
            with self.get_connection(db_name) as connection:
                result = connection.execute(text(query), **params)
                # Commit is handled by the context manager
                duration = (time.time() - start_time) * 1000
                return {
                    "success": True,
                    "results": self._parse_sqlalchemy_results(result),
                    "duration_ms": duration
                }
        except SQLAlchemyError as e:
            # Use specific exceptions if possible
            raise OperationalError(f"SQLAlchemy execution failed: {e}", orig=e, params=params, statement=query) from e

    def _execute_with_bash_tool(self, query: str, params: Dict[str, Any], db_name: str) -> Dict[str, Any]:
        """Execute a query using SQLAlchemy with BashTool as a final fallback."""

        start_time = time.time()
        try:
            with self.get_connection(db_name) as connection:
                result = connection.execute(text(query), params)
                duration = (time.time() - start_time) * 1000
                return {
                    "success": True,
                    "results": self._parse_sqlalchemy_results(result),
                    "duration_ms": duration,
                }
        except SQLAlchemyError as exc:
            logger.warning(
                "SQLAlchemy execution failed in _execute_with_bash_tool: %s. Falling back to shell command.",
                exc,
            )

        # Fallback to shell command only if SQLAlchemy fails
        db_configs = self.config.config.get("databases", {})
        db_config = db_configs.get(db_name, {})
        db_type = db_config.get("type", "postgresql").lower()

        command = self._build_db_command(db_config, query)
        logger.debug("%s", Executing BashTool command: {command})
        exit_code, output = self.bash_tool.run_command(command, timeout=60)

        if exit_code == 0:
            if db_type == "sqlite":
                try:
                    results = json.loads(output)
                    duration = (time.time() - start_time) * 1000
                    return {"success": True, "results": results, "duration_ms": duration}
                except json.JSONDecodeError as e:
                    duration = (time.time() - start_time) * 1000
                    return {"success": False, "error": f"JSON decode error: {e}", "raw_output": output, "duration_ms": duration}

            clean_output = self._clean_csv_output(output)
            results = self._parse_cli_output(clean_output, db_type)
            duration = (time.time() - start_time) * 1000
            return {"success": True, "results": results, "duration_ms": duration}

        error_detail = output.strip().split("\n")[-1]
        duration = (time.time() - start_time) * 1000
        return {
            "success": False,
            "error": f"Command failed with exit code {exit_code}. Error: {error_detail}",
            "raw_output": output,
            "duration_ms": duration,
        }

    def _build_db_command(self, db_config: Dict[str, Any], query: str) -> str:
        """Build the command to execute based on database type.

        Args:
            db_config: Database configuration dictionary
            query: SQL query to execute

        Returns:
            Command string to execute
        """
        db_type = db_config.get("type", "postgresql").lower()
        client = self.DB_CLIENTS.get(db_type)
        if not client:
            raise ValueError(f"Unsupported database type: {db_type}")

        # Sanitize inputs for command line safety - Use shlex.quote
        safe_query = shlex.quote(query) # Use shlex.quote for better shell safety

        if db_type == "sqlite":
            db_path = shlex.quote(db_config.get("path", "db.sqlite")) # Quote path
            # Use -json flag if sqlite3 version supports it, otherwise fallback
            # This requires checking sqlite3 version, complex for now, stick to headers
            return f"{client} {db_path} -header -csv {safe_query}" # Use CSV for simpler parsing

        # For PostgreSQL/MySQL
        host = shlex.quote(db_config.get("host", "localhost"))
        port = str(db_config.get("port", 5432 if db_type == "postgresql" else 3306))
        database = shlex.quote(db_config.get("database", ""))

        # Get credentials - prefer environment variables
        db_name_env = db_config.get("name", "default").upper() # Use different var name
        username = shlex.quote(os.environ.get(f"DB_{db_name_env}_USER") or db_config.get("username", ""))
        password = os.environ.get(f"DB_{db_name_env}_PASSWORD") or db_config.get("password", "") # Don't quote password directly

        # Build arguments based on database type
        if db_type == "postgresql":
            # Set PGPASSWORD environment variable instead of passing it on command line
            # Handled by BashTool if env_vars are passed correctly
            # os.environ["PGPASSWORD"] = password # Avoid setting directly here if BashTool handles env
            cmd_args = self.DB_CLI_ARGS[db_type].format(
                host=host, port=port, username=username, database=database
            )
            # Use --csv for easier parsing, -t for tuples only, -A for unaligned
            return f"{client} {cmd_args} --csv -t -A -c {safe_query}"
        elif db_type == "mysql":
            # For MySQL, use -pPASSWORD (no space)
            cmd_args = self.DB_CLI_ARGS[db_type].format(
                host=host, port=port, username=username,
                password="", # Placeholder
                database=database
            )
            # Quote the password argument carefully if it exists
            password_arg = f"-p{shlex.quote(password)}" if password else ""
            # Use --batch --raw for cleaner output, -e for execute
            return f"{client} {cmd_args} {password_arg} --batch --raw -e {safe_query}"

        # Fallback - should not reach here
        return f"{client} -e {safe_query}"

    def _parse_sqlalchemy_results(self, result: "sqlalchemy.engine.Result") -> List[Dict[str, Any]]:
        """Convert SQLAlchemy result to a list of dictionaries."""
        try:
            if hasattr(result, "mappings"):
                return [dict(row) for row in result.mappings()]
            keys = result.keys()
            return [dict(zip(keys, row)) for row in result.fetchall()]
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("Failed to parse SQLAlchemy results: %s", exc)
            return []

    def _parse_cli_output(self, output: str, db_type: str) -> List[Dict[str, Any]]:
        """Parse the CLI output from the database command.

        Args:
            output: Raw output string from the command
            db_type: Type of the database (postgresql, mysql, sqlite)

        Returns:
            List of dictionaries with parsed output
        """
        clean_lines = [line for line in output.strip().split('\n') if line]  # Remove empty lines
        if not clean_lines:
            return []

        try:
            # Handle CSV output from sqlite and postgresql
            if db_type in ["sqlite", "postgresql"] and clean_lines:
                import csv
                from io import StringIO

                # Use csv reader
                reader = csv.reader(StringIO('\\n'.join(clean_lines)))
                headers = next(reader)
                results = [dict(zip(headers, row)) for row in reader]
                return results

            elif db_type == "mysql" and clean_lines: # MySQL uses tab-separated by default with --batch --raw
                import csv
                from io import StringIO

                reader = csv.reader(StringIO('\\n'.join(clean_lines)), delimiter='\\t')
                headers = next(reader)
                results = [dict(zip(headers, row)) for row in reader]
                return results

            # Fallback: return the raw output if parsing fails or format is unexpected
            logger.warning("%s", Could not parse CLI output for {db_type}, returning raw lines.)
            return [{"output": '\\n'.join(clean_lines)}]

        except (StopIteration, csv.Error) as e: # Catch CSV parsing errors
             logger.error("%s", Error parsing CLI output ({db_type}) as CSV: {e}\\nOutput:\\n{output})
             return [{"raw_output": '\\n'.join(clean_lines)}] # Return raw on parsing error
        except Exception as e: # Catch any other parsing errors
             logger.error("%s", Unexpected error parsing CLI output ({db_type}): {e}\\nOutput:\\n{output})
             return [{"raw_output": '\\n'.join(clean_lines)}]

    def _validate_query(self, query: str) -> Dict[str, Any]:
        """Validate the query for potential security issues.

        Args:
            query: SQL query string to validate

        Returns:
            Dictionary with validation result and reason if invalid
        """
        # Use stricter regex patterns
        if self.DANGEROUS_COMMANDS_REGEX.search(query):
            match = self.DANGEROUS_COMMANDS_REGEX.search(query).group(1)
            return {"valid": False, "reason": f"Potentially unsafe operation detected: {match}"}

        # Check for UPDATE/DELETE without WHERE (simplified check)
        if re.search(r"\b(UPDATE|DELETE\s+
            FROM)\b", query, re.IGNORECASE) and not re.search(r"\bWHERE\b", query, re.IGNORECASE):            return {"valid": False, "reason": "UPDATE or DELETE without WHERE clause is discouraged"}

        # Check for potential injection patterns
        if self.POTENTIAL_INJECTION_REGEX.search(query):
            match = self.POTENTIAL_INJECTION_REGEX.search(query).group(1)
            return {"valid": False, "reason": f"Potential SQL injection pattern detected: {match}"}

        # Check for balanced quotes (basic check)
        if query.count("\"") % 2 != 0 or query.count('\'') % 2 != 0:
             return {"valid": False, "reason": "Unbalanced quotes detected"}

        return {"valid": True}

    def execute_script(self, script_path: str, db_name: str = "default") -> Dict[str, Any]:
        """Execute a SQL script file.

        Args:
            script_path: File path to the SQL script
            db_name: The name of the database configuration to use

        Returns:
            Dictionary with success status, results, and error message if any
        """
        execution_start_time = time.time() # Start timing for duration calculation

        # Read the SQL script file
        try:
            with open(script_path, 'r') as file:
                script_content = file.read()
        except Exception as e:
            return {"success": False, "error": f"Failed to read script file: {e}"}

        # Split script into individual queries - Improved splitting
        # Handles simple cases, might fail with complex PL/SQL or comments
        queries = [q.strip() for q in re.split(r';\\s*$\\n?|\';\\s*(?=--)|;\s*(?=/\\*)', script_content, flags=re.MULTILINE) if q.strip()]

        if not queries:
             return {"success": False, "error": "No valid queries found in script"}

        logger.info("%s", Executing {len(queries)} queries from script: {script_path})
        results = []

        # Option 1: Execute within a single transaction (if using SQLAlchemy)
        if self.use_sqlalchemy and db_name in self.connections:
            try:
                with self.get_connection(db_name) as conn: # Use context manager for transaction
                    for i, query in enumerate(queries):
                        logger.debug("%s", Executing script query {i+1}/{len(queries)})
                        validation = self._validate_query(query)
                        if not validation["valid"]:
                            raise ValueError(f"Invalid query in script: {validation['reason']}\\nQuery: {query[:100]}...")

                        result = conn.execute(text(query))
                        results.append({
                            "success": True,
                            "query_index": i,
                            "rowcount": result.rowcount if hasattr(result, "rowcount") else None
                        })
                    # Transaction committed automatically by context manager if no errors
                    duration = (time.time() - execution_start_time) * 1000
                    logger.info("%s", Successfully executed script {script_path} via SQLAlchemy in {duration:.2f} ms)
                    return {"success": True, "results": results, "queries_executed": len(results), "duration_ms": duration}
            except Exception as e:
                 duration = (time.time() - execution_start_time) * 1000
                 error_msg = f"Script execution failed via SQLAlchemy: {e}"
                 logger.error(error_msg)
                 # Transaction rolled back automatically by context manager
                 return {"success": False, "error": error_msg, "partial_results": results, "duration_ms": duration}

        # Option 2: Execute queries individually (fallback or if SQLAlchemy not used)
        logger.warning("%s", Executing script {script_path} query by query (no single transaction))
        for i, query in enumerate(queries):
            logger.debug("%s", Executing script query {i+1}/{len(queries)})
            result = self.execute_query(query, db_name=db_name) # Uses execute_query's validation
            results.append(result)

            # Stop on first error
            if not result["success"]:
                duration = (time.time() - execution_start_time) * 1000
                return {
                    "success": False,
                    "error": f"Script execution failed at query {i+
                        1}: {result.get('error', 'Unknown error')}",                    "partial_results": results,
                    "duration_ms": duration # Add duration
                }

        duration = (time.time() - execution_start_time) * 1000
        logger.info("%s", Successfully executed script {script_path} query-by-query in {duration:.2f} ms)
        return {
            "success": True,
            "results": results,
            "queries_executed": len(results),
            "duration_ms": duration # Add duration
        }

    def get_schema_info(self, db_name: str = "default", table_name: Optional[str] = None)
         -> Dict[str, Any]:        """Get database schema information for all tables or a specific table.

        Args:
            db_name: The name of the database configuration to use
            table_name: Optional specific table name to inspect

        Returns:
            Dictionary with schema information
        """
        start_time = time.time() # Start timing
        db_configs = self.config.config.get("databases", {})

        if db_name not in db_configs:
            logger.error("%s", Database '{db_name}' not configured)
            return {"success": False, "error": f"Database '{db_name}' not configured"}

        db_config = db_configs[db_name]
        db_type = db_config.get("type", "postgresql").lower()

        # Use SQLAlchemy Inspector if available for more reliable schema info
        if self.use_sqlalchemy and db_name in self.connections:
            try:
                engine = self.connections[db_name]
                inspector = inspect(engine)
                schema_data = {}

                tables_to_inspect = [table_name] if table_name else inspector.get_table_names()

                for tbl in tables_to_inspect:
                    columns = inspector.get_columns(tbl)
                    schema_data[tbl] = [
                        {
                            "column_name": col["name"],
                            "data_type": str(col["type"]), # Convert type object to string
                            "is_nullable": col["nullable"],
                            "default": col.get("default"),
                            "is_primary_key": col.get("primary_key", False),
                        } for col in columns
                    ]
                    # Add index and foreign key info if needed
                    # schema_data[tbl]["indexes"] = inspector.get_indexes(tbl)
                    # schema_data[tbl]["foreign_keys"] = inspector.get_foreign_keys(tbl)

                duration = (time.time() - start_time) * 1000
                logger.info("%s", Retrieved schema info for {db_name} via SQLAlchemy Inspector in {duration:.2f} ms)
                return {"success": True, "schema": schema_data, "method": "sqlalchemy_inspector", "duration_ms": duration}
            except Exception as e:
                logger.warning("%s", SQLAlchemy Inspector failed for schema info: {e}. Falling back to query.)
                # Fall through to query-based method

        # Fallback to query-based schema retrieval
        logger.info("%s", Attempting schema retrieval via query for {db_name})
        query = "" # Initialize query
        params = {}

        # Query to get table information - customize based on database type
        if db_type == "postgresql":
            table_filter_pg = ""
            if table_name:
                 table_filter_pg = "AND table_name = :table_name"
                 params["table_name"] = table_name
            query = f"""
                SELECT
                    table_name, column_name, data_type, is_nullable, column_default
                FROM
                    information_schema.columns
                WHERE
                    table_schema = 'public'
                    {table_filter_pg}
                ORDER BY
                    table_name, ordinal_position
            """

        elif db_type == "mysql":
            database = db_config.get("database", "")
            params["table_schema"] = database
            table_filter_mysql = ""
            if table_name:
                 table_filter_mysql = "AND table_name = :table_name"
                 params["table_name"] = table_name
            query = f"""
                SELECT
                    table_name, column_name, data_type, is_nullable, column_default
                FROM
                    information_schema.columns
                WHERE
                    table_schema = :table_schema
                    {table_filter_mysql}
                ORDER BY
                    table_name, ordinal_position
            """
        elif db_type == "sqlite":
             table_filter_sqlite = ""
             if table_name:
                  table_filter_sqlite = "AND m.name = :table_name"
                  params["table_name"] = table_name
             query = f"""
                SELECT
                    m.name AS table_name,
                    p.name AS column_name,
                    p.type AS data_type,
                    p.notnull AS is_nullable,
                    p.dflt_value AS column_default
                FROM
                    sqlite_master AS m
                JOIN
                    pragma_table_info(m.name) AS p ON m.name = p.table_name
                WHERE
                    m.type = 'table' AND
                    m.name NOT LIKE 'sqlite_%'
                    {table_filter_sqlite}
                ORDER BY
                    m.name, p.cid
            """

        result = self.execute_query(query, params=params, db_name=db_name) # Use execute_query

        # Structure the result if successful
        if result["success"]:
            schema_data = {}
            for row in result.get("results", []):
                tbl = row.get("table_name")
                if tbl not in schema_data:
                    schema_data[tbl] = []
                schema_data[tbl].append({
                    "column_name": row.get("column_name"),
                    "data_type": row.get("data_type"),
                    "is_nullable": row.get("is_nullable") == 'YES' if db_type != 'sqlite' else row.get("is_nullable"), # Adjust based on output
                })
            result["schema"] = schema_data # Add structured schema
            del result["results"] # Remove raw results
            result["duration_ms"] = (time.time() - start_time) * 1000 # Recalculate duration
            logger.info("%s", Retrieved schema info for {db_name} via query in {result['duration_ms']:.2f} ms)
        else:
             result["duration_ms"] = (time.time() - start_time) * 1000 # Add duration on failure too
             logger.error("%s", Failed to retrieve schema info for {db_name} via query: {result.get('error)}")

        return result

    def explain_query(self, query: str, params: Optional[Dict[str, Any]] = None,
                      db_name: str = "default") -> Dict[str, Any]:
        """Get the execution plan for a query (EXPLAIN).

        Args:
            query: SQL query to explain (typically SELECT, INSERT, UPDATE, DELETE)
            params: Optional query parameters
            db_name: The name of the database configuration to use

        Returns:
            Dictionary with the execution plan or error
        """
        start_time = time.time()
        # Basic validation: Ensure it's a DML query, not something like CREATE TABLE
        query_lower = query.strip().lower()
        if not (query_lower.startswith("select") or query_lower.startswith("insert") or \
                query_lower.startswith("update") or query_lower.startswith("delete")):
            return {"success": False, "error": "EXPLAIN typically applies to SELECT, INSERT, UPDATE, DELETE", "duration_ms": (time.time() - start_time) * 1000}

        # Prepend EXPLAIN (syntax might vary slightly, basic EXPLAIN is common)
        explain_query = f"EXPLAIN {query}"

        # Execute the EXPLAIN query - use execute_query for validation and execution
        result = self.execute_query(explain_query, params=params, db_name=db_name)

        # Rename 'results' to 'plan' for clarity
        if result["success"]:
            result["plan"] = result.pop("results", [])
            logger.info("%s", Retrieved query plan for {db_name} in {result.get('duration_ms', 0):.2f} ms)
        else:
             logger.error("%s", Failed to retrieve query plan for {db_name}: {result.get('error)}")
             result["plan"] = [] # Ensure plan key exists even on failure

        return result

    def test_connection(self, db_name: str = "default") -> Dict[str,
         Any]:  # Return type changed to Any        """Test database connection. Returns detailed status."""
        start_time = time.time()
        # Try SQLAlchemy first if available
        if self.use_sqlalchemy and db_name in self.connections:
            try:
                # Use a simple query that works across most DBs
                with self.get_connection(db_name) as conn:
                    result = conn.execute(text("SELECT 1"))
                    scalar_result = result.scalar() # Fetch the result
                duration = (time.time() - start_time) * 1000
                logger.info("%s", SQLAlchemy connection test successful for {db_name} in {duration:.2f} ms)
                return {
                    "success": True,
                    "message": f"Connection successful (Result: {scalar_result})",
                    "duration_ms": duration
                }
            except SQLAlchemyError as e: # Catch specific errors
                duration = (time.time() - start_time) * 1000
                logger.warning("%s", SQLAlchemy connection test failed for {db_name}: {e})
                # Fall through to BashTool, but record the SQLAlchemy error
                sqlalchemy_error = str(e)
            except Exception as e: # Catch unexpected errors
                 duration = (time.time() - start_time) * 1000
                 logger.error("%s", Unexpected error during SQLAlchemy connection test for {db_name}: {e})
                 return {"success": False, "error": f"Unexpected error: {e}", "duration_ms": duration}

        # Fallback to BashTool
        logger.info("%s", Attempting connection test via BashTool fallback for {db_name})
        try:
            result = self.execute_query("SELECT 1", db_name=db_name, force_fallback=True)
            duration = (time.time() - start_time) * 1000 # Recalculate duration
            if result["success"]:
                # Try to get the actual result from the output if possible
                select_result = result.get("results", [{}])[0].get("1", "N/A") # Adjust key based on parsing
                logger.info("%s", BashTool connection test successful for {db_name} in {duration:.2f} ms)
                return {
                    "success": True,
                    "message": f"Connection successful using fallback (Result: {select_result})",
                    "duration_ms": duration
                }
            else:
                logger.error("%s", BashTool connection test failed for {db_name}: {result.get('error)}")
                return {
                    "success": False,
                    "error": result.get("error", "Unknown error during fallback test"),
                    "duration_ms": duration,
                    "sqlalchemy_error": sqlalchemy_error if 'sqlalchemy_error' in locals() else None # Include previous error if exists
                }
        except Exception as e:
            duration = (time.time() - start_time) * 1000
            logger.error("%s", Connection test failed during BashTool fallback for {db_name}: {e})
            return {
                "success": False,
                "error": f"Connection test failed: {str(e)}",
                "duration_ms": duration,
                "sqlalchemy_error": sqlalchemy_error if 'sqlalchemy_error' in locals() else None # Include previous error if exists
            }
