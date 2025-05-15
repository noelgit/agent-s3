"""
Project Profiler for Adaptive Configuration.

This module analyzes the characteristics of a code repository to determine
optimal context management configuration parameters.
"""

import os
import glob
import logging
from collections import Counter, defaultdict
from typing import Dict, List, Any, Optional, Set, Tuple
import re
import math

from agent_s3.tools.context_management.token_budget import EXTENSION_TO_LANGUAGE

logger = logging.getLogger(__name__)

# Common framework detection patterns
FRAMEWORK_PATTERNS = {
    "python": {
        "django": [r'django', r'urls\.py', r'views\.py', r'models\.py', r'apps\.py'],
        "flask": [r'flask', r'@app\.route', r'Flask\s*\('],
        "fastapi": [r'fastapi', r'@app\.get', r'@app\.post'],
        "pytorch": [r'torch\.nn', r'torch\.optim'],
        "tensorflow": [r'tensorflow', r'tf\.keras', r'tf\.data'],
        "pytest": [r'pytest', r'@pytest', r'test_.*\.py'],
    },
    "javascript": {
        "react": [r'react', r'React', r'useState', r'useEffect'],
        "vue": [r'vue', r'Vue', r'createApp', r'setup\(\)'],
        "angular": [r'angular', r'@Component', r'NgModule'],
        "express": [r'express', r'app\.get', r'app\.post', r'app\.use'],
        "next.js": [r'next/router', r'getServerSideProps', r'getStaticProps'],
    },
    "typescript": {
        "react": [r'React', r'useState', r'useEffect'],
        "angular": [r'@Component', r'NgModule', r'Injectable'],
        "nest": [r'@nestjs', r'@Controller', r'@Module'],
        "next.js": [r'next/router', r'GetServerSideProps', r'GetStaticProps'],
    }
}

# Project type classification criteria
PROJECT_TYPE_CRITERIA = {
    "web_frontend": {
        "file_patterns": [r'index\.html', r'styles?\.css', r'package\.json'],
        "frameworks": ["react", "vue", "angular", "next.js"],
        "directory_patterns": ["components", "pages", "views", "public", "static"]
    },
    "web_backend": {
        "file_patterns": [r'server\.js', r'app\.py', r'urls\.py', r'routes\.'],
        "frameworks": ["django", "flask", "express", "fastapi", "nest"],
        "directory_patterns": ["routes", "controllers", "models", "api"]
    },
    "data_science": {
        "file_patterns": [r'\.ipynb$', r'data_processing', r'model\.py', r'train\.py'],
        "frameworks": ["pytorch", "tensorflow", "pandas", "scikit-learn"],
        "directory_patterns": ["data", "models", "notebooks", "experiments"]
    },
    "cli_tool": {
        "file_patterns": [r'cli\.py', r'main\.py', r'bin/', r'command'],
        "frameworks": ["click", "argparse", "commander"],
        "directory_patterns": ["commands", "cli"]
    },
    "library": {
        "file_patterns": [r'setup\.py', r'package\.json', r'Cargo\.toml', r'README\.md'],
        "frameworks": [],  # Libraries often don't use specific frameworks
        "directory_patterns": ["src", "lib", "test", "docs", "examples"]
    },
}


