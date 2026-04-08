"""Embedding service using Vertex AI"""
from vertexai.language_models import TextEmbeddingModel
import vertexai
import numpy as np

import os
project_id = os.getenv("GOOGLE_CLOUD_PROJECT", "auto-sre-ai-multi-agent-492710")
vertexai.init(project=project_id, location="us-central1")

# Use latest available embedding model
try:
    embedding_model = TextEmbeddingModel.from_pretrained("text-embedding-004")
except Exception:
    # Fallback to gecko if text-embedding-004 not available
    embedding_model = TextEmbeddingModel.from_pretrained("textembedding-gecko@latest")

def get_embeddings(texts: list[str]) -> np.ndarray:
    """Get embeddings for a list of texts"""
    try:
        embeddings = embedding_model.get_embeddings(texts)
        return np.array([e.values for e in embeddings])
    except Exception as e:
        print(f"Error getting embeddings: {e}")
        raise

def embed_text(text: str) -> list[float]:
    """Embed a single text"""
    embedding = embedding_model.get_embeddings([text])[0]
    return embedding.values

def cosine_similarity(vec1, vec2):
    """Calculate cosine similarity between two vectors"""
    return np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))
