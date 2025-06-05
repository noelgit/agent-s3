# Migration Guide: Legacy to Unified Context Management

## Overview

This guide provides step-by-step instructions for migrating from the legacy context management system to the new Unified Context Management System in Agent S3.

## Migration Strategy

### Phase 1: Assessment and Preparation (Recommended: 1-2 days)

1. **Inventory Current Usage**
   ```bash
   # Find all context manager usages
   grep -r "ContextManager" --include="*.py" .
   grep -r "context_manager" --include="*.py" .
   grep -r "get_context" --include="*.py" .
   ```

2. **Analyze Dependencies**
   ```python
   # Check which files import legacy context manager
   from agent_s3.context_manager import ContextManager  # Legacy
   from agent_s3.tools.context_management.context_manager import ContextManager  # New
   ```

3. **Backup Current Configuration**
   ```bash
   # Create backup of current system
   cp -r agent_s3/context_manager.py agent_s3/context_manager.py.backup
   ```

### Phase 2: Install Unified System (Recommended: 1 day)

1. **Verify Installation**
   ```python
   # Test that all components are available
   try:
       from agent_s3.tools.context_management.unified_context_manager import UnifiedContextManager
       from agent_s3.tools.context_management.context_monitoring import ContextMonitor
       from agent_s3.coordinator.context_bridge import OrchestratorContextBridge
       print("✓ All unified context management components available")
   except ImportError as e:
       print(f"✗ Missing component: {e}")
   ```

2. **Run Validation Tests**
   ```bash
   # Run the simplified tests to validate core functionality
   python -m pytest tests/test_simplified_context_management.py -v
   ```

### Phase 3: Parallel Operation (Recommended: 1-2 weeks)

1. **Enable Dual Retrieval Mode**
   ```python
   from agent_s3.tools.context_management.unified_context_manager import get_unified_context_manager
   from agent_s3.tools.context_management.config import ContextManagementConfig
   
   # Setup with comparison enabled
   config = ContextManagementConfig.get_development_config()
   config["context_management"]["unified_manager"]["use_dual_retrieval"] = True
   config["context_management"]["unified_manager"]["compare_results"] = True
   
   unified_manager = get_unified_context_manager()
   unified_manager.config.update(config["context_management"]["unified_manager"])
   ```

2. **Monitor Performance Differences**
   ```python
   from agent_s3.tools.context_management.context_monitoring import get_context_monitor
   
   monitor = get_context_monitor()
   
   # Check performance metrics after running both systems
   metrics = monitor.get_metrics_summary()
   print(f"Legacy manager avg time: {metrics.get('legacy_avg_time', 'N/A')}")
   print(f"New manager avg time: {metrics.get('new_avg_time', 'N/A')}")
   print(f"Context differences found: {metrics.get('context_differences', 0)}")
   ```

### Phase 4: Gradual Migration (Recommended: 1-2 weeks)

#### Step 1: Migrate Non-Critical Components

1. **Start with Test/Development Code**
   ```python
   # OLD CODE (Legacy)
   from agent_s3.context_manager import ContextManager
   
   def get_task_context(task_id):
       context_manager = ContextManager()
       return context_manager.get_context(task_id)
   
   # NEW CODE (Unified)
   from agent_s3.tools.context_management.unified_context_manager import get_unified_context_manager
   
   async def get_task_context(task_id):
       unified_manager = get_unified_context_manager()
       return await unified_manager.get_context(task_id)
   ```

2. **Migrate Utility Functions**
   ```python
   # OLD CODE
   class TaskProcessor:
       def __init__(self):
           self.context_manager = ContextManager()
       
       def process_task(self, task_id):
           context = self.context_manager.get_context(task_id)
           # Process with context
   
   # NEW CODE
   class TaskProcessor:
       def __init__(self):
           self.context_manager = get_unified_context_manager()
       
       async def process_task(self, task_id):
           context = await self.context_manager.get_context(task_id)
           # Process with context
   ```

#### Step 2: Migrate Core Components

1. **Update Orchestrator Integration**
   ```python
   # OLD CODE in orchestrator.py
   from agent_s3.context_manager import ContextManager
   
   class Orchestrator:
       def __init__(self):
           self.context_manager = ContextManager()
       
       def _planning_workflow(self, task):
           context = self.context_manager.get_context(task.id)
           # Use context
   
   # NEW CODE in orchestrator.py
   from agent_s3.coordinator.context_bridge import OrchestratorContextBridge
   from agent_s3.tools.context_management.unified_context_manager import get_unified_context_manager
   
   class Orchestrator:
       def __init__(self):
           unified_manager = get_unified_context_manager()
           self.context_bridge = OrchestratorContextBridge(context_manager=unified_manager)
       
       async def _planning_workflow(self, task):
           context = await self.context_bridge.get_workflow_context(task.id, 'planning')
           # Use optimized workflow context
   ```

