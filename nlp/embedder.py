from __future__ import annotations
import numpy as np
from sentence_transformers import SentenceTransformer

_model = None
MODEL_NAME = "all-MiniLM-L6-v2"


def get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(MODEL_NAME)
    return _model


def embed(texts: list[str]) -> np.ndarray:
    """Embed a list of strings. Returns (N, 384) float32 array."""
    model = get_model()
    return model.encode(texts, convert_to_numpy=True, show_progress_bar=False)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity between two 1-D vectors."""
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def find_duplicates(texts: list[str], threshold: float = 0.85) -> list[tuple[int, int]]:
    """
    Returns pairs of indices whose texts are semantically similar above threshold.
    Used for cross-collection deduplication.
    """
    if len(texts) < 2:
        return []
    embeddings = embed(texts)
    duplicates = []
    for i in range(len(embeddings)):
        for j in range(i + 1, len(embeddings)):
            sim = cosine_similarity(embeddings[i], embeddings[j])
            if sim >= threshold:
                duplicates.append((i, j))
    return duplicates
