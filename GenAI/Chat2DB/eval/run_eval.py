"""
Eval Runner - Runs the eval set through the RAG pipeline, computes SQL accuracy
scores, and pushes them to Langfuse as trace scores.

Usage:
    cd /Users/pokeapokemon/playground_pooja/GenAI/Chat2DB
    ENV=dev venv/bin/python eval/run_eval.py [--llm OpenAI|Claude] [--limit N]
"""

import os
import sys
import csv
import argparse

# Resolve paths
EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
CHAT2DB_DIR = os.path.join(EVAL_DIR, '..', 'chat2db')
sys.path.insert(0, CHAT2DB_DIR)

from dotenv import load_dotenv
load_dotenv(os.path.join(EVAL_DIR, '..', '.env'))

from langfuse import Langfuse
from sqlalchemy import create_engine

from llama_index.core import SQLDatabase
from llama_index.core.query_engine import NLSQLTableQueryEngine
from llama_index.llms.openai import OpenAI
from llama_index.llms.anthropic import Anthropic

from tools.db import DatabaseManager
from evaltools import (
    extract_sql_from_response,
    sql_exact_match,
    sql_structural_match,
    calculate_metrics,
)
from sqltr import SQLTestRunner


def load_eval_set(path: str) -> list[dict]:
    with open(path, newline='') as f:
        return list(csv.DictReader(f))


def build_query_engine(chat_db_manager: DatabaseManager, llm) -> NLSQLTableQueryEngine:
    conn = create_engine(chat_db_manager.get_connection_string())
    sql_database = SQLDatabase(conn)
    table_names = chat_db_manager.get_table_names()
    return NLSQLTableQueryEngine(
        sql_database=sql_database,
        tables=table_names,
        sql_only=False,
        llm=llm,
    )


def run_eval(llm_provider: str = "OpenAI", limit: int = None):
    # --- Setup ---
    os.environ['ENV'] = 'dev'

    chat_db_manager = DatabaseManager(db_type='db')
    if not chat_db_manager.test_connection():
        raise ConnectionError("Cannot connect to domain database (postgres:7433)")

    sql_runner = SQLTestRunner()

    langfuse = Langfuse(
        public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
        secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
        host=os.getenv("LANGFUSE_HOST", "http://localhost:3000"),
    )

    if llm_provider == "OpenAI":
        llm = OpenAI(model="gpt-4o-mini", temperature=0.0)
    else:
        llm = Anthropic(model="claude-3-5-haiku-20241022", temperature=0.0)

    query_engine = build_query_engine(chat_db_manager, llm)

    eval_set = load_eval_set(os.path.join(EVAL_DIR, 'data', 'eval_set.csv'))
    if limit:
        eval_set = eval_set[:limit]

    results = []
    print(f"\nRunning eval — {len(eval_set)} questions | LLM: {llm_provider}\n{'─'*60}")

    for i, row in enumerate(eval_set):
        question = row['question']
        expected_sql = row['expected_sql']
        difficulty = row['difficulty']

        print(f"[{i+1}/{len(eval_set)}] {question}")

        # Create a Langfuse trace per question
        trace = langfuse.trace(
            name="eval-sql-generation",
            input=question,
            metadata={"difficulty": difficulty, "llm_provider": llm_provider},
        )

        try:
            response = query_engine.query(question)
            generated_sql = (
                response.metadata.get("sql_query", "")
                if hasattr(response, "metadata") and response.metadata
                else extract_sql_from_response(str(response))
            )

            exact = sql_exact_match(generated_sql, expected_sql)
            structural = sql_structural_match(generated_sql, expected_sql)
            comparison = sql_runner.compare_results(generated_sql, expected_sql)
            result_score = 1.0 if comparison["match"] else 0.0

            print(f"  Generated : {generated_sql[:80]}...")
            print(f"  Expected  : {expected_sql[:80]}")
            print(f"  Exact={exact}  Structural={structural}  ResultMatch={result_score}\n")

            # Push scores to Langfuse
            trace.score(name="exact_match",      value=float(exact),     comment=f"Expected: {expected_sql}")
            trace.score(name="structural_match", value=float(structural), comment=f"Generated: {generated_sql}")
            trace.score(name="result_match",     value=result_score,     comment=f"Rows: gen={comparison['generated_rows']} exp={comparison['expected_rows']}")

            trace.update(
                output=str(response),
                metadata={
                    "difficulty": difficulty,
                    "llm_provider": llm_provider,
                    "generated_sql": generated_sql,
                    "expected_sql": expected_sql,
                },
            )

            results.append({
                "question": question,
                "difficulty": difficulty,
                "exact_match": exact,
                "structural_match": structural,
                "result_score": result_score,
            })

        except Exception as e:
            print(f"  ERROR: {e}\n")
            trace.score(name="exact_match",      value=0.0, comment=f"Error: {e}")
            trace.score(name="structural_match", value=0.0)
            trace.score(name="result_match",     value=0.0)
            results.append({
                "question": question,
                "difficulty": difficulty,
                "exact_match": False,
                "structural_match": False,
                "result_score": 0.0,
                "error": str(e),
            })

    # Flush all scores to Langfuse
    langfuse.flush()

    # Print summary
    metrics = calculate_metrics(results)
    print(f"\n{'='*60}")
    print(f"EVAL SUMMARY ({llm_provider})")
    print(f"{'='*60}")
    print(f"  Total questions   : {metrics['total_queries']}")
    print(f"  Exact match rate  : {metrics['exact_match_rate']:.1%}")
    print(f"  Structural match  : {metrics['structural_match_rate']:.1%}")
    print(f"  Result match avg  : {metrics['avg_result_score']:.1%}")
    print(f"  Success rate      : {metrics['success_rate']:.1%}")
    print(f"\nScores pushed to Langfuse at {os.getenv('LANGFUSE_HOST')}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run SQL eval and push scores to Langfuse")
    parser.add_argument("--llm", default="OpenAI", choices=["OpenAI", "Claude"], help="LLM provider")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of eval questions")
    args = parser.parse_args()
    run_eval(llm_provider=args.llm, limit=args.limit)
