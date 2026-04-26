"""
Evaluation Tools - Utility functions for evaluating SQL generation quality.

Provides metrics for comparing generated SQL against ground truth,
and functions for calling LLMs and processing results.
"""

import re
from typing import Optional
import sqlglot


def normalize_sql(sql: str) -> str:
    """Normalize a SQL query for comparison.
    
    Removes whitespace variations, standardizes casing,
    and strips trailing semicolons.
    """
    if not sql:
        return ""
    
    # Remove extra whitespace
    sql = re.sub(r'\s+', ' ', sql.strip())
    # Remove trailing semicolons
    sql = sql.rstrip(';')
    # Uppercase for comparison
    sql = sql.upper()
    return sql


def sql_exact_match(generated: str, expected: str) -> bool:
    """Check if two SQL queries are exactly equal after normalization."""
    return normalize_sql(generated) == normalize_sql(expected)


def sql_structural_match(generated: str, expected: str) -> bool:
    """Check if two SQL queries are structurally equivalent using sqlglot.
    
    This catches cases where queries are logically identical but
    use different formatting/aliases.
    """
    try:
        gen_parsed = sqlglot.transpile(generated, pretty=True)[0]
        exp_parsed = sqlglot.transpile(expected, pretty=True)[0]
        return normalize_sql(gen_parsed) == normalize_sql(exp_parsed)
    except Exception:
        return False


def result_match(generated_results: list, expected_results: list) -> float:
    """Calculate the overlap between generated and expected query results.
    
    Returns a score between 0.0 and 1.0.
    """
    if not expected_results:
        return 1.0 if not generated_results else 0.0
    
    if not generated_results:
        return 0.0

    # Convert to sets of tuples for comparison
    gen_set = set(tuple(r) if isinstance(r, (list, tuple)) else (r,) for r in generated_results)
    exp_set = set(tuple(r) if isinstance(r, (list, tuple)) else (r,) for r in expected_results)

    # Calculate intersection over union (Jaccard index)
    intersection = gen_set & exp_set
    union = gen_set | exp_set

    return len(intersection) / len(union) if union else 0.0


def extract_sql_from_response(text: str) -> Optional[str]:
    """Extract SQL query from LLM response text.
    
    Handles various formats:
    - Bare SQL
    - SQL wrapped in ```sql ... ``` code blocks
    - SQL preceded by explanatory text
    """
    if not text:
        return None

    # Try to extract from code blocks first
    code_block_pattern = r'```(?:sql)?\s*(.*?)\s*```'
    matches = re.findall(code_block_pattern, text, re.DOTALL | re.IGNORECASE)
    if matches:
        return matches[0].strip()

    # Try to find SELECT/WITH statement
    sql_pattern = r'((?:SELECT|WITH)\s+.*?)(?:;|\Z)'
    matches = re.findall(sql_pattern, text, re.DOTALL | re.IGNORECASE)
    if matches:
        return matches[0].strip()

    return text.strip()


def extract_sql_metadata(sql: str) -> dict:
    """Extract tables and columns referenced in a SQL query using sqlglot.

    Returns:
        Dict with 'tables' and 'columns' lists
    """
    if not sql:
        return {"tables": [], "columns": []}
    try:
        import sqlglot
        import sqlglot.expressions as exp
        ast = sqlglot.parse_one(sql, dialect="postgres")
        tables = sorted({t.name for t in ast.find_all(exp.Table) if t.name})
        columns = sorted({c.name for c in ast.find_all(exp.Column) if c.name})
        return {"tables": tables, "columns": columns}
    except Exception:
        return {"tables": [], "columns": []}


def calculate_metrics(results: list) -> dict:
    """Calculate aggregate metrics from evaluation results.
    
    Args:
        results: List of dicts with keys: 'exact_match', 'structural_match', 'result_score'
    
    Returns:
        Dict with aggregate metrics
    """
    if not results:
        return {}

    n = len(results)
    return {
        "total_queries": n,
        "exact_match_rate": sum(r.get("exact_match", False) for r in results) / n,
        "structural_match_rate": sum(r.get("structural_match", False) for r in results) / n,
        "avg_result_score": sum(r.get("result_score", 0.0) for r in results) / n,
        "success_rate": sum(1 for r in results if not r.get("error")) / n,
    }
