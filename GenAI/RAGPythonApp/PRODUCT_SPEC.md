# Product Specification: Production-Grade RAG Python App

## Overview

A Retrieval-Augmented Generation (RAG) application built with Python and Streamlit. Users upload multiple PDF documents and ask questions about their content. OpenAI GPT-4o generates answers grounded in the retrieved document context, with clear citations back to the source material.

---

## Architecture

**Monolithic Streamlit app** — Streamlit handles both the UI and the full RAG workflow (PDF parsing, chunking, embedding, vector storage, and querying) in a single process. No separate backend API or message queue.

**Why this design:**
- Zero additional infrastructure cost
- Simpler to run locally and deploy
- Each concern (parsing, embedding, retrieval, LLM) is its own module — easy to swap components without touching the rest

---

## High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          User (Web Browser)                             │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  │ HTTP localhost:8501
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        Streamlit App  (app.py)                          │
│                                                                         │
│   ┌──────────────────────────┐      ┌──────────────────────────────┐   │
│   │        Sidebar           │      │       Main Chat Area         │   │
│   │  • PDF file uploader     │      │  • Chat history display      │   │
│   │  • Process Documents btn │      │  • Chat input (bottom)       │   │
│   │  • Indexed docs list     │      │  • Answer + citations        │   │
│   └────────────┬─────────────┘      └──────────────┬───────────────┘   │
└────────────────┼────────────────────────────────────┼───────────────────┘
                 │ PDF bytes                          │ question
                 ▼                                   ▼
   ┌─────────────────────────┐         ┌─────────────────────────────┐
   │    doc_processor.py     │         │       vector_db.py          │
   │  • PDFReader (LlamaIdx) │         │  • Embed query (BGE model)  │
   │  • SentenceSplitter     │─chunks─▶│  • query_points() in Qdrant │
   │    chunk=300, overlap=40│         │  • Filter: score ≥ 0.3      │
   └────────────┬────────────┘         │  • Return top-7 chunks      │
                │ TextNodes            └──────────────┬──────────────┘
                ▼                                     │ chunks + question
   ┌─────────────────────────┐                        ▼
   │    vector_db.py         │         ┌─────────────────────────────┐
   │  • Embed chunks (BGE)   │         │      llm_client.py          │
   │  • Upsert into Qdrant   │         │  • Build context prompt     │
   └────────────┬────────────┘         │  • Call gpt-4o (temp=0)    │
                │                      │  • Return answer string     │
                ▼                      └──────────────┬──────────────┘
   ┌─────────────────────────┐                        │ answer
   │   Qdrant Storage        │◀──── read/write        ▼
   │   (local disk)          │              back to app.py
   │   qdrant_storage/       │              display + citations
   └─────────────────────────┘

   ┌─────────────────────────┐              ┌─────────────────────────┐
   │   BGE Embedding Model   │              │     OpenAI API          │
   │   BAAI/bge-small-en-v1.5│              │  • gpt-4o  (chat)       │
   │   (runs locally, free)  │              │  • gpt-4o-mini (eval)   │
   └─────────────────────────┘              └─────────────────────────┘
```

---

## Application Data Flow

Two separate flows run through the app — **indexing** (when PDFs are uploaded) and **querying** (when a question is asked):

```
  ╔══════════════════════════════════════════════════════════════╗
  ║                  INDEXING FLOW (one-time per PDF)           ║
  ╚══════════════════════════════════════════════════════════════╝

  User uploads PDF
        │
        ▼
  [app.py] SHA-256 hash check → skip if already indexed
        │ new PDF
        ▼
  [doc_processor.py] PDFReader → parse pages
        │ Document objects with page_label metadata
        ▼
  [doc_processor.py] SentenceSplitter → chunk (300 tokens, 40 overlap)
        │ TextNode list
        ▼
  [vector_db.py] BGE model → embed each chunk (384-dim vector)
        │ vectors + payload (text, filename, page_label)
        ▼
  [Qdrant] upsert vectors into "rag_docs" collection
        │
        ▼
  PDF indexed — persisted to qdrant_storage/


  ╔══════════════════════════════════════════════════════════════╗
  ║               QUERYING FLOW (every question)                ║
  ╚══════════════════════════════════════════════════════════════╝

  User types question
        │
        ▼
  [app.py] add to chat history, show spinner
        │
        ▼
  [vector_db.py] BGE model → embed question (with query instruction)
        │ 384-dim query vector
        ▼
  [Qdrant] query_points() → cosine similarity search
        │ top-7 results, filtered to score ≥ 0.3
        ▼
  [vector_db.py] return (text, filename, page_label) tuples
        │
        ▼
  [llm_client.py] build prompt: system + "Context:\n...\n\nQuestion: ..."
        │
        ▼
  [OpenAI] gpt-4o API call (temperature=0)
        │ answer string
        ▼
  [app.py] deduplicate citations (filename + page_label)
        │
        ▼
  Display answer + Sources: filename, p.X
