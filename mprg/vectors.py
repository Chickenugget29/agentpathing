"""Lightweight vector store for semantic similarity.

Replaces ChromaDB with a pure-Python implementation to keep
serverless bundle size under 250MB.

Uses simple TF-IDF + cosine similarity instead of heavy embeddings.
"""

from __future__ import annotations

import hashlib
import math
import re
from collections import defaultdict
from typing import List, Optional, Dict, Any, Tuple


class VectorStore:
    """Lightweight in-memory vector storage for reasoning embeddings.
    
    This is Layer 2 of the dual-layer analysis:
    - Layer 1: Symbolic FOL (structural topology)
    - Layer 2: Semantic similarity (conceptual similarity) <- THIS
    
    Uses TF-IDF for vectorization and cosine similarity for comparison.
    No heavy ML dependencies required.
    """
    
    def __init__(self, persist_dir: Optional[str] = None):
        """Initialize vector store.
        
        Args:
            persist_dir: Ignored for now (in-memory only for serverless)
        """
        self.documents: Dict[str, str] = {}  # id -> text
        self.metadata: Dict[str, Dict] = {}  # id -> metadata
        self.vectors: Dict[str, Dict[str, float]] = {}  # id -> term weights
        self.idf: Dict[str, float] = {}  # term -> inverse document frequency
        self._doc_count = 0
    
    def _tokenize(self, text: str) -> List[str]:
        """Simple tokenization: lowercase, extract words."""
        return re.findall(r'\b[a-z]+\b', text.lower())
    
    def _compute_tf(self, tokens: List[str]) -> Dict[str, float]:
        """Compute term frequency for tokens."""
        tf = defaultdict(int)
        for token in tokens:
            tf[token] += 1
        # Normalize by document length
        total = len(tokens) or 1
        return {k: v / total for k, v in tf.items()}
    
    def _update_idf(self):
        """Recompute IDF based on all documents."""
        doc_freq = defaultdict(int)
        for vec in self.vectors.values():
            for term in vec.keys():
                doc_freq[term] += 1
        
        n = len(self.documents) or 1
        self.idf = {
            term: math.log(n / (df + 1)) + 1
            for term, df in doc_freq.items()
        }
    
    def _get_tfidf(self, text: str) -> Dict[str, float]:
        """Compute TF-IDF vector for text."""
        tokens = self._tokenize(text)
        tf = self._compute_tf(tokens)
        return {term: freq * self.idf.get(term, 1.0) for term, freq in tf.items()}
    
    def _cosine_similarity(self, vec1: Dict[str, float], vec2: Dict[str, float]) -> float:
        """Compute cosine similarity between two sparse vectors."""
        if not vec1 or not vec2:
            return 0.0
        
        # Dot product
        dot = sum(vec1.get(k, 0) * vec2.get(k, 0) for k in set(vec1) | set(vec2))
        
        # Magnitudes
        mag1 = math.sqrt(sum(v * v for v in vec1.values()))
        mag2 = math.sqrt(sum(v * v for v in vec2.values()))
        
        if mag1 == 0 or mag2 == 0:
            return 0.0
        
        return dot / (mag1 * mag2)
    
    def add_reasoning(
        self,
        id: str,
        text: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Add a reasoning text.
        
        Args:
            id: Unique identifier for this reasoning
            text: The reasoning text
            metadata: Optional metadata (task_id, agent_id, etc.)
        """
        self.documents[id] = text
        self.metadata[id] = metadata or {}
        
        tokens = self._tokenize(text)
        self.vectors[id] = self._compute_tf(tokens)
        self._doc_count += 1
        
        # Update IDF periodically
        if self._doc_count % 5 == 0:
            self._update_idf()
    
    def find_similar(
        self,
        text: str,
        n_results: int = 5,
        task_id: Optional[str] = None
    ) -> List[Dict]:
        """Find reasoning texts similar to the given text.
        
        Args:
            text: Query text
            n_results: Number of results to return
            task_id: Optional filter by task
            
        Returns:
            List of similar reasoning with distances
        """
        self._update_idf()
        query_vec = self._get_tfidf(text)
        
        similarities = []
        for doc_id, doc_vec in self.vectors.items():
            # Apply task filter
            if task_id and self.metadata.get(doc_id, {}).get("task_id") != task_id:
                continue
            
            # Apply IDF to document vector
            doc_tfidf = {
                term: freq * self.idf.get(term, 1.0)
                for term, freq in doc_vec.items()
            }
            
            sim = self._cosine_similarity(query_vec, doc_tfidf)
            similarities.append((doc_id, sim))
        
        # Sort by similarity descending
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        results = []
        for doc_id, sim in similarities[:n_results]:
            results.append({
                "id": doc_id,
                "text": self.documents[doc_id],
                "metadata": self.metadata[doc_id],
                "distance": 1 - sim,  # Convert to distance
                "similarity": sim
            })
        
        return results
    
    def compute_similarity_matrix(
        self,
        reasoning_texts: List[str],
        ids: List[str]
    ) -> List[List[float]]:
        """Compute pairwise similarity matrix for reasoning texts.
        
        Args:
            reasoning_texts: List of reasoning texts
            ids: List of IDs for each text
            
        Returns:
            NxN similarity matrix
        """
        n = len(reasoning_texts)
        
        # Compute TF-IDF for all texts
        vectors = []
        for text in reasoning_texts:
            tokens = self._tokenize(text)
            tf = self._compute_tf(tokens)
            vectors.append(tf)
        
        # Compute IDF for this batch
        doc_freq = defaultdict(int)
        for vec in vectors:
            for term in vec.keys():
                doc_freq[term] += 1
        
        batch_idf = {
            term: math.log(n / (df + 1)) + 1
            for term, df in doc_freq.items()
        }
        
        # Apply IDF
        tfidf_vectors = [
            {term: freq * batch_idf.get(term, 1.0) for term, freq in vec.items()}
            for vec in vectors
        ]
        
        # Compute similarity matrix
        matrix = [[0.0] * n for _ in range(n)]
        for i in range(n):
            for j in range(n):
                if i == j:
                    matrix[i][j] = 1.0
                elif j > i:
                    sim = self._cosine_similarity(tfidf_vectors[i], tfidf_vectors[j])
                    matrix[i][j] = sim
                    matrix[j][i] = sim
        
        return matrix
    
    def get_clusters(
        self,
        task_id: str,
        threshold: float = 0.85
    ) -> List[List[str]]:
        """Cluster reasoning texts by semantic similarity.
        
        Args:
            task_id: Task to cluster
            threshold: Similarity threshold for same cluster
            
        Returns:
            List of clusters, each containing reasoning IDs
        """
        # Get all reasoning for this task
        task_docs = [
            (doc_id, text)
            for doc_id, text in self.documents.items()
            if self.metadata.get(doc_id, {}).get("task_id") == task_id
        ]
        
        if not task_docs:
            return []
        
        ids = [d[0] for d in task_docs]
        texts = [d[1] for d in task_docs]
        
        # Compute similarity matrix
        sim_matrix = self.compute_similarity_matrix(texts, ids)
        
        # Simple clustering using similarity threshold
        clusters = []
        assigned = set()
        
        for i, doc_id in enumerate(ids):
            if doc_id in assigned:
                continue
            
            # Start new cluster
            cluster = [doc_id]
            assigned.add(doc_id)
            
            # Find similar items
            for j, other_id in enumerate(ids):
                if other_id not in assigned and sim_matrix[i][j] >= threshold:
                    cluster.append(other_id)
                    assigned.add(other_id)
            
            clusters.append(cluster)
        
        return clusters


def compute_text_hash(text: str) -> str:
    """Compute hash for text (for deduplication)."""
    return hashlib.sha256(text.encode()).hexdigest()[:16]
