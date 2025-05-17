"""
Integration tests for the incremental indexing system.

These tests validate that the incremental indexing system works correctly
with the existing CodeAnalysisTool and StaticAnalyzer classes.

To run these tests:
1. Navigate to the project root
2. Run: python -m pytest tests/test_incremental_indexing.py -v
"""

import os
import sys
import time
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock, patch

# Adjust path to import from agent_s3
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agent_s3.tools.file_change_tracker import FileChangeTracker
from agent_s3.tools.dependency_impact_analyzer import DependencyImpactAnalyzer
from agent_s3.tools.repository_event_system import RepositoryEventSystem
from agent_s3.tools.index_partition_manager import IndexPartitionManager
from agent_s3.tools.incremental_indexer import IncrementalIndexer
from agent_s3.tools.incremental_indexing_adapter import IncrementalIndexingAdapter, install_incremental_indexing

# Mock dependencies
class MockEmbeddingClient:
    def get_embedding(self, text):
        # Return a fixed-size mock embedding
        return [0.1] * 384

class MockFileTool:
    def __init__(self, workspace_root=None):
        self.workspace_root = workspace_root or os.getcwd()
        
    def read_file(self, path):
        try:
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
        except:
            return ""
            
    def list_files(self, extensions=None):
        result = []
        for root, _, files in os.walk(self.workspace_root):
            for filename in files:
                if not extensions or any(filename.endswith(ext) for ext in extensions):
                    result.append(os.path.join(root, filename))
        return result

class MockStaticAnalyzer:
    def analyze_project(self, root_path, **kwargs):
        # Return a minimal dependency graph
        return {
            "nodes": [
                {"id": "file1", "type": "file", "path": os.path.join(root_path, "file1.py")},
                {"id": "file2", "type": "file", "path": os.path.join(root_path, "file2.py")},
            ],
            "edges": [
                {"source": "file1", "target": "file2", "type": "import"}
            ]
        }
        
    def analyze_file(self, file_path):
        # Return minimal file analysis
        return {
            "imports": [],
            "classes": [],
            "functions": []
        }

class MockCodeAnalysisTool:
    def __init__(self):
        self.embedding_client = MockEmbeddingClient()
        self.file_tool = MockFileTool()
        self._embedding_cache = {}
        self._cache_dir = tempfile.mkdtemp(prefix="agent_s3_test_")
        
    def search_code(self, query, top_k=10):
        # Original search function
        return [
            {
                "file": "sample.py",
                "score": 0.9,
                "content": "def hello():\n    return 'world'",
                "metadata": {}
            }
        ]
        
    def cleanup(self):
        if os.path.exists(self._cache_dir):
            shutil.rmtree(self._cache_dir)