```

---

## Technical Stack

| Component | Technology |
|-----------|-----------|
| **Frontend & Orchestration** | [Streamlit](https://streamlit.io) |
| **LLM** | OpenAI `gpt-4o` via `openai` Python package, `temperature=0` |
| **RAG Framework** | [LlamaIndex](https://www.llamaindex.ai) — PDF parsing, chunking, retrieval |
| **Vector Store** | [Qdrant](https://qdrant.tech) — local persistent mode (no Docker required) |
| **Embeddings** | `BAAI/bge-small-en-v1.5` via HuggingFace — free, runs locally, optimised for retrieval |
| **Evaluation** | [RAGAS](https://docs.ragas.io) — automated RAG evaluation framework |

> **Embedding model note:** Switched from `all-MiniLM-L6-v2` to `BAAI/bge-small-en-v1.5`. Both are 384-dimensional and free/local, but BGE is trained specifically for passage retrieval (MTEB retrieval score: ~51 vs ~41 for MiniLM). BGE requires a `query_instruction` prefix on queries (not on indexed documents).

---

## Project File Structure

```
RAGPythonApp/
├── app.py              # Streamlit entry point — UI + RAG orchestration
├── doc_processor.py    # PDF ingestion, parsing, and chunking (LlamaIndex)
├── vector_db.py        # Qdrant setup, embedding, indexing, and retrieval
├── llm_client.py       # OpenAI GPT-4o wrapper — query answering
├── eval.py             # RAGAS evaluation script — offline RAG quality scoring
├── requirements.txt    # All Python dependencies
├── .env.example        # Template for environment variables
├── PRODUCT_SPEC.md     # This file
├── TASKS.md            # Implementation task list
└── tests/
    ├── conftest.py              # sys.path setup + dummy API key for test imports
    ├── test_doc_processor.py    # 7 unit tests — PDF parsing and chunking
    ├── test_vector_db.py        # 12 unit tests — hashing, indexing, retrieval
    ├── test_llm_client.py       # 10 unit tests — GPT-4o wrapper
    ├── test_integration.py      # 10 integration tests — full pipeline (index → retrieve → answer)
    ├── test_retrieval.py        # 14 retrieval tests — basic, hard, and failure cases
    ├── test_generation.py       # 17 generation tests — grounding, adversarial, error handling
    └── test_edge_cases.py       # 23 edge case tests — robustness, Unicode, cross-component
```

### Runtime Outputs (gitignored)
| Path | Description |
|------|-------------|
| `qdrant_storage/` | Local Qdrant vector database — persists between sessions |
| `.env` | API keys (never committed) |
| `eval_results.txt` | RAGAS evaluation output — saved with `python eval.py \| tee eval_results.txt` |

---

## APIs Required

| API | Used For | Where to Get |
|-----|----------|--------------|
| **OpenAI API key** (`OPENAI_API_KEY`) | GPT-4o answer generation (chat app) + GPT-4o-mini as RAGAS judge LLM (eval only) | [platform.openai.com/api-keys](https://platform.openai.com/api-keys) |

> **No other external APIs needed.** The embedding model (`BAAI/bge-small-en-v1.5`) runs fully locally via HuggingFace. Qdrant runs fully locally with no server or account required.

> **Cost note:** The chat app calls `gpt-4o` once per question. The eval script calls `gpt-4o` for each of 8 test cases, then calls `gpt-4o-mini` many times as the RAGAS judge. Both use your OpenAI billing credits — add credits at [platform.openai.com/settings/billing](https://platform.openai.com/settings/billing).

---

## How to Run

### Prerequisites
- Python 3.9 or later
- An OpenAI API key with billing credits

### 1. Install Dependencies

Navigate to the project folder and install all packages:

```bash
cd GenAI/RAGPythonApp
pip install -r requirements.txt
```

> The first run will also download the BGE embedding model (~90 MB) from HuggingFace automatically.

### 2. Set Up Your API Key

Copy the example env file and fill in your key:

```bash
cp .env.example .env
```

Open `.env` and set:
```
OPENAI_API_KEY=sk-proj-your-key-here
```

### 3. Run the Streamlit App

```bash
streamlit run app.py
```

This opens the app in your browser at `http://localhost:8501`.

