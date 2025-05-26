"""Reference compression strategy."""

from __future__ import annotations

from typing import Any, Dict

from .base import CompressionStrategy
from .utils import hash_content

class ReferenceCompressor(CompressionStrategy):
    """
    Compresses context by replacing repeated code with references.
    """

    def __init__(
        self,
        min_pattern_length: int = 10,
        similarity_threshold: float = 0.8
    ):
        """
        Initialize the reference compressor.

        Args:
            min_pattern_length: Minimum length of patterns to identify
            similarity_threshold: Threshold for identifying similar code blocks
        """
        self.min_pattern_length = min_pattern_length
        self.similarity_threshold = similarity_threshold
        self.reference_map = {}

    def compress(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compress context by replacing repeated code with references.

        Args:
            context: The context dictionary to compress

        Returns:
            The compressed context with referenced content
        """
        compressed = context.copy()

        # Reset reference map
        self.reference_map = {}

        # Focus on code_context for reference compression
        if "code_context" in context:
            # First pass: identify repeating patterns
            self._identify_patterns(context["code_context"])

            # Second pass: replace patterns with references
            compressed_code_context = {}

            for file_path, content in context["code_context"].items():
                if not content:
                    compressed_code_context[file_path] = content
                    continue

                # Apply reference compression
                compressed_content = self._apply_references(content)
                compressed_code_context[file_path] = compressed_content

            compressed["code_context"] = compressed_code_context

            # Add reference map to context
            if "compression_metadata" not in compressed:
                compressed["compression_metadata"] = {}

            compressed["compression_metadata"]["reference_map"] = self.reference_map

            # Add overall compression information
            original_size = sum(len(content) for content in context["code_context"].values())
            compressed_size = sum(len(content) for content in compressed_code_context.values())

            compressed["compression_metadata"]["overall"] = {
                "strategy": "reference_compressor",
                "original_size": original_size,
                "compressed_size": compressed_size,
                "compression_ratio": compressed_size / original_size if original_size > 0 else 1.0
            }

        return compressed

    def decompress(self, compressed_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Decompress a reference-compressed context.

        Args:
            compressed_context: The compressed context dictionary

        Returns:
            The decompressed context with references expanded
        """
        decompressed = compressed_context.copy()

        # Extract reference map
        if "compression_metadata" in compressed_context and "reference_map" in compressed_context["compression_metadata"]:
            reference_map = compressed_context["compression_metadata"]["reference_map"]

            # Decompress code_context
            if "code_context" in compressed_context:
                decompressed_code_context = {}

                for file_path, content in compressed_context["code_context"].items():
                    # Expand references
                    decompressed_content = self._expand_references(content, reference_map)
                    decompressed_code_context[file_path] = decompressed_content

                decompressed["code_context"] = decompressed_code_context

                # Add decompression metadata
                if "decompression_metadata" not in decompressed:
                    decompressed["decompression_metadata"] = {}

                decompressed["decompression_metadata"]["reference_decompression"] = {
                    "references_expanded": len(reference_map)
                }

        return decompressed

    def _identify_patterns(self, code_context: Dict[str, str]) -> None:
        """
        Identify repeating patterns in code context.

        Args:
            code_context: Dictionary mapping file paths to content
        """
        # Extract all content
        all_content = '\n'.join(content for content in code_context.values() if content)

        # Split into lines
        lines = all_content.split('\n')

        # Initialize pattern tracking
        potential_patterns = {}

        # Process lines in chunks
        for i in range(len(lines) - self.min_pattern_length + 1):
            chunk = '\n'.join(lines[i:i + self.min_pattern_length])

            # Skip if too short
            if len(chunk) < self.min_pattern_length * 5:  # Average 5 chars per line minimum
                continue

            # Hash the chunk for quicker comparison
            chunk_hash = hash_content(chunk)

            if chunk_hash in potential_patterns:
                potential_patterns[chunk_hash]["count"] += 1
            else:
                potential_patterns[chunk_hash] = {
                    "content": chunk,
                    "count": 1
                }

        # Adaptively reduce pattern size for smaller content
        if not potential_patterns or all(v["count"] <= 1 for v in potential_patterns.values()):
            # Determine pattern size based on content length
            adaptive_length = max(2, min(5, len(lines) // 10))

            # Use adaptive pattern length
            for i in range(len(lines) - adaptive_length + 1):
                chunk = '\n'.join(lines[i:i + adaptive_length])
                if len(chunk) < 10:  # Skip very small chunks
                    continue

                chunk_hash = hash_content(chunk)
                if chunk_hash in potential_patterns:
                    potential_patterns[chunk_hash]["count"] += 1
                else:
                    potential_patterns[chunk_hash] = {
                        "content": chunk,
                        "count": 1
                    }

        # Filter to patterns that appear multiple times
        repeating_patterns = {
            k: v for k, v in potential_patterns.items()
            if v["count"] > 1 and len(v["content"]) > 10
        }

        # Convert to reference map
        ref_id = 1
        for pattern_hash, pattern_info in repeating_patterns.items():
            ref_key = f"@REF{ref_id}@"
            self.reference_map[ref_key] = pattern_info["content"]
            ref_id += 1

    def _apply_references(self, content: str) -> str:
        """
        Replace repeated patterns with references.

        Args:
            content: Original content

        Returns:
            Content with patterns replaced by references
        """
        if not self.reference_map or not content:
            return content

        compressed = content

        for ref_key, pattern in self.reference_map.items():
            if pattern in compressed:
                # Replace the pattern with a reference
                replacement = f"\n// {ref_key} - Reference to a repeated pattern\n"
                compressed = compressed.replace(pattern, replacement)

        # Add header with reference information
        if compressed != content:
            header = [
                "// Reference-Compressed Content",
                "// This file contains references to repeated patterns",
                "// References are marked with @REFn@ tags",
                ""
            ]
            compressed = '\n'.join(header) + compressed

        return compressed

    def _expand_references(self, content: str, reference_map: Dict[str, str]) -> str:
        """
        Expand references back to original content.

        Args:
            content: Content with references
            reference_map: Map of reference keys to original content

        Returns:
            Content with references expanded
        """
        if not reference_map or not content:
            return content

        decompressed = content

        for ref_key, pattern in reference_map.items():
            ref_marker = f"// {ref_key} - Reference to a repeated pattern"
            if ref_marker in decompressed:
                # Replace the reference with the original pattern
                decompressed = decompressed.replace(ref_marker, pattern)

        # Remove reference header if present
        header_lines = [
            "// Reference-Compressed Content",
            "// This file contains references to repeated patterns",
            "// References are marked with @REFn@ tags",
            ""
        ]
        for line in header_lines:
            if decompressed.startswith(line):
                decompressed = decompressed[len(line)+1:]  # +1 for newline

        return decompressed


