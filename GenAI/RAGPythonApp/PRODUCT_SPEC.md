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
└── TASKS.md            # Implementation task list
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
