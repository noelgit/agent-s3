# Unified Context Management System Documentation

## Overview

The Unified Context Management System provides a comprehensive solution for managing context across different components in the Agent S3 system. It addresses the challenges of having multiple context managers, eliminates context overlap, and provides enhanced monitoring and performance capabilities.

## Architecture

### Core Components

1. **UnifiedContextManager** - Central coordinator that manages multiple context sources
2. **ContextMonitor** - Performance monitoring and alerting system  
3. **OrchestratorContextBridge** - Workflow-aware context optimization
4. **Enhanced LLM Integration** - Improved context handling for LLM calls
5. **Configuration Management** - Centralized configuration with environment presets

### System Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    Unified Context Management                    │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐    ┌─────────────────┐   ┌───────────────┐ │
│  │ Legacy Context  │    │  New Context    │   │   Context     │ │
│  │    Manager      │    │    Manager      │   │   Monitor     │ │
│  └─────────────────┘    └─────────────────┘   └───────────────┘ │
│           │                       │                    │        │
│           └───────────┬───────────┘                    │        │
│                       │                                │        │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │              UnifiedContextManager                          │ │
│  │  • Context Deduplication                                   │ │
│  │  • Intelligent Fallback                                   │ │
│  │  • Performance Caching                                    │ │
│  │  • Monitoring Integration                                 │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                               │                                 │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │           OrchestratorContextBridge                        │ │
│  │  • Workflow-aware Context                                 │ │
│  │  • Phase-specific Optimization                            │ │
│  │  • Performance Metrics                                    │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                               │                                 │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │              LLM Integration                               │ │
│  │  • Enhanced Context Passing                               │ │
│  │  • Prompt Optimization                                    │ │
│  │  • Monitoring Integration                                 │ │
│  └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## Installation and Setup

### Basic Setup

```python
from agent_s3.tools.context_management.unified_context_manager import get_unified_context_manager
from agent_s3.tools.context_management.context_monitoring import get_context_monitor
from agent_s3.coordinator.context_bridge import OrchestratorContextBridge

# Initialize unified context manager
unified_manager = get_unified_context_manager()

# Initialize monitoring
monitor = get_context_monitor()

# Create orchestrator bridge
bridge = OrchestratorContextBridge(context_manager=unified_manager)
```

### Configuration-based Setup

```python
from agent_s3.tools.context_management.config import ContextManagementConfig, setup_enhanced_context_management

# Setup with default configuration
config = ContextManagementConfig.get_default_config()
setup_enhanced_context_management(coordinator, config)

# Setup for production environment
setup_enhanced_context_management(coordinator, environment="production")

# Setup for development environment  
setup_enhanced_context_management(coordinator, environment="development")
```

## Features

### 1. Unified Context Management

The `UnifiedContextManager` provides a single interface to multiple context sources:

```python
# Automatic context retrieval with fallback
context = await unified_manager.get_context('task_id')

# Dual retrieval mode for comparison
unified_manager.config.use_dual_retrieval = True
context = await unified_manager.get_context('task_id')  # Gets from both sources
```

**Key Features:**
- **Intelligent Fallback**: Automatically falls back to legacy manager if new manager fails
- **Context Deduplication**: Eliminates duplicate information between context sources  
- **Performance Caching**: Caches contexts to reduce redundant retrievals
- **Health Monitoring**: Tracks performance and health of context sources

### 2. Performance Monitoring

The `ContextMonitor` provides comprehensive monitoring and alerting:

```python
from agent_s3.tools.context_management.context_monitoring import get_context_monitor

monitor = get_context_monitor()

# Record custom metrics
monitor.record_metric('context_retrievals', 150)

# Track performance of operations
with monitor.track_performance('context_generation'):
    # Your context generation code here
    pass

# Log events
monitor.log_event('context_cache_hit', {'task_id': 'task_123'})

# Check for performance alerts
alerts = monitor.check_performance_alerts()
```

**Monitoring Features:**
- **Real-time Metrics**: Tracks response times, error rates, cache hit rates
- **Performance Alerts**: Automated alerts for performance degradation
- **Event Logging**: Comprehensive logging of context management events
- **Health Checks**: Regular health checks of context management components

### 3. Orchestrator Integration

The `OrchestratorContextBridge` provides workflow-aware context optimization:

```python
from agent_s3.coordinator.context_bridge import OrchestratorContextBridge

bridge = OrchestratorContextBridge(context_manager=unified_manager)

# Get workflow-specific context
planning_context = await bridge.get_workflow_context('workflow_id', 'planning')
execution_context = await bridge.get_workflow_context('workflow_id', 'execution')

# Get performance metrics
metrics = bridge.get_performance_metrics()
```

