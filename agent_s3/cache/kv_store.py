"""
In-memory KV-tensor store for vLLM prefix reuse.
"""
kv_store = {}  # key = prefix_hash, value = torch.Tensor (GPU or CPU)
