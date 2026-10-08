import os
import logging
from typing import List, Dict, Any, Optional
import chromadb
from chromadb.utils import embedding_functions
from ..config import settings

logger = logging.getLogger(__name__)

class VectorStoreManager:
    """Manages persistent ChromaDB collections for Knowledge Base & Semantic Memory."""

    def __init__(self, persist_dir: Optional[str] = None):
        self.persist_dir = str(persist_dir or settings.CHROMA_PERSIST_DIR)
        os.makedirs(self.persist_dir, exist_ok=True)
        
        # Initialize persistent Chroma client
        self.client = chromadb.PersistentClient(path=self.persist_dir)
        
        # Default embedding function: Chroma's built-in all-MiniLM-L6-v2 ONNX function
        self.embedding_fn = embedding_functions.DefaultEmbeddingFunction()
        
        # Initialize collections
        self.kb_collection = self.client.get_or_create_collection(
            name="historical_kb",
            embedding_function=self.embedding_fn,
            metadata={"hnsw:space": "cosine"}
        )
        
        self.memory_collection = self.client.get_or_create_collection(
            name="semantic_memory_vectors",
            embedding_function=self.embedding_fn,
            metadata={"hnsw:space": "cosine"}
        )
        logger.info("ChromaDB initialized at %s with collections: historical_kb, semantic_memory_vectors", self.persist_dir)

    def add_kb_documents(self, documents: List[str], metadatas: List[Dict[str, Any]], ids: List[str]):
        """Adds static knowledge base documents."""
        self.kb_collection.upsert(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )

    def search_kb(self, query: str, n_results: int = 4) -> List[Dict[str, Any]]:
        """Searches historical knowledge base."""
        try:
            results = self.kb_collection.query(
                query_texts=[query],
                n_results=n_results
            )
            parsed_results = []
            if results and results.get("documents") and results["documents"][0]:
                docs = results["documents"][0]
                metas = results["metadatas"][0] if results.get("metadatas") else [{}] * len(docs)
                dists = results["distances"][0] if results.get("distances") else [0.0] * len(docs)
                ids = results["ids"][0] if results.get("ids") else [""] * len(docs)
                
                for doc, meta, dist, doc_id in zip(docs, metas, dists, ids):
                    # Convert cosine distance to similarity: sim = 1.0 - dist
                    sim = max(0.0, 1.0 - float(dist)) if dist is not None else 0.8
                    parsed_results.append({
                        "id": doc_id,
                        "content": doc,
                        "metadata": meta,
                        "similarity": round(sim, 4),
                        "source_type": "KNOWLEDGE_BASE"
                    })
            return parsed_results
        except Exception as e:
            logger.error("Error searching KB: %s", e)
            return []

    def index_memory_fact(self, fact_id: str, fact_content: str, metadata: Dict[str, Any]):
        """Indexes a user fact into the semantic memory vector store for associative retrieval."""
        self.memory_collection.upsert(
            documents=[fact_content],
            metadatas=[metadata],
            ids=[fact_id]
        )

    def search_memory(self, query: str, user_id: str, n_results: int = 5) -> List[Dict[str, Any]]:
        """Associative vector search over long-term memories for a specific user."""
        try:
            results = self.memory_collection.query(
                query_texts=[query],
                n_results=n_results,
                where={"user_id": user_id}
            )
            parsed_results = []
            if results and results.get("documents") and results["documents"][0]:
                docs = results["documents"][0]
                metas = results["metadatas"][0] if results.get("metadatas") else [{}] * len(docs)
                dists = results["distances"][0] if results.get("distances") else [0.0] * len(docs)
                ids = results["ids"][0] if results.get("ids") else [""] * len(docs)
                
                for doc, meta, dist, fact_id in zip(docs, metas, dists, ids):
                    sim = max(0.0, 1.0 - float(dist)) if dist is not None else 0.8
                    parsed_results.append({
                        "id": fact_id,
                        "fact_content": doc,
                        "metadata": meta,
                        "similarity": round(sim, 4)
                    })
            return parsed_results
        except Exception as e:
            logger.error("Error searching semantic memory vector: %s", e)
            return []

    def delete_memory_fact(self, fact_id: str):
        try:
            self.memory_collection.delete(ids=[fact_id])
        except Exception as e:
            logger.warning("Could not delete fact vector %s: %s", fact_id, e)

vector_store = VectorStoreManager()
