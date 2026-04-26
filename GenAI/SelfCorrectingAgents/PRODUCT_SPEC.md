# Self-Correcting Multi-Agent System — Product Specification

> Reference implementation: [attharva-j/ai-playground](https://github.com/attharva-j/ai-playground/tree/main/self-correcting-multi-agent-system)

---

## Overview

A **Self-Correcting Multi-Agent System** where specialised AI agents collaborate in an iterative loop to produce accurate, validated, evidence-grounded answers. Rather than relying on a single model call, the system uses multiple agents that validate and critique each other's work — automatically correcting mistakes before surfacing a final answer.

Delivered as a **Streamlit application** with three live panels: a chat interface, a full agent trace (reasoning + corrections), and a debug panel (logs, failures, token usage).

---

## Expected Outcomes

| Metric | Expected Improvement vs Single Agent |
|--------|--------------------------------------|
| Hallucination Rate | 25–40% reduction |
| Answer Accuracy | 15–30% improvement |
| Evidence-Based Responses | 50–70% increase |
| Task Success Rate | Measurably higher on complex, multi-step problems |

---

## Architecture

### Agent Pipeline

```
User Question
      │
      ▼
┌─────────────┐
│   Solver    │  Generates initial solution with reasoning, evidence, confidence
└──────┬──────┘
       │ answer
       ▼
┌─────────────┐
│   Critic    │  Reviews for accuracy, logic, completeness → APPROVE or REJECT
└──────┬──────┘
       │
       ├─── APPROVE ──▶ ┌─────────────┐
       │                │    Judge    │  Final validation → PASS or FAIL
       │                └──────┬──────┘
       │                       │ PASS
       │                       ▼
       │                  Final Answer
       │
       └─── REJECT ──▶ Solver revises with critic feedback
                        (loop up to max_iterations)
                              │
                        (if max iterations reached)
                              ▼
                        Best available answer
```

### Core Agents

| Agent | Role | Temperature | Decision |
|-------|------|-------------|---------|
| **Solver** | Generates initial solution. On revision, incorporates critic feedback. | 0.1 | — |
| **Critic** | Reviews for factual accuracy, logical consistency, completeness. Minor style issues = APPROVE; factual errors, major gaps = REJECT. | 0.3 | APPROVE / REJECT |
| **Judge** | Final validation of critic-approved answers. Checks evidence quality, hallucinations, factual grounding. | 0.0 | PASS / FAIL |
| **Orchestrator** | Manages the iteration loop, builds revision context from critic feedback, aggregates results. | — | — |

### Tools Available to Agents

| Tool | File | What it does |
|------|------|--------------|
| **Web Search** | `tools/web_search.py` | Tavily API — searches the web, returns structured results with URL, content, relevance score. Also has `verify_claim()` for fact checking. |
| **Database** | `tools/database_tool.py` | SQLite with sample financial data (5 companies, 2020–2023). Supports SQL queries, schema inspection, financial ratio calculations (profit margin, debt ratio). |
| **Code Executor** | `tools/code_executor.py` | Sandboxed Python execution via subprocess. Validates code safety before running. Supports math calculations and data processing. Allowed imports: math, statistics, pandas, numpy, matplotlib, json, datetime, csv, re, collections. |
| **Document Retriever** | `tools/document_retriever.py` | Semantic search using `sentence-transformers/all-MiniLM-L6-v2`. SQLite-backed document store with 5 sample documents (ML, finance, quantum computing, customer service, data privacy). Falls back to keyword search if model unavailable. |

---

## Streamlit UI — Three Panels

The app is organised as three tabs in a single page, running in real time as agents execute.

### Tab 1: 💬 Chat

| Element | Description |
|---------|-------------|
| Chat history | Full conversation — all user questions and final accepted answers, persisted across queries |
| Final answer | The validated answer (PASS from Judge, or best available if max iterations reached) |
| Confidence badge | Confidence score from Judge alongside each answer |
| Status indicator | Whether the answer was accepted (✅) or reached max iterations (⚠️) |
| Chat input | Fixed at bottom; accepts any question |

### Tab 2: 🤖 Agent Trace

Shows the complete reasoning trace for the selected query — every agent, every iteration, every decision.

| Element | Description |
|---------|-------------|
| Solver output (iteration N) | Answer, reasoning, evidence list, confidence score |
| Critic feedback (iteration N) | Decision (APPROVE/REJECT), issues found, suggestions, missing elements, feedback summary |
| Judge output | Decision (PASS/FAIL), evidence quality (STRONG/MODERATE/WEAK), concerns, validation score |
| Revision context | The critic feedback passed back to Solver for revision (when REJECT) |
| Iteration counter | Which iteration each step belongs to, clearly labelled |

### Tab 3: 🐛 Debug

| Element | Description |
|---------|-------------|
| Agent failures | Which agent failed and at which iteration (Critic REJECT, Judge FAIL, API error) |
| Retry attempts | How many times each agent retried and why |
| Token usage | Per-agent token counts per iteration, total tokens for the run |
| Latency | Per-agent latency in ms per iteration |
| Full logs | All `SystemLogger` interactions — agent type, input prompt, output, timestamp |
| API errors | Any OpenAI / Tavily errors, with full traceback |
| Session metadata | Session ID, total iterations, final decision reason |

### Sidebar Settings

| Setting | Default | Description |
|---------|---------|-------------|
| Max iterations | 3 | How many Solver → Critic → Judge cycles before giving up |
| Judge confidence threshold | 0.5 | Minimum confidence for Judge to PASS |
| Enable web search | True | Toggle Tavily web search for Solver |
| Enable document retrieval | True | Toggle semantic document search |
| Enable code execution | True | Toggle Python code execution tool |
| Enable database queries | True | Toggle SQLite financial database tool |

---

## Use Cases

| Use Case | Tools Used | Description |
|----------|-----------|-------------|
| **Document Q&A with Citations** | Document Retriever | Answer questions with references to specific source documents |
| **Financial Analysis** | Database Tool, Code Executor | Query financial data, compute ratios, explain results |
| **Multi-Step Reasoning** | Web Search | Complex KPI calculations and analytical questions with justification |
| **Code Generation & Validation** | Code Executor | Generate Python code and automatically test it before surfacing |

---

## Evaluation Module

The `evaluation/` directory provides a full offline evaluation framework (separate from the Streamlit app):

| File | What it does |
|------|-------------|
| `metrics.py` | Calculates `PerformanceMetrics` — accuracy, groundedness, hallucination rate, iteration efficiency, latency, cost multiplier, quality gain vs single agent |
| `evaluator.py` | `SystemEvaluator` — runs test cases, compares multi-agent vs single-agent, generates performance reports with recommendations, saves results to `data/evaluation_results/` |
| `synthetic_data.py` | `SyntheticDataGenerator` — generates test cases across categories: factual, conceptual, reasoning, financial analysis, edge cases |

### Evaluation Metrics Tracked

| Metric | Description |
|--------|-------------|
| Accuracy Score | Proxy accuracy based on validation success × confidence |
| Confidence Score | Average Judge confidence across runs |
| Validation Success Rate | % of answers accepted by Judge |
| Hallucination Rate | Estimated % of unverifiable claims |
| Groundedness Score | % of answers with verifiable evidence |
| Average Iterations | How many cycles needed to converge |
| Average Latency | End-to-end response time |
| Average Tokens | API cost proxy |
| Cost Efficiency | Accuracy per iteration unit |
| Confidence Improvement | vs single-agent baseline |

### Running Evaluation

```bash
python -c "from evaluation.evaluator import SystemEvaluator; e = SystemEvaluator(); e.run_benchmark_suite()"
```

Results saved to `data/evaluation_results/`.

---

## Technical Stack

| Component | Technology |
|-----------|-----------|
| **LLM** | OpenAI `gpt-4o` via `openai` Python SDK |
| **Web Search** | Tavily API (`tavily-python`) |
| **Document Search** | `sentence-transformers` — `all-MiniLM-L6-v2` |
| **Database** | SQLite (`sqlite3`, stdlib) with sample financial data |
| **Code Execution** | Sandboxed subprocess execution |
| **UI** | Streamlit |
| **Data Validation** | Pydantic v2 |
| **Logging** | Custom `SystemLogger` + JSON session files |
| **Evaluation** | Custom metrics module + `numpy`, `pandas` |

---

## APIs Required

| API | Used For | Required? |
|-----|---------|-----------|
| `OPENAI_API_KEY` | All three agents (Solver, Critic, Judge) | **Required** |
| `TAVILY_API_KEY` | Web search tool (Solver agent) | Optional — system falls back to LLM knowledge only |

> Tavily free tier: 1000 searches/month. Get key at [tavily.com](https://tavily.com).

---

## Project Structure

```
SelfCorrectingAgents/
├── app.py                        # Streamlit UI — Chat, Agent Trace, Debug panels
│
├── agents/
│   ├── __init__.py
│   ├── solver_agent.py           # Generates solutions; revises using critic feedback
│   ├── critic_agent.py           # Reviews answers → APPROVE or REJECT
│   ├── judge_agent.py            # Final validation → PASS or FAIL
│   └── orchestrator.py           # Coordinates the full iteration loop
│
├── tools/
│   ├── __init__.py
│   ├── web_search.py             # Tavily web search + claim verification
│   ├── database_tool.py          # SQLite financial database queries
│   ├── code_executor.py          # Sandboxed Python code execution
│   └── document_retriever.py     # Semantic document search (sentence-transformers)
│
├── evaluation/
│   ├── __init__.py
│   ├── metrics.py                # PerformanceMetrics calculations
│   ├── evaluator.py              # SystemEvaluator — full eval framework
│   └── synthetic_data.py         # Test case generator
│
├── utils/
│   ├── __init__.py
│   ├── config.py                 # AgentConfig + SystemConfig dataclasses
│   ├── logger.py                 # SystemLogger — session tracking to JSON files
│   └── prompts.py                # Prompt templates for all three agents
│
├── data/
│   ├── sample_documents/         # Test documents for document retriever
│   ├── financial_data.json       # Sample financial dataset (5 companies, 2020–2023)
│   ├── documents.db              # SQLite document store (auto-created)
│   ├── logs/                     # Session log files (auto-created)
│   └── evaluation_results/       # Benchmark results (auto-created)
│
├── requirements.txt
├── .env.example
└── PRODUCT_SPEC.md               # This file
```

---

## How to Run

### 1. Install Dependencies

```bash
cd GenAI/SelfCorrectingAgents
pip install -r requirements.txt
```

### 2. Set Up API Keys

```bash
cp .env.example .env
```

Edit `.env`:
```
OPENAI_API_KEY=sk-proj-your-key-here
TAVILY_API_KEY=tvly-your-key-here   # Optional
```

### 3. Run the Streamlit App

```bash
streamlit run app.py
```

Opens at `http://localhost:8501`.

### 4. Use It

1. Type any question in the chat box
2. Watch agents work in real time (live status in Chat tab)
3. Switch to **Agent Trace** tab to see every agent's reasoning and decisions
4. Switch to **Debug** tab to see logs, token usage, and any failures

---

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Solver → Critic → Judge (3 agents) | Each layer catches different failure modes: Critic catches logic/completeness, Judge catches hallucination and evidence quality |
| Max 3 iterations default | Balances quality improvement vs API cost; each iteration adds 3 LLM calls |
| Judge threshold 0.5 | Lower than typical to avoid over-rejection; tune up for stricter grounding |
| Temperature: Solver 0.1, Critic 0.3, Judge 0.0 | Solver needs some creativity; Critic needs nuance; Judge must be deterministic |
| SQLite for document store | No external vector DB required — zero setup, runs locally |
| Sandboxed code executor | subprocess isolation prevents dangerous code from affecting the host system |
| JSON session logs | Full audit trail of every agent interaction; readable without special tooling |
| Streamlit `st.status` | Shows live agent progress during execution without needing WebSockets |

---

## Error Handling

| Failure | Behaviour |
|---------|-----------|
| OpenAI API error in any agent | Caught, logged to Debug panel, fallback response with confidence 0.0 |
| Tavily API key missing | Web search disabled gracefully; Solver answers from training knowledge |
| Max iterations reached without Judge PASS | Best available Solver answer is returned with ⚠️ warning badge |
| Code execution timeout (30s) | Returns error message in ExecutionResult; does not crash pipeline |
| Document retriever model unavailable | Falls back to keyword search automatically |
| SQLite database missing | Auto-creates with sample financial data on first run |
