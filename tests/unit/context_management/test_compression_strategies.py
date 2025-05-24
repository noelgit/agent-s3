import importlib.util
from pathlib import Path

def load_compression_module():
    module_path = Path(__file__).resolve().parents[3] / "agent_s3" / "tools" / "context_management" / "compression.py"
    spec = importlib.util.spec_from_file_location("compression", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


compression = load_compression_module()
SemanticSummarizer = compression.SemanticSummarizer
KeyInfoExtractor = compression.KeyInfoExtractor
ReferenceCompressor = compression.ReferenceCompressor


def test_semantic_summarizer_metadata():
    summarizer = SemanticSummarizer(summarization_threshold=5)
    context = {"code_context": {"file.py": "\n".join(f"line {i}" for i in range(20))}}
    compressed = summarizer.compress(context)
    assert "compression_metadata" in compressed
    meta = compressed["compression_metadata"]
    assert "summarized_files" in meta and "file.py" in meta["summarized_files"]
    assert meta["overall"]["strategy"] == "semantic_summarizer"
    assert compressed["code_context"]["file.py"] != context["code_context"]["file.py"]


def test_key_info_extractor_metadata():
    extractor = KeyInfoExtractor()
    content = "import os\nclass A:\n    pass\n\ndef func():\n    pass"
    context = {"code_context": {"file.py": content}}
    compressed = extractor.compress(context)
    meta = compressed["compression_metadata"]
    assert meta["overall"]["strategy"] == "key_info_extractor"
    assert "Key Information Extract" in compressed["code_context"]["file.py"]


def test_reference_compressor_metadata():
    compressor = ReferenceCompressor(min_pattern_length=2)
    repeated = "def foo():\n    pass\n"
    context = {"code_context": {"file.py": repeated * 3}}
    compressed = compressor.compress(context)
    meta = compressed["compression_metadata"]
    assert meta["overall"]["strategy"] == "reference_compressor"
    assert meta["reference_map"]
    assert "@REF" in compressed["code_context"]["file.py"] or "Reference-Compressed Content" in compressed["code_context"]["file.py"]

