import pytest
from unittest.mock import Mock
import time
from agent_s3.tools.context_management.context_manager import ContextManager

# Integration tests for ContextManager graph logic

class DummyTechStackDetector:
    def detect_tech_stack(self):
        return {'frameworks': ['fastapi']}

class DummyStaticAnalyzer:
    def get_imports(self, file_path):
        return [{'module': 'mod1', 'names': [], 'location': 1}]
    def get_inheritance_graph(self, file_path):
        return {}
    build_call_graph = get_inheritance_graph  # return empty dict
    def _extract_fastapi_routes(self, content):
        return [{'source': 'dummy@1', 'target': 'dummy@1', 'type': 'route_handler', 'location': 1}]

class DummyFileTool:
    def list_files(self, pattern, recursively=True):
        return ['app.py']
    def read_file(self, file_path):
        return 'from fastapi import FastAPI'
    def glob_files(self, pattern):
        return []
    def get_workspace_root(self):
        return '/workspace'

def test_build_dependency_graph_with_fastapi(tmp_path):
    cm = ContextManager()
    cm.initialize_tools(
        tech_stack_detector=DummyTechStackDetector(),
        code_analysis_tool=DummyStaticAnalyzer(),
        file_history_analyzer=None,
        file_tool=DummyFileTool(),
        memory_manager=None,
        test_planner=None,
        test_frameworks=None
    )
    graph = cm.get_dependency_graph()
    # File node should exist
    assert 'app.py' in graph['nodes']
    # Import edge present
    assert any(edge['type'] == 'import' for edge in graph['edges'])
    # Framework-specific route_handler edge present
    assert any(edge['type'] == 'route_handler' for edge in graph['edges'])

def test_context_snapshot_includes_dynamic_sections(monkeypatch):
    """Test that get_current_context_snapshot returns expected dynamic context keys after background loop."""
    cm = ContextManager()
    # Patch background fetchers to inject test data
    cm._fetch_recent_changes = lambda *a, **kw: {"recent_changes": ["dummy_change"]}
    cm._fetch_documentation = lambda *a, **kw: {"documentation": {"README.md": "doc content"}}
    cm._fetch_test_coverage = lambda *a, **kw: {"test_coverage": {"overall_coverage": 99}}
    # Simulate background loop run
    cm.update_context(cm._fetch_recent_changes())
    cm.update_context(cm._fetch_documentation())
    cm.update_context(cm._fetch_test_coverage())
    snapshot = cm.get_current_context_snapshot()
    assert "recent_changes" in snapshot
    assert "documentation" in snapshot
    assert "test_coverage" in snapshot

# Tests for the newly added methods in the upgrade plan

def test_check_tools_initialized_without_required_tools():
    """Test that _check_tools_initialized returns False when no tools initialized."""
    cm = ContextManager()
    # Should return False but not raise exception when no specific tools required
    assert not cm._check_tools_initialized()

def test_check_tools_initialized_with_required_tools():
    """Test that _check_tools_initialized raises exception when required tools missing."""
    cm = ContextManager()
    with pytest.raises(RuntimeError):
        cm._check_tools_initialized(['tech_stack_detector'])

def test_check_tools_initialized_with_initialized_tools():
    """Test that _check_tools_initialized returns True when all required tools are initialized."""
    cm = ContextManager()
    # Mock token_budget_analyzer
    cm._token_budget_analyzer = Mock()
    # Initialize with required tools
    cm.initialize_tools(
        tech_stack_detector=DummyTechStackDetector(),
        file_tool=DummyFileTool()
    )
    assert cm._check_tools_initialized()
    assert cm._check_tools_initialized(['tech_stack_detector', 'file_tool'])

def test_optimize_context_returns_optimized_copy():
    """Test that optimize_context returns an optimized copy of provided context."""
    cm = ContextManager()
    # Setup required mocks
    cm._token_budget_analyzer = Mock()
    cm._token_budget_analyzer.get_total_token_count = Mock(return_value=1000)
    cm._token_budget_analyzer.get_token_count = Mock(return_value=500)
    cm._memory_manager = Mock()
    cm._memory_manager.hierarchical_summarize = Mock(return_value="Summarized content")
    cm._tools_initialized = True

    # Test context optimization
    test_context = {"code_context": {"test.py": "# Test code\ndef test(): pass"}}
    result = cm.optimize_context(test_context)

    # Verify result is a copy, not the original
    assert result is not test_context
    # Verify token counting was called
    cm._token_budget_analyzer.get_total_token_count.assert_called_once()

