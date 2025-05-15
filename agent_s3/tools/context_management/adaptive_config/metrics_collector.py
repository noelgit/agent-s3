"""
Metrics Collector for Adaptive Configuration.

This module collects and analyzes metrics about context management performance
to guide configuration adjustments.
"""

import time
import logging
import json
import os
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple, Set, Union
from collections import defaultdict, deque
import statistics

logger = logging.getLogger(__name__)


class MetricsCollector:
    """
    Collects and analyzes metrics about context management performance.
    """
    
    def __init__(self, storage_path: Optional[str] = None):
        """
        Initialize the metrics collector.
        
        Args:
            storage_path: Optional path to store metrics data
        """
        self.storage_path = storage_path or ".context_metrics"
        self.current_metrics = {
            "token_usage": [],
            "search_relevance": [],
            "summarization_quality": [],
            "response_latency": [],
            "embedding_latency": [],
            "optimization_duration": [],
            "context_relevance": []
        }
        self.window_size = 50  # Number of data points to keep in memory
        self.last_save_time = time.time()
        self.save_interval = 300  # Save metrics every 5 minutes
        
        # Initialize storage if needed
        self._initialize_storage()
    
    def _initialize_storage(self) -> None:
        """Initialize storage directory for metrics."""
        if not self.storage_path:
            return
            
        try:
            os.makedirs(self.storage_path, exist_ok=True)
        except OSError as e:
            logger.error(f"Failed to create metrics storage directory: {e}")
    
    def log_token_usage(
        self, 
        total_tokens: int, 
        available_tokens: int,
        allocated_tokens: Dict[str, int]
    ) -> None:
        """
        Log token usage metrics.
        
        Args:
            total_tokens: Total tokens used
            available_tokens: Available token budget
            allocated_tokens: Dictionary mapping context sections to token counts
        """
        metric = {
            "timestamp": time.time(),
            "total_tokens": total_tokens,
            "available_tokens": available_tokens,
            "utilization_ratio": total_tokens / available_tokens if available_tokens > 0 else 1.0,
            "allocated_tokens": allocated_tokens
        }
        
        self._add_metric("token_usage", metric)
    
    def log_search_relevance(
        self, 
        query: str, 
        results: List[Dict[str, Any]], 
        relevance_scores: List[float]
    ) -> None:
        """
        Log search relevance metrics.
        
        Args:
            query: Search query
            results: Search results
            relevance_scores: Relevance scores for search results
        """
        if not results or not relevance_scores:
            return
            
        avg_relevance = sum(relevance_scores) / len(relevance_scores) if relevance_scores else 0
        
        metric = {
            "timestamp": time.time(),
            "query_length": len(query),
            "result_count": len(results),
            "top_relevance": relevance_scores[0] if relevance_scores else 0,
            "avg_relevance": avg_relevance
        }
        
        self._add_metric("search_relevance", metric)
    
    def log_summarization_quality(
        self,
        original_length: int,
        summary_length: int, 
        compression_ratio: float,
        quality_score: Optional[float] = None
    ) -> None:
        """
        Log summarization quality metrics.
        
        Args:
            original_length: Length of original text
            summary_length: Length of summary
            compression_ratio: Compression ratio achieved
            quality_score: Optional quality score (0-1)
        """
        metric = {
            "timestamp": time.time(),
            "original_length": original_length,
            "summary_length": summary_length,
            "compression_ratio": compression_ratio,
            "quality_score": quality_score
        }
        
        self._add_metric("summarization_quality", metric)
    
    def log_response_latency(self, operation: str, latency_ms: float) -> None:
        """
        Log response latency metrics.
        
        Args:
            operation: Operation type
            latency_ms: Latency in milliseconds
        """
        metric = {
            "timestamp": time.time(),
            "operation": operation,
            "latency_ms": latency_ms
        }
        
        self._add_metric("response_latency", metric)
    
    def log_embedding_latency(self, document_length: int, latency_ms: float) -> None:
        """
        Log embedding generation latency metrics.
        
        Args:
            document_length: Document length in characters
            latency_ms: Latency in milliseconds
        """
        metric = {
            "timestamp": time.time(),
            "document_length": document_length,
            "latency_ms": latency_ms,
            "chars_per_ms": document_length / latency_ms if latency_ms > 0 else 0
        }
        
        self._add_metric("embedding_latency", metric)
    
    def log_optimization_duration(self, duration_ms: float, context_size: int) -> None:
        """
        Log context optimization duration metrics.
        
        Args:
            duration_ms: Duration in milliseconds
            context_size: Size of context in tokens
        """
        metric = {
            "timestamp": time.time(),
            "duration_ms": duration_ms,
            "context_size": context_size,
            "tokens_per_ms": context_size / duration_ms if duration_ms > 0 else 0
        }
        
        self._add_metric("optimization_duration", metric)
    
    def log_context_relevance(
        self, 
        task_type: str, 
        relevance_score: float,
        config_used: Dict[str, Any]
    ) -> None:
        """
        Log context relevance metrics.
        
        Args:
            task_type: Type of task
            relevance_score: Relevance score (0-1)
            config_used: Configuration used for context management
        """
        metric = {
            "timestamp": time.time(),
            "task_type": task_type,
            "relevance_score": relevance_score,
            "config_hash": hash(json.dumps(config_used, sort_keys=True)),
            "config_params": {
                "chunk_size": config_used.get("context_management", {}).get("embedding", {}).get("chunk_size", None),
                "chunk_overlap": config_used.get("context_management", {}).get("embedding", {}).get("chunk_overlap", None),
                "bm25_k1": config_used.get("context_management", {}).get("search", {}).get("bm25", {}).get("k1", None),
                "bm25_b": config_used.get("context_management", {}).get("search", {}).get("bm25", {}).get("b", None)
            }
        }
        
        self._add_metric("context_relevance", metric)
    
    def _add_metric(self, metric_type: str, data: Dict[str, Any]) -> None:
        """
        Add a metric to the current metrics collection.
        
        Args:
            metric_type: Type of metric
            data: Metric data
        """
        if metric_type not in self.current_metrics:
            self.current_metrics[metric_type] = []
            
        # Add to current metrics, limiting to window size
        self.current_metrics[metric_type].append(data)
        if len(self.current_metrics[metric_type]) > self.window_size:
            self.current_metrics[metric_type] = self.current_metrics[metric_type][-self.window_size:]
            
        # Check if it's time to save metrics
        current_time = time.time()
        if current_time - self.last_save_time >= self.save_interval:
            self._save_metrics()
            self.last_save_time = current_time
    
    def _save_metrics(self) -> None:
        """Save current metrics to storage."""
        if not self.storage_path:
            return
            
        try:
            # Create a timestamped metrics file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = os.path.join(self.storage_path, f"metrics_{timestamp}.json")
            
            with open(filename, 'w') as f:
                json.dump(self.current_metrics, f)
                
            logger.debug(f"Saved metrics to {filename}")
            
            # Clean up old metrics files
            self._cleanup_old_metrics()
        except Exception as e:
            logger.error(f"Failed to save metrics: {e}")
    
    def _cleanup_old_metrics(self) -> None:
        """Clean up old metrics files."""
        if not self.storage_path:
            return
            
        try:
            cutoff_time = time.time() - (7 * 24 * 60 * 60)  # One week ago
            
            for filename in os.listdir(self.storage_path):
                if not filename.startswith("metrics_"):
                    continue
                    
                file_path = os.path.join(self.storage_path, filename)
                if os.path.getmtime(file_path) < cutoff_time:
                    os.remove(file_path)
                    logger.debug(f"Removed old metrics file: {filename}")
        except Exception as e:
            logger.error(f"Error cleaning up old metrics files: {e}")
    
    def get_recent_metrics(self, metric_type: str, count: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent metrics of a specific type.
        
        Args:
            metric_type: Type of metrics to get
            count: Number of recent metrics to return
            
        Returns:
            List of recent metric data
        """
        if metric_type not in self.current_metrics:
            return []
            
        metrics = self.current_metrics[metric_type]
        return metrics[-count:] if metrics else []
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """
        Get a summary of all metrics.
        
        Returns:
            Dictionary with summary statistics for each metric type
        """
        summary = {}
        
        for metric_type, metrics in self.current_metrics.items():
            if not metrics:
                continue
                
            summary[metric_type] = self._calculate_summary_for_metric(metric_type, metrics)
                
        return summary
    
    def _calculate_summary_for_metric(
        self, 
        metric_type: str, 
        metrics: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Calculate summary statistics for a specific metric type.
        
        Args:
            metric_type: Type of metric
            metrics: List of metric data
            
        Returns:
            Summary statistics
        """
        if not metrics:
            return {}
            
        result = {
            "count": len(metrics),
            "latest_timestamp": max(m.get("timestamp", 0) for m in metrics)
        }
        
        if metric_type == "token_usage":
            utilization = [m.get("utilization_ratio", 0) for m in metrics]
            result.update({
                "avg_utilization": statistics.mean(utilization) if utilization else 0,
                "max_utilization": max(utilization) if utilization else 0,
                "min_utilization": min(utilization) if utilization else 0
            })
            
        elif metric_type == "search_relevance":
            top_relevance = [m.get("top_relevance", 0) for m in metrics]
            avg_relevance = [m.get("avg_relevance", 0) for m in metrics]
            result.update({
                "avg_top_relevance": statistics.mean(top_relevance) if top_relevance else 0,
                "avg_overall_relevance": statistics.mean(avg_relevance) if avg_relevance else 0
            })
            
        elif metric_type == "summarization_quality":
            quality_scores = [m.get("quality_score", 0) for m in metrics if m.get("quality_score") is not None]
            compression_ratios = [m.get("compression_ratio", 0) for m in metrics]
            result.update({
                "avg_quality": statistics.mean(quality_scores) if quality_scores else 0,
                "avg_compression_ratio": statistics.mean(compression_ratios) if compression_ratios else 0
            })
            
        elif metric_type == "response_latency":
            latencies = [m.get("latency_ms", 0) for m in metrics]
            result.update({
                "avg_latency_ms": statistics.mean(latencies) if latencies else 0,
                "median_latency_ms": statistics.median(latencies) if latencies else 0,
                "max_latency_ms": max(latencies) if latencies else 0
            })
            
        elif metric_type == "embedding_latency":
            latencies = [m.get("latency_ms", 0) for m in metrics]
            throughputs = [m.get("chars_per_ms", 0) for m in metrics]
            result.update({
                "avg_latency_ms": statistics.mean(latencies) if latencies else 0,
                "avg_throughput": statistics.mean(throughputs) if throughputs else 0
            })
            
        elif metric_type == "optimization_duration":
            durations = [m.get("duration_ms", 0) for m in metrics]
            throughputs = [m.get("tokens_per_ms", 0) for m in metrics]
            result.update({
                "avg_duration_ms": statistics.mean(durations) if durations else 0,
                "avg_throughput": statistics.mean(throughputs) if throughputs else 0
            })
            
        elif metric_type == "context_relevance":
            relevance_scores = [m.get("relevance_score", 0) for m in metrics]
            by_task_type = defaultdict(list)
            for m in metrics:
                task_type = m.get("task_type", "unknown")
                score = m.get("relevance_score", 0)
                by_task_type[task_type].append(score)
                
            result.update({
                "avg_relevance": statistics.mean(relevance_scores) if relevance_scores else 0,
                "by_task_type": {
                    task_type: statistics.mean(scores) if scores else 0
                    for task_type, scores in by_task_type.items()
                }
            })
            
        return result
    
    def analyze_config_performance(
        self,
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Analyze how well a specific configuration performs.
        
        Args:
            config: Configuration to analyze
            
        Returns:
            Dictionary with performance metrics for this configuration
        """
        config_hash = hash(json.dumps(config, sort_keys=True))
        
        # Get context relevance metrics for this config
        relevance_metrics = [
            m for m in self.current_metrics.get("context_relevance", [])
            if m.get("config_hash") == config_hash
        ]
        
        if not relevance_metrics:
            return {
                "status": "no_data",
                "message": "No data available for this configuration"
            }
            
        # Calculate performance metrics
        relevance_scores = [m.get("relevance_score", 0) for m in relevance_metrics]
        by_task_type = defaultdict(list)
        
        for m in relevance_metrics:
            task_type = m.get("task_type", "unknown")
            score = m.get("relevance_score", 0)
            by_task_type[task_type].append(score)
            
        return {
            "status": "success",
            "sample_count": len(relevance_metrics),
            "avg_relevance": statistics.mean(relevance_scores) if relevance_scores else 0,
            "by_task_type": {
                task_type: {
                    "avg_relevance": statistics.mean(scores) if scores else 0,
                    "count": len(scores)
                }
                for task_type, scores in by_task_type.items()
            },
            "first_seen": min(m.get("timestamp", 0) for m in relevance_metrics),
            "last_seen": max(m.get("timestamp", 0) for m in relevance_metrics)
        }
    
    def recommend_config_improvements(
        self,
        current_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Recommend potential improvements to the current configuration.
        
        Args:
            current_config: Current configuration
            
        Returns:
            Dictionary with recommended improvements
        """
        current_performance = self.analyze_config_performance(current_config)
        if current_performance.get("status") == "no_data":
            return {
                "status": "no_data",
                "message": "Insufficient data to recommend improvements",
                "recommendations": []
            }
            
        # Analyze different aspects of performance
        recommendations = []
        
        # Check context relevance
        overall_relevance = current_performance.get("avg_relevance", 0)
        if overall_relevance < 0.7:
            recommendations.append({
                "aspect": "context_relevance",
                "current_value": overall_relevance,
                "recommendation": "Increase chunk overlap to improve context continuity",
                "suggested_change": {
                    "parameter": "context_management.embedding.chunk_overlap",
                    "current_value": current_config.get("context_management", {}).get("embedding", {}).get("chunk_overlap", 200),
                    "suggested_value": int(current_config.get("context_management", {}).get("embedding", {}).get("chunk_overlap", 200) * 1.2)
                },
                "confidence": "medium"
            })
            
        # Check token utilization from metrics
        token_metrics = self.get_recent_metrics("token_usage", 20)
        if token_metrics:
            utilization = [m.get("utilization_ratio", 0) for m in token_metrics]
            avg_utilization = statistics.mean(utilization) if utilization else 0
            
            if avg_utilization > 0.95:
                # We're using almost all available tokens
                recommendations.append({
                    "aspect": "token_utilization",
                    "current_value": avg_utilization,
                    "recommendation": "Increase summarization threshold to reduce context pressure",
                    "suggested_change": {
                        "parameter": "context_management.summarization.threshold",
                        "current_value": current_config.get("context_management", {}).get("summarization", {}).get("threshold", 2000),
                        "suggested_value": int(current_config.get("context_management", {}).get("summarization", {}).get("threshold", 2000) * 1.2)
                    },
                    "confidence": "high"
                })
            elif avg_utilization < 0.6:
                # We're using significantly fewer tokens than available
                recommendations.append({
                    "aspect": "token_utilization",
                    "current_value": avg_utilization,
                    "recommendation": "Decrease chunk size to optimize token usage",
                    "suggested_change": {
                        "parameter": "context_management.embedding.chunk_size",
                        "current_value": current_config.get("context_management", {}).get("embedding", {}).get("chunk_size", 1000),
                        "suggested_value": int(current_config.get("context_management", {}).get("embedding", {}).get("chunk_size", 1000) * 0.9)
                    },
                    "confidence": "medium"
                })
                
        # Check search relevance
        search_metrics = self.get_recent_metrics("search_relevance", 20)
        if search_metrics:
            top_relevance = [m.get("top_relevance", 0) for m in search_metrics]
            avg_top_relevance = statistics.mean(top_relevance) if top_relevance else 0
            
            if avg_top_relevance < 0.7:
                recommendations.append({
                    "aspect": "search_relevance",
                    "current_value": avg_top_relevance,
                    "recommendation": "Adjust BM25 parameters to improve search relevance",
                    "suggested_change": {
                        "parameter": "context_management.search.bm25.k1",
                        "current_value": current_config.get("context_management", {}).get("search", {}).get("bm25", {}).get("k1", 1.2),
                        "suggested_value": current_config.get("context_management", {}).get("search", {}).get("bm25", {}).get("k1", 1.2) + 0.2
                    },
                    "confidence": "medium"
                })
                
        # Check task-specific performance
        if "by_task_type" in current_performance:
            for task_type, stats in current_performance["by_task_type"].items():
                if stats.get("avg_relevance", 0) < 0.65 and stats.get("count", 0) >= 5:
                    recommendations.append({
                        "aspect": f"task_relevance_{task_type}",
                        "current_value": stats.get("avg_relevance", 0),
                        "recommendation": f"Adjust importance weights for {task_type} tasks",
                        "suggested_change": {
                            "parameter": f"context_management.importance_scoring.code_weight",
                            "current_value": current_config.get("context_management", {}).get("importance_scoring", {}).get("code_weight", 1.0),
                            "suggested_value": current_config.get("context_management", {}).get("importance_scoring", {}).get("code_weight", 1.0) * 1.1
                        },
                        "confidence": "medium"
                    })
                    
        return {
            "status": "success",
            "current_performance": current_performance,
            "recommendations": recommendations,
            "general_assessment": "good" if overall_relevance > 0.8 else "needs_improvement"
        }
    
    def load_historical_metrics(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Load historical metrics from storage.
        
        Returns:
            Dictionary with historical metrics
        """
        if not self.storage_path or not os.path.exists(self.storage_path):
            return {}
            
        try:
            historical = defaultdict(list)
            
            for filename in os.listdir(self.storage_path):
                if not filename.startswith("metrics_"):
                    continue
                    
                file_path = os.path.join(self.storage_path, filename)
                with open(file_path, 'r') as f:
                    metrics = json.load(f)
                    
                    for metric_type, data in metrics.items():
                        historical[metric_type].extend(data)
                        
            return dict(historical)
        except Exception as e:
            logger.error(f"Failed to load historical metrics: {e}")
            return {}
    
    def calculate_trend(self, metric_type: str, value_field: str) -> Dict[str, Any]:
        """
        Calculate trend for a specific metric field.
        
        Args:
            metric_type: Type of metric
            value_field: Field to analyze trend for
            
        Returns:
            Dictionary with trend information
        """
        metrics = self.current_metrics.get(metric_type, [])
        if not metrics or len(metrics) < 5:
            return {
                "status": "insufficient_data",
                "message": "Not enough data to calculate trend"
            }
            
        # Extract values and timestamps
        values = []
        timestamps = []
        
        for m in metrics:
            if value_field in m and m.get("timestamp"):
                values.append(m[value_field])
                timestamps.append(m["timestamp"])
                
        if not values or len(values) < 5:
            return {
                "status": "insufficient_data",
                "message": f"Field {value_field} not found in enough metrics"
            }
            
        # Calculate statistics
        earliest = min(timestamps)
        latest = max(timestamps)
        
        if latest - earliest < 3600:  # At least one hour of data
            return {
                "status": "insufficient_time_range",
                "message": "Not enough time range to calculate meaningful trend"
            }
            
        # Sort values by timestamp
        sorted_values = [v for _, v in sorted(zip(timestamps, values))]
        
        # Calculate first half and second half averages
        mid_point = len(sorted_values) // 2
        first_half = sorted_values[:mid_point]
        second_half = sorted_values[mid_point:]
        
        first_avg = statistics.mean(first_half) if first_half else 0
        second_avg = statistics.mean(second_half) if second_half else 0
        
        # Calculate trend
        if first_avg == 0:
            percent_change = 100 if second_avg > 0 else 0
        else:
            percent_change = ((second_avg - first_avg) / first_avg) * 100
            
        # Determine trend direction
        if abs(percent_change) < 5:
            direction = "stable"
        elif percent_change > 0:
            direction = "improving" if value_field in ["relevance_score", "top_relevance", "quality_score"] else "increasing"
        else:
            direction = "declining" if value_field in ["relevance_score", "top_relevance", "quality_score"] else "decreasing"
            
        return {
            "status": "success",
            "metric_type": metric_type,
            "field": value_field,
            "trend_direction": direction,
            "percent_change": percent_change,
            "first_half_avg": first_avg,
            "second_half_avg": second_avg,
            "earliest_time": earliest,
            "latest_time": latest,
            "data_points": len(sorted_values)
        }