### 4. Index Your PDFs

1. In the **sidebar**, click **"Browse files"** and select one or more PDF files
2. Click **"Process Documents"** — a progress indicator shows for each file
3. Once indexed, the PDF names appear under **"Indexed Documents"** in the sidebar

> If you restart the app, `qdrant_storage/` persists — already-indexed PDFs do not need to be re-uploaded unless you delete the storage folder.

### 5. Ask Questions

Type a question in the chat box at the bottom. Each answer includes citations showing which PDF and page number the information came from.

### 6. Run Evaluation (Optional)

RAGAS evaluation measures answer quality against ground-truth questions in `eval.py`.

**Important:** Qdrant's local storage only allows one process at a time. Stop Streamlit (`Ctrl+C`) before running eval.

```bash
# From the RAGPythonApp directory, with Streamlit stopped:
python eval.py | tee eval_results.txt
```

Results are printed to the terminal and saved to `eval_results.txt`.

### Re-indexing After Config Changes

If you change the embedding model or chunk size in `vector_db.py` / `doc_processor.py`, the existing Qdrant index becomes stale. Delete it and re-upload your PDFs:

```bash
rm -rf qdrant_storage/
streamlit run app.py   # then re-upload PDFs in the sidebar
```

---

## User Interface

### Sidebar
- **File uploader** — accepts multiple PDF files simultaneously
- **"Process Documents" button** — triggers ingestion pipeline for uploaded PDFs
- **Progress indicators** — shows indexing progress per file; displays user-friendly error messages on failure (e.g. unreadable PDF, API timeout)
- **Processed files list** — shows which documents are currently indexed

### Main Chat Area
- **Chat history** — full conversation displayed using `st.chat_message`
- **Chat input** — question input box pinned to the bottom; disabled until at least one document is indexed
- **Citations** — every answer includes references: source PDF filename and page number(s) where the answer was found

---

## RAG Workflow

```
User uploads PDFs
       ↓
doc_processor.py — parse PDF pages, split into overlapping chunks (300 tokens, 40 overlap)
       ↓
vector_db.py — embed chunks (BGE) → store in local Qdrant with cosine similarity
       ↓
User asks a question
       ↓
vector_db.py — embed query (with BGE query instruction) → retrieve top-7 chunks
             — filter out chunks with cosine score < 0.3
       ↓
llm_client.py — send chunks + question to GPT-4o → generate grounded answer
       ↓
app.py — display answer + deduplicated citations (filename + page number)
```

---

## Chunking Strategy

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| `chunk_size` | 300 tokens | Smaller, focused chunks improve retrieval precision vs. original 512 |
| `chunk_overlap` | 40 tokens | Preserves sentence continuity across chunk boundaries |
| Splitter | `SentenceSplitter` (LlamaIndex) | Respects sentence boundaries; avoids cutting mid-sentence |

---

## Retrieval Configuration

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| `top_k` | 7 | Retrieves slightly more chunks since chunks are smaller (300 tokens) |
| `score_threshold` | 0.3 | Discards low-relevance chunks; prevents noisy context reaching the LLM |
| Distance metric | Cosine | Standard for semantic similarity with normalised embeddings |
| Qdrant API | `query_points()` | Required for qdrant-client ≥ 1.9 (replaced deprecated `.search()`) |

---

