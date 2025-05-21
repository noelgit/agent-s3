"""
Semantic cache setup for Agent-S3 using GPTCache and custom GDSF eviction.
"""
from gptcache import cache, Config
from gptcache.manager import get_data_manager, get_similarity_evaluator
from gptcache.embedding import OpenAIEmbedding
import json
import os

def init_semantic_cache():
    # Read config flag from llm.json
    config_path = os.path.join(os.path.dirname(__file__), '../../llm.json')
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        cache_cfg = config.get('semantic_cache', {})
        if not cache_cfg.get('enabled', True):
            return  # Skip if disabled
        _ = cache_cfg.get('lambda_decay', 0.001)
        _ = cache_cfg.get('prefix_tokens', 50)
    except Exception:
        pass
    # Register custom GDSF policy (import triggers registration)
    from .gdsf import PrefixGDSF  # noqa: F401
    cache.init(
        config=Config(
            data_dir=".agent_s3_cache",
            eviction={"policy": "custom_gdsf"},
        ),
        embedding_func=OpenAIEmbedding(),
        data_manager=get_data_manager(
            vector_store="faiss",
            cache_store="sqlite"
        ),
        similarity_evaluator=get_similarity_evaluator("cosine")
    )
