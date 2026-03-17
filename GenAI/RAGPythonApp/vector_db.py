import hashlib
from pathlib import Path

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from llama_index.embeddings.huggingface import HuggingFaceEmbedding

EMBED_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
VECTOR_SIZE = 384  # all-MiniLM-L6-v2 output dimension
QDRANT_PATH = str(Path(__file__).parent / "qdrant_storage")
COLLECTION_NAME = "rag_docs"


def get_embed_model() -> HuggingFaceEmbedding:
    """
    Load the HuggingFace embedding model.
    Wrap this in @st.cache_resource in app.py so it loads only once.
    """
    return HuggingFaceEmbedding(model_name=EMBED_MODEL_NAME)


def get_qdrant_client() -> QdrantClient:
    """Return a persistent local Qdrant client (no Docker required)."""
    return QdrantClient(path=QDRANT_PATH)


def get_or_create_collection(client: QdrantClient, collection_name: str = COLLECTION_NAME) -> None:
    """Create the Qdrant collection if it doesn't already exist."""
    existing = {c.name for c in client.get_collections().collections}
    if collection_name not in existing:
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )


def index_chunks(
    nodes: list,
    embed_model: HuggingFaceEmbedding,
    client: QdrantClient,
    collection_name: str = COLLECTION_NAME,
) -> None:
    """
    Embed text nodes and upsert into Qdrant.
    Each point carries text, filename, and page_label in its payload.
    """
    get_or_create_collection(client, collection_name)

    points = []
    for node in nodes:
        embedding = embed_model.get_text_embedding(node.text)
        points.append(
            PointStruct(
                id=node.node_id,  # LlamaIndex node IDs are UUIDs
                vector=embedding,
                payload={
                    "text": node.text,
                    "filename": node.metadata.get("filename", ""),
                    "page_label": node.metadata.get("page_label", ""),
                },
            )
        )

    if points:
        client.upsert(collection_name=collection_name, points=points)


def retrieve(
    question: str,
    embed_model: HuggingFaceEmbedding,
    client: QdrantClient,
    collection_name: str = COLLECTION_NAME,
    top_k: int = 5,
) -> list[tuple[str, str, str]]:
    """
    Embed the query and return the top-k most relevant chunks.
    Returns a list of (text, filename, page_label) tuples.
    """
    query_vector = embed_model.get_text_embedding(question)
    results = client.search(
        collection_name=collection_name,
        query_vector=query_vector,
        limit=top_k,
    )
    return [
        (
            hit.payload["text"],
            hit.payload["filename"],
            hit.payload["page_label"],
        )
        for hit in results
    ]


def hash_file(file_bytes: bytes) -> str:
    """Return SHA-256 hex digest of file bytes for duplicate PDF detection."""
    return hashlib.sha256(file_bytes).hexdigest()
