# Unified Context Management System

Agent-S3 uses a unified context management system that optimizes what information is passed to the LLM. The system combines token accounting, compression, adaptive configuration, and performance monitoring so prompts stay within model limits while providing relevant data.

## Core Components

### ContextManager
- Central coordinator managing multiple context sources with deduplication and caching.
- Exposes APIs for updating and retrieving optimized context.
- Health monitoring with metrics tracking.
- Implemented in `agent_s3.tools.context_management.context_manager.ContextManager`.

### CompressionManager
- Applies summarization and reference-based compression when context grows too large.
- Uses semantic summarization and key information extraction strategies.
- Triggered when the token count exceeds the configured threshold.

### TokenBudgetAnalyzer
- Estimates token usage for text and code using `tiktoken`.
- Allocates tokens to files and sections based on importance.
- Provides reports indicating when optimization or pruning is applied.

### ContextMonitor
- Tracks response times, error rates, and cache hits.
- Generates alerts for performance issues.

### Adaptive Configuration
- Profiles the project and adjusts context settings over time.
- Managed by `AdaptiveConfigManager` via `set_adaptive_config_manager()`.
- Updates chunk sizes, search weights, and summarization thresholds at runtime.

### CoordinatorContextIntegration
- Enhanced integration layer between the Coordinator and Context Manager.
- Provides workflow-specific context helpers and improved error handling.

### LLM Integration
- Automatic integration with the unified context manager.
- Optimizes context for LLM token limits and constructs prompts intelligently.

## Example Configuration
```json
{
  "context_management": {
    "enabled": true,
    "optimization_interval": 60,
    "compression_threshold": 8000,
    "adaptive_config": {"enabled": true}
  }
}
```
Additional environment presets are available:
```json
{
  "context_management": {
    "unified_manager": {"enabled": true, "cache_enabled": true},
    "monitoring": {"enabled": true, "log_level": "DEBUG"}
  }
}
```

## Coordinator Integration
`setup_context_management()` creates a `ContextManager` and patches the coordinator. Tests show the integration workflow:
```python
result = setup_context_management(self.coordinator)
self.assertTrue(result)
self.assertIsNotNone(self.coordinator.context_manager)
self.assertIsNotNone(self.coordinator.adaptive_config_manager)
```
【F:tests/tools/context_management/test_adaptive_config_integration.py†L118-L131】

## LLM Utilities Integration
`integrate_with_llm_utils()` patches `cached_call_llm` so prompts are optimized automatically. The integration also starts background optimization when enabled:
```python
from agent_s3.tools.context_management.llm_integration import (
    LLMContextIntegration,
    integrate_with_llm_utils,
)
```
【F:tests/integration/test_context_management_integration.py†L16-L28】

## Usage Examples
- `TokenBudgetAnalyzer` initialization and allocation:
```python
analyzer = TokenBudgetAnalyzer(max_tokens=16000)
result = analyzer.allocate_tokens(sample_context)
assert "optimized_context" in result
```
【F:tests/test_token_budget.py†L204-L214】

- Compression workflow:
```python
manager = CompressionManager(compression_threshold=1000)
compressed = manager.compress(context, ["SemanticSummarizer"])
metadata = compressed["compression_metadata"]["overall"]
```
【F:tests/integration/test_context_management_integration.py†L246-L271】

- Basic context manager usage:
```python
from agent_s3.tools.context_management.context_manager import ContextManager
context_manager = ContextManager()
context = context_manager.get_context()
```

- Workflow integration:
```python
from agent_s3.tools.context_management.coordinator_integration import (
    CoordinatorContextIntegration,
)

integration = CoordinatorContextIntegration(coordinator)
planning_context = integration.get_context_for_planning('Plan task')
```

- Monitoring example:
```python
from agent_s3.tools.context_management.context_monitoring import get_context_monitor
monitor = get_context_monitor()
with monitor.track_performance('context_operation'):
    context = context_manager.get_context()
metrics = monitor.get_metrics_summary()
print(f"Cache hit rate: {metrics['cache_hit_rate']}")
```

## Key Features
- Unified interface for context creation with intelligent fallback and deduplication.
- Consistent context passing to LLM calls with optimization for token limits.
- Performance monitoring with real-time metrics and alerts.
- Backward compatible integration with existing code.

## Architecture Benefits
- **Scalability**: Modular design with caching and async support.
- **Reliability**: Health checks and graceful error recovery.
- **Maintainability**: Clear interfaces and comprehensive logging.
- **Observability**: Dashboards and structured event logging.

## Migration Strategy
- Supports gradual migration with dual operation and rollback options.
- Continuous performance monitoring during rollout.

## Next Steps
1. Start in development with monitoring enabled.
2. Gradually roll out to production while tracking metrics.
3. Future enhancements include ML-based relevance scoring and distributed caching.

## Conclusion
The unified system improves efficiency and reliability by eliminating context overlap, optimizing token usage, and providing comprehensive monitoring while maintaining full backward compatibility.

**Status**: ✅ Implementation Complete and Validated
