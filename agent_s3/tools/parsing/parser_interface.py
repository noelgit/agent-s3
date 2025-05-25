"""
Parser interface defining the contract for language-specific code parsers.

This module provides the ILanguageParser interface for standardized parsing across languages.
"""
from abc import ABC
from abc import abstractmethod
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

from dataclasses import dataclass
from dataclasses import field

@dataclass
class Import:
    """Represents an import statement in code."""
    module: str
    alias: Optional[str] = None
    is_local: bool = False
    line_number: int = 0
    source_text: str = ""

@dataclass
class Parameter:
    """Represents a function parameter."""
    name: str
    type_hint: Optional[str] = None
    default_value: Optional[str] = None

@dataclass
class FunctionDef:
    """Represents a function definition in code."""
    name: str
    parameters: List[Parameter] = field(default_factory=list)
    return_type: Optional[str] = None
    body: str = ""
    docstring: Optional[str] = None
    decorators: List[str] = field(default_factory=list)
    start_line: int = 0
    end_line: int = 0
    is_method: bool = False
    is_async: bool = False
    visibility: str = "public"  # public, private, protected

@dataclass
class ClassDef:
    """Represents a class definition in code."""
    name: str
    methods: List[FunctionDef] = field(default_factory=list)
    attributes: List[Dict[str, Any]] = field(default_factory=list)
    bases: List[str] = field(default_factory=list)
    docstring: Optional[str] = None
    start_line: int = 0
    end_line: int = 0
    decorators: List[str] = field(default_factory=list)

@dataclass
class VariableDef:
    """Represents a variable definition in code."""
    name: str
    value: Optional[str] = None
    type_hint: Optional[str] = None
    line_number: int = 0
    is_constant: bool = False
    scope: str = "module"  # module, class, function

@dataclass
class Dependency:
    """Represents a dependency between code elements."""
    source: str
    target: str
    type: str = "import"  # import, call, inheritance, etc.

@dataclass
class CodeStructure:
    """Standardized structure for parsed code."""
    imports: List[Import] = field(default_factory=list)
    functions: List[FunctionDef] = field(default_factory=list)
    classes: List[ClassDef] = field(default_factory=list)
    variables: List[VariableDef] = field(default_factory=list)
    dependencies: List[Dependency] = field(default_factory=list)
    comments: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


class ILanguageParser(ABC):
    """Interface for language-specific code parsers with strict contract."""

    @abstractmethod
    def parse_file(self, file_path: str) -> CodeStructure:
        """Parse a file into a standardized CodeStructure.

        Args:
            file_path: Path to the file to parse

        Returns:
            A CodeStructure object containing the parsed code elements

        Raises:
            FileNotFoundError: If the file does not exist
            PermissionError: If the file cannot be read
            ValueError: If the file is not valid for the parser's language
            Exception: For other parsing errors
        """
        raise NotImplementedError

    @abstractmethod
    def parse_code(self, code: str, file_path: Optional[str] = None) -> CodeStructure:
        """Parse code string into a standardized CodeStructure.

        Args:
            code: The code string to parse
            file_path: Optional file path for context

        Returns:
            A CodeStructure object containing the parsed code elements

        Raises:
            ValueError: If the code is not valid for the parser's language
            Exception: For other parsing errors
        """
        raise NotImplementedError

    @abstractmethod
    def extract_imports(self, code: str) -> List[Import]:
        """Extract imports from code string.

        Args:
            code: The code to extract imports from

        Returns:
            List of Import objects
        """
        raise NotImplementedError

    @abstractmethod
    def extract_functions(self, code: str) -> List[FunctionDef]:
        """Extract function definitions from code.

        Args:
            code: The code to extract functions from

        Returns:
            List of FunctionDef objects
        """
        raise NotImplementedError

    @abstractmethod
    def extract_classes(self, code: str) -> List[ClassDef]:
        """Extract class definitions from code.

        Args:
            code: The code to extract classes from

        Returns:
            List of ClassDef objects
        """
        raise NotImplementedError

    @abstractmethod
    def extract_variables(self, code: str) -> List[VariableDef]:
        """Extract variable definitions from code.

        Args:
            code: The code to extract variables from

        Returns:
            List of VariableDef objects
        """
        raise NotImplementedError

    @abstractmethod
    def extract_dependencies(self, code: str) -> List[Dependency]:
        """Extract dependencies from code.

        Args:
            code: The code to extract dependencies from

        Returns:
            List of Dependency objects
        """
        raise NotImplementedError

    @abstractmethod
    def get_language_capability_score(self) -> float:
        """Return parser capability score (0.0-1.0) for confidence metrics.

        Returns:
            A float between 0.0 and 1.0 representing the parser's capabilities
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def language(self) -> str:
        """Get the language this parser supports.

        Returns:
            The language name (e.g., 'python', 'javascript')
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def supported_extensions(self) -> List[str]:
        """Get the file extensions this parser supports.

        Returns:
            List of file extensions with leading dot (e.g., ['.py', '.pyw'])
        """
        raise NotImplementedError
