"""
Tests for the adaptive configuration system.
"""

import os
import unittest
import tempfile
import shutil
import json
from unittest import mock

from agent_s3.tools.context_management.adaptive_config.project_profiler import ProjectProfiler
from agent_s3.tools.context_management.adaptive_config.config_templates import ConfigTemplateManager
from agent_s3.tools.context_management.adaptive_config.metrics_collector import MetricsCollector
from agent_s3.tools.context_management.adaptive_config.adaptive_config_manager import AdaptiveConfigManager
from agent_s3.tools.context_management.adaptive_config.config_explainer import ConfigExplainer


class TestProjectProfiler(unittest.TestCase):
    """Test the ProjectProfiler class."""
    
    def setUp(self):
        """Set up test resources."""
        # Create a temporary directory for test repository
        self.test_repo_dir = tempfile.mkdtemp()
        
        # Create a mock repository structure
        os.makedirs(os.path.join(self.test_repo_dir, "src", "main", "python"))
        os.makedirs(os.path.join(self.test_repo_dir, "src", "test", "python"))
        
        # Create some mock Python files
        with open(os.path.join(self.test_repo_dir, "src", "main", "python", "app.py"), "w") as f:
            f.write("""
            import flask
            from flask import Flask, request

            app = Flask(__name__)

            @app.route('/')
            def index():
                \"\"\"Return the index page.\"\"\"
                return "Hello, World!"

            @app.route('/api/data')
            def get_data():
                \"\"\"Get some data.\"\"\"
                return {"data": "example"}

            if __name__ == '__main__':
                app.run(debug=True)
            """)
            
        with open(os.path.join(self.test_repo_dir, "src", "test", "python", "test_app.py"), "w") as f:
            f.write("""
            import unittest
            from app import app

            class TestApp(unittest.TestCase):
                def test_index(self):
                    \"\"\"Test the index route.\"\"\"
                    client = app.test_client()
                    response = client.get('/')
                    self.assertEqual(response.status_code, 200)
                    
                def test_get_data(self):
                    \"\"\"Test the data API.\"\"\"
                    client = app.test_client()
                    response = client.get('/api/data')
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.json, {"data": "example"})
                    
            if __name__ == '__main__':
                unittest.main()
            """)
    
    def tearDown(self):
        """Clean up test resources."""
        shutil.rmtree(self.test_repo_dir)
    
    def test_analyze_repository(self):
        """Test repository analysis."""
        profiler = ProjectProfiler(self.test_repo_dir)
        repo_metrics = profiler.analyze_repository()
        
        # Basic assertions
        self.assertIsNotNone(repo_metrics)
        self.assertIn("file_stats", repo_metrics)
        self.assertIn("language_stats", repo_metrics)
        
        # Check that Python was detected
        self.assertIn("python", repo_metrics["language_stats"]["language_counts"])
    
    def test_get_recommended_config(self):
        """Test configuration recommendation."""
        profiler = ProjectProfiler(self.test_repo_dir)
        config = profiler.get_recommended_config()
        
        # Basic assertions
        self.assertIsNotNone(config)
        self.assertIn("context_management", config)
        self.assertIn("embedding", config["context_management"])
        self.assertIn("search", config["context_management"])
        self.assertIn("summarization", config["context_management"])
        self.assertIn("importance_scoring", config["context_management"])


