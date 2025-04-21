"""Manages retrieval-augmented generation, hierarchical summarization, and context versioning.

This module provides advanced memory management capabilities as specified in instructions.md.
"""

import os
import json
import re
import time
import hashlib
from copy import deepcopy
from typing import Dict, List, Any, Optional, Set, Tuple
from datetime import datetime
import numpy as np  # type: ignore
from agent_s3.tools.embedding_client import EmbeddingClient
import tiktoken  # Add import
import openai  # Add openai import

DEFAULT_MAX_TOKENS = 4096
DEFAULT_SUMMARY_TARGET_TOKENS = 1024
DEFAULT_CHUNK_SIZE = 1000  # Tokens per chunk for summarization


class MemoryManager:
    """Tool for memory management with context versioning and hierarchical summarization."""
    
    def __init__(self, memory_path: str = ".memory_cache.json", max_context_items: int = 10):
        """Initialize the memory manager.
        
        Args:
            memory_path: Path to the memory cache file
            max_context_items: Maximum number of context items to maintain
        """
        self.memory_path = memory_path
        self.max_context_items = max_context_items
        # Initialize embedding client for retrieval-augmented generation
        cfg = {}  # placeholder: replaced below
        try:
            from agent_s3.config import Config
            config = Config()
            config.load()
            cfg = config.config
        except Exception:
            cfg = {}
        self.embedding_client = EmbeddingClient(
            store_path=cfg.get('vector_store_path', './data/vector_store.faiss'),
            dim=cfg.get('embedding_dim', 384),
            top_k=cfg.get('top_k_retrieval', 5),
            eviction_threshold=cfg.get('eviction_threshold', 0.90)
        )
        self.context_history: List[Dict[str, Any]] = []
        self.context_versions: Dict[str, List[Dict[str, Any]]] = {}
        self.summaries: Dict[str, str] = {}
        self.versioned_summaries: Dict[str, Dict[str, str]] = {}
        self.checkpoints: List[Dict[str, Any]] = []
    
    def initialize(self) -> None:
        """Initialize the memory manager.
        
        Loads existing data if available.
        """
        if os.path.exists(self.memory_path):
            try:
                with open(self.memory_path, "r") as f:
                    data = json.load(f)
                    self.context_history = data.get("context_history", [])
                    self.summaries = data.get("summaries", {})
                    self.context_versions = data.get("context_versions", {})
                    self.versioned_summaries = data.get("versioned_summaries", {})
                    self.checkpoints = data.get("checkpoints", [])
            except Exception as e:
                print(f"Error loading memory cache: {e}")
                self._reset_memory()
        else:
            self._reset_memory()
    
    def add_context(self, context_type: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Add a new context item with versioning support.
        
        Args:
            context_type: Type of context ("file", "output", "plan", etc.)
            content: The context content
            metadata: Optional metadata for the context
            
        Returns:
            The version ID of the added context
        """
        # Generate a unique version ID
        version_id = self._generate_version_id(context_type, content, metadata)
        
        # Check if content size exceeds a threshold, compress if needed
        original_size = len(content.encode('utf-8'))
        compressed_content = content
        is_compressed = False
        
        # Compress large content items (>100KB) to save memory
        if original_size > 100 * 1024:  # 100 KB
            try:
                import zlib
                compressed_bytes = zlib.compress(content.encode('utf-8'))
                if len(compressed_bytes) < original_size * 0.7:  # Only use if compression helps
                    compressed_content = f"__COMPRESSED__{compressed_bytes.hex()}"
                    is_compressed = True
                    print(f"Compressed content from {original_size} to {len(compressed_bytes)} bytes")
            except Exception as e:
                print(f"Compression error: {e}, storing uncompressed")
        
        # Create a new context item with additional metadata
        timestamp = datetime.now().isoformat()
        context_item = {
            "type": context_type,
            "content": compressed_content,
            "metadata": metadata or {},
            "version_id": version_id,
            "timestamp": timestamp,
            "is_compressed": is_compressed,
            "original_size": original_size,
            "last_accessed": timestamp,
            "access_count": 0
        }
        
        # Add to context history
        self.context_history.append(context_item)
        
        # Trim if too many items - use age-based and frequency-based eviction
        self._apply_eviction_strategy()
        
        # Handle versioning with age-based management
        context_key = self._get_context_key(context_type, metadata)
        if context_key:
            if context_key not in self.context_versions:
                self.context_versions[context_key] = []
            
            # Add this version
            version_info = {
                "version_id": version_id,
                "content": compressed_content,
                "metadata": deepcopy(metadata) if metadata else {},
                "timestamp": timestamp,
                "is_compressed": is_compressed,
                "last_accessed": timestamp,
                "access_count": 0
            }
            self.context_versions[context_key].append(version_info)
            
            # Age-based version management: keep recent ones and important ones
            if len(self.context_versions[context_key]) > 5:
                # Sort by recency and importance 
                # (newer + frequently accessed are kept; older + rarely accessed are removed)
                versions = self.context_versions[context_key]
                versions.sort(key=lambda v: (
                    # Primary sort: access count (higher is better)
                    -v.get("access_count", 0),
                    # Secondary sort: recency (newer is better)
                    -datetime.fromisoformat(v.get("last_accessed", v.get("timestamp", ""))).timestamp()
                ))
                # Keep top 5
                self.context_versions[context_key] = versions[:5]
        
        # Generate summary if it's a file or other important context
        if context_key and (context_type == "file" or context_type == "code"):
            # Decompress if needed for summarization
            content_for_summary = self._decompress_if_needed(compressed_content, is_compressed)
            
            # Current summary
            summary = self._generate_summary(content_for_summary)
            self.summaries[context_key] = summary
            
            # Versioned summary
            if context_key not in self.versioned_summaries:
                self.versioned_summaries[context_key] = {}
            self.versioned_summaries[context_key][version_id] = summary
        
        # Run periodic cache maintenance (once per ~100 additions)
        if hash(content) % 100 == 0:
            self._run_cache_maintenance()
        
        # Save changes
        self._save_memory()
        
        # Add to vector store for semantic retrieval
        try:
            # Decompress for embedding if needed
            content_for_embedding = self._decompress_if_needed(compressed_content, is_compressed)
            embedding = self._generate_embedding(content_for_embedding)
            if embedding is not None:
                self.embedding_client.add_embeddings(np.array([embedding]), [{'type': context_type, 'metadata': metadata or {}}])
            else:
                print(f"Warning: Failed to generate embedding for context: {context_type}")
        except Exception as e:
            print(f"Error adding embeddings to vector store: {e}")
        
        return version_id
        
    def _apply_eviction_strategy(self) -> None:
        """Apply smarter eviction strategy using age and access patterns."""
        if len(self.context_history) <= self.max_context_items:
            return  # No need to evict anything
            
        # Calculate how many items to evict
        num_to_evict = len(self.context_history) - self.max_context_items
        
        # Score items by age and access patterns
        scored_items = []
        now = datetime.now()
        
        for i, item in enumerate(self.context_history):
            # Get values with defaults
            timestamp_str = item.get("timestamp", "")
            try:
                age_days = (now - datetime.fromisoformat(timestamp_str)).days if timestamp_str else 365
            except:
                age_days = 365  # Default to old if we can't parse
                
            access_count = item.get("access_count", 0)
            last_accessed_str = item.get("last_accessed", timestamp_str)
            
            try:
                days_since_access = (now - datetime.fromisoformat(last_accessed_str)).days if last_accessed_str else age_days
            except:
                days_since_access = age_days
            
            # Calculate eviction score - higher means more likely to evict
            # Factors: age (older = more likely to evict)
            #          access count (less used = more likely to evict)
            #          days since last access (longer = more likely to evict)
            eviction_score = (
                age_days * 0.6 +            # Age factor 
                days_since_access * 0.3 -   # Recent access factor
                min(10, access_count) * 2   # Usage factor: max benefit for 10 accesses
            )
            
            scored_items.append((i, eviction_score, item))
            
        # Sort by eviction score (highest first - most eligible for eviction)
        scored_items.sort(key=lambda x: x[1], reverse=True)
        
        # Identify items to evict and generate summaries of important ones
        eviction_candidates = scored_items[:num_to_evict]
        indices_to_remove = [idx for idx, _, _ in eviction_candidates]
        
        # Separate by type: important (files/code) vs less important
        important_evicted = []
        
        for _, _, item in eviction_candidates:
            if item.get("type") in ("file", "code") and item.get("content"):
                # Save important items for summarization
                content = self._decompress_if_needed(
                    item.get("content", ""), 
                    item.get("is_compressed", False)
                )
                if content:
                    important_evicted.append({
                        "type": item.get("type", "unknown"),
                        "content": content,
                        "metadata": item.get("metadata", {})
                    })
        
        # Generate a summary for important evicted items if any
        if important_evicted:
            combined = "\n\n".join(item.get('content', '') for item in important_evicted)
            summary_evicted = self.hierarchical_summarize(combined, target_tokens=DEFAULT_SUMMARY_TARGET_TOKENS)
            
            # Store in special evicted summaries area
            timestamp = datetime.now().isoformat()
            eviction_key = f"evicted_{timestamp}"
            self.summaries[eviction_key] = summary_evicted
        
        # Remove items from context_history, from highest index to lowest to avoid index issues
        indices_to_remove.sort(reverse=True)
        for idx in indices_to_remove:
            self.context_history.pop(idx)
            
    def _run_cache_maintenance(self) -> None:
        """Run periodic cache maintenance tasks."""
        print("Running cache maintenance...")
        
        # 1. Clean up old or unused summaries
        summaries_to_remove = []
        for key in self.summaries:
            if key.startswith("evicted_"):
                # Extract timestamp from evicted_TIMESTAMP format
                try:
                    ts_part = key.split("_", 1)[1]
                    timestamp = datetime.fromisoformat(ts_part)
                    age_days = (datetime.now() - timestamp).days
                    
                    # Remove summaries older than 30 days
                    if age_days > 30:
                        summaries_to_remove.append(key)
                except:
                    # If we can't parse the timestamp, keep the summary
                    pass
        
        # Remove old summaries
        for key in summaries_to_remove:
            del self.summaries[key]
        
        # 2. Consolidate very similar summaries from evictions
        summary_vectors = {}
        summary_keys = []
        
        for key, summary in self.summaries.items():
            if key.startswith("evicted_"):
                try:
                    embedding = self._generate_embedding(summary)
                    if embedding is not None:
                        summary_vectors[key] = embedding
                        summary_keys.append(key)
                except:
                    pass
        
        # If we have enough to consolidate
        if len(summary_keys) > 5:
            # Find clusters of similar summaries
            consolidated_groups = []
            remaining_keys = set(summary_keys)
            
            while remaining_keys:
                current_key = next(iter(remaining_keys))
                current_vec = summary_vectors[current_key]
                
                # Find similar summaries
                similar_keys = []
                
                for key in remaining_keys:
                    if key == current_key:
                        continue
                        
                    vec = summary_vectors[key]
                    # Cosine similarity approximation
                    similarity = np.dot(current_vec, vec) / (np.linalg.norm(current_vec) * np.linalg.norm(vec))
                    
                    if similarity > 0.85:  # Very similar content
                        similar_keys.append(key)
                
                # Create a group
                group = [current_key] + similar_keys
                consolidated_groups.append(group)
                
                # Remove processed keys
                for k in group:
                    remaining_keys.remove(k)
            
            # Consolidate each group
            for group in consolidated_groups:
                if len(group) > 1:  # Only consolidate groups with multiple summaries
                    # Create a combined summary
                    combined_content = "\n\n".join([self.summaries[k] for k in group])
                    new_summary = self.hierarchical_summarize(combined_content)
                    
                    # Create a new key for the consolidated summary
                    new_key = f"consolidated_{datetime.now().isoformat()}"
                    self.summaries[new_key] = new_summary
                    
                    # Remove the individual summaries
                    for k in group:
                        del self.summaries[k]
        
        # 3. Check for vector store maintenance
        vector_store_stats = self.embedding_client.get_stats()
        
        # If load factor is too high (>80%), run a cleanup
        if vector_store_stats.get("load_factor", 0) > 0.8:
            print("Vector store load factor high, suggesting reorganization")
            try:
                self.embedding_client.reorganize()
            except:
                print("Failed to reorganize vector store")
                
        print("Cache maintenance complete")
    
    def _decompress_if_needed(self, content: str, is_compressed: bool) -> str:
        """Decompress content if it was compressed."""
        if not is_compressed or not content.startswith("__COMPRESSED__"):
            return content
            
        try:
            import zlib
            # Extract hex data after prefix
            hex_data = content[len("__COMPRESSED__"):]
            # Convert hex to bytes
            compressed_bytes = bytes.fromhex(hex_data)
            # Decompress
            decompressed_bytes = zlib.decompress(compressed_bytes)
            # Convert back to string
            return decompressed_bytes.decode('utf-8')
        except Exception as e:
            print(f"Decompression error: {e}, returning as-is")
            return content

    def get_relevant_context(self, query: str, plan_text: Optional[str] = None, 
                             file_modification_info: Optional[Dict[str, Any]] = None,
                             max_tokens: int = DEFAULT_MAX_TOKENS) -> str:
        """Retrieve relevant context based on query, respecting token limits.
        
        Args:
            query: The user query or task description
            plan_text: Optional plan text that may contain file references
            file_modification_info: Optional dict mapping filenames to recency/frequency info
            max_tokens: Maximum tokens for returned context
            
        Returns:
            Formatted context string
        """
        query_embedding = self._generate_embedding(query)
        if query_embedding is None:
            print("Warning: Failed to generate embedding for query.")
            return ""  # Return empty context if query embedding fails

        # Extract file references from the plan if available
        plan_mentioned_files = set()
        if plan_text:
            # Find file paths in the plan text using regex patterns
            # Looking for paths that are inside backticks, quotes, or mentioned after "File:" or similar
            file_patterns = [
                r'`([^`]+\.[a-zA-Z0-9]+)`',  # Files in backticks
                r'"([^"]+\.[a-zA-Z0-9]+)"',  # Files in double quotes
                r"'([^']+\.[a-zA-Z0-9]+')",  # Files in single quotes
                r'File:\s*([^\s,]+\.[a-zA-Z0-9]+)',  # Files after "File:"
                r'file:\s*([^\s,]+\.[a-zA-Z0-9]+)',  # Files after "file:"
                r'in\s+([^\s,]+\.[a-zA-Z0-9]+)',  # Files after "in"
                r'at\s+([^\s,]+\.[a-zA-Z0-9]+)'  # Files after "at"
            ]
            
            for pattern in file_patterns:
                matches = re.findall(pattern, plan_text)
                plan_mentioned_files.update(set(matches))
                
            if plan_mentioned_files:
                print(f"Files mentioned in plan: {', '.join(plan_mentioned_files)}")

        # Retrieve top-k relevant metadata entries
        results = self.embedding_client.query(np.array([query_embedding]))
        
        # Score and rank results based on multiple factors
        scored_results = []
        for i, item in enumerate(results):
            source = item.get('source', 'unknown')
            content = item.get('original_content', '')
            metadata = item.get('metadata', {})
            similarity_score = item.get('score', 0)
            
            # Base score from embedding similarity (0-1)
            score = similarity_score
            
            # Boost files specifically mentioned in the plan
            if plan_text and any(mentioned_file in source for mentioned_file in plan_mentioned_files):
                score += 0.5  # Significant boost for plan-mentioned files
            
            # Boost based on recency/modification frequency if available
            if file_modification_info and source in file_modification_info:
                file_info = file_modification_info[source]
                # Recency boost (0-0.3)
                if 'last_modified' in file_info:
                    days_since_modified = file_info.get('days_since_modified', 365)
                    recency_score = max(0, 0.3 - (days_since_modified / 30) * 0.1)
                    score += recency_score
                
                # Frequency boost (0-0.2)
                if 'modification_frequency' in file_info:
                    freq = file_info.get('modification_frequency', 0)
                    freq_score = min(0.2, freq * 0.05)  # Cap at 0.2
                    score += freq_score
            
            # Add to scored results
            scored_results.append({
                'item': item,
                'score': score,
                'original_index': i
            })
        
        # Sort by score, highest first
        scored_results.sort(key=lambda x: x['score'], reverse=True)
        
        # Now build the context with the reranked results
        combined_context = ""
        current_tokens = 0
        added_sources = set()
        
        # First add plan-mentioned files if they exist
        plan_context_added = False
        if plan_mentioned_files:
            plan_file_results = [r for r in scored_results 
                                if any(mentioned_file in r['item'].get('source', '') 
                                      for mentioned_file in plan_mentioned_files)]
            
            if plan_file_results:
                combined_context += "\n\n--- Priority Files (Mentioned in Plan) ---\n"
                for result in plan_file_results[:3]:  # Limit to top 3 plan files
                    item = result['item']
                    source = item.get('source', 'unknown')
                    if source in added_sources:
                        continue
                        
                    content = item.get('original_content', '')
                    token_count = item.get('token_count', self.estimate_token_count(content))
                    
                    # Only use max 35% of context budget for plan files
                    max_plan_tokens = max_tokens * 0.35
                    if current_tokens + token_count <= max_plan_tokens:
                        combined_context += f"\n--- {source} ---\n{content}\n"
                        current_tokens += token_count
                        added_sources.add(source)
                        plan_context_added = True
                    else:
                        # Try to fit a targeted summary
                        remaining_tokens = max_plan_tokens - current_tokens
                        if remaining_tokens > 100:
                            summary = self.hierarchical_summarize(content, target_tokens=remaining_tokens - 50)
                            summary_tokens = self.estimate_token_count(summary)
                            if current_tokens + summary_tokens <= max_plan_tokens:
                                combined_context += f"\n--- {source} (Summary) ---\n{summary}\n"
                                current_tokens += summary_tokens
                                added_sources.add(source)
                                plan_context_added = True
            
            if plan_context_added:
                combined_context += "\n\n--- Additional Context ---\n"

        # Then add the rest of the ranked results
        for result in scored_results:
            item = result['item']
            source = item.get('source', 'unknown')
            if source in added_sources:
                continue  # Skip already added sources
                
            content = item.get('original_content', '')
            token_count = item.get('token_count', self.estimate_token_count(content))
            
            remaining_budget = max_tokens - current_tokens
            
            # Apply adaptive context inclusion based on score
            score = result['score']
            if score > 0.8:  # Very relevant - try to include most/all
                max_file_tokens = min(token_count, remaining_budget * 0.7)
            elif score > 0.6:  # Moderately relevant - include partial
                max_file_tokens = min(token_count, remaining_budget * 0.3)
            else:  # Less relevant - include summary or small part
                max_file_tokens = min(token_count, remaining_budget * 0.15)
            
            # Check if we can include the content within our token budget
            if current_tokens + token_count <= current_tokens + max_file_tokens:
                combined_context += f"\n\n--- {source} (Score: {score:.2f}) ---\n{content}"
                current_tokens += token_count
                added_sources.add(source)
            else:
                # Try creating a summary that fits
                remaining_tokens = max_tokens - current_tokens
                if remaining_tokens > 100:
                    summary = self.hierarchical_summarize(content, target_tokens=int(max_file_tokens))
                    summary_tokens = self.estimate_token_count(summary)
                    if current_tokens + summary_tokens <= max_tokens:
                        combined_context += f"\n\n--- {source} (Summary, Score: {score:.2f}) ---\n{summary}"
                        current_tokens += summary_tokens
                        added_sources.add(source)
                    else:
                        break  # Cannot fit even the summary
                else:
                    break  # Not enough tokens left for any meaningful addition

        return combined_context.strip()

    def _generate_embedding(self, text: str) -> Optional[np.ndarray]:
        """Generate embedding for text using OpenAI API."""
        try:
            openai_key = os.environ.get('OPENAI_KEY')
            if not openai_key:
                raise ValueError("OpenAI API key not found in environment variables")

            client = openai.OpenAI(api_key=openai_key)
            response = client.embeddings.create(
                model="text-embedding-ada-002",
                input=text
            )
            embedding = response.data[0].embedding
            return np.array(embedding, dtype=np.float32)
        except Exception as e:
            print(f"Error generating embedding: {e}")
            return None

    def estimate_token_count(self, text: str) -> int:
        """Estimate token count using tiktoken."""
        try:
            encoding = tiktoken.get_encoding("cl100k_base")
            return len(encoding.encode(text))
        except Exception as e:
            print(f"Tiktoken error: {e}. Falling back to character-based token estimation.")
            return len(text) // 4  # Rough estimate

    def _generate_summary(self, text_chunk: str, target_tokens: Optional[int] = None) -> str:
        """Generate summary for a text chunk using an LLM."""
        try:
            openai_key = os.environ.get('OPENAI_KEY')
            if not openai_key:
                raise ValueError("OpenAI API key not found for summarization")

            client = openai.OpenAI(api_key=openai_key)

            max_tokens_hint = f" Aim for approximately {target_tokens} tokens." if target_tokens else ""
            prompt = f"""Summarize the following text concisely, capturing the main points and key information.{max_tokens_hint}

Text:
```
{text_chunk}
```

Summary:
"""

            estimated_input_tokens = self.estimate_token_count(prompt)
            output_max_tokens = target_tokens * 2 if target_tokens else 1024
            output_max_tokens = min(output_max_tokens, 4000)

            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are an expert summarizer. Create concise summaries capturing key information."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=output_max_tokens,
                top_p=1.0,
                frequency_penalty=0.0,
                presence_penalty=0.0
            )

            summary = response.choices[0].message.content.strip()
            return summary

        except Exception as e:
            print(f"Error generating summary with LLM: {e}")
            fallback_length = target_tokens * 4 if target_tokens else 4000
            return text_chunk[:fallback_length] + "... (summary failed)"

    def hierarchical_summarize(self, content: str, target_tokens: int = DEFAULT_SUMMARY_TARGET_TOKENS) -> str:
        """Summarize content hierarchically to meet target token count."""
        current_tokens = self.estimate_token_count(content)
        if current_tokens <= target_tokens:
            return content

        print(f"Hierarchically summarizing content ({current_tokens} tokens) to target ~{target_tokens} tokens...")

        chunk_size = min(DEFAULT_CHUNK_SIZE, target_tokens * 2)
        chunks = self._split_into_chunks(content, chunk_size)

        summaries = []
        for i, chunk in enumerate(chunks):
            print(f"  Summarizing chunk {i+1}/{len(chunks)}...")
            chunk_target_tokens = max(50, int(target_tokens / len(chunks)))
            summary = self._generate_summary(chunk, target_tokens=chunk_target_tokens)
            summaries.append(summary)

        combined_summary = "\n\n".join(summaries)
        combined_tokens = self.estimate_token_count(combined_summary)

        print(f"  Combined summary has {combined_tokens} tokens.")

        if combined_tokens > target_tokens:
            print(f"  Combined summary too large, summarizing the summaries...")
            final_summary = self._generate_summary(combined_summary, target_tokens=target_tokens)
            final_tokens = self.estimate_token_count(final_summary)
            print(f"  Final summary has {final_tokens} tokens.")
            return final_summary
        else:
            return combined_summary

    def _split_into_chunks(self, text: str, chunk_size_tokens: int) -> List[str]:
        """Split text into chunks of approximately chunk_size_tokens."""
        paragraphs = text.split('\n\n')
        chunks = []
        current_chunk = ""
        current_chunk_tokens = 0

        for para in paragraphs:
            para_tokens = self.estimate_token_count(para)
            if para_tokens == 0:
                continue

            if current_chunk_tokens + para_tokens <= chunk_size_tokens:
                current_chunk += ("\n\n" if current_chunk else "") + para
                current_chunk_tokens += para_tokens
            else:
                if para_tokens > chunk_size_tokens:
                    if current_chunk:
                        chunks.append(current_chunk)
                        current_chunk = ""
                        current_chunk_tokens = 0
                    lines = para.split('\n')
                    temp_chunk = ""
                    temp_chunk_tokens = 0
                    for line in lines:
                        line_tokens = self.estimate_token_count(line)
                        if temp_chunk_tokens + line_tokens <= chunk_size_tokens:
                            temp_chunk += ("\n" if temp_chunk else "") + line
                            temp_chunk_tokens += line_tokens
                        else:
                            if temp_chunk:
                                chunks.append(temp_chunk)
                            temp_chunk = line
                            temp_chunk_tokens = line_tokens
                    if temp_chunk:
                        chunks.append(temp_chunk)
                else:
                    if current_chunk:
                        chunks.append(current_chunk)
                    current_chunk = para
                    current_chunk_tokens = para_tokens

        if current_chunk:
            chunks.append(current_chunk)

        return chunks
