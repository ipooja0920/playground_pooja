"""
Chat2DB - Main Streamlit Application

Improvements over baseline:
  - Schema Explorer in sidebar (live table/column browser)
  - "How we got this answer" expander: SQL, tables used, columns used
  - LLM-as-judge scores displayed inline (relevance + answer_quality)
  - Tabular results rendered as a DataFrame when possible
  - Both RAG and TAG pipelines return structured metadata
"""

import streamlit as st
from dataclasses import dataclass

from dotenv import load_dotenv
from tools.db import DatabaseManager
from tools.rag import RAGSearch
from tools.tag import create_tag_pipeline

load_dotenv()

import asyncio
import pickle
from pathlib import Path

import pandas as pd

from langfuse.llama_index import LlamaIndexInstrumentor
from langfuse.decorators import langfuse_context, observe
from llama_index.llms.openai import OpenAI as OpenAILLM
from llama_index.llms.anthropic import Anthropic as AnthropicLLM


@dataclass
class ChatConfig:
    interaction_method: str
    llm_provider: str
    openai_model_name: str = "gpt-4o-mini"
    claude_model_name: str = "claude-3-5-sonnet-20241022"
    temperature: float = 0.1
    conversation_history: str = ""
    previous_sql: str = ""


class ChatDatabase:
    def __init__(self):
        try:
            self.vec_db_manager = DatabaseManager(db_type='vecdb')
            self.vec_db_manager.test_connection()
        except Exception as e:
            st.error(f"Error connecting to vector store: {e}")
            self.vec_db_manager = None

        try:
            self.chat_db_manager = DatabaseManager(db_type='db')
            self.chat_db_manager.test_connection()
        except Exception as e:
            st.error(f"Error connecting to SQL database: {e}")
            self.chat_db_manager = None

        self.classifier = self._load_classifier()
        self.instrumentor = LlamaIndexInstrumentor()
        self.instrumentor.start()

    def _load_classifier(self):
        model_path = Path(__file__).parent / 'classifier/combined_sql_classifier.pkl'
        if not model_path.exists():
            return None
        try:
            with open(model_path, 'rb') as f:
                return pickle.load(f)
        except Exception:
            return None

    def classify_prompt(self, prompt: str) -> bool:
        if self.classifier is None:
            return True
        vectorizer = self.classifier["vectorizer"]
        binary_clf = self.classifier["binary_classifier"]
        is_sql = binary_clf.predict(vectorizer.transform([prompt]))[0]
        return bool(is_sql)

    async def _judge_response(self, query: str, response: str, config: ChatConfig) -> dict:
        """Rate the response with a cheap LLM and push scores to Langfuse."""
        prompt = (
            f"Rate this database chatbot response (0.0–1.0).\n\n"
            f"User question: {query}\n"
            f"Response: {response}\n\n"
            f"Reply with ONLY these two lines:\n"
            f"relevance: <score>\n"
            f"answer_quality: <score>\n\n"
            f"relevance = does it directly answer the question?\n"
            f"answer_quality = is it clear, accurate, and well-structured?"
        )
        try:
            llm = (
                OpenAILLM(model="gpt-4o-mini", temperature=0.0)
                if config.llm_provider == "OpenAI"
                else AnthropicLLM(model="claude-3-5-haiku-20241022", temperature=0.0)
            )
            output = await llm.acomplete(prompt)
            scores = {}
            for line in str(output).strip().splitlines():
                if ":" in line:
                    k, _, v = line.partition(":")
                    try:
                        scores[k.strip()] = float(v.strip())
                    except ValueError:
                        pass
            for name, value in scores.items():
                langfuse_context.score_current_trace(name=name, value=value)
            return scores
        except Exception as e:
            print(f"[Judge] Scoring failed (non-critical): {e}")
            return {}

    @observe()
    async def rag_pipeline(self, query: str, config: ChatConfig) -> dict:
        try:
            rag = RAGSearch(self.vec_db_manager, self.chat_db_manager, config=config)
            result = rag.sql_query(query)
            await self._judge_response(query, result.get("answer", ""), config)
            return result
        except Exception as e:
            return {"answer": f"Error in RAG pipeline: {e}", "sql": None, "tables": [], "columns": [], "attempts": 1, "raw_results": []}

    @observe()
    async def tag_pipeline(self, query: str, config: ChatConfig) -> dict:
        try:
            if not self.vec_db_manager or not self.chat_db_manager:
                return {"answer": "Error: Database connections not initialized", "sql": None, "tables": [], "columns": [], "attempts": 1, "raw_results": []}

            workflow = create_tag_pipeline(
                vec_db_manager=self.vec_db_manager,
                chat_db_manager=self.chat_db_manager,
                config=config,
            )
            trace_id = langfuse_context.get_current_trace_id()
            obs_id = langfuse_context.get_current_observation_id()
            with self.instrumentor.observe(trace_id=trace_id, parent_observation_id=obs_id, update_parent=False):
                result = await workflow.run(query=query)

            if isinstance(result, str):
                result = {"answer": result, "sql": None, "tables": [], "columns": [], "attempts": 1, "raw_results": []}

            await self._judge_response(query, result.get("answer", ""), config)
            return result
        except Exception as e:
            return {"answer": f"Error in TAG pipeline: {e}", "sql": None, "tables": [], "columns": [], "attempts": 1, "raw_results": []}