class TestConfigTemplateManager(unittest.TestCase):
    """Test the ConfigTemplateManager class."""
    
    def setUp(self):
        """Set up test resources."""
        self.template_manager = ConfigTemplateManager()
    
    def test_get_default_config(self):
        """Test getting the default configuration."""
        config = self.template_manager.get_default_config()
        
        # Basic assertions
        self.assertIsNotNone(config)
        self.assertIn("context_management", config)
    
    def test_get_template(self):
        """Test getting a specific template."""
        config = self.template_manager.get_template("small")
        
        # Basic assertions
        self.assertIsNotNone(config)
        self.assertIn("context_management", config)
        
        # Check specific values for small template
        self.assertEqual(config["context_management"]["embedding"]["chunk_size"], 800)
    
    def test_validate_config(self):
        """Test configuration validation."""
        # Valid configuration
        valid_config = self.template_manager.get_default_config()
        is_valid, errors = self.template_manager.validate_config(valid_config)
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)
        
        # Invalid configuration (missing required field)
        invalid_config = {"context_management": {"search": {}}}
        is_valid, errors = self.template_manager.validate_config(invalid_config)
        self.assertFalse(is_valid)
        self.assertGreater(len(errors), 0)
    
    def test_merge_templates(self):
        """Test template merging."""
        merged = self.template_manager.merge_templates(["default", "small", "python"])
        
        # Basic assertions
        self.assertIsNotNone(merged)
        self.assertIn("context_management", merged)
        
        # Check that values were properly merged
        # Python template should override small template's chunk_size
        self.assertEqual(merged["context_management"]["embedding"]["chunk_size"], 900)
        
        # Small template's overlap should be preserved
        self.assertEqual(merged["context_management"]["embedding"]["chunk_overlap"], 150)
    
    def test_create_config_for_project(self):
        """Test project-specific configuration creation."""
        config = self.template_manager.create_config_for_project(
            project_size="small",
            project_type="web_backend",
            primary_language="python"
        )
        
        # Basic assertions
        self.assertIsNotNone(config)
        self.assertIn("context_management", config)
        
        # Check that Python template takes precedence for chunk size
        self.assertEqual(config["context_management"]["embedding"]["chunk_size"], 900)


class TestMetricsCollector(unittest.TestCase):
    """Test the MetricsCollector class."""
    
    def setUp(self):
        """Set up test resources."""
        # Create a temporary directory for metrics storage
        self.metrics_dir = tempfile.mkdtemp()
        self.metrics_collector = MetricsCollector(self.metrics_dir)
    
    def tearDown(self):
        """Clean up test resources."""
        shutil.rmtree(self.metrics_dir)
    
    def test_log_token_usage(self):
        """Test logging token usage metrics."""
        self.metrics_collector.log_token_usage(
            total_tokens=1000,
            available_tokens=2000,
            allocated_tokens={"code": 800, "comments": 200}
        )
        
        # Get recent metrics
        metrics = self.metrics_collector.get_recent_metrics("token_usage")
        
        # Basic assertions
        self.assertGreater(len(metrics), 0)
        self.assertEqual(metrics[0]["total_tokens"], 1000)
        self.assertEqual(metrics[0]["available_tokens"], 2000)
        self.assertEqual(metrics[0]["utilization_ratio"], 0.5)
    
    def test_log_search_relevance(self):
        """Test logging search relevance metrics."""
        self.metrics_collector.log_search_relevance(
            query="find main function",
            results=[{"id": 1}, {"id": 2}],
            relevance_scores=[0.9, 0.7]
        )
        
        # Get recent metrics
        metrics = self.metrics_collector.get_recent_metrics("search_relevance")
        
        # Basic assertions
        self.assertGreater(len(metrics), 0)
        self.assertEqual(metrics[0]["result_count"], 2)
        self.assertEqual(metrics[0]["top_relevance"], 0.9)
        self.assertEqual(metrics[0]["avg_relevance"], 0.8)
    
    def test_get_metrics_summary(self):
        """Test getting metrics summary."""
        # Log some metrics first
        self.metrics_collector.log_token_usage(
            total_tokens=1000,
            available_tokens=2000,
            allocated_tokens={"code": 800, "comments": 200}
        )
        self.metrics_collector.log_search_relevance(
            query="find main function",
            results=[{"id": 1}, {"id": 2}],
            relevance_scores=[0.9, 0.7]
        )
        
        # Get summary
        summary = self.metrics_collector.get_metrics_summary()
        
        # Basic assertions
        self.assertIn("token_usage", summary)
        self.assertIn("search_relevance", summary)
        self.assertIn("avg_utilization", summary["token_usage"])
        self.assertIn("avg_top_relevance", summary["search_relevance"])
    
    def test_recommend_config_improvements(self):
        """Test configuration improvement recommendations."""
        # Create a test configuration
        config = {
            "context_management": {
                "embedding": {
                    "chunk_size": 1000,
                    "chunk_overlap": 200
                },
                "search": {
                    "bm25": {
                        "k1": 1.2,
                        "b": 0.75
                    }
                },
                "summarization": {
                    "threshold": 2000,
                    "compression_ratio": 0.5
                },
                "importance_scoring": {
                    "code_weight": 1.0,
                    "comment_weight": 0.8
                }
            }
        }
        
        # Log context relevance metrics for this config
        config_hash = hash(json.dumps(config, sort_keys=True))
        self.metrics_collector.log_context_relevance(
            task_type="code_completion",
            relevance_score=0.65,
            config_used=config
        )
        
        # Log token usage metrics
        self.metrics_collector.log_token_usage(
            total_tokens=1900,
            available_tokens=2000,
            allocated_tokens={"code": 1500, "comments": 400}
        )
        
        # Get recommendations
        recommendations = self.metrics_collector.recommend_config_improvements(config)
        
        # Basic assertions
        self.assertIn("status", recommendations)
        
        # Since we only have one data point, should return no_data or have recommendations
        if recommendations["status"] == "success":
            self.assertIn("recommendations", recommendations)
        else:
            self.assertEqual(recommendations["status"], "no_data")


