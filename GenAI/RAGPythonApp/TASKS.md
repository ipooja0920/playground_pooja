# Implementation Tasks: RAGPythonApp

Implementation order is sequential — each task builds on the previous one.

---

## Task 1: Project Scaffolding ✅
**Files:** `requirements.txt`, `.env.example`, `.gitignore` entries

- Created `requirements.txt` with all dependencies:
  - `streamlit` — UI framework
  - `openai` — OpenAI API client
  - `llama-index-core` — RAG framework
  - `llama-index-readers-file` — PDF reader
  - `llama-index-vector-stores-qdrant` — Qdrant integration
  - `llama-index-embeddings-huggingface` — HuggingFace embedding bridge
  - `qdrant-client` — local Qdrant vector store
  - `sentence-transformers` — HuggingFace embeddings
  - `python-dotenv` — `.env` file loading
  - `ragas` — RAG evaluation framework (added in Task 7)
  - `langchain-openai` — RAGAS judge LLM wrapper (added in Task 7)
- Created `.env.example` with `OPENAI_API_KEY=your_key_here`
- Added `qdrant_storage/`, `.env`, `eval_results.txt` to `.gitignore`

---

## Task 2: LLM Client (`llm_client.py`) ✅
**File:** `llm_client.py`

- Loads `OPENAI_API_KEY` from environment via `python-dotenv`
- `get_answer(question, context_chunks)` function:
  - Joins chunks with `\n\n---\n\n` separator as context
  - System prompt instructs GPT-4o to answer strictly from document context, support every statement with context, and cover all key points
  - Calls `gpt-4o` with `temperature=0` for deterministic answers
  - Returns the answer string
- Wrapped in `try/except` — raises `RuntimeError` on API failure

---

## Task 3: Document Processor (`doc_processor.py`) ✅
**File:** `doc_processor.py`

- `load_and_chunk_pdf(file_path)` function:
  - Uses LlamaIndex `PDFReader` to parse a PDF file
  - Stamps `filename` metadata on each document before chunking
  - Splits into overlapping chunks using `SentenceSplitter`:
    - **chunk_size = 300 tokens** (reduced from 512 — smaller, more focused chunks improve retrieval precision)
    - **chunk_overlap = 40 tokens** (preserves sentence continuity across boundaries)
  - Returns a list of `TextNode` objects with `page_label` metadata intact
- Wrapped in `try/except` — raises `ValueError` for unreadable or empty PDFs

---

## Task 4: Vector Database (`vector_db.py`) ✅
**File:** `vector_db.py`

- `get_embed_model()` — loads `BAAI/bge-small-en-v1.5` via `HuggingFaceEmbedding`
  - Passes `query_instruction` prefix required by BGE for retrieval tasks
  - Vector dimension: 384 (same as MiniLM — no schema change needed)
- `get_qdrant_client()` — returns `QdrantClient(path="./qdrant_storage")` (local persistent, no Docker)
- `get_or_create_collection()` — creates Qdrant collection with cosine distance if it doesn't exist
- `index_chunks(nodes, embed_model, client)` — embeds each node and upserts into Qdrant with `text`, `filename`, `page_label` in payload
- `retrieve(question, embed_model, client, top_k=7, score_threshold=0.3)`:
  - Embeds the query using `embed_model.get_text_embedding()`
  - Calls `client.query_points()` (qdrant-client ≥ 1.9 API — replaced deprecated `.search()`)
  - Filters results to `score >= 0.3` — discards low-relevance noisy chunks
  - Returns top-7 results as `(text, filename, page_label)` tuples
- `hash_file(file_bytes)` — SHA-256 hex digest for duplicate PDF detection

---

## Task 5: Streamlit App (`app.py`) ✅
**File:** `app.py`

### Sidebar
- File uploader: accepts multiple PDFs simultaneously
- "Process Documents" button: triggers ingestion for uploaded files
  - Skips files whose SHA-256 hash is already in `st.session_state.processed_hashes`
  - Shows `st.status()` per file during indexing; `✅` on success, `❌` on failure
  - Replaces temp file path with original upload filename in chunk metadata
