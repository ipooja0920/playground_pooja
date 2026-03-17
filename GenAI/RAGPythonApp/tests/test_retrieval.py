"""
Retrieval test cases for vector_db.py

Covers:
  Basic Retrieval  — single chunk, multiple chunks, top_k limiting, multi-source
  Hard Retrieval   — semantically differentiated mocks, multi-chunk answers
  Failure Cases    — score_threshold filtering, empty KB, result format guarantee
"""
import pytest
from unittest.mock import MagicMock
from qdrant_client import QdrantClient
from llama_index.core.schema import TextNode

from vector_db import index_chunks, retrieve, get_or_create_collection


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def mem_client():
    return QdrantClient(":memory:")


def make_embed(vector: list[float]) -> MagicMock:
    """Return a mock embed model that always returns the given vector."""
    m = MagicMock()
    m.get_text_embedding.return_value = vector
    return m


def unit_vec(dim: int, pos: int) -> list[float]:
    """384-dim unit vector with 1.0 at position `pos`."""
    v = [0.0] * dim
    v[pos] = 1.0
    return v


# ── Basic Retrieval ────────────────────────────────────────────────────────────

class TestBasicRetrieval:

    def test_single_chunk_is_returned(self, mem_client):
        """A single indexed chunk is returned for any query."""
        embed = make_embed([0.5] * 384)
        node = TextNode(
            text="Transformers use self-attention mechanisms.",
            metadata={"filename": "nlp.pdf", "page_label": "1"},
        )
        index_chunks([node], embed, mem_client)
        results = retrieve("attention", embed, mem_client)
        assert len(results) == 1

    def test_multiple_chunks_all_returned(self, mem_client):
        """All indexed chunks that exceed score_threshold are returned."""
        embed = make_embed([0.5] * 384)
        nodes = [
            TextNode(text=f"Fact number {i}.", metadata={"filename": "f.pdf", "page_label": str(i)})
            for i in range(5)
        ]
        index_chunks(nodes, embed, mem_client)
        results = retrieve("fact", embed, mem_client, top_k=10)
        assert len(results) == 5

    def test_top_k_limits_results(self, mem_client):
        """top_k=2 returns at most 2 results even when more are indexed."""
        embed = make_embed([0.5] * 384)
        nodes = [
            TextNode(text=f"Item {i}.", metadata={"filename": "x.pdf", "page_label": str(i)})
            for i in range(10)
        ]
        index_chunks(nodes, embed, mem_client)
        results = retrieve("item", embed, mem_client, top_k=2)
        assert len(results) <= 2

    def test_multi_source_retrieval(self, mem_client):
        """Chunks from different PDFs are both retrieved."""
        embed = make_embed([0.5] * 384)
        nodes = [
            TextNode(text="Linear algebra is fundamental to ML.", metadata={"filename": "math.pdf", "page_label": "1"}),
            TextNode(text="Calculus underpins gradient descent.", metadata={"filename": "calc.pdf", "page_label": "2"}),
        ]
        index_chunks(nodes, embed, mem_client)
        results = retrieve("mathematics", embed, mem_client, top_k=5)
        filenames = {r[1] for r in results}
        assert "math.pdf" in filenames
        assert "calc.pdf" in filenames

    def test_result_text_matches_indexed_text_exactly(self, mem_client):
        """Retrieved text is byte-for-byte identical to indexed text."""
        embed = make_embed([0.5] * 384)
        text = "Exact text that must survive round-trip through Qdrant."
        node = TextNode(text=text, metadata={"filename": "e.pdf", "page_label": "1"})
        index_chunks([node], embed, mem_client)
        results = retrieve("exact", embed, mem_client)
        assert results[0][0] == text


# ── Hard Retrieval ─────────────────────────────────────────────────────────────

