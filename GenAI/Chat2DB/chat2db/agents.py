"""
AI agents for per-answer enrichment:

  • generate_explanation  — plain-English breakdown of SQL + key insight
  • determine_chart       — Agent 1: should we chart this? what type?
  • validate_chart        — Agent 2: is the chart spec correct against the data?
  • extract_joins         — sqlglot-based JOIN extraction (no LLM needed)
"""

import json

import sqlglot
from sqlglot import exp

from llama_index.llms.openai import OpenAI as OpenAILLM
from llama_index.llms.anthropic import Anthropic as AnthropicLLM


# ── Helpers ───────────────────────────────────────────────────────────────────

def _llm(provider: str):
    return (
        OpenAILLM(model="gpt-4o-mini", temperature=0.0)
        if provider == "OpenAI"
        else AnthropicLLM(model="claude-3-5-haiku-20241022", temperature=0.0)
    )


def _strip_md(text: str) -> str:
    """Strip markdown code fences from an LLM response."""
    text = text.strip()
    if text.startswith("```"):
        parts = text.split("```")
        text = parts[1] if len(parts) > 1 else text
        if text.startswith("json"):
            text = text[4:]
    return text.strip()


def extract_joins(sql: str) -> list[str]:
    """Parse SQL with sqlglot and return a human-readable list of JOIN clauses."""
    if not sql:
        return []
    try:
        parsed = sqlglot.parse_one(sql, dialect="postgres")
        joins = []
        for join in parsed.find_all(exp.Join):
            table = join.name or "?"
            kind  = str(join.args.get("kind", "")).strip() or "INNER"
            on_node = join.args.get("on")
            on_str  = on_node.sql(dialect="postgres") if on_node else ""
            joins.append(f"{kind} JOIN {table}" + (f" ON {on_str}" if on_str else ""))
        return joins
    except Exception:
        return []


# ── Agent 1 — chart decision ──────────────────────────────────────────────────

CHART_SCHEMA = (
    '{"chartable": true|false, '
    '"chart_type": "bar"|"line"|"pie"|"scatter"|null, '
    '"x_column": "<col>"|null, '
    '"y_column": "<col>"|null, '
    '"title": "<title>"|null, '
    '"reason": "<one line>"}'
)


async def determine_chart(data: list[dict], question: str, llm_provider: str) -> dict:
    """
    Agent 1 — Decide whether the result set is chartable.

    Returns a dict with keys: chartable, chart_type, x_column, y_column, title, reason.
    """
    if not data or len(data) < 2:
        return {"chartable": False, "reason": "Fewer than 2 rows — nothing to plot."}

    columns = list(data[0].keys())
    sample  = data[:8]

    prompt = (
        "You are a data-visualisation expert. Decide whether the query result below "
        "should be shown as a chart.\n\n"
        f"User question: {question}\n"
        f"Columns: {columns}\n"
        f"Sample rows (up to 8): {sample}\n\n"
        "Rules:\n"
        "- Only recommend a chart when it meaningfully communicates the data.\n"
        "- Choose bar for categorical comparisons, line for time-series or ordered "
        "numeric x-axis, pie for part-of-whole (≤8 slices), scatter for two continuous "
        "numeric dimensions.\n"
        "- x_column must be a column that exists in the data.\n"
        "- y_column must be a numeric column (integers, floats, or decimal strings).\n"
        "- If no meaningful chart is possible set chartable=false.\n\n"
        f"Reply with ONLY valid JSON matching exactly: {CHART_SCHEMA}"
    )
    try:
        resp = await _llm(llm_provider).acomplete(prompt)
        result = json.loads(_strip_md(str(resp)))
        print(f"[ChartAgent] {result}")
        return result
    except Exception as e:
        print(f"[ChartAgent] determine_chart error: {e}")
        return {"chartable": False, "reason": f"Agent error: {e}"}


# ── Agent 2 — chart validation ────────────────────────────────────────────────

async def validate_chart(
    chart_info: dict, data: list[dict], llm_provider: str
) -> dict:
    """
    Agent 2 — Validate the chart spec against the actual data.

    Returns: {"valid": bool, "issues": list[str], "fixed": dict|None}
    If issues are found, asks the LLM to produce a corrected spec.
    """
    if not chart_info.get("chartable"):
        return {"valid": False, "issues": ["Not chartable"], "fixed": None}

    columns = list(data[0].keys()) if data else []
    x_col   = chart_info.get("x_column")
    y_col   = chart_info.get("y_column")
    issues  = []

    # Structural checks (no LLM needed)
    if x_col and x_col not in columns:
        issues.append(f"x_column '{x_col}' does not exist (available: {columns})")
    if y_col and y_col not in columns:
        issues.append(f"y_column '{y_col}' does not exist (available: {columns})")
    elif y_col and y_col in columns:
        vals = [row.get(y_col) for row in data if row.get(y_col) is not None]
        if vals:
            try:
                [float(v) for v in vals]
            except (ValueError, TypeError):
                issues.append(f"y_column '{y_col}' is not numeric")

    if not issues:
        return {"valid": True, "issues": [], "fixed": None}

    # Ask LLM to fix the spec
    prompt = (
        "A chart specification has validation issues. Produce a corrected spec.\n\n"
        f"Original spec: {json.dumps(chart_info)}\n"
        f"Available columns: {columns}\n"
        f"Data sample: {data[:3]}\n"
        f"Issues found: {issues}\n\n"
        f"Reply with ONLY valid JSON matching: {CHART_SCHEMA}\n"
        'If no chart is possible, return {"chartable": false, "reason": "..."}.'
    )
    try:
        resp  = await _llm(llm_provider).acomplete(prompt)
        fixed = json.loads(_strip_md(str(resp)))
        print(f"[ChartValidator] fixed → {fixed}")
        return {"valid": False, "issues": issues, "fixed": fixed}
    except Exception as e:
        return {"valid": False, "issues": issues + [str(e)], "fixed": None}


# ── Explanation agent ─────────────────────────────────────────────────────────

async def generate_explanation(
    question: str,
    sql: str,
    results: list,
    tables: list,
    columns: list,
    llm_provider: str,
) -> str:
    """
    Generate a three-part plain-English explanation of the SQL and its results.
    Parts: what the SQL did · key insight · short summary.
    """
    if not sql:
        return (
            "This answer was retrieved directly from the database schema "
            "without executing a SQL query."
        )

    result_sample = str(results[:5]) if results else "No results returned."

    prompt = (
        "Explain this database query result in plain English for a business user.\n\n"
        f"User question: {question}\n"
        f"Tables used: {', '.join(tables) if tables else 'unknown'}\n"
        f"Key columns: {', '.join(columns[:10]) if columns else 'unknown'}\n"
        f"SQL:\n{sql}\n\n"
        f"Sample results: {result_sample}\n\n"
        "Write a structured explanation with exactly these three sections "
        "(use markdown bold for headers):\n\n"
        "**What the SQL did** — 1–2 sentences describing what was fetched and how "
        "(mention JOINs, filters, aggregations if present).\n\n"
        "**Key insight** — The single most important takeaway from the results.\n\n"
        "**Summary** — One plain-English sentence a non-technical stakeholder would "
        "immediately understand.\n\n"
        "Keep it concise. No code. No bullet lists inside sections."
    )
    try:
        resp = await _llm(llm_provider).acomplete(prompt)
        return str(resp).strip()
    except Exception as e:
        print(f"[ExplanationAgent] {e}")
        return f"Explanation unavailable: {e}"