2. **Update LLM Integration**
   ```python
   # OLD CODE
   from agent_s3.context_manager import ContextManager
   
   def call_llm_with_context(prompt, task_id):
       context_manager = ContextManager()
       context = context_manager.get_context(task_id)
       full_prompt = f"{prompt}\n\nContext: {context}"
       return llm_call(full_prompt)
   
   # NEW CODE
   from agent_s3.tools.context_management.llm_integration import LLMContextIntegration
   
   async def call_llm_with_context(prompt, task_id):
       integration = LLMContextIntegration()
       return await integration.call_llm_with_context(
           prompt=prompt,
           task_id=task_id,
           context_optimization=True
       )
   ```

#### Step 3: Update Configuration and Setup

1. **Migrate Coordinator Setup**
   ```python
   # OLD CODE
   from agent_s3.coordinator.orchestrator import Orchestrator
   
   def setup_coordinator():
       coordinator = Orchestrator()
       # Basic setup
       return coordinator
   
   # NEW CODE
   from agent_s3.coordinator.orchestrator import Orchestrator
   from agent_s3.tools.context_management.config import setup_enhanced_context_management
   
   def setup_coordinator(environment="production"):
       coordinator = Orchestrator()
       
       # Setup enhanced context management
       success = setup_enhanced_context_management(coordinator, environment=environment)
       if not success:
           raise RuntimeError("Failed to setup enhanced context management")
       
       return coordinator
   ```

### Phase 5: Complete Migration (Recommended: 1 week)

1. **Remove Legacy Dependencies**
   ```python
   # Remove these imports throughout codebase:
   # from agent_s3.context_manager import ContextManager
   
   # Replace with:
   # from agent_s3.tools.context_management.unified_context_manager import get_unified_context_manager
   ```

2. **Update All Async/Await Patterns**
   ```python
   # Ensure all context calls are now async
   # OLD: context = context_manager.get_context(task_id)
   # NEW: context = await unified_manager.get_context(task_id)
   ```

3. **Final Configuration**
   ```python
   # Set production configuration
   from agent_s3.tools.context_management.config import ContextManagementConfig
   
   config = ContextManagementConfig.get_production_config()
   # Disable dual retrieval mode
   config["context_management"]["unified_manager"]["use_dual_retrieval"] = False
   config["context_management"]["unified_manager"]["prefer_new_system"] = True
   
   # Apply configuration
   setup_enhanced_context_management(coordinator, config)
   ```

## Code Migration Patterns

### Pattern 1: Simple Context Retrieval

```python
# BEFORE
from agent_s3.context_manager import ContextManager

context_manager = ContextManager()
context = context_manager.get_context(task_id)

# AFTER  
from agent_s3.tools.context_management.unified_context_manager import get_unified_context_manager

unified_manager = get_unified_context_manager()
context = await unified_manager.get_context(task_id)
```

### Pattern 2: Class-based Context Management

```python
# BEFORE
class MyClass:
    def __init__(self):
        self.context_manager = ContextManager()
    
    def my_method(self, task_id):
        context = self.context_manager.get_context(task_id)
        return self.process_with_context(context)

# AFTER
class MyClass:
    def __init__(self):
        self.context_manager = get_unified_context_manager()
    
    async def my_method(self, task_id):
        context = await self.context_manager.get_context(task_id)
        return self.process_with_context(context)
```

### Pattern 3: Error Handling

```python
# BEFORE
try:
    context = context_manager.get_context(task_id)
except Exception as e:
    print(f"Context retrieval failed: {e}")
    context = {}

# AFTER
try:
    context = await unified_manager.get_context(task_id)
except Exception as e:
    print(f"Context retrieval failed: {e}")
    context = {}
    
    # Additional monitoring
    monitor = get_context_monitor()
    monitor.log_event('context_retrieval_error', {
        'task_id': task_id,
        'error': str(e)
    })
```

### Pattern 4: Workflow Integration

```python
# BEFORE
def planning_phase(workflow_id):
    context_manager = ContextManager()
    context = context_manager.get_context(workflow_id)
    # Use context for planning

def execution_phase(workflow_id):
    context_manager = ContextManager()
    context = context_manager.get_context(workflow_id)
    # Use context for execution

# AFTER
async def planning_phase(workflow_id):
    bridge = OrchestratorContextBridge(context_manager=get_unified_context_manager())
    context = await bridge.get_workflow_context(workflow_id, 'planning')
    # Use optimized planning context

async def execution_phase(workflow_id):
    bridge = OrchestratorContextBridge(context_manager=get_unified_context_manager())
    context = await bridge.get_workflow_context(workflow_id, 'execution')
    # Use optimized execution context
```

## Testing Strategy

### Unit Tests Migration

1. **Update Test Fixtures**
   ```python
   # OLD TEST
   def test_context_retrieval():
       context_manager = ContextManager()
       context = context_manager.get_context('test_task')
       assert 'data' in context
   
   # NEW TEST
   @pytest.mark.asyncio
   async def test_context_retrieval():
       unified_manager = get_unified_context_manager()
       context = await unified_manager.get_context('test_task')
       assert 'data' in context
   ```

