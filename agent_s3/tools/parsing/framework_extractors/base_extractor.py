"""
Abstract base class for framework-specific AST node extractors.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

class FrameworkExtractor(ABC):
    @abstractmethod
    def extract(self, root_node: Any, file_path: str, content: str, language: str, tech_stack: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Extract framework-specific nodes and edges from the AST.
        """
        pass

    @abstractmethod
    def is_relevant_framework(self, tech_stack: Dict[str, Any], file_path: str, content: str) -> bool:
        """
        Determine if this extractor should run for the given context.
        """
        pass