# ── UI Helpers ────────────────────────────────────────────────────────────────

def render_query_details(result: dict, scores: dict):
    """Render the 'How we got this answer' expander."""
    sql = result.get("sql")
    tables = result.get("tables", [])
    columns = result.get("columns", [])
    attempts = result.get("attempts", 1)
    raw = result.get("raw_results", [])

    with st.expander("🔍 How we got this answer", expanded=False):
        # Judge scores
        if scores:
            cols = st.columns(len(scores))
            score_colors = {1.0: "🟢", 0.8: "🟡", 0.0: "🔴"}
            for i, (name, value) in enumerate(scores.items()):
                color = next(c for threshold, c in sorted(score_colors.items(), reverse=True) if value >= threshold)
                cols[i].metric(label=name.replace("_", " ").title(), value=f"{color} {value:.2f}")

        if attempts > 1:
            st.warning(f"⚡ SQL self-corrected after {attempts} attempt(s)")

        # SQL
        if sql:
            st.markdown("**Generated SQL**")
            st.code(sql, language="sql")

            # Tables used
            if tables:
                st.markdown("**Tables referenced**")
                st.markdown(" ".join(f"`{t}`" for t in tables))

            # Columns used
            if columns:
                st.markdown("**Columns used**")
                st.markdown(" ".join(f"`{c}`" for c in columns))
        else:
            st.info("No SQL was generated for this response.")

        # Raw results as DataFrame
        if raw:
            try:
                df = pd.DataFrame(raw)
                # If columns are integers (tuples, not dicts), use SQL column names
                if df.columns.dtype == int or all(isinstance(c, int) for c in df.columns):
                    if columns:
                        df.columns = columns[:len(df.columns)]
                st.markdown("**Raw query results**")
                st.dataframe(df, use_container_width=True)
            except Exception:
                pass


def render_schema_explorer(db_manager: DatabaseManager):
    """Render a live schema browser in the sidebar."""
    with st.sidebar.expander("🗂️ Schema Explorer", expanded=False):
        try:
            schema = db_manager.get_schema_info()
            current_table = None
            for line in schema.splitlines():
                if line.startswith("Table:"):
                    current_table = line.replace("Table:", "").strip()
                    st.markdown(f"**{current_table}**")
                elif line.strip().startswith(("album_", "artist_", "customer_", "employee_", "genre_",
                                              "invoice_", "media_", "playlist_", "track_")) or (
                    line.strip() and not line.startswith("Table:") and current_table
                ):
                    st.markdown(f"<small style='color:gray;margin-left:12px'>{line.strip()}</small>",
                                unsafe_allow_html=True)
        except Exception as e:
            st.caption(f"Could not load schema: {e}")


