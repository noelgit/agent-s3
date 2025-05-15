"""
Tests for the Token Budget Allocation system.
"""

import pytest
from agent_s3.tools.context_management.token_budget import (
    TokenEstimator, 
    TokenBudgetAnalyzer,
    PriorityBasedAllocation,
    TaskAdaptiveAllocation
)


@pytest.fixture
def sample_context():
    """Sample context for testing."""
    return {
        "metadata": {
            "task_id": "test-123",
            "framework": "Django"
        },
        "code_context": {
            "models.py": """
class User:
    name = models.CharField(max_length=100)
    email = models.EmailField()
    
    def __str__(self):
        return self.name
""",
            "views.py": """
def index(request):
    users = User.objects.all()
    return render(request, 'index.html', {'users': users})

def profile(request, user_id):
    user = User.objects.get(id=user_id)
    return render(request, 'profile.html', {'user': user})
""",
            "urls.py": """
urlpatterns = [
    path('', views.index, name='index'),
    path('profile/<int:user_id>/', views.profile, name='profile'),
]
"""
        },
        "framework_structures": {
            "models": [{"name": "User", "fields": ["name", "email"]}],
            "views": [
                {"name": "index", "type": "function"},
                {"name": "profile", "type": "function"}
            ]
        }
    }

@pytest.fixture
def large_context():
    """A larger context for testing token limits."""
    large_context = {
        "metadata": {
            "task_id": "test-456",
            "framework": "Django"
        },
        "code_context": {}
    }
    
    # Add 20 files with 100 lines each
    for i in range(20):
        file_content = "\n".join([f"# Line {j} of file {i}" for j in range(100)])
        large_context["code_context"][f"file_{i}.py"] = file_content
    
    return large_context


class TestTokenEstimator:
    """Tests for the TokenEstimator class."""
    
    def test_estimate_tokens_for_text(self):
        """Test token estimation for text."""
        estimator = TokenEstimator()
        
        python_code = """
def hello_world():
    print("Hello, world!")
    return True
"""
        
        # Test with Python language
        python_tokens = estimator.estimate_tokens_for_text(python_code, "python")
        assert python_tokens > 0
        
        # Test with unknown language
        unknown_tokens = estimator.estimate_tokens_for_text(python_code)
        assert unknown_tokens > 0
        
        # Different languages should have different token estimates
        js_code = python_code  # Same code, different language
        js_tokens = estimator.estimate_tokens_for_text(js_code, "javascript")
        
        # JavaScript typically has more tokens than Python
        assert js_tokens >= python_tokens
    
    def test_estimate_tokens_for_file(self):
        """Test token estimation for files."""
        estimator = TokenEstimator()
        
        # Test with Python file
        python_tokens = estimator.estimate_tokens_for_file(
            "test.py", 
            "def test():\n    return True"
        )
        assert python_tokens > 0
        
        # Test with JavaScript file
        js_tokens = estimator.estimate_tokens_for_file(
            "test.js", 
            "function test() {\n    return true;\n}"
        )
        assert js_tokens > 0
        
        # Test with unknown file type
        unknown_tokens = estimator.estimate_tokens_for_file(
            "test.xyz", 
            "Some content"
        )
        assert unknown_tokens > 0
    
    def test_estimate_tokens_for_context(self, sample_context):
        """Test token estimation for a complete context."""
        estimator = TokenEstimator()
        
        estimates = estimator.estimate_tokens_for_context(sample_context)
        
        assert "code_context" in estimates
        assert "total" in estimates["code_context"]
        assert "files" in estimates["code_context"]
        assert "models.py" in estimates["code_context"]["files"]
        assert "views.py" in estimates["code_context"]["files"]
        assert "urls.py" in estimates["code_context"]["files"]
        
        assert "metadata" in estimates
        assert "framework_structures" in estimates
        assert "total" in estimates
        
        # Total should be the sum of all components
        assert estimates["total"] == (
            estimates["code_context"]["total"] + 
            estimates["metadata"] + 
            estimates["framework_structures"]
        )