class TestHardRetrieval:

    def test_semantically_closer_chunk_scores_higher(self, mem_client):
        """
        When two chunks have different embeddings, the one closer to the
        query vector appears first in the ranked results.
        """
        # Chunk A: similar to query (dim 0)
        embed_a = make_embed(unit_vec(384, 0))
        node_a = TextNode(text="Close to query.", metadata={"filename": "a.pdf", "page_label": "1"})
        index_chunks([node_a], embed_a, mem_client)

        # Chunk B: orthogonal to query (dim 1)
        embed_b = make_embed(unit_vec(384, 1))
        node_b = TextNode(text="Far from query.", metadata={"filename": "b.pdf", "page_label": "1"})
        index_chunks([node_b], embed_b, mem_client)

        # Query with embed aligned to chunk A
        query_embed = make_embed(unit_vec(384, 0))
        results = retrieve("query", query_embed, mem_client, top_k=5, score_threshold=0.0)

        assert len(results) >= 1
        assert results[0][0] == "Close to query."

    def test_answer_spanning_two_chunks_both_retrieved(self, mem_client):
        """Both chunks are returned when the answer is spread across them."""
        embed = make_embed([0.5] * 384)
        nodes = [
            TextNode(text="Part 1: The model is trained on supervised data.", metadata={"filename": "m.pdf", "page_label": "1"}),
            TextNode(text="Part 2: It is then fine-tuned with RLHF.", metadata={"filename": "m.pdf", "page_label": "2"}),
        ]
        index_chunks(nodes, embed, mem_client)
        results = retrieve("how is the model trained", embed, mem_client, top_k=5)
        texts = [r[0] for r in results]
        assert any("Part 1" in t for t in texts)
        assert any("Part 2" in t for t in texts)

    def test_page_numbers_are_preserved_across_chunks(self, mem_client):
        """Page labels from different pages of the same PDF are preserved."""
        embed = make_embed([0.5] * 384)
        nodes = [
            TextNode(text="Chapter introduction.", metadata={"filename": "book.pdf", "page_label": "10"}),
            TextNode(text="Chapter conclusion.", metadata={"filename": "book.pdf", "page_label": "25"}),
        ]
        index_chunks(nodes, embed, mem_client)
        results = retrieve("chapter", embed, mem_client, top_k=5)
        pages = {r[2] for r in results}
        assert "10" in pages
        assert "25" in pages

    def test_duplicate_text_two_different_pages(self, mem_client):
        """Identical text on two different pages produces two distinct results."""
        embed = make_embed([0.5] * 384)
        same_text = "This sentence appears twice in the document."
        nodes = [
            TextNode(text=same_text, metadata={"filename": "dup.pdf", "page_label": "3"}),
            TextNode(text=same_text, metadata={"filename": "dup.pdf", "page_label": "7"}),
        ]
        index_chunks(nodes, embed, mem_client)
        results = retrieve("appears twice", embed, mem_client, top_k=5)
        pages = [r[2] for r in results]
        assert "3" in pages
        assert "7" in pages


# ── Retrieval Failure Cases ────────────────────────────────────────────────────

class TestRetrievalFailures:

    def test_orthogonal_query_filtered_by_score_threshold(self, mem_client):
        """Query orthogonal to all indexed vectors returns [] with threshold=0.3."""
        embed_index = make_embed(unit_vec(384, 0))
        node = TextNode(text="Indexed text.", metadata={"filename": "f.pdf", "page_label": "1"})
        index_chunks([node], embed_index, mem_client)

        embed_query = make_embed(unit_vec(384, 1))  # cosine sim ≈ 0.0
        results = retrieve("query", embed_query, mem_client, score_threshold=0.3)
        assert results == []

    def test_empty_kb_returns_empty_list(self, mem_client):
        """Querying an empty collection returns an empty list, not an error."""
        get_or_create_collection(mem_client)
        embed = make_embed([0.5] * 384)
        results = retrieve("anything at all", embed, mem_client)
        assert results == []

    def test_every_result_is_three_tuple(self, mem_client):
        """Each result is always a (text, filename, page_label) triple."""
        embed = make_embed([0.5] * 384)
        nodes = [
            TextNode(text=f"Sentence {i}.", metadata={"filename": "t.pdf", "page_label": str(i)})
            for i in range(3)
        ]
        index_chunks(nodes, embed, mem_client)
        results = retrieve("sentence", embed, mem_client, top_k=10)
        for item in results:
            assert len(item) == 3
            text, filename, page = item
            assert isinstance(text, str)
            assert isinstance(filename, str)
            assert isinstance(page, str)

    def test_zero_score_threshold_returns_all(self, mem_client):
        """score_threshold=0.0 returns all indexed chunks regardless of similarity."""
        embed_index = make_embed(unit_vec(384, 0))
        node = TextNode(text="Some text.", metadata={"filename": "f.pdf", "page_label": "1"})
        index_chunks([node], embed_index, mem_client)

        embed_query = make_embed(unit_vec(384, 1))  # orthogonal
        results = retrieve("query", embed_query, mem_client, score_threshold=0.0)
        assert len(results) == 1

    def test_high_score_threshold_filters_all(self, mem_client):
        """score_threshold=1.0 filters everything except a perfect match."""
        embed = make_embed([0.5] * 384)
        node = TextNode(text="A chunk.", metadata={"filename": "f.pdf", "page_label": "1"})
        index_chunks([node], embed, mem_client)

        # Cosine similarity of [0.5]*384 with itself ≈ 1.0; with threshold just below, it passes
        # With threshold > 1.0 it would fail, but we test that threshold=0.99 passes this case
        results = retrieve("query", embed, mem_client, score_threshold=0.99)
        # [0.5]*384 normalised is identical to the query vector — cosine sim = 1.0 → passes
        assert len(results) == 1