## LLM Configuration

**Model:** `gpt-4o`
**Temperature:** `0` — deterministic answers; no creative drift

**System prompt:**
```
You are a helpful assistant that answers questions strictly based on the
provided document context. Do not use any outside knowledge.
Every statement in your answer must be directly supported by the provided context.
Cover all key points from the context that are relevant to the question —
do not leave out important details.
If the answer cannot be found in the context, say so clearly.
```

**Prompt design rationale:**
- Grounding instruction ("Do not use any outside knowledge") prevents the model from drawing on training data
- "Every statement must be directly supported" targets RAGAS Faithfulness — penalises any claim not traceable to the retrieved chunks
- "Cover all key points" improves RAGAS Factual Correctness by encouraging complete answers

---

## Key Design Decisions

- **`@st.cache_resource`** wraps the embedding model load — downloaded once, reused across all reruns
- **`st.session_state`** holds chat history, processed file list, and processed hashes — prevents state loss on UI reruns
- **Duplicate PDF detection** — SHA-256 file hash checked before ingestion; already-indexed files are skipped silently
- **Qdrant local persistent client** — `QdrantClient(path="./qdrant_storage")` — no Docker, data survives app restarts
- **Page number citations** — LlamaIndex `page_label` metadata is preserved through the pipeline and surfaced in every response
- **Error handling** — all ingestion and query steps wrapped in `try/except`; failures shown as `st.error()` banners without crashing the app
- **Qdrant storage lock** — local Qdrant allows only one process at a time; `eval.py` catches the lock error and prints a clear message to stop the Streamlit app first

---

## Error Handling

| Failure | Behaviour |
|---------|-----------|
| Unreadable / corrupted PDF | `st.error()` banner with filename; other files continue processing |
| OpenAI API timeout or rate limit | `st.error()` banner; chat input remains available for retry |
| Empty PDF (no extractable text) | Warning shown; file skipped |
| No documents indexed yet | Chat input disabled with prompt to upload documents first |
| Qdrant storage locked by Streamlit | `eval.py` prints clear message: stop Streamlit first, then re-run eval |

---

## Unit Testing

The project has a `tests/` directory with **93 tests** across 7 test files, covering all three core modules plus integration, retrieval, generation, and edge case scenarios. Tests run in ~7 seconds with no API credits spent and no disk storage required.

### Testing Philosophy

| Principle | How it's applied |
|-----------|-----------------|
| **No real API calls** | OpenAI `_client` is mocked in all generation/LLM tests — zero billing cost |
| **No real disk I/O** | `QdrantClient(":memory:")` used throughout — no `qdrant_storage/` needed |
| **No real PDF files** | `PDFReader` is mocked in all doc_processor tests — no binary test fixtures |
| **Fast** | All 93 tests complete in ~7 seconds |
| **Isolated** | Each test is independent; no shared state between tests |

### How to Run Tests

```bash
# From the RAGPythonApp directory:
python -m pytest tests/ -v
```

Expected output:
```
93 passed in ~7s
```

Run a specific test file:
```bash
python -m pytest tests/test_integration.py -v
```

Run a single test by name:
```bash
python -m pytest tests/test_retrieval.py::TestHardRetrieval::test_semantically_closer_chunk_scores_higher -v
```

### Test Files and What They Cover

#### `tests/conftest.py` — Shared Setup
- Adds `RAGPythonApp/` to `sys.path` so all modules are importable from tests
- Sets `OPENAI_API_KEY=sk-test-dummy-key-for-unit-tests` so `llm_client.py` can be imported without a real key (actual calls are mocked)

---

#### `tests/test_doc_processor.py` — 7 tests

Tests `load_and_chunk_pdf()` in [doc_processor.py](doc_processor.py). `PDFReader` is mocked — no actual PDF file is needed.

| Test | What it verifies |
|------|-----------------|
| `test_returns_nonempty_list_of_nodes` | A valid PDF produces at least one chunk |
| `test_nodes_have_text` | Every chunk has non-empty text content |
| `test_filename_metadata_is_set_from_path` | `filename` in chunk metadata comes from the file path, not PDFReader's internal value |
| `test_page_label_metadata_is_preserved` | `page_label` set by PDFReader flows through to the chunk |
| `test_empty_pdf_raises_value_error` | PDF with no extractable text raises `ValueError` with clear message |
| `test_unreadable_pdf_raises_value_error` | Corrupt/unreadable file raises `ValueError` |
| `test_multiple_pages_produce_chunks` | A multi-page document produces chunks from all pages |

