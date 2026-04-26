"""
RAG Pipeline - Retrieval-Augmented Generation for database queries.

Flow:
  1. User question → Query vector index (database docs) for context
  2. LLM generates SQL using retrieved context
  3. NLSQLTableQueryEngine executes SQL and generates natural language response

Adapted from LlamaIndex's example repository:
  https://docs.llamaindex.ai/en/stable/examples/
"""

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'eval'))
from evaltools import extract_sql_metadata

from tools.ingest import VectorSearch
from tools.db import DatabaseManager

from sqlalchemy import create_engine

from llama_index.core import SQLDatabase
from llama_index.core.query_engine import NLSQLTableQueryEngine

from llama_index.llms.openai import OpenAI
from llama_index.llms.anthropic import Anthropic

from dotenv import load_dotenv

load_dotenv()


class RAGSearch(VectorSearch):
    """RAG-based search: uses vector context to generate and execute SQL."""

    def __init__(self, vec_db_manager, chat_db_manager, config, *args, **kwargs):
        super().__init__(vec_db_manager, *args, **kwargs)
        self.chat_db_manager = chat_db_manager
        self.config = config

        # Assign LLM model based on provider selection
        if self.config.llm_provider == "OpenAI":
            self.llm = OpenAI(
                temperature=self.config.temperature,
                model=self.config.openai_model_name,
            )
        elif self.config.llm_provider == "Claude":
            self.llm = Anthropic(
                temperature=self.config.temperature,
                model=self.config.claude_model_name,
            )

    def query(self, query_text: str) -> str:
        """Query the vector index to get context for SQL generation."""
        index = self.load_index()
        query_engine = index.as_query_engine(llm=self.llm)
        response = query_engine.query(query_text)
        return response

    def sql_query(self, query_text: str) -> dict:
        """Perform a schema-aware text-to-SQL query on the connected database.

        Returns a structured dict with answer, sql, tables, columns, and raw_results.
        """
        conn = create_engine(self.chat_db_manager.get_connection_string())
        sql_database = SQLDatabase(conn)
        table_names = self.chat_db_manager.get_table_names()
        schema_info = self.chat_db_manager.get_schema_info()

        schema_prompt = (
            f"You are an expert SQL assistant that translates natural language to SQL.\n\n"
            f"DATABASE SCHEMA:\n{schema_info}\n\n"
            f"CONVERSATION HISTORY:\n{self.config.conversation_history or 'None'}\n\n"
            f"CURRENT SQL QUERY (if any):\n{self.config.previous_sql or 'None'}\n\n"
            f"USER MESSAGE:\n{query_text}\n\n"
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
            f"Using ONLY the tables and columns in the schema above, write and execute a valid PostgreSQL SELECT query."
        )

        query_engine = NLSQLTableQueryEngine(
            sql_database=sql_database,
            tables=table_names,
            sql_only=False,
            llm=self.llm,
        )
        response = query_engine.query(schema_prompt)

        sql = response.metadata.get("sql_query", "") if response.metadata else ""
        meta = extract_sql_metadata(sql)
        raw = self.chat_db_manager.execute_query(sql) if sql else []
        if raw is None:
            raw = []

        return {
            "answer": str(response),
            "sql": sql,
            "tables": meta["tables"],
            "columns": meta["columns"],
            "attempts": 1,
            "raw_results": raw,
        }


def run_rag_pipeline(
    query: str, llm_provider: str = "OpenAI", temperature: float = 0.1
) -> str:
    """Run the RAG pipeline with given parameters (standalone usage)."""
    config = type(
        "Config",
        (),
        {
            "llm_provider": llm_provider,
            "temperature": temperature,
            "openai_model_name": "gpt-4",
            "claude_model_name": "claude-3-5-sonnet-20241022",
        },
    )()

    # Initialize databases
    vec_db_manager = DatabaseManager(db_type='vecdb')
    chat_db_manager = DatabaseManager(db_type='db')

    if not vec_db_manager.test_connection():
        raise ConnectionError("Vector Database connection failed")
    if not chat_db_manager.test_connection():
        raise ConnectionError("Database connection failed")

    # Initialize RAGSearch
    rag_search = RAGSearch(vec_db_manager, chat_db_manager, config)

    # Generate and execute query
    sql_query = rag_search.query(
        f"You are Postgres expert. Generate a SQL based on the following "
        f"question using the additional metadata given to you: {query}"
    )
    print(f"Generated SQL: {sql_query}")

    sql_result = rag_search.sql_query(str(sql_query))
    print(f"Final Result: {sql_result}")


def main():
    """CLI entrypoint for running the RAG pipeline."""
    import argparse

    os.environ['ENV'] = 'dev'

    parser = argparse.ArgumentParser(description='RAG Pipeline CLI')
    parser.add_argument('query', help='Natural language query for the database')
    parser.add_argument(
        '--llm',
        default='OpenAI',
        choices=['OpenAI', 'Claude'],
        help='LLM provider to use (default: OpenAI)',
    )
    parser.add_argument(
        '--temperature',
        type=float,
        default=0.1,
        help='Temperature for LLM (default: 0.1)',
    )

    args = parser.parse_args()
    try:
        run_rag_pipeline(args.query, args.llm, args.temperature)
    except Exception as e:
        print(f"Error in RAG main(): {e}")
        return 1
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
