"""
Unit tests for doc_processor.py

PDFReader is mocked so no real PDF file is needed.
Tests cover: valid PDF, empty PDF, unreadable PDF, metadata propagation,
and chunk count / size behaviour.
"""
import pytest
from unittest.mock import patch, MagicMock
from llama_index.core.schema import Document

from doc_processor import load_and_chunk_pdf


# ── Helpers ──────────────────────────────────────────────────────────────────

def make_document(text: str, page_label: str = "1") -> Document:
    doc = Document(text=text)
    doc.metadata = {"page_label": page_label}
    return doc


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_returns_nonempty_list_of_nodes():
    """A PDF with enough text produces at least one chunk."""
    doc = make_document("Machine learning is a field of AI. " * 30)
    with patch("doc_processor.PDFReader") as MockReader:
        MockReader.return_value.load_data.return_value = [doc]
        nodes = load_and_chunk_pdf("/fake/path/test.pdf")
    assert len(nodes) > 0


def test_nodes_have_text():
    """Every returned node has non-empty text."""
    doc = make_document("Deep learning uses neural networks. " * 30)
    with patch("doc_processor.PDFReader") as MockReader:
        MockReader.return_value.load_data.return_value = [doc]
        nodes = load_and_chunk_pdf("/fake/path/test.pdf")
    assert all(node.text.strip() for node in nodes)


def test_filename_metadata_is_set_from_path():
    """Chunk metadata carries the filename derived from the file path, not any
    pre-existing value stamped by PDFReader."""
    doc = make_document("Some document content. " * 30)
    doc.metadata["filename"] = "old_name.pdf"  # should be overwritten

    with patch("doc_processor.PDFReader") as MockReader:
        MockReader.return_value.load_data.return_value = [doc]
        nodes = load_and_chunk_pdf("/fake/path/myfile.pdf")

    for node in nodes:
        assert node.metadata.get("filename") == "myfile.pdf"


def test_page_label_metadata_is_preserved():
    """page_label set by PDFReader flows through to the chunks."""
    doc = make_document("Content from page three. " * 30, page_label="3")
    with patch("doc_processor.PDFReader") as MockReader:
        MockReader.return_value.load_data.return_value = [doc]
        nodes = load_and_chunk_pdf("/fake/path/doc.pdf")
    assert all(node.metadata.get("page_label") == "3" for node in nodes)


def test_empty_pdf_raises_value_error():
    """A PDF with no extractable text raises ValueError."""
    with patch("doc_processor.PDFReader") as MockReader:
        MockReader.return_value.load_data.return_value = []
        with pytest.raises(ValueError, match="No text could be extracted"):
            load_and_chunk_pdf("/fake/path/empty.pdf")


def test_unreadable_pdf_raises_value_error():
    """A corrupted / unreadable PDF raises ValueError."""
    with patch("doc_processor.PDFReader") as MockReader:
        MockReader.return_value.load_data.side_effect = Exception("corrupt file")
        with pytest.raises(ValueError, match="Could not read PDF"):
            load_and_chunk_pdf("/fake/path/corrupt.pdf")


def test_multiple_pages_produce_chunks():
    """Multiple-page documents produce chunks from all pages."""
    docs = [
        make_document("Content from page one. " * 20, page_label="1"),
        make_document("Content from page two. " * 20, page_label="2"),
    ]
    with patch("doc_processor.PDFReader") as MockReader:
        MockReader.return_value.load_data.return_value = docs
        nodes = load_and_chunk_pdf("/fake/path/multipage.pdf")
    assert len(nodes) >= 2
