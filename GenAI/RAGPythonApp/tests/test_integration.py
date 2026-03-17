"""
Integration tests for the full RAG pipeline.

Tests the components working together end-to-end:
  doc_processor → vector_db (index) → vector_db (retrieve) → llm_client

Uses:
- QdrantClient(":memory:") — no disk I/O, no storage lock
- Mocked BGE embed model     — no model download required
- Mocked OpenAI client       — no API calls, no billing
"""
import pytest
from unittest.mock import patch, MagicMock
from qdrant_client import QdrantClient
from llama_index.core.schema import TextNode, Document

from vector_db import index_chunks, retrieve, get_or_create_collection
from doc_processor import load_and_chunk_pdf
from llm_client import get_answer


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def mem_client():
    return QdrantClient(":memory:")


@pytest.fixture
def embed_model():
    m = MagicMock()
    m.get_text_embedding.return_value = [0.5] * 384
    return m


def openai_response(content: str) -> MagicMock:
    r = MagicMock()
    r.choices[0].message.content = content
    return r


# ── Full pipeline tests ────────────────────────────────────────────────────────

class TestIndexThenRetrieve:

    def test_indexed_content_is_retrievable(self, mem_client, embed_model):
        """Content stored with index_chunks() is returned by retrieve()."""
        node = TextNode(
            text="Gradient descent minimises the loss function iteratively.",
            metadata={"filename": "ml.pdf", "page_label": "10"},
        )
        index_chunks([node], embed_model, mem_client)
        results = retrieve("gradient descent", embed_model, mem_client)
        assert len(results) >= 1

    def test_retrieved_text_matches_indexed_text(self, mem_client, embed_model):
        """The text returned by retrieve() is exactly what was indexed."""
        node = TextNode(
            text="Backpropagation computes gradients via the chain rule.",
            metadata={"filename": "nn.pdf", "page_label": "5"},
        )
        index_chunks([node], embed_model, mem_client)
        results = retrieve("backpropagation", embed_model, mem_client)
        assert results[0][0] == "Backpropagation computes gradients via the chain rule."

    def test_citations_carry_filename_and_page(self, mem_client, embed_model):
        """Every retrieved result includes the source filename and page number."""
        node = TextNode(
            text="Support Vector Machines maximise the margin between classes.",
            metadata={"filename": "svm_chapter.pdf", "page_label": "42"},
        )
        index_chunks([node], embed_model, mem_client)
        results = retrieve("SVM", embed_model, mem_client)
        _, filename, page = results[0]
        assert filename == "svm_chapter.pdf"
        assert page == "42"

    def test_chunks_from_multiple_pdfs_coexist(self, mem_client, embed_model):
        """Indexing two PDFs puts both into the same collection."""
        nodes = [
            TextNode(text="K-means groups data by centroid distance.", metadata={"filename": "a.pdf", "page_label": "1"}),
            TextNode(text="DBSCAN uses density to find clusters.", metadata={"filename": "b.pdf", "page_label": "3"}),
        ]
        index_chunks(nodes, embed_model, mem_client)
        results = retrieve("clustering", embed_model, mem_client, top_k=5)
        filenames = {r[1] for r in results}
        assert "a.pdf" in filenames
        assert "b.pdf" in filenames


class TestRetrieveThenAnswer:

    def test_full_pipeline_returns_string_answer(self, mem_client, embed_model):
        """index → retrieve → GPT-4o → answer completes without error."""
        node = TextNode(
            text="Random forests combine many decision trees to reduce overfitting.",
            metadata={"filename": "rf.pdf", "page_label": "8"},
        )
        index_chunks([node], embed_model, mem_client)
        hits = retrieve("random forest", embed_model, mem_client)
        context = [text for text, _, _ in hits]

        with patch("llm_client._client") as mc:
            mc.chat.completions.create.return_value = openai_response(
                "Random forests aggregate multiple decision trees."
            )
            answer = get_answer("What is a random forest?", context)

        assert isinstance(answer, str)
        assert len(answer) > 0

    def test_retrieved_context_is_passed_to_llm(self, mem_client, embed_model):
        """The text from retrieved chunks appears in the LLM user message."""
        node = TextNode(
            text="Regularisation prevents overfitting by adding a penalty term.",
            metadata={"filename": "reg.pdf", "page_label": "12"},
        )
        index_chunks([node], embed_model, mem_client)
        hits = retrieve("regularisation", embed_model, mem_client)
        context = [text for text, _, _ in hits]

        with patch("llm_client._client") as mc:
            mc.chat.completions.create.return_value = openai_response("answer")
            get_answer("What is regularisation?", context)
            messages = mc.chat.completions.create.call_args.kwargs["messages"]

        user_msg = next(m["content"] for m in messages if m["role"] == "user")
        assert "Regularisation prevents overfitting" in user_msg

    def test_openai_failure_does_not_corrupt_qdrant(self, mem_client, embed_model):
        """An OpenAI error raises RuntimeError but leaves Qdrant intact."""
        node = TextNode(
            text="Decision trees recursively split on features.",
            metadata={"filename": "dt.pdf", "page_label": "2"},
        )
        index_chunks([node], embed_model, mem_client)

        with patch("llm_client._client") as mc:
            mc.chat.completions.create.side_effect = Exception("rate limit")
            with pytest.raises(RuntimeError):
                get_answer("question", ["context"])

        # Qdrant should still be queryable after LLM failure
        results = retrieve("decision tree", embed_model, mem_client)
        assert len(results) > 0


class TestDocProcessorToVectorDb:

    def test_pdf_chunks_are_indexable_and_retrievable(self, mem_client, embed_model):
        """Chunks produced by load_and_chunk_pdf() can be indexed and retrieved."""
        mock_doc = Document(text="Ensemble methods combine multiple models. " * 20)
        mock_doc.metadata = {"page_label": "7"}

        with patch("doc_processor.PDFReader") as MockReader:
            MockReader.return_value.load_data.return_value = [mock_doc]
            nodes = load_and_chunk_pdf("/fake/path/ensemble.pdf")

        index_chunks(nodes, embed_model, mem_client)
        results = retrieve("ensemble methods", embed_model, mem_client)
        assert len(results) > 0

    def test_filename_from_path_appears_in_citations(self, mem_client, embed_model):
        """The filename in citations comes from the upload path, not PDFReader metadata."""
        mock_doc = Document(text="Convolutional layers detect spatial features. " * 20)
        mock_doc.metadata = {"page_label": "3", "filename": "temp_upload_xyz.pdf"}

        with patch("doc_processor.PDFReader") as MockReader:
            MockReader.return_value.load_data.return_value = [mock_doc]
            nodes = load_and_chunk_pdf("/fake/path/cnn_guide.pdf")

        index_chunks(nodes, embed_model, mem_client)
        results = retrieve("convolutional", embed_model, mem_client)

        filenames = {r[1] for r in results}
        assert "cnn_guide.pdf" in filenames
        assert "temp_upload_xyz.pdf" not in filenames

    def test_no_docs_indexed_returns_empty_list(self, mem_client, embed_model):
        """Querying with no documents indexed returns []."""
        get_or_create_collection(mem_client)
        results = retrieve("any question", embed_model, mem_client)
        assert results == []
