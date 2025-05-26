from __future__ import annotations

import ast
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

from agent_s3.ast_tools.parser import parse_js
from agent_s3.tools.parsing.parser_registry import ParserRegistry

logger = logging.getLogger(__name__)


class PlanValidationError(Exception):
    """Exception raised when plan validation fails."""


@dataclass
class CodeElement:
    """Represents a code element with position information."""

    name: str
    element_type: str
    start_line: int = 0
    end_line: int = 0
    params: List[str] | None = None

    def __post_init__(self) -> None:
        if self.params is None:
            self.params = []

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"{self.element_type}:{self.name}:{self.start_line}-{self.end_line}"


@dataclass
class SemanticRelation:
    """Represents a semantic relationship between code elements."""

    source: str
    target: str
    relation_type: str

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"{self.source} {self.relation_type} {self.target}"


class CodeAnalyzer:
    """AST-based code analyzer for extracting code elements across languages."""

    def __init__(self, parser_registry: ParserRegistry | None = None, file_tool: Any | None = None) -> None:
        self.parser_registry = parser_registry or ParserRegistry()
        self.file_tool = file_tool

    def analyze_code(
        self,
        code_str: str,
        lang: str | None = None,
        file_path: str | None = None,
        tech_stack: dict | None = None,
    ) -> Dict[str, Any]:
        """Analyze code and extract semantic elements using the pluggable parsers."""

        if not lang and file_path:
            parser = self.parser_registry.get_parser(file_path=file_path)
            if parser:
                lang = parser.__class__.__name__.replace("Parser", "").lower()

        if not lang:
            lang = self._detect_language(code_str)

        parser = self.parser_registry.get_parser(file_path=file_path, language_name=lang)
        if parser:
            return parser.analyze(code_str, file_path or "", tech_stack)

        logger.error("No parser found for language '%s'. Skipping analysis.", lang)
        return {
            "language": lang,
            "elements": [],
            "relations": [],
            "imports": set(),
            "functions": set(),
            "classes": set(),
            "variables": set(),
            "route_paths": set(),
            "env_vars": set(),
        }

    def _analyze_file(self, file_path: str, language: str | None = None) -> Any:
        """Analyze a file using the new parser system only."""
        if not self.file_tool:
            logger.error("FileTool is not available. Cannot analyze file.")
            return None
        if not self.parser_registry:
            logger.error("ParserRegistry not available. Cannot analyze file.")
            return None
        try:
            content = self.file_tool.read_file(file_path)
            if content is None:
                logger.warning("Could not read content of file: %s", file_path)
                return None
        except Exception as exc:  # pragma: no cover - file access failure
            logger.error("Error reading file %s: %s", file_path, exc, exc_info=True)
            return None
        if not language:
            if hasattr(self.file_tool, "get_language_from_extension"):
                language = self.file_tool.get_language_from_extension(file_path)
            if not language:
                language = Path(file_path).suffix[1:].lower() if Path(file_path).suffix else "unknown"
        parser = self.parser_registry.get_parser(language_name=language, file_path=file_path)
        if parser:
            try:
                logger.info("Analyzing %s with %s for language '%s'.", file_path, type(parser).__name__, language)
                return parser.parse_code(content, file_path)
            except Exception as exc:  # pragma: no cover - parser failure
                logger.error("Error analyzing %s with %s: %s", file_path, type(parser).__name__, exc, exc_info=True)
                return None
        logger.error("No parser found for language '%s' for file %s.", language, file_path)
        return None

    def _detect_language(self, code_str: str) -> str:
        """Best-effort language detection used when a parser is not specified."""
        snippet = code_str.strip()
        if "import " in snippet or "def " in snippet:
            return "python"
        if "function" in snippet or "=>" in snippet:
            return "javascript"
        return "unknown"
