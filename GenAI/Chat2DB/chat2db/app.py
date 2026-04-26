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
    intent: str = "new_question"   # schema_question | followup | new_question


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

    async def classify_intent_llm(self, query: str, conversation_history: str, previous_sql: str, config: ChatConfig) -> str:
        """Use a lightweight LLM call to classify query intent into one of three categories."""
        prompt = (
            f"Classify this database chatbot query into exactly one category.\n\n"
            f"CONVERSATION HISTORY:\n{conversation_history or 'None'}\n\n"
            f"PREVIOUS SQL:\n{previous_sql or 'None'}\n\n"
            f"USER QUERY: {query}\n\n"
            f"Categories:\n"
            f"- schema_question: user asks about database structure, tables, columns, or what data is available\n"
            f"- followup: user modifies or references the previous query/results (pronouns like it/that/those, words like filter/sort/limit/only/also/top N/add/exclude)\n"
            f"- new_question: completely new independent question about the data\n\n"
            f"Reply with ONLY one word: schema_question, followup, or new_question"
        )
        try:
            llm = (
                OpenAILLM(model="gpt-4o-mini", temperature=0.0)
                if config.llm_provider == "OpenAI"
                else AnthropicLLM(model="claude-3-5-haiku-20241022", temperature=0.0)
            )
            response_obj = await llm.acomplete(prompt)
            intent = str(response_obj).strip().lower().split()[0]
            if intent in ("schema_question", "followup", "new_question"):
                return intent
            return "new_question"
        except Exception as e:
            print(f"[Intent] LLM classification failed: {e}")
            return "new_question"

    async def rewrite_query(self, query: str, conversation_history: str, previous_sql: str, config: ChatConfig) -> str:
        """Rewrite the user query to be self-contained and domain-enriched before retrieval.

        Resolves coreferences (it/them/those), expands abbreviations, and adds
        Chinook domain terms so the downstream SQL generator has a cleaner signal.
        Returns the original query unchanged if rewriting fails.
        """
        prompt = (
            f"You are a query rewriter for a music-store database chatbot (Chinook schema).\n\n"
            f"CONVERSATION HISTORY:\n{conversation_history or 'None'}\n\n"
            f"PREVIOUS SQL:\n{previous_sql or 'None'}\n\n"
            f"ORIGINAL QUERY: {query}\n\n"
            f"Rewrite the query so it is:\n"
            f"1. Fully self-contained (resolve pronouns like it/them/those/that using the conversation history)\n"
            f"2. Abbreviation-free (expand rev→revenue, qty→quantity, etc.)\n"
            f"3. Domain-enriched where helpful (e.g. 'most popular' → 'highest total revenue from invoice_line', "
            f"'customer spend' → 'SUM of invoice.total per customer')\n\n"
            f"Rules:\n"
            f"- If the query is already clear and self-contained, return it verbatim\n"
            f"- Do NOT answer the question — only rewrite it\n"
            f"- Return ONLY the rewritten query, nothing else"
        )
        try:
            llm = (
                OpenAILLM(model="gpt-4o-mini", temperature=0.0)
                if config.llm_provider == "OpenAI"
                else AnthropicLLM(model="claude-3-5-haiku-20241022", temperature=0.0)
            )
            response_obj = await llm.acomplete(prompt)
            rewritten = str(response_obj).strip()
            print(f"[Rewrite] '{query}' → '{rewritten}'")
            return rewritten if rewritten else query
        except Exception as e:
            print(f"[Rewrite] Failed (non-critical): {e}")
            return query

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


# ── Custom CSS ────────────────────────────────────────────────────────────────

CUSTOM_CSS = """
<style>
#MainMenu, footer { visibility: hidden; }

/* ── Sidebar ── */
section[data-testid="stSidebar"] > div:first-child { padding-top: 0.75rem; }
section[data-testid="stSidebar"] .stButton > button {
    width: 100%;
    border-radius: 8px;
    font-weight: 600;
    margin-bottom: 4px;
}

/* ── Intent badges ── */
.badge {
    display: inline-block;
    padding: 3px 12px;
    border-radius: 12px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.6px;
    text-transform: uppercase;
    margin-right: 6px;
    margin-bottom: 10px;
}
.badge-new      { background:#0d2818; color:#4ade80; border:1px solid #22c55e; }
.badge-followup { background:#0d1f3a; color:#60a5fa; border:1px solid #3b82f6; }
.badge-schema   { background:#1e0d3a; color:#c084fc; border:1px solid #a855f7; }
.badge-rewrite  { background:#2a1a04; color:#fbbf24; border:1px solid #f59e0b; }

/* ── Conversation history items ── */
.history-item {
    padding: 6px 10px;
    border-radius: 6px;
    font-size: 12px;
    color: #8b949e;
    cursor: default;
    margin-bottom: 2px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    border-left: 2px solid #30363d;
}
.history-item:hover { color: #c9d1d9; border-left-color: #58a6ff; }

/* ── Welcome screen ── */
.welcome-card {
    background: linear-gradient(135deg, #161b22, #1c2128);
    border: 1px solid #30363d;
    border-radius: 12px;
    padding: 20px 24px;
    margin-bottom: 12px;
    cursor: pointer;
    transition: border-color 0.15s;
}
.welcome-card:hover { border-color: #58a6ff; }
.welcome-card h4 { margin: 0 0 4px 0; color: #c9d1d9; font-size: 14px; }
.welcome-card p  { margin: 0; color: #8b949e; font-size: 12px; }

/* ── Metric strip ── */
.metric-strip {
    display: flex;
    gap: 12px;
    margin-bottom: 12px;
    flex-wrap: wrap;
}
.metric-chip {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 8px;
    padding: 6px 14px;
    font-size: 12px;
    color: #8b949e;
}
.metric-chip span { color: #c9d1d9; font-weight: 600; margin-left: 4px; }
</style>
"""


