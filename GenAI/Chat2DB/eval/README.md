# Evaluation Framework

Automated SQL accuracy evaluation for Chat2DB. Runs a ground truth dataset through the pipeline, computes three metrics per question, and pushes all scores to Langfuse.

---

## Quick Start

```bash
# From Chat2DB root — Docker must be running first
docker compose up -d

# Run full eval with OpenAI
ENV=dev venv/bin/python eval/run_eval.py --llm OpenAI

# Run first 5 questions only (quick smoke test)
ENV=dev venv/bin/python eval/run_eval.py --llm OpenAI --limit 5

# Run with Claude
ENV=dev venv/bin/python eval/run_eval.py --llm Claude --limit 5
```

Scores are pushed to Langfuse at `http://localhost:3000` automatically.

---

## Metrics

| Metric | Description | Range |
|---|---|---|
| `exact_match` | Normalized SQL string comparison (whitespace + case stripped, semicolons removed) | 0 or 1 |
| `structural_match` | sqlglot AST equivalence — catches alias/formatting differences that fool string matching | 0 or 1 |
| `result_match` | Jaccard similarity between actual query result sets — measures if the right data was returned even if SQL differs | 0.0–1.0 |

All three scores are pushed per question to Langfuse as individual `trace.score()` calls so you can filter, aggregate, and compare across runs.

---

## Files

### `evaltools.py`

Core utility functions:

| Function | Description |
|---|---|
| `normalize_sql(sql)` | Strip whitespace, semicolons, uppercase for comparison |
| `sql_exact_match(gen, exp)` | True if normalized SQL strings are identical |
| `sql_structural_match(gen, exp)` | True if sqlglot-parsed ASTs are equivalent |
| `result_match(gen_rows, exp_rows)` | Jaccard index between result row sets |
| `extract_sql_from_response(text)` | Extract SQL from LLM response (handles code blocks) |
| `extract_sql_metadata(sql)` | Extract table and column names from SQL via sqlglot |
| `calculate_metrics(results)` | Aggregate metrics across all eval results |

### `run_eval.py`

CLI eval runner:
- Reads `eval/data/eval_set.csv`
- Runs each question through `NLSQLTableQueryEngine`
- Computes exact_match, structural_match, result_match
- Pushes scores to Langfuse
- Prints aggregate summary at the end

### `data/eval_set.csv`

Ground truth dataset. Each row contains:
- `question` — natural language question
- `expected_sql` — correct SQL for the Chinook database

---

## Viewing Results in Langfuse

1. Open `http://localhost:3000`
2. Go to **Traces** — each eval question is a separate trace
3. Go to **Scores** — filter by `exact_match`, `structural_match`, or `result_match`
4. Use the dashboard to compare performance across LLM providers or prompt changes

---

## Adding New Test Questions

Edit `eval/data/eval_set.csv` and add rows:

```csv
question,expected_sql
"How many customers are from Brazil?","SELECT COUNT(*) FROM customer WHERE country = 'Brazil'"
```

Use the Chinook schema as reference — tables: `customer`, `invoice`, `invoice_line`, `track`, `album`, `artist`, `genre`, `playlist`, `playlist_track`, `employee`, `media_type`.
