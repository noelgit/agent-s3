"""
Standardized data structures for parser outputs (imports, functions, classes, etc.)
"""
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

from dataclasses import dataclass
from dataclasses import field

@dataclass
class Import:
    module: str
    alias: Optional[str] = None
    is_local: bool = False
    line_number: int = 0
    source_text: str = ""

@dataclass
class Parameter:
    name: str
    type_hint: Optional[str] = None
    default_value: Optional[str] = None

@dataclass
class FunctionDef:
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
    visibility: str = "public"

@dataclass
class ClassDef:
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
    name: str
    value: Optional[str] = None
    type_hint: Optional[str] = None
    line_number: int = 0
    is_constant: bool = False
    scope: str = "module"

@dataclass
class Dependency:
    source: str
    target: str
    type: str = "import"

@dataclass
class CodeStructure:
    imports: List[Import] = field(default_factory=list)
    functions: List[FunctionDef] = field(default_factory=list)
    classes: List[ClassDef] = field(default_factory=list)
    variables: List[VariableDef] = field(default_factory=list)
    dependencies: List[Dependency] = field(default_factory=list)
    comments: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