# ── UI Helpers ────────────────────────────────────────────────────────────────

def _intent_badge(intent: str) -> str:
    mapping = {
        "new_question": ("badge-new",      "new question"),
        "followup":     ("badge-followup", "follow-up"),
        "schema_question": ("badge-schema","schema lookup"),
    }
    cls, label = mapping.get(intent, ("badge-new", intent))
    return f'<span class="badge {cls}">{label}</span>'


def render_details_tab(result: dict, scores: dict, intent: str):
    """Content for the 'How we got this answer' tab."""
    sql      = result.get("sql")
    tables   = result.get("tables", [])
    columns  = result.get("columns", [])
    attempts = result.get("attempts", 1)
    rewritten = result.get("rewritten_query")

    # Intent badge + optional rewrite badge
    badges = _intent_badge(intent)
    if rewritten:
        badges += '<span class="badge badge-rewrite">rewritten</span>'
    st.markdown(badges, unsafe_allow_html=True)

    # Rewritten query text
    if rewritten:
        st.caption(f'"{rewritten}"')
        st.divider()

    # LLM-as-Judge scores
    if scores:
        score_cols = st.columns(len(scores))
        for j, (name, value) in enumerate(scores.items()):
            color = "🟢" if value >= 1.0 else "🟡" if value >= 0.8 else "🔴"
            score_cols[j].metric(name.replace("_", " ").title(), f"{color} {value:.2f}")
        st.divider()

    if attempts > 1:
        st.warning(f"SQL self-corrected after {attempts} attempt(s)")

    # Generated SQL
    if sql:
        st.markdown("**Generated SQL**")
        st.code(sql, language="sql")

        if tables or columns:
            c1, c2 = st.columns(2)
            if tables:
                c1.markdown("**Tables**")
                c1.markdown(" ".join(f"`{t}`" for t in tables))
            if columns:
                c2.markdown("**Columns**")
                c2.markdown(" ".join(f"`{c}`" for c in columns))
    else:
        st.info("No SQL was generated — answer came directly from the schema.")


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
                elif line.strip() and not line.startswith("Table:") and current_table:
                    st.markdown(
                        f"<small style='color:gray;margin-left:12px'>{line.strip()}</small>",
                        unsafe_allow_html=True,
                    )
        except Exception as e:
            st.caption(f"Could not load schema: {e}")


def _render_assistant_message(message: dict, meta: dict):
    """Render a single assistant message with metric strip + Answer/Details tabs."""
    result  = meta["result"]
    scores  = meta["scores"]
    intent  = meta.get("intent", "new_question")
    raw     = result.get("raw_results", [])
    tables  = result.get("tables", [])
    attempts = result.get("attempts", 1)

    # ── Metric strip ──────────────────────────────────────────────────────────
    chips = []
    if raw:
        chips.append(f'<span class="metric-chip">Rows<span>{len(raw)}</span></span>')
    if tables:
        chips.append(f'<span class="metric-chip">Tables<span>{len(tables)}</span></span>')
    chips.append(f'<span class="metric-chip">Attempts<span>{attempts}</span></span>')
    if scores:
        avg = sum(scores.values()) / len(scores)
        chips.append(f'<span class="metric-chip">LLM Score<span>{avg:.2f}</span></span>')
    if chips:
        st.markdown(f'<div class="metric-strip">{"".join(chips)}</div>', unsafe_allow_html=True)

    # ── Tabs ──────────────────────────────────────────────────────────────────
    tab_answer, tab_details = st.tabs(["Answer", "How we got this answer"])

    with tab_answer:
        st.write(message["content"])
        if raw:
            try:
                df = pd.DataFrame(raw)
                if df.columns.dtype == int or all(isinstance(c, int) for c in df.columns):
                    cols_list = result.get("columns", [])
                    if cols_list:
                        df.columns = cols_list[:len(df.columns)]
                st.dataframe(df, use_container_width=True)
            except Exception:
                pass

    with tab_details:
        render_details_tab(result, scores, intent)


# ── Main App ──────────────────────────────────────────────────────────────────

SAMPLE_QUESTIONS = [
    ("What track has the most revenue?",      "Revenue analysis"),
    ("Which customer spent the most?",         "Customer ranking"),
    ("How many tracks per genre?",             "Genre breakdown"),
    ("Show top 5 artists by album count",      "Artist stats"),
    ("What is the total revenue by country?",  "Geographic revenue"),
    ("What tables are in the database?",       "Schema question"),
]


