"""
Enhanced fallback parser with improved regex patterns for languages without dedicated parsers.
"""
import re
from typing import List

from agent_s3.tools.parsing.parser_interface import (
    ILanguageParser,
    CodeStructure,
    Import,
    FunctionDef,
    ClassDef,
    VariableDef,
    Dependency,
)

class EnhancedRegexParser(ILanguageParser):
    language = "generic"
    supported_extensions = []

    def parse_file(self, file_path: str) -> CodeStructure:
        with open(file_path, "r", encoding="utf-8") as f:
            code = f.read()
        return self.parse_code(code, file_path)

    def parse_code(self, code: str, file_path: str = None) -> CodeStructure:
        """Parse code using simple regex heuristics."""
        imports = self.extract_imports(code)
        functions = self.extract_functions(code)
        classes = self.extract_classes(code)
        variables = self.extract_variables(code)
        dependencies = self.extract_dependencies(code)

        return CodeStructure(
            imports=imports,
            functions=functions,
            classes=classes,
            variables=variables,
            dependencies=dependencies,
            errors=[],
        )

    def extract_imports(self, code: str) -> List[Import]:
        """Extract import like statements from code."""
        imports: List[Import] = []
        lines = code.splitlines()
        for i, line in enumerate(lines, 1):
            line_strip = line.strip()

            m = re.match(r"import\s+([\w\.]+)(?:\s+as\s+(\w+))?", line_strip)
            if m:
                imports.append(
                    Import(
                        module=m.group(1),
                        alias=m.group(2),
                        line_number=i,
                        source_text=line_strip,
                    )
                )
                continue

            m = re.match(r"from\s+([\w\.]+)\s+import\s+([\w\*,\s]+)", line_strip)
            if m:
                imports.append(
                    Import(
                        module=f"{m.group(1)}.{m.group(2).strip()}",
                        line_number=i,
                        source_text=line_strip,
                    )
                )
                continue

            m = re.match(r"#include\s+[<\"]([^>\"]+)[>\"]", line_strip)
            if m:
                imports.append(
                    Import(
                        module=m.group(1),
                        is_local=line_strip.find("<") == -1,
                        line_number=i,
                        source_text=line_strip,
                    )
                )
                continue

            # JavaScript/Node.js require
            m = re.search(r"require\s*\(\s*['\"]([^'\"]+)['\"]\s*\)", line_strip)
            if m:
                imports.append(
                    Import(
                        module=m.group(1),
                        line_number=i,
                        source_text=line_strip,
                    )
                )
                continue

            # ES6 imports
            m = re.search(r"import\s+(?:{\s*[\w\s,]+\s*}|[\w\s*]+)\s+from\s+['\"]([^'\"]+
                )['\"]", line_strip)            if m:
                imports.append(
                    Import(
                        module=m.group(1),
                        line_number=i,
                        source_text=line_strip,
                    )
                )
                continue

            # PHP uses/requires
            m = re.search(r"(?:use|require|include|require_once|include_once)\s+['\"]?([^;'\"]+
                )['\"]?", line_strip)            if m:
                imports.append(
                    Import(
                        module=m.group(1),
                        line_number=i,
                        source_text=line_strip,
                    )
                )

        return imports

    def extract_functions(self, code: str) -> List[FunctionDef]:
        """Extract function definitions using regex heuristics."""
        functions: List[FunctionDef] = []
        # Match Python/JavaScript/PHP function definitions
        pattern = re.compile(
            r"^\s*(?:def|function|async\s+function|public\s+function|private\s+function|static\s+
                function)\s+(?P<name>[A-Za-z_][\w]*)",            re.MULTILINE
        )
        for match in pattern.finditer(code):
            start_line = code.count("\n", 0, match.start()) + 1
            functions.append(
                FunctionDef(
                    name=match.group("name"),
                    start_line=start_line,
                )
            )
        # Generic C/JS style functions without keyword
        pattern2 = re.compile(
            r"^\s*(?P<name>[A-Za-z_][\w]*)\s*\([^\)]*\)\s*\{", re.MULTILINE
        )
        for match in pattern2.finditer(code):
            start_line = code.count("\n", 0, match.start()) + 1
            if not any(f.name == match.group("name") for f in functions):
                functions.append(
                    FunctionDef(name=match.group("name"), start_line=start_line)
                )

        # Lambda/arrow functions with explicit names
        pattern3 = re.compile(
            r"(?:const|let|var)\s+(?P<name>[A-Za-z_][\w]*)\s*=\s*(?:function|\([^\)]*\)\s*=>)",
            re.MULTILINE
        )
        for match in pattern3.finditer(code):
            start_line = code.count("\n", 0, match.start()) + 1
            if not any(f.name == match.group("name") for f in functions):
                functions.append(
                    FunctionDef(name=match.group("name"), start_line=start_line)
                )

        # Class methods
        pattern4 = re.compile(
            r"^\s*(?:public|private|protected|static|async)?\s*(?P<name>[A-Za-z_][\w]*)\s*\([^\)]*\)\s*{",
            re.MULTILINE
        )
        for match in pattern4.finditer(code):
            start_line = code.count("\n", 0, match.start()) + 1
            method_name = match.group("name")
            # Skip if it's a common constructor name or already found
            if method_name not in ("constructor", "init", "__init__") and not any(f.name == method_name for f in functions):
                functions.append(
                    FunctionDef(name=method_name, start_line=start_line)
                )

        return functions

    def extract_classes(self, code: str) -> List[ClassDef]:
        """Extract class definitions."""
        classes: List[ClassDef] = []
        # Standard class declarations
        pattern = re.compile(
            r"^\s*(?:class|interface|trait|abstract\s+class)\s+(?P<name>[A-Za-z_][\w]*)",
            re.MULTILINE
        )
        for match in pattern.finditer(code):
            start_line = code.count("\n", 0, match.start()) + 1
            classes.append(ClassDef(name=match.group("name"), start_line=start_line))

        # JavaScript class expressions
        pattern2 = re.compile(
            r"(?:const|let|var)\s+(?P<name>[A-Za-z_][\w]*)\s*=\s*class\s*{",
            re.MULTILINE
        )
        for match in pattern2.finditer(code):
            start_line = code.count("\n", 0, match.start()) + 1
            classes.append(ClassDef(name=match.group("name"), start_line=start_line))

        # TypeScript interfaces
        pattern3 = re.compile(
            r"(?:export\s+)?interface\s+(?P<name>[A-Za-z_][\w]*)",
            re.MULTILINE
        )
        for match in pattern3.finditer(code):
            start_line = code.count("\n", 0, match.start()) + 1
            classes.append(ClassDef(name=match.group("name"), start_line=start_line))

        return classes

    def extract_variables(self, code: str) -> List[VariableDef]:
        """Extract simple variable assignments."""
        variables: List[VariableDef] = []
        # Match variable declarations across languages
        pattern = re.compile(
            r"^\s*(?:var|let|const|public|private|protected|static|final|int|float|double|char|bool|string|auto)?\s*(?P<name>[A-Za-z_][\w]*)\s*=",
            re.MULTILINE,
        )
        for match in pattern.finditer(code):
            line_no = code.count("\n", 0, match.start()) + 1
            variables.append(VariableDef(name=match.group("name"), line_number=line_no))

        # PHP variables
        pattern2 = re.compile(r"^\s*\$(?P<name>[A-Za-z_][\w]*)\s*=", re.MULTILINE)
        for match in pattern2.finditer(code):
            line_no = code.count("\n", 0, match.start()) + 1
            variables.append(VariableDef(name=match.group("name"), line_number=line_no))

        # TypeScript/Java declarations without assignment
        pattern3 = re.compile(
            r"^\s*(?:public|private|protected)?\s*(?:const|readonly)?\s*(?P<name>[A-Za-z_][\w]*)\s*:\s*[A-Za-z_][\w<>,\[\]]*\s*;",
            re.MULTILINE
        )
        for match in pattern3.finditer(code):
            line_no = code.count("\n", 0, match.start()) + 1
            variables.append(VariableDef(name=match.group("name"), line_number=line_no))

        return variables

    def extract_dependencies(self, code: str) -> List[Dependency]:
        """Derive dependencies from imports and class inheritance."""
        deps: List[Dependency] = []

        # Import dependencies
        for imp in self.extract_imports(code):
            deps.append(Dependency(source="", target=imp.module, type="import"))

        # Extract class inheritance in OOP languages
        pattern = re.compile(
            r"class\s+([A-Za-z_][\w]*)\s+(?:extends|implements|:)\s+([A-Za-z_][\w,\s]*)",
            re.MULTILINE,
        )
        for match in pattern.finditer(code):
            base_classes = re.split(r',\s*', match.group(2))
            for base in base_classes:
                base = base.strip()
                deps.append(Dependency(source=match.group(1), target=base, type="inherit"))

        # Function calls (basic detection)
        pattern2 = re.compile(r"(?P<name>[A-Za-z_][\w]*)\s*\([^\)]*\)", re.MULTILINE)
        for match in pattern2.finditer(code):
            func_name = match.group("name")
            # Skip common built-ins and low-signal names
            if func_name not in ("print", "if", "for", "while", "log", "console"):
                deps.append(Dependency(source="", target=func_name, type="call"))

        return deps

    def get_language_capability_score(self) -> float:
        """Return a score indicating how capable this parser is.

        The score is between 0 and 1, where:
        - 0.0: Not capable at all
        - 0.5: Moderately capable with good heuristics
        - 1.0: Full AST-level parsing
        """
        return 0.5  # Enhanced from 0.2 with improved regex patterns
