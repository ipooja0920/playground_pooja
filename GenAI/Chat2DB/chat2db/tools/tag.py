"""
TAG Pipeline - Table-Augmented Generation for database queries.

Enhancements over baseline:
  - Schema-aware prompting: full table/column/FK schema injected into every prompt
  - Self-correcting SQL: up to MAX_RETRIES attempts to fix failed SQL using the error message

Flow:
  StartEvent
    → query_synthesis      (NL → SQL, schema injected)
    → query_execution      (execute SQL; on error → SQLCorrectionEvent)
    → [sql_correction]     (LLM fixes SQL, re-executes; loops up to MAX_RETRIES)
    → answer_generation    (SQL results → natural language)
    → StopEvent
"""

import asyncio
import os
import sys
from pathlib import Path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'eval'))
from evaltools import extract_sql_metadata

from sqlalchemy import create_engine

from llama_index.core import SQLDatabase
from llama_index.core.query_engine import NLSQLTableQueryEngine
from llama_index.llms.openai import OpenAI
from llama_index.llms.anthropic import Anthropic
from llama_index.core.workflow import (
    Workflow, StartEvent, StopEvent, step, Context, Event,
)
from typing import List, Union
from dotenv import load_dotenv

load_dotenv()

MAX_RETRIES = 3


# ── Events ────────────────────────────────────────────────────────────────────

class QuerySynthesisEvent(Event):
    sql_query: str
    query: str
    relevant_tables: List[str]


class QueryExecutionEvent(Event):
    results: List[tuple]
    query: str
    sql_query: str


class SQLCorrectionEvent(Event):
    """Fired when SQL execution fails — carries the bad SQL and the error for the LLM to fix."""
    failed_sql: str
    error: str
    query: str
    attempt: int


# ── Workflow ──────────────────────────────────────────────────────────────────