def main():
    st.set_page_config(
        page_title="Chat2DB",
        page_icon="🤖",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

    # ── Session state init ────────────────────────────────────────────────────
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "message_meta" not in st.session_state:
        st.session_state.message_meta = {}
    if "intent_classifier_enabled" not in st.session_state:
        st.session_state.intent_classifier_enabled = False
    if "previous_sql" not in st.session_state:
        st.session_state.previous_sql = ""

    chat = ChatDatabase()

    # ── Sidebar ───────────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown("## 🤖 Chat2DB")
        st.caption("Talk to your database in plain English")
        st.divider()

        if st.button("＋  New Chat", use_container_width=True, type="primary"):
            st.session_state.messages = []
            st.session_state.message_meta = {}
            st.session_state.previous_sql = ""
            st.rerun()

        st.divider()

        interaction_method = st.selectbox(
            "Mode", ["Hybrid", "Standard"],
            help="Hybrid: parallel retrieval + self-correcting SQL. Standard: schema-aware SQL generation.",
        )
        llm_provider = st.selectbox(
            "LLM Provider", ["OpenAI", "Claude"],
        )

        with st.expander("Advanced"):
            temperature = st.slider("Temperature", 0.0, 1.0, 0.1, 0.1,
                                    help="Lower = more deterministic")
            st.session_state.intent_classifier_enabled = st.toggle(
                "Binary intent filter",
                value=st.session_state.intent_classifier_enabled,
                help="Pre-filter non-database questions with a local ML classifier",
            )

        st.divider()

        # Conversation history
        user_msgs = [(i, m) for i, m in enumerate(st.session_state.messages) if m["role"] == "user"]
        if user_msgs:
            st.markdown("**💬 History**")
            for _, m in reversed(user_msgs[-8:]):
                truncated = m["content"][:48] + ("…" if len(m["content"]) > 48 else "")
                st.markdown(
                    f'<div class="history-item">• {truncated}</div>',
                    unsafe_allow_html=True,
                )
            st.divider()

        # Schema explorer
        if chat.chat_db_manager:
            render_schema_explorer(chat.chat_db_manager)

    # ── Main content ──────────────────────────────────────────────────────────

    # Welcome screen when conversation is empty
    if not st.session_state.messages:
        st.markdown("## Ask your database anything")
        st.caption("Powered by Hybrid (parallel retrieval + self-correcting SQL) · LLM intent routing · Query rewriting")
        st.markdown("")
        cols = st.columns(3)
        for idx, (question, label) in enumerate(SAMPLE_QUESTIONS):
            with cols[idx % 3]:
                st.markdown(
                    f'<div class="welcome-card"><h4>{label}</h4><p>{question}</p></div>',
                    unsafe_allow_html=True,
                )

    # Chat input
    if query := st.chat_input("Ask a question about your database…"):
        history_lines = []
        for m in st.session_state.messages[-6:]:
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

        with st.spinner("Thinking…"):
            should_process = True
            if st.session_state.intent_classifier_enabled:
                should_process = chat.classify_prompt(query)
                if not should_process:
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": "This question doesn't appear to be database-related.",
                    })

            if should_process:
                async def _process():
                    intent = await chat.classify_intent_llm(
                        query, conversation_history, st.session_state.previous_sql, config
                    )
                    config.intent = intent

                    if intent == "schema_question":
                        schema = chat.chat_db_manager.get_schema_info() if chat.chat_db_manager else ""
                        answer_text = (
                            "Here's the current database schema:\n\n" + schema
                            if schema else "I couldn't retrieve the schema right now."
                        )
                        return {"answer": answer_text, "sql": None, "tables": [], "columns": [],
                                "attempts": 1, "raw_results": [], "rewritten_query": None}

                    rewritten = await chat.rewrite_query(
                        query, conversation_history, st.session_state.previous_sql, config
                    )

                    if interaction_method == "Standard":
                        result = await chat.rag_pipeline(rewritten, config)
                    else:
                        result = await chat.tag_pipeline(rewritten, config)

                    if isinstance(result, dict):
                        result["rewritten_query"] = rewritten if rewritten != query else None
                    return result

                result = asyncio.run(_process())
                answer = result.get("answer", str(result)) if isinstance(result, dict) else str(result)
                if isinstance(result, dict) and result.get("sql"):
                    st.session_state.previous_sql = result["sql"]
                msg_index = len(st.session_state.messages)
                st.session_state.messages.append({"role": "assistant", "content": answer})
                st.session_state.message_meta[msg_index] = {
                    "result": result,
                    "scores": {},
                    "intent": config.intent,
                }

    # Render chat history
    for i, message in enumerate(st.session_state.messages):
        with st.chat_message(message["role"]):
            if message["role"] == "assistant" and i in st.session_state.message_meta:
                _render_assistant_message(message, st.session_state.message_meta[i])
            else:
                st.write(message["content"])


if __name__ == "__main__":
    if "intent_classifier_enabled" not in st.session_state:
        st.session_state.intent_classifier_enabled = False
    main()