**Integration Features:**
- **Phase-specific Optimization**: Different context optimization for planning vs execution
- **Workflow Caching**: Caches context per workflow to reduce redundant calls
- **Performance Metrics**: Tracks workflow-specific context performance
- **Context Staleness Detection**: Detects and refreshes stale context

### 4. Enhanced LLM Integration

Enhanced context handling for LLM calls:

```python
from agent_s3.tools.context_management.llm_integration import LLMContextIntegration

# Automatically uses unified context manager
integration = LLMContextIntegration()

# Enhanced context passing to LLM
result = await integration.call_llm_with_context(
    prompt="Your prompt here",
    task_id="task_123",
    context_optimization=True
)
```

**LLM Integration Features:**
- **Automatic Context Optimization**: Optimizes context for LLM token limits
- **Intelligent Prompt Construction**: Builds prompts with optimal context
- **Performance Monitoring**: Tracks LLM call performance and context effectiveness
- **Backward Compatibility**: Works with existing LLM integration code

## Configuration

### Environment-Specific Configurations

#### Development Configuration
```python
config = ContextManagementConfig.get_development_config()
# Features:
# - Verbose logging (DEBUG level)
# - Lenient performance thresholds  
# - Smaller cache sizes
# - More detailed monitoring
```

#### Production Configuration  
```python
config = ContextManagementConfig.get_production_config()
# Features:
# - Warning level logging
# - Strict performance thresholds
# - Larger cache sizes
# - Optimized for performance
```

### Custom Configuration

```python
custom_config = {
    "context_management": {
        "unified_manager": {
            "enabled": True,
            "prefer_new_system": True,
            "enable_deduplication": True,
            "max_token_limit": 150000,
            "cache_enabled": True,
            "cache_size_limit": 2000
        },
        "monitoring": {
            "enabled": True,
            "log_level": "INFO",
            "max_events": 20000,
            "performance_thresholds": {
                "max_response_time": 20.0,
                "max_error_rate": 0.05,
                "min_cache_hit_rate": 0.8
            }
        }
    }
}

# Validate configuration
is_valid, errors = ContextManagementConfig.validate_config(custom_config)
if is_valid:
    setup_enhanced_context_management(coordinator, custom_config)
```

## API Reference

### UnifiedContextManager

```python
class UnifiedContextManager:
    async def get_context(self, task_id: str) -> Dict[str, Any]:
        """Get unified context for a task"""
        
    def get_health_status(self) -> Dict[str, Any]:
        """Get health status of context managers"""
        
    def clear_cache(self) -> None:
        """Clear the context cache"""
        
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics"""
```

### ContextMonitor

```python
class ContextMonitor:
    def record_metric(self, name: str, value: Any) -> None:
        """Record a custom metric"""
        
    def log_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """Log an event"""
        
    def track_performance(self, operation_name: str) -> ContextManager:
        """Context manager for tracking operation performance"""
        
    def check_performance_alerts(self) -> List[Dict[str, Any]]:
        """Check for performance alerts"""
        
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get summary of all metrics"""
```

### OrchestratorContextBridge

```python
class OrchestratorContextBridge:
    async def get_workflow_context(self, workflow_id: str, phase: str) -> Dict[str, Any]:
        """Get workflow-specific context"""
        
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get workflow performance metrics"""
        
    def clear_workflow_cache(self, workflow_id: str = None) -> None:
        """Clear workflow cache"""
        
    def optimize_context_for_phase(self, context: Dict[str, Any], phase: str) -> Dict[str, Any]:
        """Optimize context for specific workflow phase"""
```

## Migration Guide

### From Legacy Context Manager

1. **Immediate Migration** (Recommended):
```python
# Old way
from agent_s3.context_manager import ContextManager
context_manager = ContextManager()
context = context_manager.get_context(task_id)

# New way
from agent_s3.tools.context_management.unified_context_manager import get_unified_context_manager
unified_manager = get_unified_context_manager()
context = await unified_manager.get_context(task_id)
```

2. **Gradual Migration**:
```python
# Enable dual retrieval mode for comparison
unified_manager.config.use_dual_retrieval = True
unified_manager.config.compare_results = True  # Log differences

# Monitor performance and switch when confident
```

### From New Context Manager Only

```python
# Old way
from agent_s3.tools.context_management.context_manager import ContextManager
context_manager = ContextManager()
context = await context_manager.get_context(task_id)

# New way - automatic integration
from agent_s3.tools.context_management.unified_context_manager import get_unified_context_manager
unified_manager = get_unified_context_manager()  # Automatically uses new manager as primary
context = await unified_manager.get_context(task_id)
```

## Performance Optimization

### Caching Strategies

1. **Enable Caching**:
```python
config = {
    "context_management": {
        "unified_manager": {
            "cache_enabled": True,
            "cache_size_limit": 2000,
            "cache_ttl": 300  # 5 minutes
        }
    }
}
```