# ── Main App ──────────────────────────────────────────────────────────────────

def main():
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "message_meta" not in st.session_state:
        st.session_state.message_meta = {}  # index → {result, scores}
    if "intent_classifier_enabled" not in st.session_state:
        st.session_state.intent_classifier_enabled = False
    if "previous_sql" not in st.session_state:
        st.session_state.previous_sql = ""

    st.set_page_config(
        page_title="Chat2DB — Talk to Your Database",
        page_icon="🤖",
        layout="wide",
    )

    st.title("🤖 Chat To Your Database")
    st.caption("Ask questions about your database in plain English")

    chat = ChatDatabase()

    with st.sidebar:
        st.header("⚙️ Configuration")

        interaction_method = st.selectbox(
            "Interaction Method", ["RAG", "TAG"],
            help="RAG: Schema-aware SQL generation. TAG: Self-correcting multi-step pipeline.",
        )
        llm_provider = st.selectbox(
            "LLM Provider", ["OpenAI", "Claude"],
            help="Choose which LLM to use for query generation.",
        )

        with st.expander("Advanced Settings"):
            temperature = st.slider("Temperature", 0.0, 1.0, 0.1, 0.1,
                                    help="Lower = more deterministic")
            st.session_state.intent_classifier_enabled = st.toggle(
                "Intent Classifier",
                value=st.session_state.intent_classifier_enabled,
            )

        st.divider()
        st.markdown("### 📊 Sample Questions")
        st.markdown("""
- What track has the most revenue?
- Which customer spent the most?
- List all jazz albums
- How many tracks per genre?
- Show top 5 artists by album count
- What is the total revenue by country?
        """)

        # Live schema explorer
        if chat.chat_db_manager:
            render_schema_explorer(chat.chat_db_manager)

    # Chat input
    if query := st.chat_input("Ask a question about your database"):
        # Build conversation history from last 6 messages (3 turns)
        history_lines = []
        recent = st.session_state.messages[-6:]
        for m in recent:
            role = "User" if m["role"] == "user" else "Assistant"
            history_lines.append(f"{role}: {m['content']}")
        conversation_history = "\n".join(history_lines)

        config = ChatConfig(
            interaction_method=interaction_method,
            llm_provider=llm_provider,
            temperature=temperature,
            conversation_history=conversation_history,
            previous_sql=st.session_state.previous_sql,
        )

        st.session_state.messages.append({"role": "user", "content": query})

        with st.spinner("Thinking..."):
            should_process = True
            if st.session_state.intent_classifier_enabled:
                should_process = chat.classify_prompt(query)
                if not should_process:
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": "This question doesn't appear to be database-related.",
                    })

            if should_process:
                run = (
                    chat.rag_pipeline(query, config)
                    if interaction_method == "RAG"
                    else chat.tag_pipeline(query, config)
                )
                result = asyncio.run(run)
                scores = {}  # scores are pushed to Langfuse inside _judge_response

                answer = result.get("answer", str(result)) if isinstance(result, dict) else str(result)
                # Track the SQL for next turn
                if isinstance(result, dict) and result.get("sql"):
                    st.session_state.previous_sql = result["sql"]
                msg_index = len(st.session_state.messages)
                st.session_state.messages.append({"role": "assistant", "content": answer})
                st.session_state.message_meta[msg_index] = {"result": result, "scores": scores}

    # Render chat history
    for i, message in enumerate(st.session_state.messages):
        with st.chat_message(message["role"]):
            st.write(message["content"])
            # Show query details expander for assistant messages that have metadata
            if message["role"] == "assistant" and i in st.session_state.message_meta:
                meta = st.session_state.message_meta[i]
                render_query_details(meta["result"], meta["scores"])


if __name__ == "__main__":
    if "intent_classifier_enabled" not in st.session_state:
        st.session_state.intent_classifier_enabled = False
    main()