- Processed files list: displays all currently indexed PDF names

### Main Chat Area
- Initialises `st.session_state.messages`, `processed_hashes`, `processed_files` on first run
- Renders full chat history with `st.chat_message`
- Chat input disabled with hint if no documents are indexed
- On submit:
  1. Retrieve top-k chunks from Qdrant (filtered by score threshold)
  2. Call `llm_client.get_answer()` with question + chunks
  3. Build deduplicated citations: unique `(filename, page_label)` pairs
  4. Append question and answer+citations to `st.session_state.messages`
- Wrapped in `try/except` — shows `st.error()` banner on failure

---

## Task 6: End-to-End Test & Polish ✅

- Ran app locally: `streamlit run app.py`
- Verified:
  - PDF indexing progress indicators work
  - Duplicate PDF detection skips re-indexing
  - Chat returns grounded answers with citations (filename + page number)
  - Error banners show on bad PDFs without crashing the app
  - `qdrant_storage/` persists between app restarts
- Fixed: `QdrantClient` `.search()` → `.query_points()` for qdrant-client ≥ 1.9 compatibility
- Fixed: Qdrant storage lock — added clear error message in `eval.py` when Streamlit holds the lock

---

## Task 7: RAGAS Evaluation (`eval.py`) ✅
**File:** `eval.py`

- Added `ragas>=0.2.0` and `langchain-openai>=0.1.0` to `requirements.txt`
- 8 test cases covering ML textbook content (machine learning challenges, out-of-core learning, train-dev sets, classification, regression, SVMs, decision trees)
- Each test case has a `question` and `reference` (ground-truth answer from the PDF)
- Pipeline:
  1. Loads embed model and Qdrant client
  2. For each question: retrieves chunks, generates GPT-4o answer
  3. Builds `EvaluationDataset` from samples
  4. Runs RAGAS with 4 metrics: `Faithfulness`, `ResponseRelevancy`, `LLMContextRecall`, `FactualCorrectness`
  5. Uses `gpt-4o-mini` as judge LLM (cheaper than `gpt-4o`)
  6. Prints overall scores + per-sample breakdown
- Handles Qdrant storage lock with clear actionable error message
- Run with: `python eval.py | tee eval_results.txt`

---

## Task 8: RAG Optimisation ✅

Iterative improvements guided by RAGAS scores.

### Changes Made

| Change | File | Before | After |
|--------|------|--------|-------|
| Embedding model | `vector_db.py` | `all-MiniLM-L6-v2` | `BAAI/bge-small-en-v1.5` |
| BGE query instruction | `vector_db.py` | — | Added `query_instruction` prefix |
| Chunk size | `doc_processor.py` | 512 tokens | 300 tokens |
| Chunk overlap | `doc_processor.py` | 50 tokens | 40 tokens |
| Top-k retrieval | `vector_db.py` | 5 | 7 |
| Score threshold | `vector_db.py` | — | 0.3 (filters noisy chunks) |
| Grounding prompt | `llm_client.py` | Basic "use only context" | Added "every statement must be supported" + "cover all key points" |

### RAGAS Score Progression

| Metric | Baseline | After Optimisation |
|--------|----------|-------------------|
| Faithfulness | 0.77 | **0.94** |
| Answer Relevancy | 0.71 | **0.84** |
| Context Recall | 0.75 | **0.81** |
| Factual Correctness | 0.35 | **0.67** |

### Key Lessons

- **Embedding model is the biggest lever** — switching from MiniLM to BGE drove the largest gains across all metrics
- **Over-restrictive prompts hurt answer relevancy** — prompts with too many rules made the model evasive; short, clear instructions work best
- **Score threshold prevents hallucination** — filtering out low-scoring chunks removes the "noisy context gap-filling" behaviour that causes faithfulness failures
- **Factual correctness is partly a reference-wording problem** — verbatim textbook references vs. concise paraphrased answers creates an F1 penalty even when answers are correct
