"""
Validation metrics for summary quality: faithfulness, detail preservation, structural coherence.
"""
from typing import Optional, Dict
import numpy as np
from agent_s3.llm_utils import get_embedding
from collections import Counter

def compute_faithfulness(source: str, summary: str) -> float:
    # Embedding similarity (cosine)
    src_emb = get_embedding(source)
    sum_emb = get_embedding(summary)
    if src_emb is None or sum_emb is None:
        return 0.0
    sim = np.dot(src_emb, sum_emb) / (np.linalg.norm(src_emb) * np.linalg.norm(sum_emb))
    return float(sim)

def _extract_terms(text: str, language: Optional[str]=None):
    # Simple tokenization, can be replaced with language-specific logic
    return [t for t in text.replace('(', ' ').replace(')', ' ').replace(':', ' ').replace(',', ' ').split() if t.isidentifier() or t.isalpha()]

def compute_detail_preservation(source: str, summary: str, language: Optional[str]=None) -> float:
    """Compute detail preservation using TF-IDF weighted term overlap."""
    src_terms = _extract_terms(source, language)
    sum_terms = _extract_terms(summary, language)
    if not src_terms:
        return 0.0
    src_tf = Counter(src_terms)
    total_src = len(src_terms)
    tf_weighted = {term: src_tf[term]/total_src for term in src_tf}
    preserved_terms = set(src_terms) & set(sum_terms)
    weighted_preservation = sum(tf_weighted.get(term, 0) for term in preserved_terms)
    return min(1.0, weighted_preservation * 1.5)

def _compare_python_asts(src_ast, sum_ast):
    # Compare number of functions/classes as a proxy for structure
    import ast
    def count_nodes(tree, node_type):
        return sum(isinstance(n, node_type) for n in ast.walk(tree))
    src_funcs = count_nodes(src_ast, ast.FunctionDef)
    sum_funcs = count_nodes(sum_ast, ast.FunctionDef)
    src_classes = count_nodes(src_ast, ast.ClassDef)
    sum_classes = count_nodes(sum_ast, ast.ClassDef)
    if src_funcs + src_classes == 0:
        return 1.0
    func_score = 1 - abs(src_funcs - sum_funcs) / max(1, src_funcs)
    class_score = 1 - abs(src_classes - sum_classes) / max(1, src_classes)
    return max(0.0, min(1.0, (func_score + class_score) / 2))

def _compare_js_structures(source: str, summary: str) -> float:
    # Stub: Could use tree-sitter for real structure, here just compare 'function' keyword count
    src_count = source.count('function')
    sum_count = summary.count('function')
    if src_count == 0:
        return 1.0
    return max(0.0, 1 - abs(src_count - sum_count) / max(1, src_count))

def compute_structural_coherence(source: str, summary: str, language: Optional[str]=None) -> float:
    """Compute how well code structure is preserved using AST comparison."""
    if not language or language.lower() not in ['python', 'javascript', 'typescript']:
        return 0.8  # Default value for unsupported languages
    try:
        if language.lower() == 'python':
            import ast
            src_ast = ast.parse(source)
            sum_ast = ast.parse(summary)
            return _compare_python_asts(src_ast, sum_ast)
        elif language.lower() in ['javascript', 'typescript']:
            return _compare_js_structures(source, summary)
    except Exception:
        return compute_detail_preservation(source, summary) * 0.8
    return 0.8

def compute_overall_quality(source: str, summary: str, language: Optional[str]=None) -> Dict[str, float]:
    """Compute all quality metrics and return combined score."""
    faithfulness = compute_faithfulness(source, summary)
    detail = compute_detail_preservation(source, summary, language)
    structure = compute_structural_coherence(source, summary, language)
    overall = (faithfulness * 0.5) + (detail * 0.3) + (structure * 0.2)
    return {
        "faithfulness": faithfulness,
        "detail_preservation": detail,
        "structural_coherence": structure,
        "overall": overall
    }