def validate_code_syntax(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Validate syntax of code signatures in system_design.code_elements.

    Args:
        data: Parsed JSON data from pre-planner

    Returns:
        List of error objects, each with 'feature_name', 'group_idx', 'feature_idx', 'element_idx', 'element_name', 'message'
    """
    errors = []
    # analyzer = CodeAnalyzer() # Not strictly needed if only parsing signatures with ast/tree-sitter directly

    for group_idx, group_data in enumerate(data.get("feature_groups", [])):
        if not isinstance(group_data, dict):
            continue
        for feature_idx, feature_data in enumerate(group_data.get("features", [])):
            if not isinstance(feature_data, dict):
                continue

            current_feature_name = feature_data.get("name", f"Feature {feature_idx}")

            system_design = feature_data.get("system_design")
            if not isinstance(system_design, dict):
                # errors.append({...}) # Covered by schema validation
                continue

            code_elements = system_design.get("code_elements")
            if not isinstance(code_elements, list):
                # errors.append({...}) # Covered by schema validation
                continue

            for el_idx, element in enumerate(code_elements):
                if not isinstance(element, dict):
                    # errors.append({...}) # Covered by schema validation
                    continue

                signature_str = element.get("signature")
                element_type = element.get("element_type")
                element_name = element.get("name", f"unnamed_element_{el_idx}")
                target_file = element.get("target_file", "")

                if not isinstance(signature_str, str) or not signature_str.strip():
                    errors.append({
                        "feature_name": current_feature_name, "group_idx": group_idx, "feature_idx": feature_idx,
                        "element_idx": el_idx, "element_name": element_name,
                        "message": "Missing or empty 'signature' for code_element."
                    })
                    continue

                # Determine language for parsing
                lang = "python" # Default
                if isinstance(target_file, str):
                    if target_file.endswith((".js", ".jsx", ".mjs")):
                        lang = "javascript"
                    elif target_file.endswith((".ts", ".tsx")):
                        lang = "typescript"
                    elif target_file.endswith(".php"):
                        lang = "php"
                    elif target_file.endswith(".java"):
                        lang = "java"

                parse_content = signature_str
                try:
                    if lang == "python":
                        # Attempt to make it a parsable snippet
                        if element_type == "function" and signature_str.strip().endswith(":"):
                            parse_content = f"{signature_str}\n  pass"
                        elif element_type == "class" and signature_str.strip().endswith("):"):
                             parse_content = f"{signature_str}\n  pass"
                        elif element_type == "class" and not signature_str.strip().endswith("):") and ":" not in signature_str : # e.g. "class MyClass"
                             parse_content = f"{signature_str}:\n  pass"

                        ast.parse(parse_content)

                    elif lang in ["javascript", "typescript"]:
                        # Attempt to make it a parsable snippet for tree-sitter
                        if element_type == "function":
                            # Handle arrow functions or regular functions
                            if "=>" in signature_str:
                                if not signature_str.strip().endswith(";") and not signature_str.strip().endswith("}"):
                                    if not re.match(r"^\s*(const|let|var)\s+\w+\s*=", signature_str):
                                        parse_content = f"const tempFunc = {signature_str};"
                                    elif not signature_str.strip().endswith(";"):
                                        parse_content = f"{signature_str};"
                            elif "(" in signature_str and ")" in signature_str and not signature_str.strip().endswith(";") and not signature_str.strip().endswith("}"):
                                parse_content = f"{signature_str} {{}}"
                        elif element_type == "class" and not signature_str.strip().endswith("}"):
                            parse_content = f"{signature_str} {{}}"
                        elif element_type == "interface" and not signature_str.strip().endswith("}"):
                            parse_content = f"{signature_str} {{}}"
                        # Use the appropriate parser from agent_s3.ast_tools
                        if lang == "javascript":
                            parse_js(bytes(parse_content, "utf8"))
                        elif lang == "typescript":
                            # from agent_s3.ast_tools.parser import parse_ts # Ensure this is available
                            # For now, using parse_js as a fallback for basic TS syntax if parse_ts isn't set up
                            # This is a simplification; a real TS parser would be better.
                            try:
                                from agent_s3.ast_tools.ts_languages import get_ts_parser # Try to import specific TS parser
                                parser = get_ts_parser()
                                parser.parse(bytes(parse_content, "utf8"))
                            except ImportError:
                                logger.warning("TypeScript parser not fully available, using JavaScript parser for basic syntax check of TS.")
                                parse_js(bytes(parse_content, "utf8"))


                    elif lang == "php":
                        # PHP parsing is complex. A simple check:
                        if element_type == "function" and "function " not in signature_str:
                             errors.append({"message": f"PHP function signature for '{element_name}' should start with 'function '."}) # Example
                        # Full PHP syntax check usually requires `php -l` or a dedicated PHP parser lib
                        pass # Placeholder for more robust PHP check

                    elif lang == "java":
                        # Java parsing is also complex. Basic check:
                        if element_type == "class" and "class " not in signature_str:
                            errors.append({"message": f"Java class signature for '{element_name}' should start with 'class '."})
                        elif element_type == "interface" and "interface " not in signature_str:
                            errors.append({"message": f"Java interface signature for '{element_name}' should start with 'interface '."})
                        # Full Java syntax check requires a Java compiler/parser
                        pass # Placeholder

                except SyntaxError as e: # Python's ast.parse specific error
                    errors.append({
                        "feature_name": current_feature_name, "group_idx": group_idx, "feature_idx": feature_idx,
                        "element_idx": el_idx, "element_name": element_name,
                        "message": f"Python syntax error in signature '{signature_str[:50]}...': {e.msg} (line {e.lineno}, offset {e.offset}). Parsed as: '{parse_content[:50]}...'"
                    })
                except Exception as e: # Generic error for other parsers or issues
                    errors.append({
                        "feature_name": current_feature_name, "group_idx": group_idx, "feature_idx": feature_idx,
                        "element_idx": el_idx, "element_name": element_name,
                        "message": f"Syntax error or parsing issue in {lang} signature '{signature_str[:50]}...': {str(e)}. Parsed as: '{parse_content[:50]}...'"
                    })
    return errors



