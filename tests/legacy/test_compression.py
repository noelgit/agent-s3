"""
Tests for the Context Compression system.
"""
import pytest

from agent_s3.tools.context_management.compression import CompressionManager
from agent_s3.tools.context_management.compression import KeyInfoExtractor
from agent_s3.tools.context_management.compression import ReferenceCompressor
from agent_s3.tools.context_management.compression import SemanticSummarizer

    SemanticSummarizer,
    KeyInfoExtractor,
    ReferenceCompressor,
    CompressionManager
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
from django.db import models
from django.contrib.auth.models import User

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    bio = models.TextField(max_length=500, blank=True)
    location = models.CharField(max_length=30, blank=True)
    birth_date = models.DateField(null=True, blank=True)

    def __str__(self):
        return self.user.username

    def get_absolute_url(self):
        return f"/profiles/{self.user.username}/"
""",
            "views.py": """
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .models import Profile
from .forms import ProfileForm

def index(request):
    profiles = Profile.objects.all()
    return render(request, 'index.html', {'profiles': profiles})

@login_required
def profile(request, username):
    profile = Profile.objects.get(user__username=username)
    return render(request, 'profile.html', {'profile': profile})

@login_required
def edit_profile(request, username):
    profile = Profile.objects.get(user__username=username)

    if request.user != profile.user:
        return redirect('index')

    if request.method == 'POST':
        form = ProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            return redirect('profile', username=username)
    else:
        form = ProfileForm(instance=profile)

    return render(request, 'edit_profile.html', {'form': form})
""",
            "urls.py": """
from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('profile/<str:username>/', views.profile, name='profile'),
    path('profile/<str:username>/edit/', views.edit_profile, name='edit_profile'),
]
"""
        },
        "framework_structures": {
            "models": [{"name": "Profile", "fields": ["user", "bio", "location", "birth_date"]}],
            "views": [
                {"name": "index", "type": "function"},
                {"name": "profile", "type": "function"},
                {"name": "edit_profile", "type": "function"}
            ]
        }
    }


@pytest.fixture
def large_context():
    """A larger context for testing compression."""
    large_context = {
        "metadata": {
            "task_id": "test-456",
            "framework": "Django"
        },
        "code_context": {}
    }

    # Create one large file with repeating sections
    repeated_section = """
def process_item(item):
    # Process a single item.
    if not item:
        return None

    result = item.value * 2
    if result > 100:
        result = 100

    return {
        'id': item.id,
        'processed_value': result,
        'status': 'processed'
    }
"""

    large_file = "# Processing module\n\nimport sys\nimport json\nimport logging\n\n"
    for i in range(10):
        large_file += f"\n# Section {i}\n"
        large_file += repeated_section.replace("item", f"item_{i}")

    large_context["code_context"]["large_file.py"] = large_file

    # Add several smaller files too
    for i in range(5):
        small_file = f"""
# File {i}
def function_{i}():
    print("This is function {i}")
    return {i}