def test_ensure_background_optimization_running():
    """Test that ensure_background_optimization_running starts the background thread if not running."""
    cm = ContextManager()  # Background optimization always enabled
    # Mock the _start_background_optimization method
    cm._start_background_optimization = Mock()

    # Test when optimization is not running
    cm.optimization_running = False
    cm.ensure_background_optimization_running()
    cm._start_background_optimization.assert_called_once()

    # Reset mock and test when optimization is already running
    cm._start_background_optimization.reset_mock()
    cm.optimization_running = True
    cm.ensure_background_optimization_running()
    cm._start_background_optimization.assert_not_called()

def test_background_task_scheduling():
    """Test that BackgroundTask correctly tracks when tasks should run."""
    cm = ContextManager()
    task = cm._BackgroundTask("test_task", lambda: True, interval=10.0, priority=2)

    # Task should not run right after creation (last_run is 0)
    assert task.should_run(5.0)

    # After running, task should update last_run timestamp
    task.run()
    current_time = task.last_run

    # Task should not run again immediately
    assert not task.should_run(current_time)
    assert not task.should_run(current_time + 5.0)

    # Task should run after interval has passed
    assert task.should_run(current_time + 10.0)
    assert task.should_run(current_time + 15.0)

def test_dependency_graph_function_relocation(monkeypatch):
    """Test that _update_dependency_graph correctly handles function relocation between files."""
    from unittest.mock import Mock

    cm = ContextManager()

    # Mock the file tool
    file_tool_mock = Mock()
    file_tool_mock.get_workspace_root.return_value = '/workspace'
    cm._file_tool = file_tool_mock

    # Create mock analyzer
    analyzer_mock = Mock()

    # Setup initial dependency graph state
    cm._dependency_graph = {
        "nodes": {
            "file1": {"id": "file1", "type": "file", "path": "file1.py", "name": "file1.py"},
            "file2": {"id": "file2", "type": "file", "path": "file2.py", "name": "file2.py"},
            "func1": {"id": "func1", "type": "function", "path": "file1.py", "name": "calculate_sum"},
            "func2": {"id": "func2", "type": "function", "path": "file1.py", "name": "process_data"}
        },
        "edges": [
            {"source": "file1", "target": "func1", "type": "contains"},
            {"source": "file1", "target": "func2", "type": "contains"},
            {"source": "func2", "target": "func1", "type": "call"}
        ]
    }
    cm._graph_last_updated = time.time()

    # Setup mock for analyze_file_with_tech_stack to simulate function moved to file2
    def mock_analyze_file(fp, tech_stack, project_root):
        if fp == "file1.py":
            return {
                'nodes': [
                    {"id": "file1", "type": "file", "path": "file1.py", "name": "file1.py"},
                    # func1 is gone, moved to file2
                ],
                'edges': []
            }
        elif fp == "file2.py":
            return {
                'nodes': [
                    {"id": "file2", "type": "file", "path": "file2.py", "name": "file2.py"},
                    {"id": "func1_new", "type": "function", "path": "file2.py", "name": "calculate_sum"}
                ],
                'edges': [
                    {"source": "file2", "target": "func1_new", "type": "contains"}
                ]
            }
        return {'nodes': [], 'edges': []}

    analyzer_mock.analyze_file_with_tech_stack.side_effect = mock_analyze_file

    # Mock edge resolution to return edges unchanged
    analyzer_mock.resolve_dependency_targets.side_effect = lambda nodes, edges: edges

    # Patch StaticAnalyzer import to return our mock
    monkeypatch.setattr('agent_s3.tools.static_analyzer.StaticAnalyzer', lambda **kwargs: analyzer_mock)

    # Update the graph
    cm._update_dependency_graph(["file1.py", "file2.py"])

    # Verify:
    # 1. func1 node is now updated to the new ID
    assert "func1_new" in cm._dependency_graph["nodes"]
    assert "func1" not in cm._dependency_graph["nodes"]

    # 2. New contains edge from file2 to func1_new exists
    assert any(e["source"] == "file2" and e["target"] == "func1_new" and e["type"] == "contains"
               for e in cm._dependency_graph["edges"])

    # 3. Old call edge is properly updated to reference the new function ID
    call_edges = [e for e in cm._dependency_graph["edges"] if e["type"] == "call"]
    assert len(call_edges) >= 1
    # Either the edge was updated to reference func1_new, or a new edge was created
    assert any(e["target"] == "func1_new" for e in call_edges)