class TestIncrementalIndexing(unittest.TestCase):
    """Test suite for incremental indexing system."""
    
    def setUp(self):
        # Create a temporary directory for tests
        self.temp_dir = tempfile.mkdtemp(prefix="agent_s3_index_test_")
        
        # Create mock dependencies
        self.code_analysis_tool = MockCodeAnalysisTool()
        self.static_analyzer = MockStaticAnalyzer()
        
        # Sample files for testing
        self.test_files = {}
        self.create_test_files()
    
    def tearDown(self):
        # Remove temp directory
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
            
        # Clean up code analysis tool
        self.code_analysis_tool.cleanup()
    
    def create_test_files(self):
        """Create sample files for testing."""
        # Create Python files
        py_file1 = os.path.join(self.temp_dir, "file1.py")
        with open(py_file1, 'w') as f:
            f.write("# File 1\nfrom file2 import func2\n\ndef func1():\n    return func2()\n")
        self.test_files["file1"] = py_file1
            
        py_file2 = os.path.join(self.temp_dir, "file2.py")
        with open(py_file2, 'w') as f:
            f.write("# File 2\n\ndef func2():\n    return 'Hello from func2'\n")
        self.test_files["file2"] = py_file2
    
    def modify_test_file(self, file_key, new_content):
        """Modify a test file with new content."""
        file_path = self.test_files.get(file_key)
        if file_path and os.path.exists(file_path):
            with open(file_path, 'w') as f:
                f.write(new_content)
            # Sleep to ensure file modification time changes
            time.sleep(0.1)
            return True
        return False
    
    def test_file_change_tracker(self):
        """Test the FileChangeTracker class."""
        # Create tracker
        tracker = FileChangeTracker(os.path.join(self.temp_dir, "tracking"))
        
        # Track initial state
        count = tracker.track_directory(self.temp_dir)
        self.assertEqual(count, 2)  # Two Python files
        
        # Check if anything changed (should be False since we just tracked)
        changed_files = tracker.get_changed_files(self.temp_dir)
        self.assertEqual(len(changed_files), 0)
        
        # Modify a file
        self.modify_test_file("file1", "# Modified File 1\nfrom file2 import func2\n\ndef func1_modified():\n    return func2()\n")
        
        # Check if it detects the change
        changed_files = tracker.get_changed_files(self.temp_dir)
        self.assertEqual(len(changed_files), 1)
        self.assertIn(self.test_files["file1"], changed_files)
    
    def test_dependency_impact_analyzer(self):
        """Test the DependencyImpactAnalyzer class."""
        # Create analyzer
        analyzer = DependencyImpactAnalyzer()
        
        # Build from minimal dependency graph
        graph = {
            "nodes": {
                "file1": {"id": "file1", "type": "file", "path": self.test_files["file1"]},
                "file2": {"id": "file2", "type": "file", "path": self.test_files["file2"]},
            },
            "edges": [
                {"source": "file1", "target": "file2", "type": "import"}
            ]
        }
        
        analyzer.build_from_dependency_graph(graph)
        
        # Test forward dependencies
        self.assertIn(self.test_files["file2"], analyzer.forward_deps[self.test_files["file1"]])
        
        # Test reverse dependencies
        self.assertIn(self.test_files["file1"], analyzer.reverse_deps[self.test_files["file2"]])
        
        # Test impact calculation
        impact = analyzer.calculate_impact_scope([self.test_files["file2"]])
        self.assertIn(self.test_files["file1"], impact["directly_impacted_files"])
    
    def test_incremental_indexer(self):
        """Test the IncrementalIndexer class."""
        # Configure file tool to use our temp dir
        self.code_analysis_tool.file_tool.workspace_root = self.temp_dir
        
        # Create indexer
        indexer = IncrementalIndexer(
            storage_path=os.path.join(self.temp_dir, "index"),
            embedding_client=self.code_analysis_tool.embedding_client,
            file_tool=self.code_analysis_tool.file_tool,
            static_analyzer=self.static_analyzer
        )
        
        # Test initial indexing
        result = indexer.index_repository(self.temp_dir)
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["files_indexed"], 2)
        
        # Modify a file
        self.modify_test_file("file1", "# Modified File 1\nfrom file2 import func2\n\ndef func1_modified():\n    return func2()\n")
        
        # Test incremental update
        result = indexer.index_repository(self.temp_dir)
        self.assertEqual(result["status"], "success")
        self.assertTrue(result["files_indexed"] >= 1)
    
    def test_integration_with_code_analysis_tool(self):
        """Test integrating with CodeAnalysisTool through the adapter."""
        # Configure file tool to use our temp dir
        self.code_analysis_tool.file_tool.workspace_root = self.temp_dir
        
        # Install incremental indexing
        adapter = install_incremental_indexing(
            self.code_analysis_tool, 
            self.static_analyzer
        )
        
        # Test initial indexing
        result = adapter.update_index(force_full=True)
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["files_indexed"], 2)
        
        # Test search
        search_results = self.code_analysis_tool.search_code("func1")
        self.assertTrue(len(search_results) > 0)
        
        # Modify a file
        self.modify_test_file("file1", "# Modified File 1\nfrom file2 import func2\n\ndef func1_modified():\n    return func2()\n")
        
        # Test incremental update
        result = adapter.update_index([self.test_files["file1"]])
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["files_indexed"], 1)
        
        # Test watch mode
        watch_id = adapter.enable_watch_mode(self.temp_dir)
        self.assertTrue(bool(watch_id))
        
        # Test stats
        stats = adapter.get_index_stats()
        self.assertIn("partitions", stats)
        
        # Clean up
        adapter.teardown()


if __name__ == "__main__":
    unittest.main()
