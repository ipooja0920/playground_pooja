# Product Specification: Production-Grade RAG Python App

## Overview

A Retrieval-Augmented Generation (RAG) application built with Python and Streamlit. Users upload multiple PDF documents and ask questions about their content. Anthropic Claude generates answers grounded in the retrieved document context, with clear citations back to the source material.

---

## Architecture

**Monolithic Streamlit app** — Streamlit handles both the UI and the full RAG workflow (PDF parsing, chunking, embedding, vector storage, and querying) in a single process. No separate backend API or message queue.

**Why this design:**
- Zero additional infrastructure cost
- Simpler to run locally and deploy
- Modular file structure ensures it can be split into a Streamlit frontend + FastAPI/worker backend later without major rewrites

---

## Technical Stack

| Component | Technology |
|-----------|-----------|
| **Frontend & Orchestration** | [Streamlit](https://streamlit.io) |
| **LLM** | Anthropic Claude (`claude-sonnet-4-6`) via `anthropic` Python package |
| **RAG Framework** | [LlamaIndex](https://www.llamaindex.ai) — PDF parsing, chunking, retrieval |
| **Vector Store** | [Qdrant](https://qdrant.tech) — local persistent mode (no Docker required) |
| **Embeddings** | HuggingFace `all-MiniLM-L6-v2` via `sentence-transformers` — free, runs locally |

---

## Project File Structure

```
RAGPythonApp/
├── app.py              # Streamlit entry point — UI + RAG orchestration
├── doc_processor.py    # PDF ingestion, parsing, and chunking (LlamaIndex)
├── vector_db.py        # Qdrant setup, embedding, indexing, and retrieval
├── llm_client.py       # Anthropic Claude wrapper — query answering
├── requirements.txt    # All Python dependencies
├── .env.example        # Template for environment variables
├── PRODUCT_SPEC.md     # This file
└── TASKS.md            # Implementation task list
```

### Runtime Outputs (gitignored)
| Path | Description |
|------|-------------|
| `qdrant_storage/` | Local Qdrant vector database — persists between sessions |
| `.env` | API keys (never committed) |

---

## User Interface

### Sidebar
- **File uploader** — accepts multiple PDF files simultaneously
- **"Process Documents" button** — triggers ingestion pipeline for uploaded PDFs
- **Progress indicators** — shows indexing progress per file; displays user-friendly error messages on failure (e.g. unreadable PDF, API timeout)
- **Processed files list** — shows which documents are currently indexed

### Main Chat Area
- **Chat history** — full conversation displayed using `st.chat_message`
- **Chat input** — question input box pinned to the bottom
- **Citations** — every answer includes references: source PDF filename and page number(s) where the answer was found

---

## RAG Workflow

```
User uploads PDFs
       ↓
doc_processor.py — parse PDF pages, split into overlapping chunks
       ↓
vector_db.py — embed chunks (HuggingFace) → store in local Qdrant
       ↓
User asks a question
       ↓
vector_db.py — embed query → retrieve top-k most relevant chunks
       ↓
llm_client.py — send chunks + question to Claude → generate answer
       ↓
app.py — display answer + citations (filename + page number)
```

---

## Key Design Decisions

- **`@st.cache_resource`** wraps the HuggingFace embedding model load — downloaded once, reused across all reruns (avoids ~90MB re-download on every interaction)
- **`st.session_state`** holds chat history, the list of processed files, and the Qdrant collection reference — prevents state loss on UI reruns
- **Duplicate PDF detection** — file content hash checked before ingestion; already-indexed files are skipped silently
- **Qdrant local persistent client** — `QdrantClient(path="./qdrant_storage")` — no Docker, data survives app restarts
- **Page number citations** — LlamaIndex `page_label` metadata is preserved through the pipeline and surfaced in every response
- **Error handling** — all ingestion and query steps wrapped in `try/except`; failures shown as `st.error()` banners without crashing the app

---

## Error Handling

| Failure | Behaviour |
|---------|-----------|
| Unreadable / corrupted PDF | `st.error()` banner with filename; other files continue processing |
| Anthropic API timeout or rate limit | `st.error()` banner; chat input remains available for retry |
| Empty PDF (no extractable text) | Warning shown; file skipped |
| No documents indexed yet | Chat input disabled with prompt to upload documents first |

---

## Future Extensibility

The modular structure (`doc_processor.py`, `vector_db.py`, `llm_client.py`) makes it straightforward to:
- Swap Claude for another LLM
- Swap Qdrant for a hosted vector DB (Pinecone, Weaviate)
- Replace HuggingFace embeddings with Voyage or OpenAI embeddings
- Extract the RAG logic into a FastAPI backend with Inngest job queue (matching the Tim reference architecture)