def test_refine_context_with_missing_tools():
    """Test that _refine_current_context handles missing tools with appropriate fallbacks."""
    from unittest.mock import Mock

    cm = ContextManager()

    # Configure with only token_budget_analyzer and memory_manager (minimal required tools)
    cm._token_budget_analyzer = Mock()
    cm._token_budget_analyzer.get_token_count.return_value = 100
    cm._token_budget_analyzer.get_total_token_count.return_value = 500
    cm._token_budget_analyzer.allocate_tokens.side_effect = lambda content, scores, budget: {k: 50 for k in content}

    cm._memory_manager = Mock()
    cm._memory_manager.hierarchical_summarize.return_value = "Summarized content"

    # Missing code_analysis_tool and compression_manager
    cm._code_analysis_tool = None
    cm._compression_manager = None

    # Create test context
    with cm._context_lock:
        cm.current_context = {
            "code_context": {
                "file1.py": "def test(): pass\n" * 50,
                "file2.py": "class Test: pass\n" * 50
            },
            "documentation": {
                "README.md": "# Project Documentation\n" * 50
            }
        }

    # Run refinement on specific files
    cm._refine_current_context(["file1.py", "file2.py"])

    with cm._context_lock:
        refined = cm.current_context.get("files", {})

    # Verify fallbacks were used:
    # No file tool -> context should remain unchanged
    assert refined == {}

    # hierarchical_summarize should not be invoked without a file tool
    cm._memory_manager.hierarchical_summarize.assert_not_called()

    # Set up a second test with only token_budget_analyzer (no memory_manager)
    cm2 = ContextManager()
    cm2._token_budget_analyzer = cm._token_budget_analyzer
    cm2._memory_manager = None
    cm2._compression_manager = None
    cm2._code_analysis_tool = None

    # Create test context
    with cm2._context_lock:
        cm2.current_context = cm.current_context.copy()

    # Run refinement
    cm2._refine_current_context(["file1.py", "file2.py"])

    with cm2._context_lock:
        refined2 = cm2.current_context.get("files", {})

    # Should still have no additional content
    assert refined2 == {}


def test_log_metrics_invalid_context(caplog):
    cm = ContextManager()
    cm.adaptive_config_manager = Mock()

    caplog.set_level("ERROR")
    cm._log_metrics_to_adaptive_config(None)

    assert "Context data is missing or malformed" in caplog.text
    cm.adaptive_config_manager.log_token_usage.assert_not_called()


def test_log_metrics_uses_estimator():
    cm = ContextManager()
    cm.adaptive_config_manager = Mock()

    estimator_mock = Mock()
    estimator_mock.estimate_tokens_for_context.return_value = {"total": 10}
    cm.token_budget_analyzer.estimator = estimator_mock
    cm.token_budget_analyzer.max_tokens = 100

    context = {"code_context": {"a.py": "print('hi')"}}
    cm._log_metrics_to_adaptive_config(context, task_type="test", relevance_score=0.5)

    estimator_mock.estimate_tokens_for_context.assert_called_once_with(context)
    cm.adaptive_config_manager.log_token_usage.assert_called_once()


class DummyLock:
    def __init__(self):
        self.entered = 0

    def __enter__(self):
        self.entered += 1

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False


def test_gather_context_snapshot_fields():
    cm = ContextManager()

    cm.allocation_strategy = Mock()
    cm.allocation_strategy.allocate.return_value = {"optimized_context": {}}

    cm.update_context({"code_context": {"a.py": "print('hi')"}})

    dummy_lock = DummyLock()
    cm._context_lock = dummy_lock

    result = cm.gather_context()

    assert result == {}
    assert dummy_lock.entered == 1

    called_context = cm.allocation_strategy.allocate.call_args[0][0]
    assert called_context == {"code_context": {"a.py": "print('hi')"}}
    assert called_context is not cm.current_context


def test_set_adaptive_config_manager_updates_compression(monkeypatch):
    """Ensure compression settings are updated using adaptive config manager."""
    cm = ContextManager()

    # Prepare dummy adaptive configuration
    class DummyManager:
        def __init__(self):
            self.metrics_collector = Mock(register_callback=Mock())

        def get_current_config(self):
            return {
                "context_management": {
                    "summarization": {
                        "threshold": 3000,
                        "compression_ratio": 0.25,
                    }
                }
            }

        def get_config_version(self):
            return 1

    called = {"threshold": None, "ratio": None}

    def fake_set_threshold(value: int) -> None:
        called["threshold"] = value

    def fake_set_ratio(value: float) -> None:
        called["ratio"] = value

    # Patch CompressionManager methods with monkeypatch to restore them later
    monkeypatch.setattr(
        cm.compression_manager,
        "set_summarization_threshold",
        fake_set_threshold,
    )
    monkeypatch.setattr(
        cm.compression_manager,
        "set_compression_ratio",
        fake_set_ratio,
    )
    monkeypatch.setattr(cm, "_start_background_optimization", lambda: None)

    cm.set_adaptive_config_manager(DummyManager())

    assert called["threshold"] == 3000
    assert called["ratio"] == 0.25