class TestTokenBudgetAnalyzer:
    """Tests for the TokenBudgetAnalyzer class."""
    
    def test_initialization(self):
        """Test analyzer initialization."""
        analyzer = TokenBudgetAnalyzer(max_tokens=12000, reserved_tokens=1000)
        
        assert analyzer.max_tokens == 12000
        assert analyzer.reserved_tokens == 1000
        assert analyzer.available_tokens == 11000
    
    def test_analyze_content_complexity(self, sample_context):
        """Test content complexity analysis."""
        analyzer = TokenBudgetAnalyzer()
        
        complexity_scores = analyzer.analyze_content_complexity(sample_context["code_context"])
        
        assert "models.py" in complexity_scores
        assert "views.py" in complexity_scores
        assert "urls.py" in complexity_scores
        
        # All scores should be positive
        assert all(score > 0 for score in complexity_scores.values())
    
    def test_calculate_importance_scores(self, sample_context):
        """Test importance score calculation."""
        analyzer = TokenBudgetAnalyzer()
        
        # Test with different task types
        debugging_scores = analyzer.calculate_importance_scores(sample_context, "debugging")
        implementation_scores = analyzer.calculate_importance_scores(sample_context, "implementation")
        
        assert "code_context" in debugging_scores
        assert "code_context" in implementation_scores
        
        # Check file-level scores
        assert "models.py" in debugging_scores["code_context"]
        assert "views.py" in debugging_scores["code_context"]
        
        # Other sections should have scores
        for section in ["metadata", "framework_structures"]:
            if section in sample_context:
                assert section in debugging_scores
                assert section in implementation_scores
    
    def test_allocate_tokens(self, sample_context):
        """Test token allocation within limits."""
        analyzer = TokenBudgetAnalyzer(max_tokens=16000)
        
        result = analyzer.allocate_tokens(sample_context)
        
        assert "optimized_context" in result
        assert "allocation_report" in result
        
        # If context fits within limit, it should be unchanged
        assert result["optimized_context"] == sample_context
        assert result["allocation_report"]["optimization_applied"] is False
    
    def test_allocate_tokens_with_limit(self, large_context):
        """Test token allocation with limits exceeded."""
        analyzer = TokenBudgetAnalyzer(max_tokens=8000)
        
        result = analyzer.allocate_tokens(large_context)
        
        assert "optimized_context" in result
        assert "allocation_report" in result
        
        # Context should be optimized
        assert result["allocation_report"]["optimization_applied"] is True
        
        # Allocated tokens should be less than or equal to available tokens
        assert result["allocation_report"]["allocated_tokens"] <= analyzer.available_tokens
        
        # Context should be smaller than original
        orig_file_count = len(large_context["code_context"])
        opt_file_count = len(result["optimized_context"]["code_context"])
        
        # Either fewer files or some files are truncated
        assert opt_file_count <= orig_file_count
        
        # Check file allocations
        if "file_allocations" in result["allocation_report"]:
            for file_path, allocation in result["allocation_report"]["file_allocations"].items():
                assert "allocated_tokens" in allocation
                assert "importance_score" in allocation


class TestPriorityBasedAllocation:
    """Tests for the PriorityBasedAllocation strategy."""
    
    def test_initialization(self):
        """Test strategy initialization."""
        strategy = PriorityBasedAllocation(max_tokens=12000, reserved_tokens=1000)
        
        assert strategy.analyzer.max_tokens == 12000
        assert strategy.analyzer.reserved_tokens == 1000
        assert strategy.analyzer.available_tokens == 11000
        assert strategy.priorities["code_context"] == 1.0
    
    def test_allocate(self, sample_context):
        """Test allocation with priorities."""
        strategy = PriorityBasedAllocation(max_tokens=16000)
        
        result = strategy.allocate(sample_context)
        
        assert "optimized_context" in result
        assert "allocation_report" in result
        
        # If context fits within limit, it should be unchanged
        assert result["optimized_context"] == sample_context
        assert result["allocation_report"]["optimization_applied"] is False
    
    def test_allocate_with_custom_priorities(self, large_context):
        """Test allocation with custom priorities."""
        custom_priorities = {
            "code_context": 0.8,
            "metadata": 1.5
        }
        
        strategy = PriorityBasedAllocation(
            max_tokens=8000,
            priorities=custom_priorities
        )
        
        result = strategy.allocate(large_context)
        
        assert "optimized_context" in result
        assert "allocation_report" in result
        
        # Context should be optimized
        assert result["allocation_report"]["optimization_applied"] is True
        
        # Allocated tokens should be less than or equal to available tokens
        assert result["allocation_report"]["allocated_tokens"] <= strategy.analyzer.available_tokens


class TestTaskAdaptiveAllocation:
    """Tests for the TaskAdaptiveAllocation strategy."""
    
    def test_initialization(self):
        """Test strategy initialization."""
        strategy = TaskAdaptiveAllocation(max_tokens=12000, reserved_tokens=1000)
        
        assert strategy.analyzer.max_tokens == 12000
        assert strategy.analyzer.reserved_tokens == 1000
        assert strategy.analyzer.available_tokens == 11000
        assert "debugging" in strategy.task_priorities
        assert "implementation" in strategy.task_priorities
    
    def test_allocate_for_different_tasks(self, sample_context):
        """Test allocation for different task types."""
        strategy = TaskAdaptiveAllocation(max_tokens=16000)
        
        debugging_result = strategy.allocate(sample_context, "debugging")
        implementation_result = strategy.allocate(sample_context, "implementation")
        documentation_result = strategy.allocate(sample_context, "documentation")
        
        # All results should have the expected structure
        for result in [debugging_result, implementation_result, documentation_result]:
            assert "optimized_context" in result
            assert "allocation_report" in result
    
    def test_allocate_with_limited_tokens(self, large_context):
        """Test task-adaptive allocation with token limits."""
        strategy = TaskAdaptiveAllocation(max_tokens=8000)
        
        # Test for different task types
        for task_type in ["debugging", "implementation", "documentation", "refactoring"]:
            result = strategy.allocate(large_context, task_type)
            
            assert "optimized_context" in result
            assert "allocation_report" in result
            
            # Context should be optimized
            assert result["allocation_report"]["optimization_applied"] is True
            
            # Allocated tokens should be less than or equal to available tokens
            assert result["allocation_report"]["allocated_tokens"] <= strategy.analyzer.available_tokens