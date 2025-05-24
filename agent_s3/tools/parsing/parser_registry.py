"""
Manages and provides access to language parser instances.
"""
import os
from typing import Dict, List, Optional
from .python_parser import PythonNativeParser
from .javascript_parser import JavaScriptTreeSitterParser
from .php_parser import PHPTreeSitterParser
from .base_parser import LanguageParser
from .framework_extractors.react_extractor import ReactExtractor
from .framework_extractors.laravel_extractor import LaravelExtractor

class ParserRegistry:
    def __init__(self):
        self.parsers_by_ext: Dict[str, LanguageParser] = {}
        self.parsers_by_lang_name: Dict[str, LanguageParser] = {}
        self._register_defaults()

    def _register_defaults(self):
        self.register_parser(PythonNativeParser(), ['python'])
        self.register_parser(JavaScriptTreeSitterParser(
            framework_extractors=[ReactExtractor()]), ['javascript', 'typescript'])
        self.register_parser(PHPTreeSitterParser(
            framework_extractors=[LaravelExtractor()]), ['php'])

    def register_parser(self, parser_instance: LanguageParser, language_names: List[str]):
        for ext in parser_instance.get_supported_extensions():
            self.parsers_by_ext[ext] = parser_instance
        for name in language_names:
            self.parsers_by_lang_name[name.lower()] = parser_instance

    def get_parser(self, file_path: Optional[str] = None, language_name: Optional[str] = None)
         -> Optional[LanguageParser]:        if file_path:
            ext = os.path.splitext(file_path)[1].lower()
            if ext in self.parsers_by_ext:
                return self.parsers_by_ext[ext]
        if language_name and language_name.lower() in self.parsers_by_lang_name:
            return self.parsers_by_lang_name[language_name.lower()]
        return None
