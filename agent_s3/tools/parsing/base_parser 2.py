"""
Abstract base class for language-specific code parsers.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional

class LanguageParser(ABC):
    @abstractmethod
    def analyze(self, code_str: str, file_path: str, tech_stack: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Analyze the given code string and return a structured representation (nodes, edges).
        """
        pass

    @abstractmethod
    def get_supported_extensions(self) -> List[str]:
        """
        Returns a list of file extensions this parser supports.
        """
        pass
