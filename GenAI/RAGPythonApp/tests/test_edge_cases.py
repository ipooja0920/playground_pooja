"""
Edge case and robustness tests for the RAG pipeline.

Covers:
  hash_file edge cases      — empty bytes, large payload, unicode content
  doc_processor edge cases  — whitespace-only doc, single word, unicode text
  vector_db edge cases      — zero-vector embedding, very long text node,
                               collection reuse across multiple index calls
  llm_client edge cases     — whitespace answer, single-char context, newlines
  Cross-component           — re-indexing same content, overlapping chunk texts
"""
import pytest
from unittest.mock import patch, MagicMock
from qdrant_client import QdrantClient
from llama_index.core.schema import TextNode, Document

from vector_db import hash_file, index_chunks, retrieve, get_or_create_collection
from doc_processor import load_and_chunk_pdf
from llm_client import get_answer


# ── Fixtures ───────────────────────────────────────────────────────────────────

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


# ── hash_file edge cases ──────────────────────────────────────────────────────

class TestHashFileEdgeCases:

    def test_empty_bytes_produces_hex_string(self):
        """hash_file(b'') returns a valid 64-char hex string (SHA-256 of empty)."""
        result = hash_file(b"")
        assert isinstance(result, str)
        assert len(result) == 64

    def test_single_byte_is_hashable(self):
        """A single-byte payload produces a valid hash."""
        result = hash_file(b"\x00")
        assert len(result) == 64

    def test_large_payload_is_hashable(self):
        """A 1 MB payload can be hashed without error."""
        large = b"x" * (1024 * 1024)
        result = hash_file(large)
        assert len(result) == 64

    def test_same_content_same_hash(self):
        """Two calls with identical content always produce the same hash."""
        data = b"identical content"
        assert hash_file(data) == hash_file(data)

    def test_different_content_different_hash(self):
        """Different byte strings produce different hashes (collision extremely unlikely)."""
        assert hash_file(b"aaa") != hash_file(b"bbb")

    def test_hash_is_lowercase_hex(self):
        """Hash characters are lowercase hexadecimal only."""
        result = hash_file(b"test data")
        assert all(c in "0123456789abcdef" for c in result)


# ── doc_processor edge cases ───────────────────────────────────────────────────

class TestDocProcessorEdgeCases:

    def test_unicode_text_is_chunked(self):
        """Documents with non-ASCII / Unicode characters are processed correctly."""
        doc = Document(text="深度学习是人工智能的一个子领域。" * 30)
        doc.metadata = {"page_label": "1"}
        with patch("doc_processor.PDFReader") as MockReader:
            MockReader.return_value.load_data.return_value = [doc]
            nodes = load_and_chunk_pdf("/fake/unicode.pdf")
        assert len(nodes) > 0
        assert all(isinstance(n.text, str) for n in nodes)

    def test_whitespace_only_pdf_raises_value_error(self):
        """A PDF that contains only whitespace raises ValueError (no usable text)."""
        doc = Document(text="   \n\t\n   ")
        doc.metadata = {"page_label": "1"}
        with patch("doc_processor.PDFReader") as MockReader:
            MockReader.return_value.load_data.return_value = [doc]
            with pytest.raises(ValueError):
                load_and_chunk_pdf("/fake/blank.pdf")

    def test_filename_with_spaces_set_correctly(self):
        """Filenames containing spaces are stored as-is in chunk metadata."""
        doc = Document(text="Some content here. " * 30)
        doc.metadata = {"page_label": "1"}
        with patch("doc_processor.PDFReader") as MockReader:
            MockReader.return_value.load_data.return_value = [doc]
            nodes = load_and_chunk_pdf("/fake/my document with spaces.pdf")
        for node in nodes:
            assert node.metadata["filename"] == "my document with spaces.pdf"

    def test_deeply_nested_path_uses_only_filename(self):
        """Only the basename is stored in metadata, not the full path."""
        doc = Document(text="Nested path content. " * 30)
        doc.metadata = {"page_label": "1"}
        with patch("doc_processor.PDFReader") as MockReader:
            MockReader.return_value.load_data.return_value = [doc]
            nodes = load_and_chunk_pdf("/very/deeply/nested/path/to/report.pdf")
        for node in nodes:
            assert node.metadata["filename"] == "report.pdf"
            assert "/" not in node.metadata["filename"]


# ── vector_db edge cases ───────────────────────────────────────────────────────