---

#### `tests/test_vector_db.py` — 12 tests

Tests [vector_db.py](vector_db.py) using `QdrantClient(":memory:")` — no disk I/O, no Qdrant storage lock.
The embedding model is mocked to return a fixed 384-dim vector — no HuggingFace download required.

**`hash_file()` tests (3):**

| Test | What it verifies |
|------|-----------------|
| `test_hash_file_is_deterministic` | Same bytes always produce the same hash (needed for duplicate PDF detection) |
| `test_hash_file_different_inputs_differ` | Different bytes produce different hashes |
| `test_hash_file_returns_64_char_hex` | Output is a 64-character lowercase hex string (SHA-256 format) |

**Collection management tests (2):**

| Test | What it verifies |
|------|-----------------|
| `test_collection_is_created` | `get_or_create_collection()` creates the `rag_docs` collection |
| `test_create_collection_is_idempotent` | Calling twice does not raise and leaves exactly one collection |

**Indexing + retrieval tests (7):**

| Test | What it verifies |
|------|-----------------|
| `test_indexed_node_is_retrievable` | A node upserted with `index_chunks()` is returned by `retrieve()` |
| `test_retrieve_returns_correct_text` | The retrieved text matches exactly what was indexed |
| `test_retrieve_returns_correct_metadata` | filename and page_label are returned correctly |
| `test_retrieve_returns_three_tuple` | Each result is a `(text, filename, page_label)` triple |
| `test_retrieve_empty_collection_returns_empty` | Querying an empty collection returns `[]` |
| `test_score_threshold_filters_low_similarity` | Orthogonal vectors (cosine ≈ 0.0) are filtered out by `score_threshold=0.3` |
| `test_multiple_nodes_all_indexed` | All 3 indexed nodes are returned when `top_k=3` |

---

#### `tests/test_llm_client.py` — 10 tests

Tests `get_answer()` in [llm_client.py](llm_client.py). The OpenAI `_client` module-level object is mocked — no real API calls, no billing.

**Happy-path tests (8):**

| Test | What it verifies |
|------|-----------------|
| `test_returns_stripped_string` | Whitespace is stripped from the model's response |
| `test_uses_gpt4o_model` | The API call always requests `model="gpt-4o"` |
| `test_temperature_is_zero` | `temperature=0` is always set (deterministic answers) |
| `test_context_chunks_appear_in_user_message` | All chunks are included in the user message sent to GPT-4o |
| `test_question_appears_in_user_message` | The question is included in the user message |
| `test_system_message_is_present` | A system-role message is included in the messages list |
| `test_system_message_enforces_grounding` | The system prompt contains grounding instructions |
| `test_multiple_chunks_joined_in_message` | Multiple chunks result in exactly one API call (not one per chunk) |

**Error-handling tests (2):**

| Test | What it verifies |
|------|-----------------|
| `test_api_failure_raises_runtime_error` | Any OpenAI exception is re-raised as `RuntimeError` |
| `test_runtime_error_message_includes_original_error` | The original error message is preserved in the `RuntimeError` |

---

#### `tests/test_integration.py` — 10 tests

End-to-end pipeline tests using real in-memory Qdrant + mocked OpenAI. Verifies all three modules working together: `doc_processor → vector_db → llm_client`.

**`TestIndexThenRetrieve` (4 tests):**

| Test | What it verifies |
|------|-----------------|
| `test_indexed_content_is_retrievable` | Content indexed with `index_chunks()` is returned by `retrieve()` |
| `test_retrieved_text_matches_indexed_text` | Retrieved text is exactly what was indexed (no corruption in transit) |
| `test_citations_carry_filename_and_page` | Every result includes the source filename and page number |
| `test_chunks_from_multiple_pdfs_coexist` | Chunks from two different PDFs coexist in the same collection |

