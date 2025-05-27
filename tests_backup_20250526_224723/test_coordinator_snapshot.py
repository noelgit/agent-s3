from agent_s3.tools.context_management.context_registry import ContextRegistry
from agent_s3.error_handler import ErrorHandler

class DummyContextManager:
    def __init__(self):
        self.received = None
    def get_current_context_snapshot(self, context_type=None, query=None):
        self.received = (context_type, query)
        return {"snapshot": True}

class DummyCoordinator:
    def __init__(self, context_registry):
        self.context_registry = context_registry
        self.error_handler = ErrorHandler("CoordinatorTest", reraise=True)
    def get_current_context_snapshot(self, context_type=None, query=None):
        with self.error_handler.error_context(phase="context", operation="get_current_context_snapshot"):
            return self.context_registry.get_current_context_snapshot(context_type=context_type, query=query)


def test_coordinator_snapshot_forwarding():
    registry = ContextRegistry()
    manager = DummyContextManager()
    registry.register_provider("context_manager", manager)
    coordinator = DummyCoordinator(registry)

    result = coordinator.get_current_context_snapshot(context_type="files", query="app.py")
    assert result == {"snapshot": True}
    assert manager.received == ("files", "app.py")


def test_coordinator_snapshot_legacy_manager():
    class LegacyManager:
        def __init__(self):
            self.called = False
        def get_current_context_snapshot(self):
            self.called = True
            return {"legacy": True}
    registry = ContextRegistry()
    manager = LegacyManager()
    registry.register_provider("context_manager", manager)
    coordinator = DummyCoordinator(registry)

    result = coordinator.get_current_context_snapshot(context_type="tech_stack", query="")
    assert result == {"legacy": True}
    assert manager.called