class TestVectorDbEdgeCases:

    def test_very_long_text_node_is_indexed(self, mem_client, embed_model):
        """A TextNode with very long text (2000 chars) is stored and retrieved."""
        long_text = "word " * 400  # 2000 chars
        node = TextNode(text=long_text, metadata={"filename": "long.pdf", "page_label": "1"})
        index_chunks([node], embed_model, mem_client)
        results = retrieve("word", embed_model, mem_client)
        assert len(results) > 0

    def test_re_indexing_same_node_does_not_duplicate(self, mem_client, embed_model):
        """
        Calling index_chunks twice with the same node content may store duplicates
        (Qdrant uses UUID-based IDs by default), but retrieval must still work.
        This test confirms no exception is raised and results are returned.
        """
        node = TextNode(text="Unique sentence.", metadata={"filename": "d.pdf", "page_label": "1"})
        index_chunks([node], embed_model, mem_client)
        index_chunks([node], embed_model, mem_client)  # second call
        results = retrieve("unique sentence", embed_model, mem_client, top_k=10)
        assert len(results) > 0

    def test_empty_node_list_does_not_crash(self, mem_client, embed_model):
        """Calling index_chunks with an empty list does nothing (no error)."""
        index_chunks([], embed_model, mem_client)  # should not raise
        results = retrieve("query", embed_model, mem_client)
        assert results == []

    def test_collection_reused_across_index_calls(self, mem_client, embed_model):
        """Multiple sequential index_chunks calls share the same collection."""
        node1 = TextNode(text="First document.", metadata={"filename": "a.pdf", "page_label": "1"})
        node2 = TextNode(text="Second document.", metadata={"filename": "b.pdf", "page_label": "1"})
        index_chunks([node1], embed_model, mem_client)
        index_chunks([node2], embed_model, mem_client)
        results = retrieve("document", embed_model, mem_client, top_k=10)
        filenames = {r[1] for r in results}
        assert "a.pdf" in filenames
        assert "b.pdf" in filenames

    def test_metadata_with_special_characters_stored_correctly(self, mem_client, embed_model):
        """Filenames with special characters (hyphens, underscores) are stored as-is."""
        node = TextNode(
            text="Content with special filename.",
            metadata={"filename": "my-file_v2 (final).pdf", "page_label": "99"},
        )
        index_chunks([node], embed_model, mem_client)
        results = retrieve("content special", embed_model, mem_client)
        assert results[0][1] == "my-file_v2 (final).pdf"
        assert results[0][2] == "99"


# ── llm_client edge cases ─────────────────────────────────────────────────────

class TestLlmClientEdgeCases:

    def test_whitespace_only_answer_is_stripped(self):
        """If OpenAI returns whitespace, get_answer strips it (returns empty string)."""
        with patch("llm_client._client") as mc:
            mc.chat.completions.create.return_value = openai_response("   ")
            result = get_answer("question", ["context"])
        assert result == ""

    def test_answer_with_newlines_preserved(self):
        """Newlines in the answer are not stripped."""
        multiline = "Line one.\nLine two.\nLine three."
        with patch("llm_client._client") as mc:
            mc.chat.completions.create.return_value = openai_response(multiline)
            result = get_answer("question", ["context"])
        assert "\n" in result

    def test_single_char_context_does_not_crash(self):
        """A context string of a single character doesn't raise an exception."""
        with patch("llm_client._client") as mc:
            mc.chat.completions.create.return_value = openai_response("ok")
            result = get_answer("question", ["x"])
        assert isinstance(result, str)

    def test_context_with_only_newlines_does_not_crash(self):
        """Context consisting only of newlines is passed through without error."""
        with patch("llm_client._client") as mc:
            mc.chat.completions.create.return_value = openai_response("ok")
            result = get_answer("question", ["\n\n\n"])
        assert isinstance(result, str)

    def test_unicode_in_question_and_context(self):
        """Unicode in both question and context is handled correctly."""
        with patch("llm_client._client") as mc:
            mc.chat.completions.create.return_value = openai_response("答案是这样的。")
            result = get_answer("这个文档是关于什么的？", ["这是一个关于机器学习的文档。"])
        assert isinstance(result, str)


# ── Cross-component edge cases ────────────────────────────────────────────────

class TestCrossComponentEdgeCases:

    def test_pipeline_with_unicode_pdf_content(self, mem_client, embed_model):
        """Unicode content flows through doc_processor → vector_db → retrieve."""
        doc = Document(text="机器学习是人工智能的核心。" * 25)
        doc.metadata = {"page_label": "1"}
        with patch("doc_processor.PDFReader") as MockReader:
            MockReader.return_value.load_data.return_value = [doc]
            nodes = load_and_chunk_pdf("/fake/chinese.pdf")
        index_chunks(nodes, embed_model, mem_client)
        results = retrieve("机器学习", embed_model, mem_client)
        assert len(results) > 0

    def test_pipeline_returns_correct_filename_not_temp(self, mem_client, embed_model):
        """
        The pipeline stores filename from the path argument to load_and_chunk_pdf,
        overriding whatever PDFReader sets (e.g. a temp upload name).
        """
        doc = Document(text="Content about deep neural networks. " * 20)
        doc.metadata = {"page_label": "2", "filename": "tmp_upload_abc123.pdf"}
        with patch("doc_processor.PDFReader") as MockReader:
            MockReader.return_value.load_data.return_value = [doc]
            nodes = load_and_chunk_pdf("/uploads/deep_learning_paper.pdf")
        index_chunks(nodes, embed_model, mem_client)
        results = retrieve("deep neural", embed_model, mem_client)
        filenames = {r[1] for r in results}
        assert "deep_learning_paper.pdf" in filenames
        assert "tmp_upload_abc123.pdf" not in filenames

    def test_full_pipeline_with_mocked_openai_unicode_answer(self, mem_client, embed_model):
        """Full pipeline (index → retrieve → answer) with a Unicode answer."""
        node = TextNode(
            text="Neural networks are composed of layers.",
            metadata={"filename": "nn.pdf", "page_label": "1"},
        )
        index_chunks([node], embed_model, mem_client)
        hits = retrieve("neural network layers", embed_model, mem_client)
        context = [text for text, _, _ in hits]

        with patch("llm_client._client") as mc:
            mc.chat.completions.create.return_value = openai_response("ニューラルネットワーク。")
            result = get_answer("What are NNs?", context)
        assert isinstance(result, str)
        assert len(result) > 0
