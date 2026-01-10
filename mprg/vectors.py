"""Vector database for semantic embeddings using ChromaDB.

Stores English text embeddings for semantic similarity comparison,
independent of the symbolic FOL analysis.
"""

from __future__ import annotations

import hashlib
import os
from typing import List, Optional, Dict, Any

import chromadb
from chromadb.config import Settings


class VectorStore:
    """ChromaDB-backed vector storage for reasoning embeddings.
    
    This is Layer 2 of the dual-layer analysis:
    - Layer 1: Symbolic FOL (structural topology)
    - Layer 2: Semantic embeddings (conceptual similarity) <- THIS
    """
    
    def __init__(self, persist_dir: Optional[str] = None):
        """Initialize ChromaDB.
        
        Args:
            persist_dir: Directory for persistence. None = in-memory.
        """
        if persist_dir:
            self.client = chromadb.PersistentClient(path=persist_dir)
        else:
            self.client = chromadb.Client()
            
        # Collection for reasoning embeddings
        self.collection = self.client.get_or_create_collection(
            name="reasoning_embeddings",
            metadata={"description": "Semantic embeddings of agent reasoning"}
        )
    
    def add_reasoning(
        self,
        id: str,
        text: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Add a reasoning text with its embedding.
        
        ChromaDB automatically generates embeddings using its default model.
        
        Args:
            id: Unique identifier for this reasoning
            text: The reasoning text to embed
            metadata: Optional metadata (task_id, agent_id, etc.)
        """
        self.collection.add(
            ids=[id],
            documents=[text],
            metadatas=[metadata or {}]
        )
    
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
        where_filter = {"task_id": task_id} if task_id else None
        
        results = self.collection.query(
            query_texts=[text],
            n_results=n_results,
            where=where_filter,
            include=["documents", "metadatas", "distances"]
        )
        
        similar = []
        for i in range(len(results["ids"][0])):
            similar.append({
                "id": results["ids"][0][i],
                "text": results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
                "distance": results["distances"][0][i],
                "similarity": 1 - results["distances"][0][i]  # Convert distance to similarity
            })
            
        return similar
    
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
        matrix = [[0.0] * n for _ in range(n)]
        
        # Add all texts first
        for i, (id_, text) in enumerate(zip(ids, reasoning_texts)):
            try:
                self.collection.add(
                    ids=[f"temp_{id_}"],
                    documents=[text],
                    metadatas=[{"index": i}]
                )
            except:
                pass  # Already exists
        
        # Query each against all others
        for i, text in enumerate(reasoning_texts):
            results = self.collection.query(
                query_texts=[text],
                n_results=n,
                include=["distances"]
            )
            
            for j, distance in enumerate(results["distances"][0]):
                if j < n:
                    matrix[i][j] = 1 - distance  # Convert to similarity
                    
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
        results = self.collection.get(
            where={"task_id": task_id},
            include=["documents", "metadatas"]
        )
        
        if not results["ids"]:
            return []
            
        ids = results["ids"]
        texts = results["documents"]
        
        # Simple clustering using similarity threshold
        clusters = []
        assigned = set()
        
        for i, (id_, text) in enumerate(zip(ids, texts)):
            if id_ in assigned:
                continue
                
            # Start new cluster
            cluster = [id_]
            assigned.add(id_)
            
            # Find similar items
            similar = self.find_similar(text, n_results=len(ids), task_id=task_id)
            
            for item in similar:
                if item["id"] not in assigned and item["similarity"] >= threshold:
                    cluster.append(item["id"])
                    assigned.add(item["id"])
                    
            clusters.append(cluster)
            
        return clusters


def compute_text_hash(text: str) -> str:
    """Compute hash for text (for deduplication)."""
    return hashlib.sha256(text.encode()).hexdigest()[:16]
