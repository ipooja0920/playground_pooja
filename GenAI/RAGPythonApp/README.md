> **For full technical details** — architecture diagrams, evaluation results, test documentation, and design decisions — read [PRODUCT_SPEC.md](PRODUCT_SPEC.md).

---

# RAG Python App

A Retrieval-Augmented Generation (RAG) application built with Python and Streamlit. Upload PDF documents and ask questions about their content. Answers are grounded in the documents with page-level citations — no hallucination from outside knowledge.

## What it does

- Upload one or more PDFs via the sidebar
- Ask questions in a chat interface
- Get answers sourced directly from your documents, with citations showing the filename and page number

## Screenshots

<!-- To add a screenshot:
     1. Take a screenshot and save it to the screenshots/ folder
     2. Replace the placeholder line below with:
        ![Description](screenshots/your-filename.png)
-->

### Uploading PDFs and Indexing

![PDF upload and indexing](screenshots/indexing.png)

### Asking a Question and Getting a Cited Answer

![Chat with citations](screenshots/chat.png)

### RAGAS Evaluation Results

![RAGAS evaluation scores](screenshots/eval.png)

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| UI | Streamlit |
| LLM | OpenAI `gpt-4o` |
| Embeddings | `BAAI/bge-small-en-v1.5` (local, free) |
| Vector Store | Qdrant (local, no Docker needed) |
| RAG Framework | LlamaIndex |
| Evaluation | RAGAS |

## Quick Start

**1. Install dependencies**

```bash
cd GenAI/RAGPythonApp
pip install -r requirements.txt
```

> The first run downloads the BGE embedding model (~90 MB) from HuggingFace automatically.

**2. Add your OpenAI API key**

```bash
cp .env.example .env
```

Edit `.env` and set:
```
OPENAI_API_KEY=sk-proj-your-key-here
```

**3. Run the app**

```bash
streamlit run app.py
```

Opens at `http://localhost:8501`.

**4. Use it**

1. Upload PDFs in the sidebar → click **"Process Documents"**
2. Type a question in the chat box
3. Get a grounded answer with source citations

## Running Tests

```bash
python -m pytest tests/ -v
```

**93 tests, ~7 seconds, zero API cost** — all mocked (no OpenAI calls, no disk I/O).

| File | Tests | What it covers |
|------|------:|----------------|
| `test_doc_processor.py` | 7 | PDF parsing and chunking |
| `test_vector_db.py` | 12 | Hashing, indexing, retrieval |
| `test_llm_client.py` | 10 | GPT-4o wrapper |
| `test_integration.py` | 10 | Full pipeline end-to-end |
| `test_retrieval.py` | 14 | Retrieval ranking and failure cases |
| `test_generation.py` | 17 | Grounding, adversarial, error handling |
| `test_edge_cases.py` | 23 | Unicode, empty inputs, robustness |

## Running Evaluation (RAGAS)

Stop Streamlit first (Qdrant allows only one process at a time), then:

```bash
python eval.py | tee eval_results.txt
```

**Latest scores:** Faithfulness 0.95 · Answer Relevancy 0.84 · Context Recall 0.88 · Factual Correctness 0.66

See [PRODUCT_SPEC.md](PRODUCT_SPEC.md) for the full per-question breakdown and optimisation history.

## Project Structure

```
RAGPythonApp/
├── app.py              # Streamlit UI + RAG orchestration
├── doc_processor.py    # PDF parsing and chunking
├── vector_db.py        # Qdrant embedding, indexing, retrieval
├── llm_client.py       # OpenAI GPT-4o wrapper
├── eval.py             # RAGAS evaluation script
├── requirements.txt
├── .env.example
├── PRODUCT_SPEC.md     # Full technical specification
├── TASKS.md            # Implementation history
└── tests/              # 93 tests across 7 files
```