**`TestRetrieveThenAnswer` (3 tests):**

| Test | What it verifies |
|------|-----------------|
| `test_full_pipeline_returns_string_answer` | `index → retrieve → GPT-4o → answer` completes without error |
| `test_retrieved_context_is_passed_to_llm` | Retrieved chunk text appears in the user message sent to OpenAI |
| `test_openai_failure_does_not_corrupt_qdrant` | An OpenAI exception raises `RuntimeError` but Qdrant stays queryable |

**`TestDocProcessorToVectorDb` (3 tests):**

| Test | What it verifies |
|------|-----------------|
| `test_pdf_chunks_are_indexable_and_retrievable` | Chunks from `load_and_chunk_pdf()` can be indexed and retrieved end-to-end |
| `test_filename_from_path_appears_in_citations` | Filename in citations comes from the upload path, not the temp PDFReader value |
| `test_no_docs_indexed_returns_empty_list` | Querying with no documents indexed returns `[]` |

---

#### `tests/test_retrieval.py` — 14 tests

Focused tests for retrieval correctness, ranking, and failure modes in [vector_db.py](vector_db.py).

**`TestBasicRetrieval` (5 tests):**

| Test | What it verifies |
|------|-----------------|
| `test_single_chunk_is_returned` | A single indexed chunk is returned for any query |
| `test_multiple_chunks_all_returned` | All chunks that exceed `score_threshold` are returned |
| `test_top_k_limits_results` | `top_k=2` returns at most 2 results even with 10 indexed |
| `test_multi_source_retrieval` | Chunks from different PDFs are both retrieved |
| `test_result_text_matches_indexed_text_exactly` | Retrieved text is byte-for-byte identical to indexed text |

**`TestHardRetrieval` (4 tests):**

| Test | What it verifies |
|------|-----------------|
| `test_semantically_closer_chunk_scores_higher` | The chunk with the closer embedding vector ranks first |
| `test_answer_spanning_two_chunks_both_retrieved` | Both chunks are returned when an answer spans multiple chunks |
| `test_page_numbers_are_preserved_across_chunks` | Page labels from different pages of the same PDF are preserved |
| `test_duplicate_text_two_different_pages` | Identical text on two different pages produces two distinct results |

**`TestRetrievalFailures` (5 tests):**

| Test | What it verifies |
|------|-----------------|
| `test_orthogonal_query_filtered_by_score_threshold` | Query orthogonal to all indexed vectors returns `[]` with `threshold=0.3` |
| `test_empty_kb_returns_empty_list` | Querying an empty collection returns `[]`, not an error |
| `test_every_result_is_three_tuple` | Each result is always a `(str, str, str)` triple |
| `test_zero_score_threshold_returns_all` | `score_threshold=0.0` returns all chunks regardless of similarity |
| `test_high_score_threshold_filters_all` | A self-similar query passes `score_threshold=0.99` (cosine sim = 1.0) |

---

#### `tests/test_generation.py` — 17 tests

Tests for LLM answer generation correctness, grounding, adversarial robustness, and error handling in [llm_client.py](llm_client.py).

**`TestGrounding` (6 tests):**

| Test | What it verifies |
|------|-----------------|
| `test_system_prompt_restricts_to_document` | System prompt contains grounding keywords (context/document/provided) |
| `test_context_chunks_appear_in_user_message` | Every context chunk appears verbatim in the user message |
| `test_question_appears_in_user_message` | The user's question text is present in the user message |
| `test_multiple_context_chunks_all_included` | All five context chunks are present when five are provided |
| `test_model_is_gpt4o` | The API call always uses `model="gpt-4o"` |
| `test_temperature_is_zero` | `temperature=0` is always set for deterministic answers |

**`TestAnswerRelevancy` (4 tests):**

| Test | What it verifies |
|------|-----------------|
| `test_answer_is_string` | `get_answer()` always returns a `str` |
| `test_answer_is_non_empty` | Returns a non-empty string when OpenAI replies |
| `test_answer_matches_openai_response` | The string returned is exactly what OpenAI replied |
| `test_single_api_call_per_question` | Exactly one OpenAI call is made per `get_answer()` invocation |

**`TestAdversarial` (4 tests):**