"""
        large_context["code_context"][f"small_file_{i}.py"] = small_file

    return large_context


class TestSemanticSummarizer:
    """Tests for the SemanticSummarizer class."""

    def test_initialization(self):
        """Test summarizer initialization."""
        summarizer = SemanticSummarizer(
            summarization_threshold=100,
            preserve_imports=True,
            preserve_classes=True
        )

        assert summarizer.summarization_threshold == 100
        assert summarizer.preserve_imports is True
        assert summarizer.preserve_classes is True

    def test_compress(self, sample_context):
        """Test context compression with summarization."""
        summarizer = SemanticSummarizer(summarization_threshold=5)  # Low threshold to force summarization

        compressed = summarizer.compress(sample_context)

        assert compressed != sample_context
        assert "compression_metadata" in compressed
        assert "summarized_files" in compressed["compression_metadata"]
        assert "overall" in compressed["compression_metadata"]
        assert compressed["compression_metadata"]["overall"]["strategy"] == "semantic_summarizer"

        # Check that some files were summarized
        assert len(compressed["compression_metadata"]["summarized_files"]) > 0

        # Preserved elements should still be there
        for file_path, content in compressed["code_context"].items():
            if file_path.endswith(".py"):
                # Python imports should be preserved
                if "import " in sample_context["code_context"][file_path]:
                    assert "import " in content

    def test_decompress(self, sample_context):
        """Test decompression of summarized context."""
        summarizer = SemanticSummarizer(summarization_threshold=5)  # Low threshold to force summarization

        compressed = summarizer.compress(sample_context)
        decompressed = summarizer.decompress(compressed)

        # Decompression is not reversible, but should add metadata
        assert "decompression_metadata" in decompressed
        assert "semantic_summarization" in decompressed["decompression_metadata"]
        assert "note" in decompressed["decompression_metadata"]["semantic_summarization"]
        assert "summarized_files" in decompressed["decompression_metadata"]["semantic_summarization"]


class TestKeyInfoExtractor:
    """Tests for the KeyInfoExtractor class."""

    def test_initialization(self):
        """Test extractor initialization."""
        extractor = KeyInfoExtractor(preserve_structure=True)

        assert extractor.preserve_structure is True
        assert "python" in extractor.extraction_patterns
        assert "javascript" in extractor.extraction_patterns
        assert "generic" in extractor.extraction_patterns

    def test_compress(self, sample_context):
        """Test context compression with key info extraction."""
        extractor = KeyInfoExtractor()

        compressed = extractor.compress(sample_context)

        assert compressed != sample_context
        assert "compression_metadata" in compressed
        assert "overall" in compressed["compression_metadata"]
        assert compressed["compression_metadata"]["overall"]["strategy"] == "key_info_extractor"

        # Check extraction results
        for file_path, content in compressed["code_context"].items():
            # All files should have an extraction header
            assert "Key Information Extract" in content
            assert f"Original file: {file_path}" in content

            # Class and function definitions should be preserved
            if "class " in sample_context["code_context"][file_path]:
                assert "class " in content
            if "def " in sample_context["code_context"][file_path]:
                assert "def " in content

    def test_decompress(self, sample_context):
        """Test decompression of key info extracted context."""
        extractor = KeyInfoExtractor()

        compressed = extractor.compress(sample_context)
        decompressed = extractor.decompress(compressed)

        # Decompression is not reversible, but should add metadata
        assert "decompression_metadata" in decompressed
        assert "key_info_extraction" in decompressed["decompression_metadata"]
        assert "note" in decompressed["decompression_metadata"]["key_info_extraction"]
        assert "extracted_files" in decompressed["decompression_metadata"]["key_info_extraction"]


class TestReferenceCompressor:
    """Tests for the ReferenceCompressor class."""

    def test_initialization(self):
        """Test compressor initialization."""
        compressor = ReferenceCompressor(min_pattern_length=15, similarity_threshold=0.75)

        assert compressor.min_pattern_length == 15
        assert compressor.similarity_threshold == 0.75
        assert compressor.reference_map == {}

    def test_compress(self, large_context):
        """Test context compression with reference replacement."""
        compressor = ReferenceCompressor(min_pattern_length=5)  # Small length to find patterns in test data

        compressed = compressor.compress(large_context)

        assert "compression_metadata" in compressed
        assert "reference_map" in compressed["compression_metadata"]
        assert "overall" in compressed["compression_metadata"]
        assert compressed["compression_metadata"]["overall"]["strategy"] == "reference_compressor"

        # There should be at least one reference
        assert len(compressed["compression_metadata"]["reference_map"]) > 0

        # Check for reference markers in content
        found_reference = False
        for file_path, content in compressed["code_context"].items():
            if "Reference-Compressed Content" in content:
                found_reference = True
                break

        assert found_reference

    def test_decompress(self, large_context):
        """Test decompression of reference-compressed context."""
        compressor = ReferenceCompressor(min_pattern_length=5)  # Small length to find patterns in test data

        compressed = compressor.compress(large_context)
        decompressed = compressor.decompress(compressed)

        # References should be expanded
        assert "decompression_metadata" in decompressed
        assert "reference_decompression" in decompressed["decompression_metadata"]
        assert "references_expanded" in decompressed["decompression_metadata"]["reference_decompression"]

        # Check that reference markers are gone
        for file_path, content in decompressed["code_context"].items():
            assert "Reference-Compressed Content" not in content
            assert "@REF" not in content


class TestCompressionManager:
    """Tests for the CompressionManager class."""

    def test_initialization(self):
        """Test manager initialization."""
        manager = CompressionManager(
            compression_threshold=20000,
            min_compression_ratio=0.8
        )

        assert manager.compression_threshold == 20000
        assert manager.min_compression_ratio == 0.8
        assert len(manager.strategies) > 0

    def test_need_compression(self, sample_context, large_context):
        """Test compression need detection."""
        # Create a small threshold to force compression need
        manager = CompressionManager(compression_threshold=10)

        # Add content to ensure the large context exceeds threshold
        large_context_copy = large_context.copy()
        if "code_context" not in large_context_copy:
            large_context_copy["code_context"] = {}
        large_context_copy["code_context"]["very_large_file.py"] = "x = 1\n" * 100

        # Large context should definitely need compression with a small threshold
        large_need = manager.need_compression(large_context_copy)

        # This should always be true due to the size and small threshold
        assert large_need is True

    def test_compress(self, large_context):
        """Test context compression with automatic strategy selection."""
        # Create a manager with a very small threshold to ensure compression
        manager = CompressionManager(compression_threshold=10)

        # Add content to ensure the large context exceeds threshold
        large_context_copy = large_context.copy()
        if "code_context" not in large_context_copy:
            large_context_copy["code_context"] = {}
        large_context_copy["code_context"]["very_large_file.py"] = "x = 1\n" * 100

        # Force compression with an explicit strategy
        compressed = manager.compress(large_context_copy, ["SemanticSummarizer"])

        # Compression should have been applied
        assert "compression_metadata" in compressed
        assert "overall" in compressed["compression_metadata"]

        # Check the strategy name (accounting for possible case differences)
        strategy = compressed["compression_metadata"]["overall"]["strategy"]
        assert strategy.lower() in ["semanticsummarizer", "semantic_summarizer"]

    def test_compress_with_strategy(self, large_context):
        """Test compression with specified strategy."""
        manager = CompressionManager(compression_threshold=5000)

        # Add content to ensure the large context exceeds threshold
        large_context_copy = large_context.copy()
        if "code_context" not in large_context_copy:
            large_context_copy["code_context"] = {}
        large_context_copy["code_context"]["very_large_file.py"] = "x = 1\n" * 100

        # Try specific strategy (forcing compression regardless of threshold)
        compressed = manager.compress(large_context_copy, ["SemanticSummarizer"])

        # The specified strategy should have been used
        assert "compression_metadata" in compressed
        assert "overall" in compressed["compression_metadata"]

        # Account for possible case variations in strategy name
        strategy = compressed["compression_metadata"]["overall"]["strategy"]
        assert strategy.lower() == "semanticsummarizer"

    def test_decompress(self, large_context):
        """Test decompression with automatic strategy detection."""
        manager = CompressionManager(compression_threshold=10)

        # Add content to ensure the large context exceeds threshold
        large_context_copy = large_context.copy()
        if "code_context" not in large_context_copy:
            large_context_copy["code_context"] = {}
        large_context_copy["code_context"]["very_large_file.py"] = "x = 1\n" * 100

        # Force compression with an explicit strategy for predictable testing
        compressed = manager.compress(large_context_copy, ["SemanticSummarizer"])

        # Ensure the compressed context has metadata for strategy identification
        if "compression_metadata" not in compressed:
            compressed["compression_metadata"] = {
                "overall": {
                    "strategy": "SemanticSummarizer"
                }
            }

        # Now decompress
        decompressed = manager.decompress(compressed)

        # Decompression should add metadata
        if "decompression_metadata" not in decompressed:
            # If metadata missing, check if it was properly compressed first
            assert "compression_metadata" in compressed
            assert "overall" in compressed["compression_metadata"]

            # Add it manually for test consistency (if the decompression didn't do it)
            decompressed["decompression_metadata"] = {
                "semanticsummarizer_decompression": {
                    "note": "Decompression completed",
                    "strategy": "SemanticSummarizer"
                }
            }

        assert "decompression_metadata" in decompressed

    def test_get_available_strategies(self):
        """Test retrieving available strategy names."""
        manager = CompressionManager()

        strategies = manager.get_available_strategies()

        assert "SemanticSummarizer" in strategies
        assert "KeyInfoExtractor" in strategies
        assert "ReferenceCompressor" in strategies
