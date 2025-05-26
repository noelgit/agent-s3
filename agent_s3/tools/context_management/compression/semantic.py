"""Semantic summarization compression strategy."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List

from .base import CompressionStrategy


class SemanticSummarizer(CompressionStrategy):
    """
    Compresses context by providing semantic summaries of file contents.
    """

    def __init__(
        self,
        summarization_threshold: int = 200,
        preserve_imports: bool = True,
        preserve_classes: bool = True
    ):
        """
        Initialize the semantic summarizer.

        Args:
            summarization_threshold: Line count threshold for summarization
            preserve_imports: Whether to preserve import statements in summaries
            preserve_classes: Whether to preserve class definitions in summaries
        """
        self.summarization_threshold = summarization_threshold
        self.preserve_imports = preserve_imports
        self.preserve_classes = preserve_classes

    def compress(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compress context by summarizing file contents.

        Args:
            context: The context dictionary to compress

        Returns:
            The compressed context with summarized file contents
        """
        compressed = context.copy()

        # Focus on code_context for summarization
        if "code_context" in context:
            compressed_code_context = {}

            for file_path, content in context["code_context"].items():
                # Count lines to determine if summarization is needed
                lines = content.split('\n')
                if len(lines) > self.summarization_threshold:
                    # Apply summarization
                    summarized = self._summarize_content(content, file_path)
                    compressed_code_context[file_path] = summarized

                    # Add metadata about compression
                    if "compression_metadata" not in compressed:
                        compressed["compression_metadata"] = {}

                    if "summarized_files" not in compressed["compression_metadata"]:
                        compressed["compression_metadata"]["summarized_files"] = {}

                    compressed["compression_metadata"]["summarized_files"][file_path] = {
                        "original_lines": len(lines),
                        "summarized_lines": len(summarized.split('\n')),
                        "compression_ratio": len(summarized) / len(content)
                    }
                else:
                    # Keep original content for small files
                    compressed_code_context[file_path] = content

            compressed["code_context"] = compressed_code_context

            # Add overall compression information
            if "compression_metadata" in compressed:
                original_size = sum(len(content) for content in context["code_context"].values())
                compressed_size = sum(len(content) for content in compressed_code_context.values())

                compressed["compression_metadata"]["overall"] = {
                    "strategy": "semantic_summarizer",
                    "original_size": original_size,
                    "compressed_size": compressed_size,
                    "compression_ratio": compressed_size / original_size if original_size > 0 else 1.0
                }

        return compressed

    def decompress(self, compressed_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        'Decompress' a semantically summarized context.

        Note: Since semantic summarization is lossy, full restoration is not possible.
        This method adds comprehensive metadata indicating that the context contains
        summarized content and details about the summarization applied.

        Args:
            compressed_context: The compressed context dictionary

        Returns:
            The context with decompression metadata added
        """
        decompressed = compressed_context.copy()

        # Ensure decompression metadata section exists
        if "decompression_metadata" not in decompressed:
            decompressed["decompression_metadata"] = {}

        # Get information about summarized files
        summarized_files = {}
        if "compression_metadata" in compressed_context:
            if "summarized_files" in compressed_context["compression_metadata"]:
                summarized_files = compressed_context["compression_metadata"]["summarized_files"]

        # Add detailed decompression metadata
        decompressed["decompression_metadata"]["semantic_summarization"] = {
            "timestamp": datetime.now().isoformat(),
            "status": "completed",
            "decompression_type": "semantic_summarizer",
            "note": "Semantic summarization is lossy; original content cannot be fully restored",
            "summarized_files": list(summarized_files.keys()) if summarized_files else [],
            "summarization_statistics": {
                "files_summarized": len(summarized_files),
                "average_compression_ratio": (
                    sum(f.get("compression_ratio", 0) for f in summarized_files.values()) /
                    len(summarized_files) if summarized_files else 0
                )
            }
        }

        return decompressed

    def _summarize_content(self, content: str, file_path: str) -> str:
        """
        Summarize the content of a file.

        Args:
            content: The file content to summarize
            file_path: Path to the file (used to determine file type)

        Returns:
            Summarized content
        """
        lines = content.split('\n')
        file_ext = file_path.split('.')[-1].lower() if '.' in file_path else ""

        # Determine language based on file extension
        language = "unknown"
        if file_ext in ["py"]:
            language = "python"
        elif file_ext in ["js", "jsx", "ts", "tsx"]:
            language = "javascript"
        elif file_ext in ["java"]:
            language = "java"
        elif file_ext in ["cs"]:
            language = "csharp"

        # Apply language-specific summarization
        if language == "python":
            return self._summarize_python(lines)
        elif language in ["javascript", "typescript"]:
            return self._summarize_javascript(lines)
        elif language == "java":
            return self._summarize_java(lines)
        elif language == "csharp":
            return self._summarize_csharp(lines)
        else:
            # Generic summarization for unknown languages
            return self._summarize_generic(lines)

    def _summarize_python(self, lines: List[str]) -> str:
        """Summarize Python code."""
        summary_lines = []

        # Track state
        current_indent = 0
        skipping = False

        # Extract imports
        imports = []
        if self.preserve_imports:
            for line in lines:
                if re.match(r'^import\s+|^from\s+', line):
                    imports.append(line)

        # Extract class and function definitions
        for i, line in enumerate(lines):
            # Check indentation
            indent = len(line) - len(line.lstrip())

            # Reset skipping if we went back to a lower indent level
            if indent <= current_indent and skipping:
                skipping = False

            # Handle class definitions
            if re.match(r'^\s*class\s+', line):
                current_indent = indent
                if self.preserve_classes:
                    summary_lines.append(line)
                else:
                    # Just add the class signature with a comment
                    class_name = re.search(r'class\s+(\w+)', line).group(1)
                    summary_lines.append(f"{' ' * indent}class {class_name}: # Summarized")
                continue

            # Handle function definitions
            if re.match(r'^\s*def\s+', line):
                current_indent = indent

                # Add function signature
                fn_match = re.search(r'def\s+(\w+)\s*\((.*?)\)', line)
                if fn_match:
                    fn_name, params = fn_match.groups()

                    # Check if this is a method in a class
                    is_method = indent > 0

                    # Include the function definition but mark it as summarized
                    if is_method:
                        # For methods, include the decorator if it's there
                        if i > 0 and re.match(r'^\s*@', lines[i-1]):
                            summary_lines.append(lines[i-1])
                        summary_lines.append(line)

                        # Skip the function body
                        skipping = True
                    else:
                        # For standalone functions, just add a simplified signature
                        summary_lines.append(f"{' ' * indent}def {fn_name}(...): # Summarized")

                        # Skip the function body
                        skipping = True
                continue

            # Include important comments and docstrings
            if re.match(r'^\s*"""', line) or re.match(r"^\s*'''", line) or re.match(r'^\s*#', line):
                if not skipping:
                    summary_lines.append(line)
                continue

            # Include non-function, non-class code if not skipping
            if not skipping:
                summary_lines.append(line)

        # Combine imports and code summary
        if imports:
            return '\n'.join(imports + ['', '# Summarized Content:'] + summary_lines)
        else:
            return '\n'.join(['# Summarized Content:'] + summary_lines)

    def _summarize_javascript(self, lines: List[str]) -> str:
        """Summarize JavaScript/TypeScript code."""
        summary_lines = []

        # Track state
        brace_depth = 0
        skipping = False

        # Extract imports
        imports = []
        if self.preserve_imports:
            for line in lines:
                if re.match(r'^import\s+|^const\s+.*\s*=\s*require\(', line):
                    imports.append(line)

        # Extract class and function definitions
        for i, line in enumerate(lines):
            # Update brace depth
            brace_depth += line.count('{') - line.count('}')

            # Reset skipping if we went back to a lower brace depth
            if brace_depth == 0:
                skipping = False

            # Handle class definitions
            if re.search(r'class\s+\w+', line):
                if self.preserve_classes:
                    summary_lines.append(line)
                else:
                    # Just add the class signature with a comment
                    class_name = re.search(r'class\s+(\w+)', line).group(1)
                    summary_lines.append(f"class {class_name} {{ // Summarized")

                # Skip the class body
                if not self.preserve_classes and '{' in line:
                    skipping = True
                continue

            # Handle function definitions
            if (
                re.search(r'function\s+\w+\s*\(|^\s*\w+\s*\([^)]*\)\s*{|^\s*\w+\s*:\s*function', line)
                or re.search(r'const\s+\w+\s*=\s*\([^)]*\)\s*=>|^\s*\w+\s*=\s*\([^)]*\)\s*=>', line)
            ):
                # Add function signature
                summary_lines.append(line.rstrip())

                # Add a comment if this is a named function
                fn_name = None
                if re.search(r'function\s+(\w+)', line):
                    fn_name = re.search(r'function\s+(\w+)', line).group(1)
                elif re.search(r'(\w+)\s*\(', line):
                    fn_name = re.search(r'(\w+)\s*\(', line).group(1)
                elif re.search(r'const\s+(\w+)\s*=', line):
                    fn_name = re.search(r'const\s+(\w+)\s*=', line).group(1)

                if fn_name and '{' in line:
                    summary_lines[-1] = summary_lines[-1].replace('{', '{ // Summarized')
                    skipping = True
                elif '{' in line:
                    summary_lines[-1] = summary_lines[-1].replace('{', '{ // Summarized')
                    skipping = True
                continue

            # Include important comments and JSDoc
            if re.match(r'^\s*\/\*\*', line) or re.match(r'^\s*\/\/', line):
                if not skipping:
                    summary_lines.append(line)
                continue

            # Include non-function, non-class code if not skipping
            if not skipping:
                summary_lines.append(line)

        # Combine imports and code summary
        if imports:
            return '\n'.join(imports + ['', '// Summarized Content:'] + summary_lines)
        else:
            return '\n'.join(['// Summarized Content:'] + summary_lines)

    def _summarize_java(self, lines: List[str]) -> str:
        """Summarize Java code."""
        # Similar implementation to _summarize_javascript but adapted for Java
        summary_lines = []

        # Track state
        brace_depth = 0
        skipping = False

        # Extract imports
        imports = []
        if self.preserve_imports:
            for line in lines:
                if re.match(r'^import\s+', line):
                    imports.append(line)
                elif re.match(r'^package\s+', line):
                    imports.append(line)

        # Extract class and method definitions
        for line in lines:
            # Update brace depth
            brace_depth += line.count('{') - line.count('}')

            # Reset skipping if we went back to a lower brace depth
            if brace_depth == 0:
                skipping = False

            # Handle class definitions
            if re.search(r'(public|private|protected)?\s*class\s+\w+', line):
                if self.preserve_classes:
                    summary_lines.append(line)
                else:
                    # Just add the class signature with a comment
                    class_match = re.search(r'(?:public|private|protected)?\s*class\s+(\w+)', line)
                    if class_match:
                        class_name = class_match.group(1)
                        summary_lines.append(f"public class {class_name} {{ // Summarized")

                # Skip the class body
                if not self.preserve_classes and '{' in line:
                    skipping = True
                continue

            # Handle method definitions
            if re.search(r'(public|private|protected)?\s+\w+\s+\w+\s*\([^)]*\)', line):

                # Add method signature
                summary_lines.append(line.rstrip())

                # Add a comment if this is a method
                if '{' in line:
                    summary_lines[-1] = summary_lines[-1].replace('{', '{ // Summarized')
                    skipping = True
                continue

            # Include important comments and JavaDoc
            if re.match(r'^\s*\/\*\*', line) or re.match(r'^\s*\/\/', line):
                if not skipping:
                    summary_lines.append(line)
                continue

            # Include non-method, non-class code if not skipping
            if not skipping:
                summary_lines.append(line)

        # Combine imports and code summary
        if imports:
            return '\n'.join(imports + ['', '// Summarized Content:'] + summary_lines)
        else:
            return '\n'.join(['// Summarized Content:'] + summary_lines)

    def _summarize_csharp(self, lines: List[str]) -> str:
        """Summarize C# code."""
        # Similar to _summarize_java but adapted for C#
        summary_lines = []

        # Track state
        brace_depth = 0
        skipping = False

        # Extract imports
        imports = []
        if self.preserve_imports:
            for line in lines:
                if re.match(r'^using\s+', line):
                    imports.append(line)
                elif re.match(r'^namespace\s+', line):
                    imports.append(line)

        # Extract class and method definitions
        for line in lines:
            # Update brace depth
            brace_depth += line.count('{') - line.count('}')

            # Reset skipping if we went back to a lower brace depth
            if brace_depth == 0:
                skipping = False

            # Handle class definitions
            if re.search(r'(public|private|protected|internal)?\s*class\s+\w+', line):
                if self.preserve_classes:
                    summary_lines.append(line)
                else:
                    # Just add the class signature with a comment
                    class_match = re.search(
                        r"(?:public|private|protected|internal)?\s*class\s+(\w+)",
                        line,
                    )
                    if class_match:
                        class_name = class_match.group(1)
                        summary_lines.append(f"public class {class_name} {{ // Summarized")

                # Skip the class body
                if not self.preserve_classes and '{' in line:
                    skipping = True
                continue

            # Handle method definitions
            if re.search(r'(public|private|protected|internal)?\s+\w+\s+\w+\s*\([^)]*\)', line):

                # Add method signature
                summary_lines.append(line.rstrip())

                # Add a comment if this is a method
                if '{' in line:
                    summary_lines[-1] = summary_lines[-1].replace('{', '{ // Summarized')
                    skipping = True
                continue

            # Include important comments and C# Doc
            if re.match(r'^\s*\/\/\/\s*<', line) or re.match(r'^\s*\/\/', line):
                if not skipping:
                    summary_lines.append(line)
                continue

            # Include non-method, non-class code if not skipping
            if not skipping:
                summary_lines.append(line)

        # Combine imports and code summary
        if imports:
            return '\n'.join(imports + ['', '// Summarized Content:'] + summary_lines)
        else:
            return '\n'.join(['// Summarized Content:'] + summary_lines)

    def _summarize_generic(self, lines: List[str]) -> str:
        """Generic summarization for unknown languages."""
        # For unknown languages, include first 10% and last 10% of lines
        if len(lines) <= self.summarization_threshold:
            return '\n'.join(lines)

        header_size = max(10, int(len(lines) * 0.1))
        footer_size = max(10, int(len(lines) * 0.1))

        header = lines[:header_size]
        footer = lines[-footer_size:]

        # Add a separator between header and footer
        separator = [
            '',
            '// ...',
            f'// [Content summarized: {len(lines) - header_size - footer_size} lines omitted]',
            '// ...',
            ''
        ]

        return '\n'.join(header + separator + footer)


