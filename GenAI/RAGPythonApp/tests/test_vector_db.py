"""
Unit tests for vector_db.py

Uses QdrantClient(":memory:") so no disk I/O occurs and the Streamlit app
does not need to be stopped first.
The embedding model is mocked to return fixed vectors — no HuggingFace
download required.
"""
import pytest
from unittest.mock import MagicMock
from qdrant_client import QdrantClient
from llama_index.core.schema import TextNode

from vector_db import (
    hash_file,
    get_or_create_collection,
    index_chunks,
    retrieve,
    COLLECTION_NAME,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def mem_client():
    """In-memory Qdrant client — isolated per test, no qdrant_storage/ needed."""
    return QdrantClient(":memory:")


@pytest.fixture
def embed_model():
    """Mock embedding model that always returns the same 384-dim unit vector."""
    model = MagicMock()
    model.get_text_embedding.return_value = [0.1] * 384
    return model


@pytest.fixture
def indexed_client(mem_client, embed_model):
    """Client pre-loaded with one TextNode for retrieval tests."""
    node = TextNode(
        text="Neural networks learn patterns from data.",
        metadata={"filename": "ml.pdf", "page_label": "5"},
    )
    index_chunks([node], embed_model, mem_client)
    return mem_client


# ── hash_file ─────────────────────────────────────────────────────────────────

def test_hash_file_is_deterministic():
    assert hash_file(b"hello") == hash_file(b"hello")


def test_hash_file_different_inputs_differ():
    assert hash_file(b"abc") != hash_file(b"xyz")


def test_hash_file_returns_64_char_hex():
    result = hash_file(b"some bytes")
    assert isinstance(result, str)
    assert len(result) == 64
    assert all(c in "0123456789abcdef" for c in result)


# ── get_or_create_collection ──────────────────────────────────────────────────

def test_collection_is_created(mem_client):
    get_or_create_collection(mem_client)
    names = {c.name for c in mem_client.get_collections().collections}
    assert COLLECTION_NAME in names


def test_create_collection_is_idempotent(mem_client):
    """Calling twice does not raise and collection appears exactly once."""
    get_or_create_collection(mem_client)
    get_or_create_collection(mem_client)
    names = [c.name for c in mem_client.get_collections().collections]
    assert names.count(COLLECTION_NAME) == 1


# ── index_chunks + retrieve ───────────────────────────────────────────────────

def test_indexed_node_is_retrievable(indexed_client, embed_model):
    results = retrieve("neural networks", embed_model, indexed_client)
    assert len(results) > 0


def test_retrieve_returns_correct_text(indexed_client, embed_model):
    results = retrieve("neural networks", embed_model, indexed_client)
    texts = [r[0] for r in results]
    assert "Neural networks learn patterns from data." in texts


def test_retrieve_returns_correct_metadata(indexed_client, embed_model):
    results = retrieve("neural networks", embed_model, indexed_client)
    _, filename, page = results[0]
    assert filename == "ml.pdf"
    assert page == "5"


def test_retrieve_returns_three_tuple(indexed_client, embed_model):
    """Each result must be a (text, filename, page_label) triple."""
    results = retrieve("query", embed_model, indexed_client)
    for item in results:
        assert len(item) == 3


def test_retrieve_empty_collection_returns_empty(mem_client, embed_model):
    """Querying a collection with no vectors returns an empty list."""
    get_or_create_collection(mem_client)
    results = retrieve("anything", embed_model, mem_client)
    assert results == []


def test_score_threshold_filters_low_similarity(mem_client):
    """Vectors with near-zero cosine similarity are filtered by score_threshold."""
    # index_embed: unit vector along dimension 0
    index_embed = MagicMock()
    index_embed.get_text_embedding.return_value = [1.0] + [0.0] * 383

    # query_embed: unit vector along dimension 383 — orthogonal to the stored vector
    query_embed = MagicMock()
    query_embed.get_text_embedding.return_value = [0.0] * 383 + [1.0]

    node = TextNode(text="some text", metadata={"filename": "f.pdf", "page_label": "1"})
    index_chunks([node], index_embed, mem_client)

    # Cosine similarity ≈ 0.0 — well below the default threshold of 0.3
    results = retrieve("query", query_embed, mem_client, score_threshold=0.3)
    assert results == []


def test_multiple_nodes_all_indexed(mem_client, embed_model):
    """All indexed nodes are retrievable (up to top_k)."""
    nodes = [
        TextNode(text=f"Document {i}", metadata={"filename": "doc.pdf", "page_label": str(i)})
        for i in range(3)
    ]
    index_chunks(nodes, embed_model, mem_client)
    results = retrieve("document", embed_model, mem_client, top_k=3)
    assert len(results) == 3
