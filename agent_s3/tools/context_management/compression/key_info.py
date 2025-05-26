"""Key information extraction compression strategy."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .base import CompressionStrategy

class KeyInfoExtractor(CompressionStrategy):
    """
    Extracts and preserves only key information from context.
    """

    def __init__(
        self,
        extraction_patterns: Optional[Dict[str, List[str]]] = None,
        preserve_structure: bool = True
    ):
        """
        Initialize the key information extractor.

        Args:
            extraction_patterns: Patterns for extracting key information by language
            preserve_structure: Whether to preserve the overall structure
        """
        self.preserve_structure = preserve_structure
        self.extraction_patterns = extraction_patterns or {
            "python": [
                r'^\s*import\s+.*$',
                r'^\s*from\s+.*\s+import\s+.*$',
                r'^\s*class\s+\w+.*:$',
                r'^\s*def\s+\w+\s*\(.*\):$',
                r'^\s*@.*$',
                r'^\s*""".*?"""$'
            ],
            "javascript": [
                r'^\s*import\s+.*$',
                r'^\s*export\s+.*$',
                r'^\s*class\s+\w+.*{$',
                r'^\s*function\s+\w+\s*\(.*\)\s*{$',
                r'^\s*const\s+\w+\s*=\s*\(.*\)\s*=>.*$',
                r'^\s*\/\*\*.*?\*\/$'
            ],
            "generic": [
                r'^\s*function\s+\w+',
                r'^\s*class\s+\w+',
                r'^\s*\w+\s*\(',
                r'^\s*\/\/\s*\w+'
            ]
        }

    def compress(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compress context by extracting key information.

        Args:
            context: The context dictionary to compress

        Returns:
            The compressed context with only key information
        """
        compressed = context.copy()

        # Focus on code_context for key info extraction
        if "code_context" in context:
            compressed_code_context = {}

            for file_path, content in context["code_context"].items():
                # Extract key information from content
                extracted = self._extract_key_info(content, file_path)
                compressed_code_context[file_path] = extracted

            compressed["code_context"] = compressed_code_context

            # Add compression metadata
            if "compression_metadata" not in compressed:
                compressed["compression_metadata"] = {}

            original_size = sum(len(content) for content in context["code_context"].values())
            compressed_size = sum(len(content) for content in compressed_code_context.values())

            compressed["compression_metadata"]["overall"] = {
                "strategy": "key_info_extractor",
                "original_size": original_size,
                "compressed_size": compressed_size,
                "compression_ratio": compressed_size / original_size if original_size > 0 else 1.0
            }

        return compressed

    def decompress(self, compressed_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        'Decompress' a context with only key information.

        Note: Since key information extraction is lossy, full restoration is not possible.
        This method adds detailed metadata indicating that the context contains
        only key information and the nature of the extraction performed.

        Args:
            compressed_context: The compressed context dictionary

        Returns:
            The context with decompression metadata added
        """
        decompressed = compressed_context.copy()

        # Ensure decompression metadata section exists
        if "decompression_metadata" not in decompressed:
            decompressed["decompression_metadata"] = {}

        # Extract information about the compression
        extracted_files = []
        if "code_context" in compressed_context:
            extracted_files = list(compressed_context["code_context"].keys())

        compression_stats = {}
        if "compression_metadata" in compressed_context and "overall" in compressed_context["compression_metadata"]:
            compression_stats = compressed_context["compression_metadata"]["overall"]

        # Add comprehensive decompression metadata
        decompressed["decompression_metadata"]["key_info_extraction"] = {
            "timestamp": datetime.now().isoformat(),
            "status": "completed",
            "decompression_type": "key_info_extractor",
            "note": "Key information extraction is lossy; original content cannot be fully restored",
            "extracted_files": extracted_files,
            "extraction_info": {
                "files_processed": len(extracted_files),
                "original_size": compression_stats.get("original_size", 0),
                "compressed_size": compression_stats.get("compressed_size", 0),
                "compression_ratio": compression_stats.get("compression_ratio", 1.0),
                "patterns_used": [p for patterns in self.extraction_patterns.values() for p in patterns]
            }
        }

        return decompressed

    def _extract_key_info(self, content: str, file_path: str) -> str:
        """
        Extract key information from file content.

        Args:
            content: The file content to extract from
            file_path: Path to the file (used to determine file type)

        Returns:
            Content with only key information
        """
        lines = content.split('\n')
        file_ext = file_path.split('.')[-1].lower() if '.' in file_path else ""

        # Determine language based on file extension
        language = "generic"
        if file_ext in ["py"]:
            language = "python"
        elif file_ext in ["js", "jsx", "ts", "tsx"]:
            language = "javascript"

        # Get patterns for this language
        patterns = self.extraction_patterns.get(language, self.extraction_patterns["generic"])

        # Extract matching lines
        extracted_lines = []
        structure_indicators = []

        for i, line in enumerate(lines):
            # Check if the line matches any pattern
            if any(re.search(pattern, line, re.DOTALL) for pattern in patterns):
                extracted_lines.append((i, line))
            elif line.strip() and self.preserve_structure:
                # Record indentation level for structure preservation
                indent = len(line) - len(line.lstrip())
                if indent > 0:
                    structure_indicators.append((i, indent))

        # If preserving structure, add indicator lines
        if self.preserve_structure:
            # Group structure indicators by indentation level
            indent_groups = {}
            for i, indent in structure_indicators:
                if indent not in indent_groups:
                    indent_groups[indent] = []
                indent_groups[indent].append(i)

            # Add indicator lines with original indentation
            for indent, positions in indent_groups.items():
                for group in self._group_consecutive(positions):
                    if group and len(group) > 2:  # Only add for larger blocks
                        mid_pos = group[len(group) // 2]
                        extracted_lines.append((mid_pos, ' ' * indent + "// ..."))

        # Sort by original line number
        extracted_lines.sort()

        # Build the final extracted content
        extracted_content = []
        last_line = -1

        for i, line in extracted_lines:
            # Add separator if there's a gap
            if last_line >= 0 and i - last_line > 1:
                extracted_content.append("// ...")

            extracted_content.append(line)
            last_line = i

        # Add header with extraction information
        header = [
            "// Key Information Extract",
            f"// Original file: {file_path}",
            f"// Extraction patterns: {language}",
            f"// Original size: {len(lines)} lines",
            f"// Extracted size: {len(extracted_content)} elements",
            "// Note: This is a compressed representation with only key elements",
            ""
        ]

        return '\n'.join(header + extracted_content)

    def _group_consecutive(self, numbers: List[int]) -> List[List[int]]:
        """Group consecutive numbers into sublists."""
        groups = []
        if not numbers:
            return groups

        current_group = [numbers[0]]

        for i in range(1, len(numbers)):
            if numbers[i] == numbers[i-1] + 1:
                current_group.append(numbers[i])
            else:
                groups.append(current_group)
                current_group = [numbers[i]]

        if current_group:
            groups.append(current_group)

        return groups