class TestAdaptiveConfigManager(unittest.TestCase):
    """Test the AdaptiveConfigManager class."""
    
    def setUp(self):
        """Set up test resources."""
        # Create a temporary directory for test repository and config
        self.test_repo_dir = tempfile.mkdtemp()
        self.config_dir = os.path.join(self.test_repo_dir, ".agent_s3", "config")
        self.metrics_dir = os.path.join(self.test_repo_dir, ".agent_s3", "metrics")
        
        # Create some mock repository structure (similar to TestProjectProfiler)
        os.makedirs(os.path.join(self.test_repo_dir, "src", "main", "python"))
        
        # Create a mock Python file
        with open(os.path.join(self.test_repo_dir, "src", "main", "python", "app.py"), "w") as f:
            f.write("print('Hello, World!')")
            
        # Initialize the adaptive config manager
        self.config_manager = AdaptiveConfigManager(
            repo_path=self.test_repo_dir,
            config_dir=self.config_dir,
            metrics_dir=self.metrics_dir
        )
    
    def tearDown(self):
        """Clean up test resources."""
        shutil.rmtree(self.test_repo_dir)
    
    def test_initialization(self):
        """Test initialization of the config manager."""
        # Check that directories were created
        self.assertTrue(os.path.exists(self.config_dir))
        self.assertTrue(os.path.exists(self.metrics_dir))
        
        # Check that active config was created
        config = self.config_manager.get_current_config()
        self.assertIsNotNone(config)
        self.assertIn("context_management", config)
    
    def test_update_configuration(self):
        """Test updating the configuration."""
        # Get current config
        current_config = self.config_manager.get_current_config()
        current_version = self.config_manager.get_config_version()
        
        # Create a modified config
        new_config = current_config.copy()
        new_config["context_management"]["embedding"]["chunk_size"] = 800
        
        # Update configuration
        success = self.config_manager.update_configuration(
            new_config=new_config,
            reason="Testing update"
        )
        
        # Basic assertions
        self.assertTrue(success)
        self.assertEqual(self.config_manager.get_config_version(), current_version + 1)
        
        # Check that change was applied
        updated_config = self.config_manager.get_current_config()
        self.assertEqual(updated_config["context_management"]["embedding"]["chunk_size"], 800)
    
    def test_log_metrics(self):
        """Test logging metrics through the config manager."""
        # Log token usage
        self.config_manager.log_token_usage(
            total_tokens=1000,
            available_tokens=2000,
            allocated_tokens={"code": 800, "comments": 200}
        )
        
        # Log context performance
        self.config_manager.log_context_performance(
            task_type="code_completion",
            relevance_score=0.8
        )
        
        # Get performance summary
        summary = self.config_manager.get_performance_summary()
        self.assertIsNotNone(summary)
    
    def test_get_config_history(self):
        """Test getting configuration history."""
        # Update configuration a few times
        current_config = self.config_manager.get_current_config()
        
        for i in range(3):
            new_config = current_config.copy()
            new_config["context_management"]["embedding"]["chunk_size"] = 800 + i * 100
            self.config_manager.update_configuration(
                new_config=new_config,
                reason=f"Update {i+1}"
            )
            
        # Get history
        history = self.config_manager.get_config_history()
        
        # Basic assertions
        self.assertGreaterEqual(len(history), 3)
        self.assertEqual(history[0]["reason"], "Update 3")
        self.assertEqual(history[1]["reason"], "Update 2")
        self.assertEqual(history[2]["reason"], "Update 1")