class TAGWorkflow(Workflow):
    """Table-Augmented Generation workflow with schema awareness and SQL self-correction."""

    def __init__(self, vec_db_manager, chat_db_manager, llm, config=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.vec_db_manager = vec_db_manager
        self.chat_db_manager = chat_db_manager
        self.llm = llm
        self.config = config
        self.schema_info = chat_db_manager.get_schema_info()

        conn = create_engine(self.chat_db_manager.get_connection_string())
        sql_database = SQLDatabase(conn)
        self.query_engine = NLSQLTableQueryEngine(
            sql_database=sql_database,
            tables=self.chat_db_manager.get_table_names(),
            llm=self.llm,
            sql_only=True,
        )

    def _is_valid_sql(self, sql: str) -> bool:
        if not sql:
            return False
        s = sql.strip().upper()
        return s.startswith('SELECT') or s.startswith('WITH') or (
            s.startswith('CREATE TABLE') and 'AS SELECT' in s
        )

    async def _get_schema_async(self) -> str:
        """Fetch live DB schema in a thread executor so it can run concurrently."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.chat_db_manager.get_schema_info)

    async def _get_business_rules_async(self) -> str:
        """Load curated Chinook business rules from disk concurrently."""
        loop = asyncio.get_event_loop()
        def _read():
            rules_path = Path(__file__).parent.parent.parent / "db" / "chinook_business_rules.md"
            return rules_path.read_text() if rules_path.exists() else ""
        return await loop.run_in_executor(None, _read)

    # ── Step 1: Query Synthesis ───────────────────────────────────────────────

    def _make_error_result(self, message: str) -> dict:
        return {"answer": message, "sql": None, "tables": [], "columns": [], "attempts": 1}

    @step
    async def query_synthesis(
        self, ctx: Context, ev: StartEvent
    ) -> Union[QuerySynthesisEvent, StopEvent]:
        """Translate natural language → SQL using the full database schema as context."""
        try:
            await ctx.set("original_query", ev.query)
            all_tables = self.chat_db_manager.get_table_names()

            config = getattr(self, 'config', None)
            conversation_history = getattr(config, 'conversation_history', '') if config else ''
            previous_sql = getattr(config, 'previous_sql', '') if config else ''

            # Parallel retrieval: schema (live DB) and business rules (vector store doc) concurrently
            schema_info, business_rules = await asyncio.gather(
                self._get_schema_async(),
                self._get_business_rules_async(),
            )

            business_rules_section = (
                f"DOMAIN BUSINESS RULES:\n{business_rules}\n\n" if business_rules else ""
            )

            schema_prompt = (
                f"You are an expert SQL assistant that translates natural language to SQL.\n\n"
                f"DATABASE SCHEMA:\n{schema_info}\n\n"
                f"{business_rules_section}"
                f"CONVERSATION HISTORY:\n{conversation_history or 'None'}\n\n"
                f"CURRENT SQL QUERY (if any):\n{previous_sql or 'None'}\n\n"
                f"USER MESSAGE:\n{ev.query}\n\n"
                f"INSTRUCTIONS:\n"
                f"First, silently decide: is the user asking a NEW question or MODIFYING the previous query?\n\n"
                f"Signs it is a MODIFICATION:\n"
                f"- Uses pronouns like 'it', 'that', 'those', 'them'\n"
                f"- Uses words like 'filter', 'only', 'also', 'now', 'instead', 'add', 'remove', 'exclude', 'sort', 'limit', 'top N'\n"
                f"- The message is short and would not make sense without context\n"
                f"- Refers to results just shown\n\n"
                f"Signs it is a NEW question:\n"
                f"- Introduces a completely new entity or topic not in the previous query\n"
                f"- Does not reference anything from the conversation\n"
                f"- Would make sense asked in isolation\n\n"
                f"If MODIFICATION → take the CURRENT SQL QUERY and apply the change. Preserve all existing JOINs, GROUP BY, aliases, and aggregations unless explicitly changed.\n"
                f"If NEW QUESTION → ignore the previous SQL and generate fresh.\n\n"
                f"Return ONLY valid SQL. No explanation. No markdown."
            )

            response = await self.query_engine.aquery(schema_prompt)
            sql_query = response.metadata.get("sql_query", "")
            print(f"[TAG] Generated SQL: {sql_query}")

            if not self._is_valid_sql(sql_query):
                return StopEvent(result=self._make_error_result(
                    "I cannot generate a valid SQL query for this question. "
                    "The required information might not be available in the database."
                ))

            relevant_tables = [t for t in all_tables if t.lower() in sql_query.lower()]
            await ctx.set("sql_query", sql_query)
            await ctx.set("relevant_tables", relevant_tables)

            return QuerySynthesisEvent(
                sql_query=sql_query, query=ev.query, relevant_tables=relevant_tables
            )
        except Exception as e:
            print(f"[TAG] Error in query_synthesis: {e}")
            return StopEvent(result=self._make_error_result(f"Error generating SQL query: {e}"))

    # ── Step 2: Query Execution ───────────────────────────────────────────────

    @step
    async def query_execution(
        self, ctx: Context, ev: QuerySynthesisEvent
    ) -> Union[QueryExecutionEvent, SQLCorrectionEvent]:
        """Execute the generated SQL. On failure, fire SQLCorrectionEvent for retry."""
        await ctx.set("attempts", 1)
        try:
            results = self.chat_db_manager.execute_query(ev.sql_query)
            if results is None:
                raise ValueError("Query returned None — likely a syntax or runtime error.")
            return QueryExecutionEvent(
                results=list(results), query=ev.query, sql_query=ev.sql_query
            )
        except Exception as e:
            print(f"[TAG] Execution failed (attempt 1): {e}")
            return SQLCorrectionEvent(
                failed_sql=ev.sql_query, error=str(e), query=ev.query, attempt=1
            )

    # ── Step 3 (optional): SQL Self-Correction ────────────────────────────────

    @step
    async def sql_correction(
        self, ctx: Context, ev: SQLCorrectionEvent
    ) -> Union[QueryExecutionEvent, StopEvent]:
        """Ask the LLM to fix the failed SQL, then re-execute. Retries up to MAX_RETRIES."""
        if ev.attempt >= MAX_RETRIES:
            print(f"[TAG] Max retries ({MAX_RETRIES}) reached. Giving up.")
            return StopEvent(result=self._make_error_result(
                f"I tried {MAX_RETRIES} times but could not generate a valid SQL query. "
                f"Last error: {ev.error}"
            ))

        correction_prompt = (
            f"The following PostgreSQL query failed with an error.\n\n"
            f"DATABASE SCHEMA:\n{self.schema_info}\n\n"
            f"Original question: {ev.query}\n"
            f"Failed SQL:\n{ev.failed_sql}\n\n"
            f"Error message:\n{ev.error}\n\n"
            f"Fix the SQL query so it runs correctly against the schema above. "
            f"Return ONLY the corrected SQL query, no explanation."
        )

        print(f"[TAG] Attempting SQL correction (attempt {ev.attempt + 1}/{MAX_RETRIES})...")
        correction_response = await self.llm.acomplete(correction_prompt)
        fixed_sql = str(correction_response).strip().strip("```sql").strip("```").strip()
        print(f"[TAG] Corrected SQL: {fixed_sql}")

        try:
            results = self.chat_db_manager.execute_query(fixed_sql)
            if results is None:
                raise ValueError("Corrected query returned None.")
            print(f"[TAG] Correction succeeded on attempt {ev.attempt + 1}")
            return QueryExecutionEvent(
                results=list(results), query=ev.query, sql_query=fixed_sql
            )
        except Exception as e:
            print(f"[TAG] Correction attempt {ev.attempt + 1} still failed: {e}")
            # Fire another correction event with incremented attempt counter
            return SQLCorrectionEvent(
                failed_sql=fixed_sql, error=str(e), query=ev.query, attempt=ev.attempt + 1
            )

    # ── Step 4: Answer Generation ─────────────────────────────────────────────

    @step
    async def answer_generation(
        self, ctx: Context, ev: QueryExecutionEvent
    ) -> StopEvent:
        """Turn SQL results into a natural language answer."""
        try:
            original_query = await ctx.get("original_query")
            attempts = await ctx.get("attempts", default=1)
            result_str = (
                "\n".join(str(r) for r in ev.results) if ev.results else "No results found."
            )
            prompt = (
                f"Answer the following question in clear natural language based on the "
                f"query results. If no results were found, say so.\n\n"
                f"Question: {original_query}\n"
                f"SQL used: {ev.sql_query}\n"
                f"Results:\n{result_str}"
            )
            response = await self.llm.acomplete(prompt)
            meta = extract_sql_metadata(ev.sql_query)
            return StopEvent(result={
                "answer": str(response),
                "sql": ev.sql_query,
                "tables": meta["tables"],
                "columns": meta["columns"],
                "attempts": attempts,
                "raw_results": ev.results,
            })
        except Exception as e:
            print(f"[TAG] Error in answer_generation: {e}")
            return StopEvent(result=self._make_error_result(f"Error generating response: {e}"))


# ── Factory & CLI ─────────────────────────────────────────────────────────────

def create_tag_pipeline(vec_db_manager, chat_db_manager, config):
    llm = (
        OpenAI(model=config.openai_model_name, temperature=config.temperature)
        if config.llm_provider == "OpenAI"
        else Anthropic(model=config.claude_model_name, temperature=config.temperature)
    )
    return TAGWorkflow(
        vec_db_manager=vec_db_manager,
        chat_db_manager=chat_db_manager,
        llm=llm,
        config=config,
        verbose=True,
        timeout=None,
    )


async def run_tag_pipeline(
    query: str, llm_provider: str = "OpenAI", temperature: float = 0.1
) -> str:
    from tools.db import DatabaseManager

    vec_db_manager = DatabaseManager(db_type='vecdb')
    chat_db_manager = DatabaseManager(db_type='db')

    if not vec_db_manager.test_connection():
        raise ConnectionError("Vector Database connection failed")
    if not chat_db_manager.test_connection():
        raise ConnectionError("Database connection failed")

    llm = (
        OpenAI(model="gpt-4o-mini", temperature=temperature)
        if llm_provider == "OpenAI"
        else Anthropic(model="claude-3-5-haiku-20241022", temperature=temperature)
    )
    workflow = TAGWorkflow(
        vec_db_manager=vec_db_manager,
        chat_db_manager=chat_db_manager,
        llm=llm,
        verbose=True,
        timeout=None,
    )
    result = await workflow.run(query=query)
    print(f"Final Result: {result}")
    return result


async def main():
    import argparse
    os.environ['ENV'] = 'dev'
    parser = argparse.ArgumentParser(description='TAG Pipeline CLI')
    parser.add_argument('query')
    parser.add_argument('--llm', default='OpenAI', choices=['OpenAI', 'Claude'])
    parser.add_argument('--temperature', type=float, default=0.1)
    args = parser.parse_args()
    try:
        await run_tag_pipeline(args.query, args.llm, args.temperature)
    except Exception as e:
        print(f"Error: {e}")
        return 1
    return 0


if __name__ == "__main__":
    import sys
    import asyncio
    sys.exit(asyncio.run(main()))