| Test | What it verifies |
|------|-----------------|
| `test_prompt_injection_in_context_still_returns_answer` | Injected instructions in context don't crash the pipeline |
| `test_empty_context_list_does_not_crash` | `get_answer()` with `[]` context still returns a string |
| `test_very_long_context_does_not_crash` | A very long context (500-sentence repeat) doesn't raise |
| `test_special_characters_in_question_do_not_crash` | Questions with special characters are handled without error |

**`TestErrorHandling` (3 tests):**

| Test | What it verifies |
|------|-----------------|
| `test_openai_exception_raises_runtime_error` | Any OpenAI exception is wrapped in `RuntimeError` |
| `test_runtime_error_message_contains_original` | The `RuntimeError` message includes the original exception text |
| `test_timeout_exception_wrapped_as_runtime_error` | `TimeoutError` from OpenAI is also wrapped in `RuntimeError` |

---

#### `tests/test_edge_cases.py` — 23 tests

Robustness tests covering unusual inputs, Unicode content, and cross-component interactions.

**`TestHashFileEdgeCases` (6 tests):** empty bytes, single byte, 1 MB payload, same-content determinism, different-content collision, lowercase hex format.

**`TestDocProcessorEdgeCases` (4 tests):** Unicode PDF content, whitespace-only PDF raises `ValueError`, filenames with spaces, deeply nested paths use only the basename.

**`TestVectorDbEdgeCases` (5 tests):** very long text nodes (2000 chars), re-indexing same content doesn't crash, empty node list is a no-op, collection reused across multiple `index_chunks()` calls, special characters in metadata stored correctly.

**`TestLlmClientEdgeCases` (5 tests):** whitespace-only answer is stripped to `""`, newlines in answer are preserved, single-character context doesn't crash, context with only newlines doesn't crash, Unicode in question and context is handled.

**`TestCrossComponentEdgeCases` (3 tests):** Unicode PDF content flows through the full pipeline, filename from upload path overrides temp PDFReader value, full pipeline returns a Unicode answer without error.

---

### Test Coverage Summary

| File | Tests | Category | Key Techniques |
|------|------:|----------|---------------|
| `test_doc_processor.py` | 7 | Unit | Mock PDFReader, fake paths |
| `test_vector_db.py` | 12 | Unit | In-memory Qdrant, mock embed model |
| `test_llm_client.py` | 10 | Unit | Mock `_client`, inspect call args |
| `test_integration.py` | 10 | Integration | In-memory Qdrant + mock OpenAI end-to-end |
| `test_retrieval.py` | 14 | Retrieval | Orthogonal unit vectors for ranking tests |
| `test_generation.py` | 17 | Generation | Adversarial context, error injection |
| `test_edge_cases.py` | 23 | Edge Cases | Unicode, empty inputs, cross-component |
| **Total** | **93** | | **~7 seconds, zero API cost** |

---

### Unit Tests vs RAGAS Evaluation

| | Unit Tests (`pytest`) | RAGAS Evaluation (`eval.py`) |
|---|---|---|
| **Purpose** | Verify code correctness | Measure answer quality |
| **Speed** | ~7 seconds | ~5–10 minutes |
| **API cost** | Free (fully mocked) | Uses OpenAI credits |
| **When to run** | Every code change | After tuning retrieval or prompt |
| **What it catches** | Bugs in logic, regressions, error handling | Hallucination, poor retrieval, irrelevant answers |

---

## Evaluation (RAGAS)

Offline evaluation is done with **RAGAS** (`eval.py`) using `gpt-4o-mini` as the judge LLM.

### Metrics

| Metric | What it measures |
|--------|-----------------|
| **Faithfulness** | Fraction of claims in the answer that are supported by the retrieved context (detects hallucination) |
| **Answer Relevancy** | How well the answer addresses the actual question asked |
| **Context Recall** | Fraction of the reference answer's information that is present in the retrieved chunks |
| **Factual Correctness** | How closely the answer matches the ground-truth reference answer (F1 score) |

### Running Evaluation

```bash
# Stop Streamlit first (Qdrant storage lock), then:
python eval.py | tee eval_results.txt
```

