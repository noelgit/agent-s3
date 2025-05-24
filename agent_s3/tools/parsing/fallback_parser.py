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
            m = re.search(r"import\s+(?:{\s*[\w\s,]+\s*}|[\w\s*]+)\s+from\s+['\"]([^'\"]+)['\"]", line_strip)
            if m:
                imports.append(
                    Import(
                        module=m.group(1),
                        line_number=i,
                        source_text=line_strip,
                    )
                )
                continue

            # PHP uses/requires
            m = re.search(r"(?:use|require|include|require_once|include_once)\s+['\"]?([^;'\"]+)['\"]?", line_strip)
            if m:
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
            r"^\s*(?:def|function|async\s+function|public\s+function|private\s+function|static\s+function)\s+(?P<name>[A-Za-z_][\w]*)",
            re.MULTILINE
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

        return variables

    def extract_dependencies(self, code: str) -> List[Dependency]:
        """Derive simple dependencies from imports."""
        deps: List[Dependency] = []
        for imp in self.extract_imports(code):
            deps.append(Dependency(source="", target=imp.module, type="import"))

        # Extract class inheritance
        pattern = re.compile(
            r"class\s+([A-Za-z_][\w]*)\s+(?:extends|implements|:)\s+([A-Za-z_][\w,\s]*)",
            re.MULTILINE,
        )
        for match in pattern.finditer(code):
            base_classes = re.split(r',\s*', match.group(2))
            for base in base_classes:
                base = base.strip()
                deps.append(Dependency(source=match.group(1), target=base, type="inherit"))

        return deps

    def get_language_capability_score(self) -> float:
        return 0.5  # Improved capability with more comprehensive patterns