2. **Add Integration Tests**
   ```python
   @pytest.mark.asyncio
   async def test_dual_retrieval_consistency():
       unified_manager = get_unified_context_manager()
       unified_manager.config.use_dual_retrieval = True
       
       context = await unified_manager.get_context('test_task')
       
       # Should have data from both sources
       assert context is not None
       
       # Check monitoring recorded the comparison
       monitor = get_context_monitor()
       events = monitor.get_events_by_type('dual_retrieval_comparison')
       assert len(events) > 0
   ```

### Performance Testing

1. **Benchmark Comparison**
   ```python
   import time
   import asyncio
   
   async def benchmark_unified_manager():
       unified_manager = get_unified_context_manager()
       
       start_time = time.time()
       for i in range(100):
           await unified_manager.get_context(f'task_{i}')
       end_time = time.time()
       
       print(f"Unified manager: {end_time - start_time:.2f} seconds")
   
   def benchmark_legacy_manager():
       context_manager = ContextManager()
       
       start_time = time.time()
       for i in range(100):
           context_manager.get_context(f'task_{i}')
       end_time = time.time()
       
       print(f"Legacy manager: {end_time - start_time:.2f} seconds")
   ```

## Validation Checklist

### Pre-Migration Checklist

- [ ] All context manager usage identified
- [ ] Current performance baseline established
- [ ] Backup of current system created
- [ ] Test environment prepared
- [ ] Migration timeline planned

### During Migration Checklist

- [ ] Unified context management components installed
- [ ] Validation tests passing
- [ ] Dual retrieval mode enabled
- [ ] Performance monitoring active
- [ ] Context consistency verified

### Post-Migration Checklist

- [ ] All legacy imports removed
- [ ] All context calls converted to async
- [ ] Production configuration applied
- [ ] Performance monitoring showing healthy metrics
- [ ] No context retrieval errors in logs
- [ ] Cache hit rates at acceptable levels
- [ ] Error rates within thresholds

## Rollback Plan

### Emergency Rollback

1. **Disable Unified System**
   ```python
   # In emergency, disable unified system
   config = {
       "context_management": {
           "unified_manager": {
               "enabled": False,
               "prefer_new_system": False
           }
       }
   }
   ```

2. **Revert to Legacy Only**
   ```bash
   # Restore backup
   cp agent_s3/context_manager.py.backup agent_s3/context_manager.py
   
   # Restart services
   systemctl restart agent-s3
   ```

### Gradual Rollback

1. **Switch to Legacy Preference**
   ```python
   unified_manager.config.prefer_new_system = False
   unified_manager.config.fallback_to_legacy = True
   ```

2. **Monitor and Adjust**
   ```python
   # Monitor performance after rollback
   monitor = get_context_monitor()
   metrics = monitor.get_metrics_summary()
   print(f"Post-rollback performance: {metrics}")
   ```

## Troubleshooting

### Common Migration Issues

1. **Async/Await Errors**
   ```python
   # ERROR: Cannot use 'await' outside async function
   # SOLUTION: Make calling function async
   async def calling_function():
       context = await unified_manager.get_context(task_id)
   ```

2. **Import Errors**
   ```python
   # ERROR: ImportError: cannot import name 'UnifiedContextManager'
   # SOLUTION: Check import path
   from agent_s3.tools.context_management.unified_context_manager import get_unified_context_manager
   ```

3. **Performance Degradation**
   ```python
   # Check cache settings
   config = unified_manager.config
   if not config.cache_enabled:
       config.cache_enabled = True
       config.cache_size_limit = 2000
   ```

### Monitoring During Migration

1. **Set Up Alerts**
   ```python
   monitor = get_context_monitor()
   
   # Monitor for high error rates
   error_rate = monitor.metrics.get('error_rate', 0)
   if error_rate > 0.1:  # 10% error rate
       print("ALERT: High error rate during migration")
   
   # Monitor response times
   avg_time = monitor.metrics.get('avg_response_time', 0)
   if avg_time > 30:  # 30 seconds
       print("ALERT: Slow response times during migration")
   ```

2. **Daily Health Checks**
   ```python
   def daily_health_check():
       unified_manager = get_unified_context_manager()
       health = unified_manager.get_health_status()
       
       print("=== Daily Health Check ===")
       print(f"Legacy Manager: {'✓' if health['legacy_manager']['healthy'] else '✗'}")
       print(f"New Manager: {'✓' if health['new_manager']['healthy'] else '✗'}")
       print(f"Cache Hit Rate: {health['cache']['hit_rate']:.2%}")
       print(f"Error Rate: {health['overall']['error_rate']:.2%}")
   ```

This migration guide provides a structured approach to safely transitioning from the legacy context management system to the new unified system while minimizing risk and maintaining system stability.