2. **Workflow-Level Caching**:
```python
# Context is cached per workflow and phase
bridge = OrchestratorContextBridge(context_manager=unified_manager)
context = await bridge.get_workflow_context('workflow_id', 'planning')
```

### Performance Monitoring

1. **Set Performance Thresholds**:
```python
config = {
    "context_management": {
        "monitoring": {
            "performance_thresholds": {
                "max_response_time": 15.0,  # 15 seconds max
                "max_error_rate": 0.05,     # 5% max error rate  
                "min_cache_hit_rate": 0.7   # 70% min cache hit rate
            }
        }
    }
}
```

2. **Monitor Performance**:
```python
monitor = get_context_monitor()

# Get performance summary
summary = monitor.get_metrics_summary()
print(f"Average response time: {summary['avg_response_time']}")
print(f"Cache hit rate: {summary['cache_hit_rate']}")
print(f"Error rate: {summary['error_rate']}")

# Check for alerts
alerts = monitor.check_performance_alerts()
for alert in alerts:
    print(f"Alert: {alert['message']}")
```

## Troubleshooting

### Common Issues

1. **Context Manager Not Found**:
```python
# Ensure managers are properly initialized
from agent_s3.tools.context_management.unified_context_manager import get_unified_context_manager
try:
    unified_manager = get_unified_context_manager()
    print("Unified manager initialized successfully")
except Exception as e:
    print(f"Failed to initialize: {e}")
```

2. **Performance Issues**:
```python
# Check health status
health = unified_manager.get_health_status()
if not health['legacy_manager']['healthy']:
    print("Legacy manager is unhealthy")
if not health['new_manager']['healthy']:
    print("New manager is unhealthy")

# Check cache effectiveness
metrics = unified_manager.get_performance_metrics()
print(f"Cache hit rate: {metrics['cache_hit_rate']}")
```

3. **Configuration Issues**:
```python
# Validate configuration
is_valid, errors = ContextManagementConfig.validate_config(config)
if not is_valid:
    print("Configuration errors:")
    for error in errors:
        print(f"  - {error}")
```

### Debugging

1. **Enable Debug Logging**:
```python
config = {
    "context_management": {
        "monitoring": {
            "log_level": "DEBUG",
            "enable_file_logging": True,
            "log_directory": "/path/to/logs"
        }
    }
}
```

2. **Monitor Context Flow**:
```python
monitor = get_context_monitor()

# Track all context retrievals
@monitor.track_operation('context_retrieval')
async def get_context_with_tracking(task_id):
    return await unified_manager.get_context(task_id)

# Review events
events = monitor.get_events_by_type('context_retrieval')
for event in events:
    print(f"Context retrieval: {event['data']}")
```

## Best Practices

### 1. Configuration Management
- Use environment-specific configurations
- Validate configurations before deployment
- Store configurations in version control
- Use configuration templates for consistency

### 2. Performance Optimization  
- Enable caching for frequently accessed contexts
- Monitor cache hit rates and adjust cache sizes
- Set appropriate performance thresholds
- Use workflow-level caching when possible

### 3. Error Handling
- Always handle both manager failures gracefully
- Implement proper fallback mechanisms
- Monitor error rates and set up alerts
- Log errors with sufficient context for debugging

### 4. Testing
- Test both context managers individually
- Test fallback mechanisms
- Test performance under load
- Test configuration validation

### 5. Monitoring
- Set up performance alerts
- Monitor cache effectiveness
- Track error rates and response times
- Review logs regularly for issues

## Examples

### Complete Integration Example

```python
from agent_s3.tools.context_management.config import setup_enhanced_context_management
from agent_s3.coordinator.context_bridge import OrchestratorContextBridge

# Setup enhanced context management
config = {
    "context_management": {
        "unified_manager": {
            "enabled": True,
            "prefer_new_system": True,
            "enable_deduplication": True,
            "cache_enabled": True
        },
        "monitoring": {
            "enabled": True,
            "log_level": "INFO"
        },
        "orchestrator_integration": {
            "enabled": True
        }
    }
}

# Initialize for coordinator
success = setup_enhanced_context_management(coordinator, config)
if success:
    print("Enhanced context management setup completed")
    
    # Use in workflow
    bridge = OrchestratorContextBridge(
        context_manager=coordinator.unified_context_manager
    )
    
    # Get workflow context
    context = await bridge.get_workflow_context('my_workflow', 'planning')
    
    # Check performance
    metrics = bridge.get_performance_metrics()
    print(f"Context retrieval time: {metrics['avg_response_time']}")
```

This documentation provides comprehensive guidance for implementing and using the Unified Context Management System in the Agent S3 project.
