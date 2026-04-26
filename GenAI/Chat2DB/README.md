# Chat2DB — Talk to Your Database

A production-quality GenAI chatbot that translates plain English into SQL, executes queries against a live PostgreSQL database, and explains results — with full observability, automated evaluation, and multi-turn conversation support.

Built on the Chinook music store database as the domain, using LlamaIndex, Langfuse, and OpenAI/Anthropic models.

---

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Pipelines](#pipelines)
- [Query Processing Pipeline](#query-processing-pipeline)
- [LLM-as-Judge Scoring](#llm-as-judge-scoring)
- [Conversational SQL](#conversational-sql)
- [UI Highlights](#ui-highlights)
- [Evaluation Framework](#evaluation-framework)
- [Setup and Installation](#setup-and-installation)
- [Running the App](#running-the-app)
- [CLI Usage](#cli-usage)
- [Project Structure](#project-structure)
- [References](#references)

---

## Features

| Feature | Description |
|---|---|
| Natural language to SQL | Ask questions in plain English, get SQL + results |
| Two modes | Standard (schema-aware) and Hybrid (self-correcting agentic with parallel retrieval) |
| LLM intent classification | Classifies every query into `schema_question`, `followup`, or `new_question` |
| LLM query rewriting | Resolves coreferences, expands abbreviations, adds domain context before retrieval |
| Multi-turn conversation | Follow-up questions modify the previous SQL automatically |
| Curated domain knowledge | Business rules, aggregation gotchas, and column clarifications injected into Hybrid prompts |
| Parallel retrieval | Hybrid mode fetches schema and business rules concurrently via `asyncio.gather` |
| LLM-as-Judge | Automated response scoring pushed to Langfuse |
| Schema Explorer | Live sidebar browser of all tables and columns |
| Query Provenance | Expander shows rewritten query, SQL used, tables, columns, raw results |
| LLM provider choice | OpenAI GPT-4o-mini or Anthropic Claude 3.5 Sonnet |
| Intent classifier | TF-IDF + SVM filters non-database questions (optional toggle) |
| Observability | Full Langfuse tracing, scoring, and dashboard |
| Eval pipeline | Automated SQL accuracy scoring against ground truth |

---

## Architecture

```
User Question
      │
      ▼
[Optional] Binary Classifier (TF-IDF + SVM)
      │ is DB question?
      ▼
LLM Intent Classifier
      │ schema_question | followup | new_question
      ├─── schema_question ──→ Answer from live schema (no SQL)
      │
      ▼
LLM Query Rewriter
      │ resolve coreferences, expand abbreviations, add domain context
      ▼
┌─────────────────┐     ┌──────────────────────────────────┐
│  Standard Mode  │  or │          Hybrid Mode             │
│                 │     │                                  │
│ Schema +        │     │ asyncio.gather(                  │
│ Conv history    │     │   schema_context,                │
│ → LLM SQL       │     │   business_rules_context         │
│ → Execute       │     │ ) + Conv history                 │
│ → Answer        │     │ → LLM generates SQL              │
└─────────────────┘     │ → Execute                        │
                        │ → Error? Self-correct (3 retries)│
                        │ → Answer                         │
                        └──────────────────────────────────┘
                                      │
                                      ▼
                            LLM-as-Judge Scoring
                            (relevance + answer_quality)
                                      │
                                      ▼
                            Langfuse (traces + scores)
```

**Infrastructure:**
- **Frontend**: Streamlit
- **LLM Framework**: LlamaIndex 0.13.x
- **Vector DB**: PostgreSQL + pgvector (port 6433)
- **Domain DB**: PostgreSQL 16 — Chinook music store (port 7433)
- **Observability**: Langfuse (port 3000)
- **Document Parsing**: Docling

---

## Pipelines

### Standard — Schema-Aware SQL Generation

1. Injects the full live database schema into the prompt
2. Includes conversation history and previous SQL for follow-up support
3. Uses LlamaIndex `NLSQLTableQueryEngine` to generate and execute SQL
4. Returns answer, SQL, tables used, columns used, and raw results

### Hybrid — Agentic Self-Correcting Pipeline

An agentic workflow built with LlamaIndex `Workflow` that also fetches curated domain knowledge:

| Step | What happens |
|---|---|
| `query_synthesis` | Parallel fetch of schema + business rules via `asyncio.gather`, then NL → SQL with full context |
| `query_execution` | Execute SQL against PostgreSQL |
| `sql_correction` | If execution fails, LLM fixes SQL and retries (up to 3x) |
| `answer_generation` | SQL results → natural language answer |

Self-correction fires a `SQLCorrectionEvent` with the failed SQL + error message, letting the LLM produce a corrected query autonomously.

---

## Query Processing Pipeline

Every user query goes through four stages before reaching SQL generation:

### Stage 0 — Binary Classifier (optional)
TF-IDF + SVM model filters out non-database questions. Toggled via the **Intent Classifier** switch in Advanced Settings.

### Stage 1 — LLM Intent Classification
A cheap LLM call classifies the query into one of three categories:

| Intent | Meaning | Action |
|---|---|---|
| `schema_question` | User asks about tables, columns, or data available | Answer directly from live schema — no SQL generated |
| `followup` | User modifies or references the previous query/results | Pass to pipeline with conversation context |
| `new_question` | Completely new independent question | Pass to pipeline fresh |

### Stage 2 — LLM Query Rewriting
Before retrieval, the query is reformulated by a cheap LLM to improve SQL generation accuracy:

- **Coreference resolution**: "show them sorted" → "show the top 5 customers by total spend, sorted descending"
- **Abbreviation expansion**: "rev by genre" → "total revenue from invoice_line grouped by genre"
- **Domain enrichment**: "most popular track" → "track with the highest total revenue from invoice_line"

If the query is already clear and self-contained, it is returned verbatim (no noise added).

### Stage 3 — SQL Generation + Execution
The rewritten query is sent to Standard or Hybrid mode for SQL generation, execution, and answer synthesis.

---

## LLM-as-Judge Scoring

After every response, a second (cheap) LLM call automatically rates the answer on two dimensions:

| Score | What it measures |
|---|---|
| `relevance` | Does the answer directly address the question? (0.0–1.0) |
| `answer_quality` | Is it clear, accurate, and well-structured? (0.0–1.0) |

Both scores are pushed to **Langfuse** via `langfuse_context.score_current_trace()` and displayed inline in the UI with color indicators:

- 🟢 ≥ 1.0 — excellent
- 🟡 ≥ 0.8 — good
- 🔴 < 0.8 — needs improvement

The judge uses `gpt-4o-mini` (OpenAI) or `claude-3-5-haiku` (Anthropic) — a lightweight, cheap model deliberately chosen to keep scoring cost near zero while still providing meaningful signal.

This pattern (LLM-as-Judge) is based on [Zheng et al., 2023](https://arxiv.org/abs/2306.05685) and is widely used for automated evaluation of LLM outputs where human annotation is not feasible at scale.

---

## Conversational SQL

The app supports multi-turn conversations where follow-up questions modify the previous SQL rather than starting from scratch.

Each new question receives:
- Full database schema
- Last 3 turns of conversation history
- The previous SQL query

The LLM intent classifier first decides: **schema_question**, **followup**, or **new_question**. For followups, the query rewriter resolves all pronouns before SQL generation.

**Example conversation:**
```
User:  Which customer spent the most?
SQL:   SELECT c.first_name, SUM(i.total) FROM customer c JOIN invoice i ...

User:  What country are they from?
Intent: followup
Rewritten: "What country is the customer with the highest total spend from?"
→ Modifies previous SQL, adds billing_country

User:  Now show top 5 instead
Intent: followup
Rewritten: "Show the top 5 customers by total spend with their country"
→ Adds LIMIT 5 to the existing query

User:  List all jazz albums
Intent: new_question
→ Fresh SQL generated from scratch
```

---

## UI Highlights

**Schema Explorer** (sidebar)
- Live browser of all tables and columns pulled directly from the database at runtime

**"How we got this answer" expander**
- Rewritten query (shown only when it differs from what you typed)
- LLM-as-Judge scores with color-coded indicators
- Generated SQL with syntax highlighting
- Tables and columns referenced in the query
- Raw query results as a labeled DataFrame with proper column names
- Warning badge if SQL needed self-correction retries

---

## Evaluation Framework

Located in `eval/`. Runs automated SQL accuracy evaluation against a ground truth dataset and pushes all scores to Langfuse.

### Metrics computed per question

| Metric | Description |
|---|---|
| `exact_match` | Normalized SQL string match after whitespace/case normalization |
| `structural_match` | sqlglot AST equivalence — catches alias and formatting differences |
| `result_match` | Jaccard similarity between actual query result sets |

### Running the eval

```bash
# Full eval (from Chat2DB root, Docker must be running)
ENV=dev venv/bin/python eval/run_eval.py --llm OpenAI

# Quick test with first N questions
ENV=dev venv/bin/python eval/run_eval.py --llm OpenAI --limit 5

# Using Claude instead
ENV=dev venv/bin/python eval/run_eval.py --llm Claude --limit 5
```

All scores are pushed to Langfuse — open `http://localhost:3000` to view per-question and aggregate results.

### Ground truth dataset

`eval/data/eval_set.csv` — natural language questions paired with expected SQL for the Chinook database.

---

## Setup and Installation

### Prerequisites

| Tool | Version |
|---|---|
| Python | 3.11+ (3.13 recommended) |
| Docker Desktop | Latest |
| OpenAI API key | Required |
| Anthropic API key | Optional (for Claude) |

### 1. Clone and configure

```bash
git clone <repo-url>
cd Chat2DB
cp .env.example .env
```

Edit `.env`:

```env
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...        # optional

LANGFUSE_SECRET_KEY=secret
LANGFUSE_PUBLIC_KEY=public
LANGFUSE_HOST=http://localhost:3000

DB_NAME=chatdb
DB_USER=postgres
DB_PASSWORD=postgres
DB_HOST=localhost
DB_PORT=7433

VECDB_NAME=vecdb
VECDB_USER=postgres
VECDB_PASSWORD=postgres
VECDB_HOST=localhost
VECDB_PORT=6433
```

### 2. Create Python virtual environment

```bash
python3.13 -m venv venv
venv/bin/pip install --upgrade pip setuptools
venv/bin/pip install -r requirements.txt
```

### 3. Start databases and Langfuse

```bash
docker compose up -d
```

Starts:
- PostgreSQL (Chinook) on port **7433**
- pgvector on port **6433**
- Langfuse on port **3000**

### 4. Ingest database docs into vector store

```bash
ENV=dev venv/bin/python -m chat2db.tools.ingest
```

---

## Running the App

```bash
cd Chat2DB
ENV=dev venv/bin/python -m streamlit run chat2db/app.py
```

- **Chatbot UI**: http://localhost:8501
- **Langfuse Dashboard**: http://localhost:3000

### Sample questions

```
What track has the most revenue?
Which customer spent the most?
List all jazz albums
How many tracks per genre?
Show top 5 artists by album count
What is the total revenue by country?
What tables are in the database?        ← answered from schema directly
What columns does the invoice table have?  ← answered from schema directly
```

### Multi-turn follow-ups

```
How many tracks per genre?
→ Now sort by count descending
→ Only show genres with more than 50 tracks
→ What is the average revenue per genre?    ← new question, starts fresh
```

---

## CLI Usage

```bash
# Standard pipeline
ENV=dev venv/bin/python -m chat2db.tools.rag "which customer spent the most" --llm OpenAI

# Hybrid pipeline
ENV=dev venv/bin/python -m chat2db.tools.tag "list all jazz albums" --llm Claude --temperature 0.1
```

---

## Project Structure

```
Chat2DB/
├── chat2db/
│   ├── app.py              # Streamlit UI — intent classifier, query rewriter, chat, LLM-as-judge
│   ├── classifier/
│   │   └── combined_sql_classifier.pkl   # TF-IDF + SVM binary intent classifier
│   └── tools/
│       ├── db.py           # DatabaseManager — schema introspection, query execution (returns named dicts)
│       ├── rag.py          # Standard pipeline — schema-aware conversational NL→SQL
│       ├── tag.py          # Hybrid pipeline — parallel retrieval + agentic self-correcting workflow
│       └── ingest.py       # Vector store ingestion (Docling + pgvector)
├── eval/
│   ├── evaltools.py        # SQL metrics: exact_match, structural_match, result_match
│   ├── run_eval.py         # Eval runner — pushes scores to Langfuse
│   ├── README.md           # Eval framework documentation
│   └── data/
│       └── eval_set.csv    # Ground truth question→SQL pairs
├── db/
│   ├── Chinook_Data_Dictionary.md
│   ├── Chinook_Data_Model.md
│   ├── chinook_business_rules.md   # Curated domain rules injected into Hybrid prompts
│   └── database_setup.sql
├── docker-compose.yml      # PostgreSQL + pgvector + Langfuse
├── Dockerfile
├── Makefile
└── requirements.txt
```

---

## References

- [RAG Paper — Facebook AI](https://arxiv.org/abs/2005.11401)
- [TAG Paper — UC Berkeley & Stanford](https://arxiv.org/pdf/2408.14717)
- [LLM-as-Judge — Zheng et al., 2023](https://arxiv.org/abs/2306.05685)
- [Query Rewriting for RAG — Ma et al., 2023](https://arxiv.org/abs/2305.14283)
- [Chinook Database](https://github.com/lerocha/chinook-database)
- [LlamaIndex Workflows](https://docs.llamaindex.ai/en/stable/module_guides/workflow/)
- [Langfuse Observability](https://langfuse.com/docs)
- Inspired by [garyzava/chat-to-database-chatbot](https://github.com/garyzava/chat-to-database-chatbot)

---

## License

MIT
