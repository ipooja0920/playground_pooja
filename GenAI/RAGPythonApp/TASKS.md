# Implementation Tasks: RAGPythonApp

Implementation order is sequential — each task builds on the previous one.

---

## Task 1: Project Scaffolding
**Files:** `requirements.txt`, `.env.example`, `.gitignore` entries

- Create `requirements.txt` with all dependencies:
  - `streamlit` — UI framework
  - `anthropic` — Claude API client
  - `llama-index-core` — RAG framework
  - `llama-index-readers-file` — PDF reader
  - `llama-index-vector-stores-qdrant` — Qdrant integration
  - `llama-index-embeddings-huggingface` — HuggingFace embedding bridge
  - `qdrant-client` — local Qdrant vector store
  - `sentence-transformers` — HuggingFace `all-MiniLM-L6-v2` embeddings
  - `python-dotenv` — `.env` file loading
- Create `.env.example` with `ANTHROPIC_API_KEY=your_key_here`
- Add `qdrant_storage/` and `.env` to `.gitignore`

---

## Task 2: LLM Client (`llm_client.py`)
**File:** `llm_client.py`

- Load `ANTHROPIC_API_KEY` from environment
- `get_answer(question, context_chunks)` function:
  - Accepts a question string and a list of retrieved text chunks
  - Builds a system prompt instructing Claude to answer only from provided context
  - Calls `claude-sonnet-4-6` via the `anthropic` Python package
  - Returns the answer string
- Wrap the API call in `try/except` — raise a descriptive error on failure

---

## Task 3: Document Processor (`doc_processor.py`)
**File:** `doc_processor.py`

- `load_and_chunk_pdf(file_path)` function:
  - Uses `LlamaIndex` `SimpleDirectoryReader` (or `PDFReader`) to parse a PDF
  - Preserves `page_label` metadata on each node
  - Splits into overlapping chunks using `SentenceSplitter` (chunk size ~512, overlap ~50)
  - Returns a list of `TextNode` objects
- Wrap in `try/except` — raise descriptive errors for unreadable or empty PDFs

---

## Task 4: Vector Database (`vector_db.py`)
**File:** `vector_db.py`

- `get_embed_model()` — loads `all-MiniLM-L6-v2` via `HuggingFaceEmbedding` (wrapped in `@st.cache_resource` when called from app)
- `get_or_create_collection(collection_name="rag_docs")` — returns a `QdrantClient` pointing to `./qdrant_storage` and ensures the collection exists
- `index_chunks(nodes, collection_name)` — embeds each node and upserts into Qdrant with metadata (`filename`, `page_label`)
- `retrieve(question, collection_name, top_k=5)` — embeds the query, runs similarity search, returns top-k results as `(text, filename, page_label)` tuples
- Content hash helper — `hash_file(file_bytes)` returns a SHA-256 hex digest for duplicate detection

---

## Task 5: Streamlit App (`app.py`)
**File:** `app.py`

### Sidebar
- File uploader: accepts multiple PDFs simultaneously
- "Process Documents" button: triggers ingestion for uploaded files
  - Skips files whose hash is already in `st.session_state.processed_hashes`
  - Shows `st.progress()` per file during indexing
  - Shows `st.success()` on completion, `st.error()` on failure
- Processed files list: displays all currently indexed PDF names

### Main Chat Area
- Initialise `st.session_state.messages` (chat history) and `st.session_state.processed_hashes`
- Render full chat history with `st.chat_message`
- Chat input pinned to bottom (disabled with hint if no documents indexed)
- On submit:
  1. Retrieve top-k chunks from Qdrant
  2. Call `llm_client.get_answer()` with question + chunks
  3. Append question and answer to `st.session_state.messages`
  4. Display answer with citations: filename + page number(s)
- Wrap retrieval and LLM call in `try/except` — show `st.error()` banner on failure

---

## Task 6: End-to-End Test & Polish
- Run the app locally: `streamlit run app.py`
- Upload 2–3 sample PDFs and verify:
  - Indexing progress indicators work
  - Duplicate PDF detection skips re-indexing
  - Chat returns grounded answers with citations
  - Error banners show on bad PDFs (don't crash the app)
  - `qdrant_storage/` persists between app restarts
- Fix any bugs found during testing
- Commit final state

---

## Commit Strategy

Each task gets its own commit with a clear message, e.g.:
- `Task 1: Add project scaffolding (requirements.txt, .env.example)`
- `Task 2: Add LLM client (Claude wrapper)`
- `Task 3: Add document processor (PDF ingestion + chunking)`
- `Task 4: Add vector DB layer (Qdrant + HuggingFace embeddings)`
- `Task 5: Add Streamlit app (UI + RAG orchestration)`
- `Task 6: End-to-end test and polish`