class ProjectProfiler:
    """
    Analyzes code repository characteristics to determine optimal configuration
    settings for context management.
    """
    
    def __init__(self, repo_path: str):
        """
        Initialize the project profiler with a repository path.
        
        Args:
            repo_path: Path to the code repository
        """
        self.repo_path = repo_path
        self.file_stats = {}
        self.language_stats = {}
        self.framework_stats = {}
        self.project_type = None
        self.project_size = None
        self.directory_structure = {}
        self.repo_metrics = {}
        self._content_samples = {}
        
    def analyze_repository(self) -> Dict[str, Any]:
        """
        Perform a comprehensive analysis of the repository.
        
        Returns:
            Dictionary containing repository metrics and characteristics
        """
        logger.info(f"Analyzing repository at {self.repo_path}")
        
        # Gather basic repository metrics
        self._gather_file_statistics()
        self._detect_languages()
        self._analyze_directory_structure()
        self._detect_frameworks()
        self._determine_project_type()
        self._calculate_code_density()
        
        # Compile all metrics into a single report
        self.repo_metrics = {
            "file_stats": self.file_stats,
            "language_stats": self.language_stats,
            "framework_stats": self.framework_stats,
            "project_type": self.project_type,
            "project_size": self.project_size,
            "directory_structure": self.directory_structure,
            "code_density": self.file_stats.get("code_density", {}),
        }
        
        logger.info(f"Repository analysis complete: {self.project_type} project with "
                  f"primary language {self.get_primary_language()}")
        
        return self.repo_metrics
    
    def get_recommended_config(self) -> Dict[str, Any]:
        """
        Get recommended configuration settings based on repository analysis.
        
        Returns:
            Dictionary with recommended configuration parameters
        """
        # Ensure we have analysis results
        if not self.repo_metrics:
            self.analyze_repository()
        
        # Base configuration
        config = {
            "context_management": {
                "enabled": True,
                "background_enabled": True,
                "optimization_interval": 60,
                "embedding": {
                    "chunk_size": 1000,
                    "chunk_overlap": 200,
                },
                "search": {
                    "bm25": {
                        "k1": 1.2, 
                        "b": 0.75
                    },
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
        
        # Adjust configuration based on project type
        self._adjust_config_for_project_type(config)
        
        # Adjust configuration based on project size
        self._adjust_config_for_project_size(config)
        
        # Adjust configuration based on language
        self._adjust_config_for_language(config)
        
        # Adjust configuration based on code density
        self._adjust_config_for_code_density(config)
        
        return config
    
    def _gather_file_statistics(self) -> None:
        """Gather statistics about files in the repository."""
        file_count = 0
        total_size = 0
        extension_counts = Counter()
        size_by_extension = defaultdict(int)
        
        # Ignore common directories that don't contain source code
        ignore_patterns = [
            ".git", "__pycache__", "node_modules", "venv", 
            "build", "dist", ".vscode", ".idea"
        ]
        ignore_dirs = set()
        
        for root, dirs, files in os.walk(self.repo_path):
            # Filter out directories to ignore
            dirs[:] = [d for d in dirs if d not in ignore_patterns]
            
            for file in files:
                file_path = os.path.join(root, file)
                
                # Skip if file is in an ignored directory
                if any(ignored in file_path for ignored in ignore_dirs):
                    continue
                
                # Skip binary files and very large files
                try:
                    if os.path.getsize(file_path) > 10 * 1024 * 1024:  # Skip files larger than 10MB
                        continue
                        
                    _, ext = os.path.splitext(file)
                    ext = ext.lower()
                    
                    file_size = os.path.getsize(file_path)
                    file_count += 1
                    total_size += file_size
                    extension_counts[ext] += 1
                    size_by_extension[ext] += file_size
                    
                except OSError:
                    continue
        
        # Calculate average file size by extension
        avg_size_by_extension = {
            ext: size_by_extension[ext] / count 
            for ext, count in extension_counts.items() 
            if count > 0
        }
        
        # Calculate project size category
        if file_count < 100:
            project_size = "small"
        elif file_count < 1000:
            project_size = "medium"
        else:
            project_size = "large"
        
        self.file_stats = {
            "file_count": file_count,
            "total_size": total_size,
            "avg_file_size": total_size / file_count if file_count > 0 else 0,
            "extension_counts": dict(extension_counts),
            "avg_size_by_extension": avg_size_by_extension
        }
        
        self.project_size = project_size
    
    def _detect_languages(self) -> None:
        """Detect programming languages used in the repository."""
        if not self.file_stats:
            self._gather_file_statistics()
            
        language_counts = Counter()
        language_sizes = defaultdict(int)
        
        # Map file extensions to languages
        for ext, count in self.file_stats["extension_counts"].items():
            language = EXTENSION_TO_LANGUAGE.get(ext, "unknown")
            if language != "unknown":
                language_counts[language] += count
                language_sizes[language] += self.file_stats["avg_size_by_extension"].get(ext, 0) * count
        
        # Calculate language percentages by file count
        total_files = sum(language_counts.values())
        language_percentages = {
            lang: count / total_files * 100 
            for lang, count in language_counts.items()
        } if total_files > 0 else {}
        
        # Calculate language percentages by file size
        total_size = sum(language_sizes.values())
        language_size_percentages = {
            lang: size / total_size * 100 
            for lang, size in language_sizes.items()
        } if total_size > 0 else {}
        
        self.language_stats = {
            "language_counts": dict(language_counts),
            "language_percentages": language_percentages,
            "language_size_percentages": language_size_percentages,
            "primary_language": language_counts.most_common(1)[0][0] if language_counts else "unknown"
        }
    
    def _get_content_sample(self, language: str) -> List[str]:
        """
        Get a sample of file content for a specific language.
        
        Args:
            language: The programming language
            
        Returns:
            List of file content samples for the specified language
        """
        if language in self._content_samples:
            return self._content_samples[language]
            
        samples = []
        sample_count = 0
        max_samples = 10
        
        for ext, lang in EXTENSION_TO_LANGUAGE.items():
            if lang != language:
                continue
                
            # Find files with this extension
            for root, _, files in os.walk(self.repo_path):
                for file in files:
                    if not file.endswith(ext):
                        continue
                        
                    file_path = os.path.join(root, file)
                    try:
                        # Only read the first 50KB to avoid large files
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read(50 * 1024)
                            samples.append(content)
                            sample_count += 1
                            
                            if sample_count >= max_samples:
                                self._content_samples[language] = samples
                                return samples
                    except Exception:
                        continue
        
        self._content_samples[language] = samples
        return samples
    
    def _detect_frameworks(self) -> None:
        """Detect frameworks used in the repository."""
        if not self.language_stats:
            self._detect_languages()
            
        framework_scores = defaultdict(float)
        
        # Check for framework patterns in each language
        for language, percentage in self.language_stats["language_percentages"].items():
            if percentage < 5:  # Skip languages with less than 5% usage
                continue
                
            if language not in FRAMEWORK_PATTERNS:
                continue
                
            # Get content samples for this language
            samples = self._get_content_sample(language)
            if not samples:
                continue
                
            # Check each framework's patterns
            for framework, patterns in FRAMEWORK_PATTERNS[language].items():
                framework_key = f"{language}.{framework}"
                score = 0
                
                # Check for framework patterns in content samples
                for sample in samples:
                    for pattern in patterns:
                        matches = re.findall(pattern, sample, re.IGNORECASE)
                        if matches:
                            score += len(matches) * 0.5
                
                # Check for framework files and directories
                for pattern in patterns:
                    matching_files = glob.glob(f"{self.repo_path}/**/*{pattern}*", recursive=True)
                    score += len(matching_files)
                    
                if score > 0:
                    framework_scores[framework_key] = score
        
        # Normalize scores
        total_score = sum(framework_scores.values()) or 1
        framework_percentages = {
            framework: (score / total_score) * 100
            for framework, score in framework_scores.items()
        }
        
        self.framework_stats = {
            "detected_frameworks": {
                k: v for k, v in framework_scores.items() if v > 0
            },
            "framework_percentages": framework_percentages
        }
    
    def _analyze_directory_structure(self) -> None:
        """Analyze the repository directory structure."""
        dirs = defaultdict(int)
        dir_depths = []
        
        for root, directories, files in os.walk(self.repo_path):
            # Calculate depth from repo root
            rel_path = os.path.relpath(root, self.repo_path)
            if rel_path == '.':
                depth = 0
            else:
                depth = rel_path.count(os.sep) + 1
                
            dir_depths.append(depth)
            
            # Count directories at each level
            for directory in directories:
                dirs[directory.lower()] += 1
        
        self.directory_structure = {
            "common_directories": {k: v for k, v in sorted(dirs.items(), key=lambda x: x[1], reverse=True)[:20]},
            "max_depth": max(dir_depths) if dir_depths else 0,
            "avg_depth": sum(dir_depths) / len(dir_depths) if dir_depths else 0
        }
    
    def _determine_project_type(self) -> None:
        """Determine the type of project based on files and frameworks."""
        if not self.framework_stats or not self.directory_structure:
            self._detect_frameworks()
            self._analyze_directory_structure()
        
        scores = defaultdict(float)
        
        # Score based on file patterns
        for project_type, criteria in PROJECT_TYPE_CRITERIA.items():
            # Check file patterns
            for pattern in criteria["file_patterns"]:
                matching_files = glob.glob(f"{self.repo_path}/**/{pattern}", recursive=True)
                scores[project_type] += len(matching_files) * 2
            
            # Check frameworks
            detected_frameworks = set(self.framework_stats.get("detected_frameworks", {}).keys())
            for framework in criteria["frameworks"]:
                for detected in detected_frameworks:
                    if framework in detected.lower():
                        scores[project_type] += 5
            
            # Check directory patterns
            common_dirs = set(self.directory_structure["common_directories"].keys())
            for dir_pattern in criteria["directory_patterns"]:
                for common_dir in common_dirs:
                    if dir_pattern in common_dir:
                        scores[project_type] += 3
        
        # Determine the most likely project type
        if scores:
            self.project_type = max(scores.items(), key=lambda x: x[1])[0]
        else:
            self.project_type = "unknown"
    
    def _calculate_code_density(self) -> None:
        """Calculate code density metrics for the repository."""
        language_density = {}
        
        # Calculate density for each major language
        for language, percentage in self.language_stats.get("language_percentages", {}).items():
            if percentage < 5:  # Skip languages with less than 5% usage
                continue
                
            samples = self._get_content_sample(language)
            if not samples:
                continue
                
            # Calculate metrics
            total_lines = 0
            total_chars = 0
            total_empty_lines = 0
            total_comment_lines = 0
            
            comment_patterns = {
                "python": r'^\s*#.*$',
                "javascript": r'^\s*(//.*)$|^\s*/\*[\s\S]*?\*/',
                "typescript": r'^\s*(//.*)$|^\s*/\*[\s\S]*?\*/',
                "java": r'^\s*(//.*)$|^\s*/\*[\s\S]*?\*/',
                "csharp": r'^\s*(//.*)$|^\s*/\*[\s\S]*?\*/',
            }
            
            comment_pattern = comment_patterns.get(language, r'^\s*#.*$')
            
            for sample in samples:
                lines = sample.split('\n')
                total_lines += len(lines)
                total_chars += len(sample)
                
                for line in lines:
                    if not line.strip():
                        total_empty_lines += 1
                    elif re.match(comment_pattern, line):
                        total_comment_lines += 1
            
            if total_lines > 0:
                language_density[language] = {
                    "avg_line_length": total_chars / total_lines,
                    "empty_line_ratio": total_empty_lines / total_lines,
                    "comment_ratio": total_comment_lines / total_lines,
                    "code_density_score": (total_lines - total_empty_lines - total_comment_lines) / total_lines
                }
        
        self.file_stats["code_density"] = language_density
    
    def get_primary_language(self) -> str:
        """Get the primary programming language used in the repository."""
        if not self.language_stats:
            self._detect_languages()
            
        return self.language_stats.get("primary_language", "unknown")
    
    def _adjust_config_for_project_type(self, config: Dict[str, Any]) -> None:
        """
        Adjust configuration based on detected project type.
        
        Args:
            config: Configuration dictionary to adjust
        """
        cm_config = config["context_management"]
        
        if self.project_type == "web_frontend":
            # Frontend projects often benefit from smaller chunks with more overlap
            cm_config["embedding"]["chunk_size"] = 800
            cm_config["embedding"]["chunk_overlap"] = 250
            cm_config["importance_scoring"]["code_weight"] = 1.1
            cm_config["importance_scoring"]["framework_weight"] = 1.2
            
        elif self.project_type == "web_backend":
            # Backend projects often have more structured code
            cm_config["embedding"]["chunk_size"] = 1200
            cm_config["search"]["bm25"]["k1"] = 1.5  # Higher k1 for more term frequency impact
            cm_config["importance_scoring"]["code_weight"] = 1.2
            
        elif self.project_type == "data_science":
            # Data science projects often have notebooks and data processing code
            cm_config["embedding"]["chunk_size"] = 1500
            cm_config["embedding"]["chunk_overlap"] = 300
            cm_config["importance_scoring"]["comment_weight"] = 1.0  # Comments often contain important explanations
            
        elif self.project_type == "cli_tool":
            # CLI tools often have simpler structure
            cm_config["embedding"]["chunk_size"] = 900
            cm_config["importance_scoring"]["code_weight"] = 1.3
            
        elif self.project_type == "library":
            # Libraries often have well-documented interfaces
            cm_config["embedding"]["chunk_size"] = 1100
            cm_config["importance_scoring"]["code_weight"] = 1.1
            cm_config["importance_scoring"]["comment_weight"] = 1.0
    
    def _adjust_config_for_project_size(self, config: Dict[str, Any]) -> None:
        """
        Adjust configuration based on project size.
        
        Args:
            config: Configuration dictionary to adjust
        """
        cm_config = config["context_management"]
        
        if self.project_size == "small":
            # Small projects can use smaller optimization intervals
            cm_config["optimization_interval"] = 30
            cm_config["summarization"]["threshold"] = 1500
            
        elif self.project_size == "medium":
            # Medium projects use the default settings
            pass
            
        elif self.project_size == "large":
            # Large projects need more aggressive optimization
            cm_config["optimization_interval"] = 90  # More frequent optimization
            cm_config["summarization"]["threshold"] = 2500
            cm_config["summarization"]["compression_ratio"] = 0.4  # More aggressive summarization
    
    def _adjust_config_for_language(self, config: Dict[str, Any]) -> None:
        """
        Adjust configuration based on primary programming language.
        
        Args:
            config: Configuration dictionary to adjust
        """
        cm_config = config["context_management"]
        primary_language = self.get_primary_language()
        
        if primary_language == "python":
            # Python tends to be more concise
            cm_config["embedding"]["chunk_size"] = int(cm_config["embedding"]["chunk_size"] * 0.9)
            
        elif primary_language in ["java", "csharp"]:
            # Java and C# tend to be more verbose
            cm_config["embedding"]["chunk_size"] = int(cm_config["embedding"]["chunk_size"] * 1.2)
            cm_config["search"]["bm25"]["b"] = 0.8  # Slightly higher b for more document length normalization
            
        elif primary_language in ["javascript", "typescript"]:
            # JS/TS often have many short functions
            cm_config["embedding"]["chunk_size"] = int(cm_config["embedding"]["chunk_size"] * 0.95)
            cm_config["search"]["bm25"]["k1"] = 1.3  # Higher k1 for more term frequency impact
    
    def _adjust_config_for_code_density(self, config: Dict[str, Any]) -> None:
        """
        Adjust configuration based on code density metrics.
        
        Args:
            config: Configuration dictionary to adjust
        """
        cm_config = config["context_management"]
        primary_language = self.get_primary_language()
        
        density_metrics = self.file_stats.get("code_density", {}).get(primary_language, {})
        if not density_metrics:
            return
            
        code_density_score = density_metrics.get("code_density_score", 0.7)  # Default if not available
        
        # Adjust chunk size based on code density
        if code_density_score > 0.8:
            # Very dense code, use smaller chunks
            cm_config["embedding"]["chunk_size"] = int(cm_config["embedding"]["chunk_size"] * 0.9)
            cm_config["embedding"]["chunk_overlap"] = int(cm_config["embedding"]["chunk_overlap"] * 1.1)
            
        elif code_density_score < 0.5:
            # Less dense code (more comments, whitespace), can use larger chunks
            cm_config["embedding"]["chunk_size"] = int(cm_config["embedding"]["chunk_size"] * 1.1)
            
        # Adjust importance weights based on comment ratio
        comment_ratio = density_metrics.get("comment_ratio", 0.2)
        if comment_ratio > 0.3:
            # Many comments, likely important documentation
            cm_config["importance_scoring"]["comment_weight"] = min(1.2, cm_config["importance_scoring"]["comment_weight"] * 1.2)
        elif comment_ratio < 0.1:
            # Few comments, less likely to be important
            cm_config["importance_scoring"]["comment_weight"] = max(0.5, cm_config["importance_scoring"]["comment_weight"] * 0.8)