### Evaluation Results (Final)

**Overall scores (average across 8 test cases):**

| Metric | Baseline | After BGE + Optimisations |
|--------|----------|--------------------------|
| Faithfulness | 0.77 | **0.95** |
| Answer Relevancy | 0.71 | **0.84** |
| Context Recall | 0.75 | **0.88** |
| Factual Correctness | 0.35 | **0.66** |

**Per-question breakdown (latest run):**

| # | Question (abbreviated) | Faithfulness | Answer Relevancy | Context Recall | Factual Correctness |
|---|------------------------|:------------:|:----------------:|:--------------:|:-------------------:|
| 1 | Four main challenges in ML | 1.00 | 0.96 | 1.00 | 1.00 |
| 2 | What is out-of-core learning? | 1.00 | 1.00 | 1.00 | 1.00 |
| 3 | Train-dev set: what, when, how? | 1.00 | 0.00 | 0.00 | 0.00 |
| 4 | Two logistic regression vs one softmax? | 1.00 | 0.89 | 1.00 | 1.00 |
| 5 | Ridge vs plain linear regression? | 1.00 | 0.94 | 1.00 | 0.67 |
| 6 | Choose between LinearSVC, SVC, SGDClassifier? | 0.78 | 0.96 | 1.00 | 0.60 |
| 7 | SVC instead of LinearSVC — when? | 0.82 | 0.96 | 1.00 | 0.57 |
| 8 | Decision tree depth on 1 million instances? | 1.00 | 0.98 | 1.00 | 0.44 |

**Notable observations from per-question results:**

- **Q3 scored 0.00 across all metrics** — the model correctly said "I cannot find this information in the provided documents." The train-dev set content was not retrieved (context_recall=0.00), meaning that topic is either not in the indexed PDF or needs better retrieval. This is a *correct refusal*, not a hallucination.
- **Q6 and Q7 (SVC/LinearSVC) have faithfulness < 1.0** — the model added minor details beyond what was in the retrieved chunks. These are the hallucination-prone cases RAGAS is designed to catch.
- **Q8 (decision tree depth) has low factual correctness (0.44)** — the reference answer includes the full mathematical derivation (log₂(10⁶) ≈ 20). The model's answer was correct but less detailed, causing an F1 penalty on wording rather than factual accuracy.

### Optimisation History

| Change | Impact |
|--------|--------|
| Switched embedding model: `all-MiniLM-L6-v2` → `BAAI/bge-small-en-v1.5` | Biggest single improvement — faithfulness +0.17, factual correctness +0.32 |
| Reduced chunk size: 512 → 300 tokens | More targeted retrieval; each chunk covers a narrower topic |
| Added score threshold: `score_threshold=0.3` | Filters noisy low-relevance chunks before they reach the LLM |
| Increased top_k: 5 → 7 | Compensates for smaller chunks; improves context recall |
| Added BGE query instruction | Required for BGE to perform at its retrieval benchmark score |
| Prompt: added "Every statement must be directly supported" | Targets faithfulness specifically |
| Prompt: added "Cover all key points" | Targets factual correctness by encouraging complete answers |

> **Note on Factual Correctness:** The reference answers in `eval.py` are verbatim textbook paragraphs (very detailed). The model produces concise paraphrased answers — both correct, but RAGAS F1 penalises phrasing divergence. A score of 0.67 reflects this mismatch, not poor answer quality.

---

## Future Extensibility

> **Note:** FastAPI is **not** used in this project. The app is a single Streamlit process. The items below are potential future upgrades only.

The modular structure (`doc_processor.py`, `vector_db.py`, `llm_client.py`) makes it straightforward to:
- Swap GPT-4o for another LLM (Claude, Gemini, local models via Ollama)
- Swap Qdrant for a hosted vector DB (Pinecone, Weaviate)
- Upgrade to `BAAI/bge-base-en-v1.5` (768-dim) for even better retrieval quality at the cost of re-indexing
- Extract the RAG logic into a FastAPI backend with a job queue (for multi-user or production deployments)
- Add a cross-encoder reranker (e.g. `cross-encoder/ms-marco-MiniLM-L-6-v2`) between retrieval and generation for further precision gains