class TestConfigExplainer(unittest.TestCase):
    """Test the ConfigExplainer class."""
    
    def setUp(self):
        """Set up test resources."""
        self.explainer = ConfigExplainer()
        
        # Create a test configuration
        self.config = {
            "context_management": {
                "embedding": {
                    "chunk_size": 1000,
                    "chunk_overlap": 200
                },
                "search": {
                    "bm25": {
                        "k1": 1.2,
                        "b": 0.75
                    }
                },
                "summarization": {
                    "threshold": 2000,
                    "compression_ratio": 0.5
                },
                "importance_scoring": {
                    "code_weight": 1.0,
                    "comment_weight": 0.8,
                    "metadata_weight": 0.7,
                    "framework_weight": 0.9
                }
            }
        }
    
    def test_explain_config(self):
        """Test configuration explanation."""
        explanation = self.explainer.explain_config(self.config)
        
        # Basic assertions
        self.assertIn("overview", explanation)
        self.assertIn("parameters", explanation)
        self.assertIn("performance_impact", explanation)
        
        # Check that key parameters are explained
        self.assertIn("chunk_size", explanation["parameters"])
        self.assertIn("chunk_overlap", explanation["parameters"])
        self.assertIn("bm25_k1", explanation["parameters"])
        self.assertIn("bm25_b", explanation["parameters"])
        
        # Check that parameter values are included
        self.assertEqual(explanation["parameters"]["chunk_size"]["value"], 1000)
        self.assertEqual(explanation["parameters"]["chunk_overlap"]["value"], 200)
    
    def test_explain_config_change(self):
        """Test configuration change explanation."""
        # Create a modified config
        new_config = {
            "context_management": {
                "embedding": {
                    "chunk_size": 1200,  # Changed
                    "chunk_overlap": 200
                },
                "search": {
                    "bm25": {
                        "k1": 1.5,  # Changed
                        "b": 0.75
                    }
                },
                "summarization": {
                    "threshold": 2000,
                    "compression_ratio": 0.5
                },
                "importance_scoring": {
                    "code_weight": 1.0,
                    "comment_weight": 0.8,
                    "metadata_weight": 0.7,
                    "framework_weight": 0.9
                }
            }
        }
        
        # Get change explanation
        explanation = self.explainer.explain_config_change(self.config, new_config)
        
        # Basic assertions
        self.assertIn("overview", explanation)
        self.assertIn("changes", explanation)
        self.assertIn("impact", explanation)
        
        # Check that changes were detected
        self.assertEqual(len(explanation["changes"]), 2)
        
        # Check specific changes
        changes = {change["parameter"]: change for change in explanation["changes"]}
        self.assertIn("context_management.embedding.chunk_size", changes)
        self.assertIn("context_management.search.bm25.k1", changes)
        
        # Check change values
        self.assertEqual(changes["context_management.embedding.chunk_size"]["old_value"], 1000)
        self.assertEqual(changes["context_management.embedding.chunk_size"]["new_value"], 1200)
    
    def test_get_human_readable_report(self):
        """Test human-readable report generation."""
        # Create a mock AdaptiveConfigManager
        with mock.patch("agent_s3.tools.context_management.adaptive_config.config_explainer.AdaptiveConfigManager") as mock_manager:
            mock_manager.get_current_config.return_value = self.config
            mock_manager.get_config_version.return_value = 1
            mock_manager.get_config_history.return_value = []
            mock_manager.get_performance_summary.return_value = {
                "token_usage": {"avg_utilization": 0.8, "max_utilization": 0.95}
            }
            
            # Create explainer with mock manager
            explainer = ConfigExplainer(mock_manager)
            
            # Get human-readable report
            report = explainer.get_human_readable_report()
            
            # Basic assertions
            self.assertIsNotNone(report)
            self.assertIsInstance(report, str)
            self.assertIn("Context Management Configuration Report", report)


if __name__ == '__main__':
    unittest.main()
