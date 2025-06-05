"""
Context Management Monitoring and Logging Enhancement

This module provides comprehensive monitoring, logging, and analytics for the
context management system to help identify performance issues and optimization opportunities.
"""

import logging
import time
import threading
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict, deque
import json
import os


logger = logging.getLogger(__name__)


@dataclass
class ContextEvent:
    """Represents a context management event for monitoring."""
    timestamp: datetime
    event_type: str  # 'retrieval', 'optimization', 'error', 'cache_hit', 'cache_miss'
    source: str      # 'legacy', 'new', 'unified'
    query: str
    duration: Optional[float] = None
    token_count: Optional[int] = None
    success: bool = True
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ContextMetrics:
    """Aggregated metrics for context management performance."""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    average_response_time: float = 0.0
    total_tokens_processed: int = 0
    cache_hit_rate: float = 0.0
    optimization_count: int = 0
    error_rate: float = 0.0
    peak_response_time: float = 0.0
    requests_per_minute: float = 0.0


class ContextMonitor:
    """
    Comprehensive monitoring system for context management operations.
    
    This class provides:
    - Real-time performance monitoring
    - Event logging and analytics
    - Performance alerting
    - Metrics aggregation and reporting
    """
    
    def __init__(self, 
                 log_level: str = "INFO",
                 max_events: int = 10000,
                 metrics_window: int = 300,  # 5 minutes
                 enable_file_logging: bool = True,
                 log_directory: Optional[str] = None):
        """
        Initialize the context monitor.
        
        Args:
            log_level: Logging level for context events
            max_events: Maximum number of events to keep in memory
            metrics_window: Time window for metrics calculation (seconds)
            enable_file_logging: Whether to log events to files
            log_directory: Directory for log files (defaults to .agent_s3/logs)
        """
        self.log_level = log_level
        self.max_events = max_events
        self.metrics_window = metrics_window
        self.enable_file_logging = enable_file_logging
        
        # Event storage
        self._events: deque = deque(maxlen=max_events)
        self._event_lock = threading.Lock()
        
        # Metrics tracking
        self._metrics_lock = threading.Lock()
        self._request_times: deque = deque()
        self._request_counts: Dict[str, int] = defaultdict(int)
        self._error_counts: Dict[str, int] = defaultdict(int)
        self._token_counts: deque = deque()
        
        # Performance thresholds for alerting
        self.performance_thresholds = {
            'max_response_time': 30.0,  # seconds
            'max_error_rate': 0.1,      # 10%
            'min_cache_hit_rate': 0.5   # 50%
        }
        
        # Alert callbacks
        self._alert_callbacks: List[Callable[[str, Dict[str, Any]], None]] = []
        
        # Setup logging
        self._setup_logging(log_directory)
        
        # Start background metrics calculation
        self._metrics_thread = threading.Thread(target=self._calculate_metrics_loop, daemon=True)
        self._running = True
        self._metrics_thread.start()
        
        logger.info("Context monitoring system initialized")
    
    def _setup_logging(self, log_directory: Optional[str]):
        """Setup file logging for context events."""
        if not self.enable_file_logging:
            return
            
        if log_directory is None:
            log_directory = os.path.join(os.getcwd(), ".agent_s3", "logs")
            
        os.makedirs(log_directory, exist_ok=True)
        
        # Create file handler for context events
        log_file = os.path.join(log_directory, "context_events.log")
        self.file_handler = logging.FileHandler(log_file)
        self.file_handler.setLevel(getattr(logging, self.log_level))
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.file_handler.setFormatter(formatter)
        
        # Add handler to logger
        context_logger = logging.getLogger("agent_s3.context_monitoring")
        context_logger.addHandler(self.file_handler)
        context_logger.setLevel(getattr(logging, self.log_level))
        
        self.context_logger = context_logger
    
    def record_event(self, 
                    event_type: str,
                    source: str,
                    query: str,
                    duration: Optional[float] = None,
                    token_count: Optional[int] = None,
                    success: bool = True,
                    error_message: Optional[str] = None,
                    **metadata):
        """
        Record a context management event.
        
        Args:
            event_type: Type of event ('retrieval', 'optimization', 'error', etc.)
            source: Source of the event ('legacy', 'new', 'unified')
            query: The context query
            duration: How long the operation took (seconds)
            token_count: Number of tokens processed
            success: Whether the operation was successful
            error_message: Error message if unsuccessful
            **metadata: Additional metadata for the event
        """
        event = ContextEvent(
            timestamp=datetime.now(),
            event_type=event_type,
            source=source,
            query=query[:100],  # Truncate long queries
            duration=duration,
            token_count=token_count,
            success=success,
            error_message=error_message,
            metadata=metadata
        )
        
        with self._event_lock:
            self._events.append(event)
        
        # Update metrics tracking
        with self._metrics_lock:
            self._request_counts[event_type] += 1
            if not success:
                self._error_counts[event_type] += 1
            
            if duration is not None:
                self._request_times.append((datetime.now(), duration))
                
            if token_count is not None:
                self._token_counts.append((datetime.now(), token_count))
        
        # Log the event
        if hasattr(self, 'context_logger'):
            log_message = f"{event_type} from {source}: {query[:50]}..."
            if duration is not None:
                log_message += f" (took {duration:.2f}s)"
            if token_count is not None:
                log_message += f" ({token_count} tokens)"
            if not success:
                log_message += f" FAILED: {error_message}"
                
            if success:
                self.context_logger.info(log_message)
            else:
                self.context_logger.error(log_message)
    
    def get_recent_events(self, 
                         event_type: Optional[str] = None,
                         source: Optional[str] = None,
                         limit: int = 100) -> List[ContextEvent]:
        """
        Get recent context events with optional filtering.
        
        Args:
            event_type: Filter by event type
            source: Filter by source
            limit: Maximum number of events to return
            
        Returns:
            List of matching events
        """
        with self._event_lock:
            events = list(self._events)
        
        # Apply filters
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        if source:
            events = [e for e in events if e.source == source]
        
        # Sort by timestamp (most recent first) and limit
        events.sort(key=lambda e: e.timestamp, reverse=True)
        return events[:limit]
    
    def get_current_metrics(self) -> ContextMetrics:
        """
        Get current aggregated metrics.
        
        Returns:
            Current context metrics
        """
        with self._metrics_lock:
            # Calculate metrics for the current window
            now = datetime.now()
            window_start = now - timedelta(seconds=self.metrics_window)
            
            # Filter recent request times
            recent_times = [
                (ts, duration) for ts, duration in self._request_times
                if ts >= window_start
            ]
            
            # Filter recent token counts
            recent_tokens = [
                (ts, count) for ts, count in self._token_counts
                if ts >= window_start
            ]
            
            # Calculate metrics
            total_requests = sum(self._request_counts.values())
            total_errors = sum(self._error_counts.values())
            successful_requests = total_requests - total_errors
            
            avg_response_time = 0.0
            peak_response_time = 0.0
            if recent_times:
                durations = [duration for _, duration in recent_times]
                avg_response_time = sum(durations) / len(durations)
                peak_response_time = max(durations)
            
            total_tokens = sum(count for _, count in recent_tokens)
            
            error_rate = total_errors / total_requests if total_requests > 0 else 0.0
            
            # Calculate requests per minute
            requests_per_minute = len(recent_times) * (60.0 / self.metrics_window)
            
            # Calculate cache hit rate (approximate)
            cache_hits = self._request_counts.get('cache_hit', 0)
            cache_misses = self._request_counts.get('cache_miss', 0)
            cache_hit_rate = cache_hits / (cache_hits + cache_misses) if (cache_hits + cache_misses) > 0 else 0.0
            
            return ContextMetrics(
                total_requests=total_requests,
                successful_requests=successful_requests,
                failed_requests=total_errors,
                average_response_time=avg_response_time,
                total_tokens_processed=total_tokens,
                cache_hit_rate=cache_hit_rate,
                optimization_count=self._request_counts.get('optimization', 0),
                error_rate=error_rate,
                peak_response_time=peak_response_time,
                requests_per_minute=requests_per_minute
            )
    
    def add_alert_callback(self, callback: Callable[[str, Dict[str, Any]], None]):
        """
        Add a callback function to be called when performance alerts are triggered.
        
        Args:
            callback: Function that takes (alert_type, alert_data) as parameters
        """
        self._alert_callbacks.append(callback)
    
    def _calculate_metrics_loop(self):
        """Background thread for calculating metrics and checking alerts."""
        while self._running:
            try:
                metrics = self.get_current_metrics()
                self._check_performance_alerts(metrics)
                time.sleep(30)  # Check every 30 seconds
            except Exception as e:
                logger.error(f"Error in metrics calculation loop: {e}")
                time.sleep(60)  # Wait longer on error
    
    def _check_performance_alerts(self, metrics: ContextMetrics):
        """Check if any performance thresholds are exceeded and trigger alerts."""
        alerts = []
        
        # Check response time
        if metrics.peak_response_time > self.performance_thresholds['max_response_time']:
            alerts.append({
                'type': 'high_response_time',
                'value': metrics.peak_response_time,
                'threshold': self.performance_thresholds['max_response_time'],
                'message': f"Peak response time ({metrics.peak_response_time:.2f}s) exceeds threshold"
            })
        
        # Check error rate
        if metrics.error_rate > self.performance_thresholds['max_error_rate']:
            alerts.append({
                'type': 'high_error_rate',
                'value': metrics.error_rate,
                'threshold': self.performance_thresholds['max_error_rate'],
                'message': f"Error rate ({metrics.error_rate:.1%}) exceeds threshold"
            })
        
        # Check cache hit rate
        if metrics.cache_hit_rate < self.performance_thresholds['min_cache_hit_rate']:
            alerts.append({
                'type': 'low_cache_hit_rate',
                'value': metrics.cache_hit_rate,
                'threshold': self.performance_thresholds['min_cache_hit_rate'],
                'message': f"Cache hit rate ({metrics.cache_hit_rate:.1%}) below threshold"
            })
        
        # Trigger alert callbacks
        for alert in alerts:
            for callback in self._alert_callbacks:
                try:
                    callback(alert['type'], alert)
                except Exception as e:
                    logger.error(f"Error in alert callback: {e}")
    
    def export_metrics_to_file(self, filename: Optional[str] = None) -> str:
        """
        Export current metrics to a JSON file.
        
        Args:
            filename: Output filename (defaults to timestamped file)
            
        Returns:
            Path to the exported file
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"context_metrics_{timestamp}.json"
        
        metrics = self.get_current_metrics()
        recent_events = self.get_recent_events(limit=1000)
        
        data = {
            'export_timestamp': datetime.now().isoformat(),
            'metrics': {
                'total_requests': metrics.total_requests,
                'successful_requests': metrics.successful_requests,
                'failed_requests': metrics.failed_requests,
                'average_response_time': metrics.average_response_time,
                'total_tokens_processed': metrics.total_tokens_processed,
                'cache_hit_rate': metrics.cache_hit_rate,
                'optimization_count': metrics.optimization_count,
                'error_rate': metrics.error_rate,
                'peak_response_time': metrics.peak_response_time,
                'requests_per_minute': metrics.requests_per_minute
            },
            'recent_events': [
                {
                    'timestamp': event.timestamp.isoformat(),
                    'event_type': event.event_type,
                    'source': event.source,
                    'query': event.query,
                    'duration': event.duration,
                    'token_count': event.token_count,
                    'success': event.success,
                    'error_message': event.error_message,
                    'metadata': event.metadata
                }
                for event in recent_events
            ],
            'performance_thresholds': self.performance_thresholds
        }
        
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Metrics exported to {filename}")
        return filename
    
    def shutdown(self):
        """Shutdown the monitoring system."""
        self._running = False
        if self._metrics_thread.is_alive():
            self._metrics_thread.join(timeout=5)
        
        if hasattr(self, 'file_handler'):
            self.file_handler.close()
        
        logger.info("Context monitoring system shut down")


# Global monitor instance
_context_monitor = None


def get_context_monitor() -> ContextMonitor:
    """Get the global context monitor instance."""
    global _context_monitor
    if _context_monitor is None:
        _context_monitor = ContextMonitor()
    return _context_monitor


def reset_context_monitor():
    """Reset the global context monitor instance."""
    global _context_monitor
    if _context_monitor is not None:
        _context_monitor.shutdown()
    _context_monitor = None


# Decorator for monitoring context operations
def monitor_context_operation(operation_type: str, source: str = "unknown"):
    """
    Decorator to automatically monitor context management operations.
    
    Args:
        operation_type: Type of operation being monitored
        source: Source of the operation
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            monitor = get_context_monitor()
            start_time = time.time()
            
            # Extract query from arguments (common patterns)
            query = "unknown"
            if args:
                if isinstance(args[0], str):
                    query = args[0]
                elif len(args) > 1 and isinstance(args[1], str):
                    query = args[1]
            
            if 'query' in kwargs:
                query = kwargs['query']
            elif 'task_description' in kwargs:
                query = kwargs['task_description']
            
            success = True
            error_message = None
            result = None
            
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                error_message = str(e)
                raise
            finally:
                duration = time.time() - start_time
                
                # Estimate token count if result is string
                token_count = None
                if result and isinstance(result, str):
                    token_count = len(result) // 4  # Rough estimation
                
                monitor.record_event(
                    event_type=operation_type,
                    source=source,
                    query=query,
                    duration=duration,
                    token_count=token_count,
                    success=success,
                    error_message=error_message,
                    function_name=func.__name__
                )
        
        return wrapper
    return decorator
