"""
Context Registry for Agent-S3

Central facade for accessing all context providers. All context access in the system should go through this registry.
"""
from typing import Dict, Any, List, Optional
import logging
from agent_s3.tools.context_management.interfaces import (
    ContextProvider, TechStackProvider, FileContextProvider, ProjectContextProvider,
    TestContextProvider, MemoryContextProvider, DependencyGraphProvider # Added Test and Memory
)

logger = logging.getLogger(__name__)

class ContextRegistry:
    """
    Central registry for accessing all context providers.
    Serves as a facade to all context sources.
    """
    def __init__(self):
        self._providers = {}
    def register_provider(self, name: str, provider: ContextProvider) -> None:
        self._providers[name] = provider
        logger.info("%s", "Registered context provider: %s", name)
    def get_provider(self, name: str) -> Optional[ContextProvider]:
        return self._providers.get(name)
    def get_tech_stack(self) -> Dict[str, Any]:
        for provider in self._providers.values():
            if isinstance(provider, TechStackProvider) and hasattr(provider, "get_tech_stack"):
                return provider.get_tech_stack()
        logger.warning("No provider found for tech stack information")
        return {}
    def get_relevant_files(self, query: str, top_n: int = 10) -> List[Dict[str, Any]]:
        for provider in self._providers.values():
            if isinstance(provider, FileContextProvider) and hasattr(provider, "get_relevant_files"):
                return provider.get_relevant_files(query, top_n)
        logger.warning("No provider found for relevant files: %s", query)
        return []
    def get_file_history(self, file_path: str = None) -> Dict[str, Any]:
        for provider in self._providers.values():
            if isinstance(provider, FileContextProvider) and hasattr(provider, "get_file_history"):
                return provider.get_file_history(file_path)
        logger.warning("No provider found for file history: %s", file_path)
        return {}
    def get_file_metadata(self, file_path: str = None) -> Dict[str, Any]:
        for provider in self._providers.values():
            if isinstance(provider, FileContextProvider) and hasattr(provider, "get_file_metadata"):
                return provider.get_file_metadata(file_path)
        logger.warning("No provider found for file metadata: %s", file_path)
        return {}
    def get_project_structure(self) -> Dict[str, Any]:
        for provider in self._providers.values():
            if isinstance(provider, ProjectContextProvider) and hasattr(provider, "get_project_structure"):
                return provider.get_project_structure()
        logger.warning("No provider found for project structure")
        return {}
    def get_config_files(self) -> Dict[str, Any]:
        for provider in self._providers.values():
            if isinstance(provider, ProjectContextProvider) and hasattr(provider, "get_config_files"):
                return provider.get_config_files()
        logger.warning("No provider found for config files")
        return {}

    # --- Added Passthrough Methods ---

    def read_file(self, file_path: str) -> str:
        for provider in self._providers.values():
            if isinstance(provider, FileContextProvider) and hasattr(provider, "read_file"):
                return provider.read_file(file_path)
        logger.warning("No provider found for read_file: %s", file_path)
        return ""

    def get_code_elements(self, file_path: str) -> List[Dict[str, Any]]:
        for provider in self._providers.values():
            if isinstance(provider, FileContextProvider) and hasattr(provider, "get_code_elements"):
                return provider.get_code_elements(file_path)
        logger.warning("No provider found for get_code_elements: %s", file_path)
        return []

    def get_file_imports(self, file_path: str) -> List[str]:
        for provider in self._providers.values():
            if isinstance(provider, FileContextProvider) and hasattr(provider, "get_file_imports"):
                return provider.get_file_imports(file_path)
        logger.warning("No provider found for get_file_imports: %s", file_path)
        return []

    def get_files_importing(self, file_path: str) -> List[str]:
        for provider in self._providers.values():
            if isinstance(provider, FileContextProvider) and hasattr(provider, "get_files_importing"):
                return provider.get_files_importing(file_path)
        logger.warning("No provider found for get_files_importing: %s", file_path)
        return []

    def get_convention_related_files(self, file_path: str) -> List[str]:
        for provider in self._providers.values():
            if isinstance(provider, FileContextProvider) and hasattr(provider, "get_convention_related_files"):
                return provider.get_convention_related_files(file_path)
        logger.warning("No provider found for get_convention_related_files: %s", file_path)
        return []

    def get_hotspot_files(self) -> List[str]:
        for provider in self._providers.values():
            if isinstance(provider, FileContextProvider) and hasattr(provider, "get_hotspot_files"):
                return provider.get_hotspot_files()
        logger.warning("No provider found for get_hotspot_files")
        return []

    def get_code_ownership(self) -> Dict[str, List[str]]:
        for provider in self._providers.values():
            if isinstance(provider, FileContextProvider) and hasattr(provider, "get_code_ownership"):
                return provider.get_code_ownership()
        logger.warning("No provider found for get_code_ownership")
        return {}

    def get_project_root(self) -> str:
        for provider in self._providers.values():
            if isinstance(provider, ProjectContextProvider) and hasattr(provider, "get_project_root"):
                return provider.get_project_root()
        logger.warning("No provider found for get_project_root")
        return ""

    def get_coding_guidelines(self) -> Optional[str]:
        for provider in self._providers.values():
            if isinstance(provider, ProjectContextProvider) and hasattr(provider, "get_coding_guidelines"):
                return provider.get_coding_guidelines()
        logger.warning("No provider found for get_coding_guidelines")
        return None

    def find_test_files(self, impl_file_path: str) -> List[str]:
        for provider in self._providers.values():
            if isinstance(provider, TestContextProvider) and hasattr(provider, "find_test_files"):
                return provider.find_test_files(impl_file_path)
        logger.warning("No provider found for find_test_files: %s", impl_file_path)
        return []

    def suggest_unit_tests(self, code_element: Dict[str, Any]) -> List[str]:
        for provider in self._providers.values():
            if isinstance(provider, TestContextProvider) and hasattr(provider, "suggest_unit_tests"):
                return provider.suggest_unit_tests(code_element)
        logger.warning("No provider found for suggest_unit_tests")
        return []

    def suggest_integration_tests(self, code_element: Dict[str, Any]) -> List[str]:
        for provider in self._providers.values():
            if isinstance(provider, TestContextProvider) and hasattr(provider, "suggest_integration_tests"):
                return provider.suggest_integration_tests(code_element)
        logger.warning("No provider found for suggest_integration_tests")
        return []

    def get_test_framework_dependencies(self, test_type: str, language: str) -> Dict[str, bool]:
        for provider in self._providers.values():
            if isinstance(provider, TestContextProvider) and hasattr(provider, "get_test_framework_dependencies"):
                return provider.get_test_framework_dependencies(test_type, language)
        logger.warning("No provider found for get_test_framework_dependencies")
        return {}

    def get_similar_tasks(self, query: str, top_n: int = 5) -> List[Dict[str, Any]]:
        for provider in self._providers.values():
            if isinstance(provider, MemoryContextProvider) and hasattr(provider, "get_similar_tasks"):
                return provider.get_similar_tasks(query, top_n)
        logger.warning("No provider found for get_similar_tasks: %s", query)
        return []

    def get_dependency_graph(self, scope: Optional[str] = None) -> Dict[str, Any]:
        for provider in self._providers.values():
            if isinstance(provider, DependencyGraphProvider) and hasattr(provider, "get_dependency_graph"):
                return provider.get_dependency_graph(scope)
        logger.warning("No provider found for dependency graph")
        return {}

    # --- End Added Passthrough Methods ---

    def get_optimized_context(self, context_type: str = None) -> Dict[str, Any]:
        result = {}
        for provider in self._providers.values():
            if hasattr(provider, "get_optimized_context"):
                ctx = provider.get_optimized_context()
                for k, v in ctx.items():
                    if k not in result:
                        result[k] = v
        return result
