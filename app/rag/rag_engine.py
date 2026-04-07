"""Vector-based RAG Engine with FAISS"""
import json
import faiss
import numpy as np
from app.utils.embeddings import get_embeddings, embed_text, cosine_similarity
import os

KNOWLEDGE_BASE_FILE = "app/rag/knowledge_base.json"
FAISS_INDEX_FILE = "app/rag/faiss_index.bin"
KB_EMBEDDINGS_FILE = "app/rag/kb_embeddings.npy"

class RAGEngine:
    def __init__(self):
        self.knowledge_base = self._load_kb()
        self.documents = list(self.knowledge_base.values())
        self.index = None
        self.embeddings = None
        self._initialize_index()
    
    def _load_kb(self):
        """Load knowledge base from JSON"""
        if not os.path.exists(KNOWLEDGE_BASE_FILE):
            return {}
        with open(KNOWLEDGE_BASE_FILE) as f:
            return json.load(f)
    
    def _initialize_index(self):
        """Initialize FAISS index from saved files or create new one"""
        if os.path.exists(FAISS_INDEX_FILE) and os.path.exists(KB_EMBEDDINGS_FILE):
            # Load existing index
            self.index = faiss.read_index(FAISS_INDEX_FILE)
            self.embeddings = np.load(KB_EMBEDDINGS_FILE)
        else:
            # Create new index
            self._rebuild_index()
    
    def _rebuild_index(self):
        """Rebuild FAISS index from knowledge base"""
        if not self.documents:
            self.index = faiss.IndexFlatL2(384)  # 384 for textembedding-gecko
            self.embeddings = np.array([])
            return
        
        # Get embeddings for all documents
        doc_texts = [json.dumps(doc) if isinstance(doc, dict) else str(doc) 
                     for doc in self.documents]
        embeddings = get_embeddings(doc_texts)
        
        # Create FAISS index
        dimension = embeddings.shape[1]
        index = faiss.IndexFlatL2(dimension)
        index.add(embeddings.astype(np.float32))
        
        self.index = index
        self.embeddings = embeddings
        
        # Save index and embeddings
        os.makedirs("app/rag", exist_ok=True)
        faiss.write_index(self.index, FAISS_INDEX_FILE)
        np.save(KB_EMBEDDINGS_FILE, embeddings)
    
    def search(self, query: str, top_k: int = 3) -> list[dict]:
        """Search similar documents using vector similarity"""
        if not self.documents or self.index.ntotal == 0:
            return []
        
        # Embed the query
        query_embedding = embed_text(query)
        query_array = np.array([query_embedding]).astype(np.float32)
        
        # Search
        distances, indices = self.index.search(query_array, min(top_k, len(self.documents)))
        
        results = []
        for i, idx in enumerate(indices[0]):
            if idx == -1:  # No more results
                break
            
            doc = self.documents[idx]
            # Distance in L2 is actually similarity (lower is better for L2)
            similarity = 1 / (1 + distances[0][i])  # Convert L2 distance to similarity
            
            results.append({
                "document": doc,
                "similarity": float(similarity),
                "rank": i + 1
            })
        
        return results
    
    def add_document(self, error_type: str, solution: dict):
        """Add a new document to the knowledge base"""
        self.knowledge_base[error_type] = solution
        self.documents.append(solution)
        
        # Save to JSON
        os.makedirs("app/rag", exist_ok=True)
        with open(KNOWLEDGE_BASE_FILE, 'w') as f:
            json.dump(self.knowledge_base, f, indent=2)
        
        # Rebuild index
        self._rebuild_index()

# Singleton instance
_rag_engine = None

def get_rag_engine():
    """Get or create RAG engine instance"""
    global _rag_engine
    if _rag_engine is None:
        _rag_engine = RAGEngine()
    return _rag_engine
