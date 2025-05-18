"""High level database operations using DatabaseTool."""

from typing import Optional, Dict, Any

from agent_s3.tools.database_tool import DatabaseTool


class DatabaseManager:
    """Wrapper around :class:`DatabaseTool` providing higher level operations."""

    def __init__(self, coordinator=None, database_tool: Optional[DatabaseTool] = None) -> None:
        self.coordinator = coordinator
        self.database_tool = database_tool or getattr(coordinator, "database_tool", None)
        self.scratchpad = getattr(coordinator, "scratchpad", None)

    def _log(self, message: str) -> None:
        if self.scratchpad:
            self.scratchpad.log("DatabaseManager", message)

    def setup_database(self, db_name: str = "default") -> Dict[str, Any]:
        """Verify and prepare the given database."""
        if not self.database_tool:
            return {"success": False, "error": "Database tool not available"}
        self._log(f"Setting up database {db_name}")
        return self.database_tool.test_connection(db_name)

    def run_migration(self, script_path: str, db_name: str = "default") -> Dict[str, Any]:
        """Run a SQL migration script using ``DatabaseTool``."""
        if not self.database_tool:
            return {"success": False, "error": "Database tool not available"}
        self._log(f"Running migration {script_path} on {db_name}")
        return self.database_tool.execute_script(script_path, db_name=db_name)

    def execute_query(self, sql: str, db_name: str = "default") -> Dict[str, Any]:
        """Execute a SQL query."""
        if not self.database_tool:
            return {"success": False, "error": "Database tool not available"}
        self._log(f"Executing query on {db_name}")
        return self.database_tool.execute_query(sql, db_name=db_name)

