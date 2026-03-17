from pathlib import Path
from llama_index.readers.file import PDFReader
from llama_index.core.node_parser import SentenceSplitter


def load_and_chunk_pdf(file_path: str) -> list:
    """
    Parse a PDF and split it into overlapping text chunks.

    Returns a list of TextNode objects. Each node carries:
      - node.text          — the chunk content
      - node.metadata["filename"]   — source PDF filename
      - node.metadata["page_label"] — page number (set by PDFReader)

    Raises ValueError for unreadable, empty, or unchunkable PDFs.
    """
    path = Path(file_path)

    try:
        reader = PDFReader()
        documents = reader.load_data(file=path)
    except Exception as e:
        raise ValueError(f"Could not read PDF '{path.name}': {e}") from e

    if not documents:
        raise ValueError(f"No text could be extracted from '{path.name}'.")

    # Stamp filename onto every document so it flows through to chunk metadata
    for doc in documents:
        doc.metadata["filename"] = path.name

    splitter = SentenceSplitter(chunk_size=512, chunk_overlap=50)

    try:
        nodes = splitter.get_nodes_from_documents(documents)
    except Exception as e:
        raise ValueError(f"Failed to chunk PDF '{path.name}': {e}") from e

    if not nodes:
        raise ValueError(f"No chunks produced from '{path.name}'.")

    return nodes
