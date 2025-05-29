"""
Context Provider Interfaces for Agent-S3 Context Management

Defines the contracts for all context providers used by the ContextRegistry.
"""
from abc import abstractmethod
from typing import Any
from typing import Dict
from typing import List
from typing import Literal
from typing import Optional
from typing import Protocol
from typing import TypedDict

class ContextProvider(Protocol):
    """Base protocol for all context providers."""
    pass

class TechStackProvider(ContextProvider):
    """Provides information about the project's technology stack."""
    @abstractmethod
    def get_tech_stack(self) -> Dict[str, Any]:
        ...

class FileContextProvider(ContextProvider):
    """Provides context related to files and their history."""
    @abstractmethod
    def get_relevant_files(self, query: str, top_n: int = 10) -> List[Dict[str, Any]]:
        ...

    @abstractmethod
    def get_file_history(self, file_path: Optional[str] = None) -> Dict[str, Any]:
        ...

    @abstractmethod
    def get_file_metadata(self, file_path: Optional[str] = None) -> Dict[str, Any]:
        ...

    @abstractmethod
    def read_file(self, file_path: str) -> str:
        """Reads the content of a specific file."""
        ...

    @abstractmethod
    def get_code_elements(self, file_path: str) -> List[Dict[str, Any]]:
        """Gets detailed information about code elements (functions, classes) in a file."""
        ...

    @abstractmethod
    def get_file_imports(self, file_path: str) -> List[Dict[str, Any]]:
        """Gets the list of modules imported by a file."""
        ...

    @abstractmethod
    def get_files_importing(self, file_path: str) -> List[str]:
        """Gets the list of files that import the given file."""
        ...

    @abstractmethod
    def get_convention_related_files(self, file_path: str) -> List[str]:
        """Gets files related by naming convention."""
        ...

    @abstractmethod
    def get_hotspot_files(self) -> List[str]:
        """Gets files with high change frequency."""
        ...

    @abstractmethod
    def get_code_ownership(self) -> Dict[str, List[str]]:
        """Gets information about primary authors/contributors per file/module."""
        ...


class ProjectContextProvider(ContextProvider):
    """Provides context about the overall project structure and configuration."""
    @abstractmethod
    def get_project_structure(self) -> Dict[str, Any]:
        ...

    @abstractmethod
    def get_config_files(self) -> Dict[str, Any]:
        ...

    @abstractmethod
    def get_project_root(self) -> str:
        """Gets the absolute path to the project root directory."""
        ...

    @abstractmethod
    def get_coding_guidelines(self) -> Optional[str]:
        """Gets project-specific coding guidelines."""
        ...

class TestContextProvider(ContextProvider):
    """Provides context related to testing."""
    @abstractmethod
    def find_test_files(self, impl_file_path: str) -> List[str]:
        """Locates corresponding test files for an implementation file."""
        ...

    @abstractmethod
    def suggest_unit_tests(self, code_element: Dict[str, Any]) -> List[str]:
        """Generates basic unit test ideas based on a code element."""
        ...


    @abstractmethod
    def get_test_framework_dependencies(self, test_type: str, language: str) -> Dict[str, bool]:
        """Checks if necessary testing libraries are installed for a given test type and language."""
        ...

class MemoryContextProvider(ContextProvider):
    """Provides historical context from past tasks and interactions."""
    @abstractmethod
    def get_similar_tasks(self, query: str, top_n: int = 5) -> List[Dict[str, Any]]:
        """Retrieves summaries or details of previously completed similar tasks."""
        ...

class DependencyNode(TypedDict):
    """Represents a node in the project dependency graph.

    Attributes:
      id: Unique node identifier (e.g., file path or file_path:ClassName).
      type: Node type ('file', 'class', 'function', 'module', 'variable').
      name: Human-readable name of the node.
      path: File path where the node is defined.
      language: Programming language (e.g., 'python', 'javascript').
      line: Line number of definition (0-based), if known.
      framework_role: Optional role within a framework (e.g., 'FastAPI route handler').
    """
    id: str
    type: Literal["file", "class", "function", "module", "variable"]
    name: str
    path: Optional[str]
    language: Optional[str]
    line: Optional[int]
    framework_role: Optional[str]

class DependencyEdge(TypedDict):
    """Represents a directed dependency between two nodes in the graph.

    Attributes:
      source: ID of the source DependencyNode.
      target: ID of the target DependencyNode.
      type: Dependency type ('import', 'call', 'inherit', 'route_handler', 'component_usage', etc.).
      location: Optional line number where the dependency occurs (0-based).
    """
    source: str
    target: str
    type: Literal[
        "import", "call", "inherit", "contains",
        "route_handler", "component_usage",
        "di_injection", "data_fetcher", "module_dependency"
    ]
    location: Optional[int]

class DependencyGraphProvider(ContextProvider):
    """Protocol to provide a project dependency graph.

    Method:
      get_dependency_graph(scope: Optional[str] = None) -> Dict[str, Any]
    Returns:
      A dictionary with 'nodes' (mapping IDs to DependencyNode) and 'edges' (list of DependencyEdge).
    """
    @abstractmethod
    def get_dependency_graph(self, scope: Optional[str] = None) -> Dict[str, Any]:
        ...
