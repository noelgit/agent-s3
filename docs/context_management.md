# Context Management System

Agent-S3 includes a modular context management subsystem that optimizes what information is passed to the LLM.  It combines token accounting, compression and adaptive configuration so prompts stay within model limits while still providing relevant data.

## Core Components

### ContextManager
- Orchestrates background optimization of context and exposes APIs for updating and retrieving optimized context.
- Registers utility tools such as the token budget analyzer and compression manager.
- Supports optional adaptive configuration for dynamic tuning of internal parameters.
- Provides an `optimize_context(context)` method to update and optimize context on demand.
- Implemented in `agent_s3.tools.context_management.context_manager.ContextManager`.

### CompressionManager
- Applies summarization and reference based compression when context grows too large.
- Uses strategies like semantic summarization and key information extraction.
- Triggered when total token count exceeds the configured threshold.

### TokenBudgetAnalyzer
- Estimates token usage for text and code using `tiktoken`.
- Allocates tokens to individual files and sections based on importance.
- Provides reports indicating when optimization or pruning is applied.

### Adaptive Configuration
- Profiles the project and collects metrics to adjust context settings over time.
- Managed by `AdaptiveConfigManager` and connected to the `ContextManager` via `set_adaptive_config_manager()`.
- Updates parameters such as chunk sizes, search weights and summarization thresholds at runtime.

## Example Configuration
```json
{
  "context_management": {
    "enabled": true,
    "optimization_interval": 60,
    "compression_threshold": 8000,
    "adaptive_config": { "enabled": true }
  }
}
```

## Coordinator Integration
`setup_context_management()` creates a `ContextManager` and patches the coordinator.  Tests show the integration workflow:
```python
result = setup_context_management(self.coordinator)
self.assertTrue(result)
self.assertIsNotNone(self.coordinator.context_manager)
self.assertIsNotNone(self.coordinator.adaptive_config_manager)
```
【F:tests/tools/context_management/test_adaptive_config_integration.py†L118-L131】

## LLM Utilities Integration
`integrate_with_llm_utils()` patches `cached_call_llm` so prompts are optimized automatically.  The integration also starts background optimization when enabled.  The helper is imported alongside other components:
```python
from agent_s3.tools.context_management.llm_integration import (
    LLMContextIntegration,
    integrate_with_llm_utils,
)
```
【F:tests/integration/test_context_management_integration.py†L16-L28】

## Usage Examples from Tests
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

These tests demonstrate how each component interacts with real context data and confirm that integration with the coordinator works as expected.
