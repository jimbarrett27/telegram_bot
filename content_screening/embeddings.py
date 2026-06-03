"""Embedding utilities for content screening.

Embeddings are computed at ingest time (see ``scanner.process_new_articles``) and
stored in ``articles.embedding`` so a supervised relevance model can later be
trained on them, using the triage decisions as labels. Vectors are serialised as
little-endian float32 via the stdlib ``array`` module (no numpy dependency).
"""

import array
import math
from typing import List, Optional

import requests

from content_screening.models import Article
from gcp_util.secrets import get_openrouter_api_key
from util.logging_util import setup_logger

logger = setup_logger(__name__)

# OpenRouter embedding model (priced ~$0.20 / 1M tokens; abstracts are ~350 tokens).
EMBEDDING_MODEL = "google/gemini-embedding-2"
# The model's maximum (it also supports 768/1536 via Matryoshka truncation).
# Pinned explicitly so every stored vector has the same dimensionality for
# training, regardless of any future change to the API default.
EMBEDDING_DIM = 3072
_EMBEDDING_URL = "https://openrouter.ai/api/v1/embeddings"


def get_embedding(text: str) -> Optional[bytes]:
    """Embed ``text`` and return the vector serialised as float32 bytes.

    Calls OpenRouter's embeddings endpoint directly via ``requests`` — the
    ``openai`` SDK defaults to base64-encoded embeddings, which OpenRouter does
    not return in the form the SDK decodes. Best-effort: returns ``None``
    (logging the error) on empty input or any failure, so embedding never blocks
    article ingestion.
    """
    text = (text or "").strip()
    if not text:
        return None
    try:
        response = requests.post(
            _EMBEDDING_URL,
            headers={
                "Authorization": f"Bearer {get_openrouter_api_key()}",
                "Content-Type": "application/json",
            },
            json={"model": EMBEDDING_MODEL, "input": text, "dimensions": EMBEDDING_DIM},
            timeout=30,
        )
        response.raise_for_status()
        vector = response.json()["data"][0]["embedding"]
        return array.array("f", vector).tobytes()
    except Exception as exc:  # noqa: BLE001 - embedding is best-effort, never fatal
        logger.error("Embedding generation failed: %s", exc)
        return None


def deserialize_embedding(blob: bytes) -> List[float]:
    """Inverse of ``get_embedding``'s serialisation: bytes → list[float]."""
    vector = array.array("f")
    vector.frombytes(blob)
    return list(vector)


def compute_article_embedding(article: Article) -> Optional[bytes]:
    """Compute an embedding for an article from its title and abstract."""
    text = f"{article.title}\n\n{article.abstract or ''}"
    return get_embedding(text)


def compute_similarity(embedding1: bytes, embedding2: bytes) -> float:
    """Cosine similarity between two serialised embedding vectors (0.0–1.0)."""
    a = deserialize_embedding(embedding1)
    b = deserialize_embedding(embedding2)
    if not a or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def find_similar_articles(
    target_embedding: bytes,
    candidate_articles: List[Article],
    threshold: float = 0.7,
) -> List[Article]:
    """Articles whose embedding is at least ``threshold`` similar to the target."""
    similar = []
    for candidate in candidate_articles:
        if candidate.embedding is None:
            continue
        if compute_similarity(target_embedding, candidate.embedding) >= threshold:
            similar.append(candidate)
    return similar
