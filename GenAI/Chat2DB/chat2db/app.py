"""
Chat2DB - Main Streamlit Application
Claude-style sidebar layout with persistent chat history.
"""

from dataclasses import dataclass
import asyncio
import pickle
import uuid
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv
import pandas as pd

from tools.db import DatabaseManager
from tools.rag import RAGSearch
from tools.tag import create_tag_pipeline
from history import HistoryManager

load_dotenv()

from langfuse.llama_index import LlamaIndexInstrumentor
from langfuse.decorators import langfuse_context, observe
from llama_index.llms.openai import OpenAI as OpenAILLM
from llama_index.llms.anthropic import Anthropic as AnthropicLLM


# ── Config dataclass ──────────────────────────────────────────────────────────

@dataclass
class ChatConfig:
    interaction_method: str
    llm_provider: str
    openai_model_name: str = "gpt-4o-mini"
    claude_model_name: str = "claude-3-5-sonnet-20241022"
    temperature: float = 0.1
    conversation_history: str = ""
    previous_sql: str = ""
    intent: str = "new_question"


# ── ChatDatabase ──────────────────────────────────────────────────────────────

class ChatDatabase:
    def __init__(self):
        try:
            self.vec_db_manager = DatabaseManager(db_type="vecdb")
            self.vec_db_manager.test_connection()
        except Exception as e:
            st.error(f"Vector store error: {e}")
            self.vec_db_manager = None

        try:
            self.chat_db_manager = DatabaseManager(db_type="db")
            self.chat_db_manager.test_connection()
        except Exception as e:
            st.error(f"SQL database error: {e}")
            self.chat_db_manager = None

        self.classifier = self._load_classifier()
        self.instrumentor = LlamaIndexInstrumentor()
        self.instrumentor.start()

    def check_connections(self) -> dict:
        """Return live connection status for the DB and vector store."""
        return {
            "db":    self.chat_db_manager is not None and self.chat_db_manager.test_connection(),
            "vecdb": self.vec_db_manager  is not None and self.vec_db_manager.test_connection(),
        }

    def _load_classifier(self):
        model_path = Path(__file__).parent / "classifier/combined_sql_classifier.pkl"
        if not model_path.exists():
            return None
        try:
            with open(model_path, "rb") as f:
                return pickle.load(f)
        except Exception:
            return None

    def classify_prompt(self, prompt: str) -> bool:
        if self.classifier is None:
            return True
        v = self.classifier["vectorizer"]
        clf = self.classifier["binary_classifier"]
        return bool(clf.predict(v.transform([prompt]))[0])

    async def classify_intent_llm(self, query, conv_history, prev_sql, config) -> str:
        prompt = (
            f"Classify this database chatbot query into exactly one category.\n\n"
            f"CONVERSATION HISTORY:\n{conv_history or 'None'}\n\n"
            f"PREVIOUS SQL:\n{prev_sql or 'None'}\n\n"
            f"USER QUERY: {query}\n\n"
            f"Categories:\n"
            f"- schema_question: user asks about database structure, tables, columns\n"
            f"- followup: modifies/references previous query (it/that/filter/sort/limit)\n"
            f"- new_question: completely new independent question\n\n"
            f"Reply with ONLY one word: schema_question, followup, or new_question"
        )
        try:
            llm = (
                OpenAILLM(model="gpt-4o-mini", temperature=0.0)
                if config.llm_provider == "OpenAI"
                else AnthropicLLM(model="claude-3-5-haiku-20241022", temperature=0.0)
            )
            resp = await llm.acomplete(prompt)
            intent = str(resp).strip().lower().split()[0]
            return intent if intent in ("schema_question", "followup", "new_question") else "new_question"
        except Exception as e:
            print(f"[Intent] {e}")
            return "new_question"

    async def rewrite_query(self, query, conv_history, prev_sql, config) -> str:
        prompt = (
            f"You are a query rewriter for a music-store database chatbot (Chinook schema).\n\n"
            f"CONVERSATION HISTORY:\n{conv_history or 'None'}\n\n"
            f"PREVIOUS SQL:\n{prev_sql or 'None'}\n\n"
            f"ORIGINAL QUERY: {query}\n\n"
            f"Rewrite so it is self-contained (resolve pronouns), abbreviation-free, "
            f"and domain-enriched. If already clear, return verbatim. "
            f"Return ONLY the rewritten query."
        )
        try:
            llm = (
                OpenAILLM(model="gpt-4o-mini", temperature=0.0)
                if config.llm_provider == "OpenAI"
                else AnthropicLLM(model="claude-3-5-haiku-20241022", temperature=0.0)
            )
            resp = await llm.acomplete(prompt)
            rewritten = str(resp).strip()
            print(f"[Rewrite] '{query}' → '{rewritten}'")
            return rewritten or query
        except Exception as e:
            print(f"[Rewrite] {e}")
            return query

    async def _judge_response(self, query, response, config) -> dict:
        prompt = (
            f"Rate this database chatbot response (0.0–1.0).\n\n"
            f"User question: {query}\nResponse: {response}\n\n"
            f"Reply with ONLY:\nrelevance: <score>\nanswer_quality: <score>"
        )
        try:
            llm = (
                OpenAILLM(model="gpt-4o-mini", temperature=0.0)
                if config.llm_provider == "OpenAI"
                else AnthropicLLM(model="claude-3-5-haiku-20241022", temperature=0.0)
            )
            out = await llm.acomplete(prompt)
            scores = {}
            for line in str(out).strip().splitlines():
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
            print(f"[Judge] {e}")
            return {}

    @observe()
    async def rag_pipeline(self, query: str, config: ChatConfig) -> dict:
        try:
            rag = RAGSearch(self.vec_db_manager, self.chat_db_manager, config=config)
            result = rag.sql_query(query)
            await self._judge_response(query, result.get("answer", ""), config)
            return result
        except Exception as e:
            return {"answer": f"Error in RAG pipeline: {e}", "sql": None, "tables": [],
                    "columns": [], "attempts": 1, "raw_results": []}

    @observe()
    async def tag_pipeline(self, query: str, config: ChatConfig) -> dict:
        try:
            if not self.vec_db_manager or not self.chat_db_manager:
                return {"answer": "Error: DB not initialised", "sql": None, "tables": [],
                        "columns": [], "attempts": 1, "raw_results": []}
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
                result = {"answer": result, "sql": None, "tables": [], "columns": [],
                          "attempts": 1, "raw_results": []}
            await self._judge_response(query, result.get("answer", ""), config)
            return result
        except Exception as e:
            return {"answer": f"Error in TAG pipeline: {e}", "sql": None, "tables": [],
                    "columns": [], "attempts": 1, "raw_results": []}


# ── CSS ───────────────────────────────────────────────────────────────────────

CUSTOM_CSS = """
<style>
/* ── Root palette ── */
:root {
    --bg:      #07101f;
    --panel:   #0e1729;
    --border:  rgba(149,167,209,0.14);
    --text:    #f0f4ff;
    --muted:   #7a8bb0;
    --purple:  #7c3aed;
    --purple2: #5b21b6;
    --green:   #10b981;
}

/* ── Global background ── */
html, body,
[data-testid="stAppViewContainer"],
[data-testid="stMain"] {
    background: radial-gradient(circle at 10% 0%, rgba(124,58,237,.15) 0%, transparent 40%),
                radial-gradient(circle at 90% 100%, rgba(37,99,235,.10) 0%, transparent 40%),
                var(--bg) !important;
    color: var(--text) !important;
}

/* ── Hide Streamlit chrome ── */
#MainMenu, footer, header { visibility: hidden; }

[data-testid="stAppViewContainer"] .main .block-container {
    padding-top: 0.8rem;
    padding-bottom: 2rem;
    max-width: 1400px;
}

/* ── Sidebar shell ── */
section[data-testid="stSidebar"] {
    border-right: 1px solid var(--border);
    min-width: 240px !important;
    max-width: 240px !important;
}
section[data-testid="stSidebar"] > div:first-child {
    background: linear-gradient(180deg,#0d1728,#07101f) !important;
    padding: 1rem 0.75rem 1rem 0.75rem;
}

/* ── New Question button ── */
section[data-testid="stSidebar"] .stButton > button {
    background: linear-gradient(90deg, var(--purple), var(--purple2)) !important;
    color: #fff !important;
    border: none !important;
    border-radius: 14px !important;
    font-weight: 700 !important;
    padding: 0.6rem 1rem !important;
    width: 100% !important;
    margin-bottom: 4px;
    box-shadow: 0 6px 20px rgba(91,33,182,.35);
    transition: opacity .15s;
}
section[data-testid="stSidebar"] .stButton > button:hover { opacity: .88; }

/* ── Nav divider & labels ── */
section[data-testid="stSidebar"] hr { border-color: var(--border) !important; }

/* ── History items ── */
.hist-item {
    display: block;
    padding: 7px 10px;
    border-radius: 10px;
    font-size: 12.5px;
    color: var(--muted);
    border-left: 2px solid transparent;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    margin-bottom: 3px;
    cursor: pointer;
    transition: all .12s;
}
.hist-item:hover { color: var(--text); border-left-color: var(--purple); background: rgba(124,58,237,.08); }

/* ── Dashboard cards ── */
.dash-card {
    background: linear-gradient(160deg,#101c35,#0c1628);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 18px 20px;
    margin-bottom: 12px;
    cursor: pointer;
    transition: border-color .15s, box-shadow .15s;
}
.dash-card:hover { border-color: var(--purple); box-shadow: 0 0 0 1px rgba(124,58,237,.25); }
.dash-card-icon { font-size: 1.6rem; margin-bottom: 8px; }
.dash-card-label { font-size: 12px; color: var(--muted); font-weight: 600; text-transform: uppercase; letter-spacing: .6px; margin-bottom: 4px; }
.dash-card-q { font-size: 14px; color: var(--text); }

/* ── Chat message area ── */
.stChatMessage { border-radius: 14px !important; }

/* ── Metric chips ── */
.mchip {
    display: inline-block;
    background: rgba(17,27,48,.9);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 5px 13px;
    font-size: 12px;
    color: var(--muted);
    margin-right: 8px;
    margin-bottom: 8px;
}
.mchip b { color: var(--text); }

/* ── Intent badges ── */
.badge {
    display: inline-block;
    padding: 3px 11px;
    border-radius: 10px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: .5px;
    text-transform: uppercase;
    margin-right: 6px;
    margin-bottom: 10px;
}
.b-new      { background:#0d2818; color:#4ade80; border:1px solid #22c55e; }
.b-followup { background:#0d1f3a; color:#60a5fa; border:1px solid #3b82f6; }
.b-schema   { background:#1e0d3a; color:#c084fc; border:1px solid #a855f7; }
.b-rewrite  { background:#2a1a04; color:#fbbf24; border:1px solid #f59e0b; }

/* ── Schema table ── */
.schema-table { font-size: 12px; color: var(--muted); margin-left: 12px; }
.schema-table-name { font-weight: 700; color: var(--text); font-size: 13px; margin-top: 10px; }

/* ── Top bar ── */
.topbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    background: rgba(14,23,41,0.80);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 10px 20px;
    margin-bottom: 18px;
    backdrop-filter: blur(8px);
}
.topbar-left  { display: flex; align-items: center; gap: 10px; }
.topbar-right { display: flex; align-items: center; gap: 8px; font-size: 13px; color: var(--muted); }
.conn-dot {
    width: 10px; height: 10px; border-radius: 50%;
    display: inline-block; margin-right: 4px;
}
.conn-dot.green { background: #10b981; box-shadow: 0 0 8px rgba(16,185,129,.7); }
.conn-dot.red   { background: #ef4444; box-shadow: 0 0 8px rgba(239,68,68,.7); }

/* ── Saved / Favorites cards ── */
.saved-card {
    background: #0e1729;
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 14px 18px;
    margin-bottom: 10px;
}
.saved-card h4 { margin: 0 0 6px 0; font-size: 14px; color: var(--text); }
.saved-card p  { margin: 0; font-size: 12px; color: var(--muted); }
</style>
"""

# ── Dashboard question cards ──────────────────────────────────────────────────

DASHBOARD_CARDS = [
    ("💰", "Revenue Analysis",   "What track has the most revenue?"),
    ("👥", "Customer Ranking",   "Which customer spent the most?"),
    ("🎵", "Music Catalog",      "List all jazz albums"),
    ("📊", "Genre Breakdown",    "How many tracks per genre?"),
    ("🌍", "Geographic Revenue", "What is the total revenue by country?"),
    ("🏆", "Artist Rankings",    "Show top 5 artists by album count"),
]


# ── Page renderers ────────────────────────────────────────────────────────────

def render_dashboard():
    st.markdown("## Welcome to Chat2DB")
    st.caption("Your AI-powered SQL analyst. Click a card below to start — or type your own question.")
    st.markdown("")

    cols = st.columns(3)
    for i, (icon, label, question) in enumerate(DASHBOARD_CARDS):
        with cols[i % 3]:
            st.markdown(
                f'<div class="dash-card">'
                f'<div class="dash-card-icon">{icon}</div>'
                f'<div class="dash-card-label">{label}</div>'
                f'<div class="dash-card-q">{question}</div>'
                f"</div>",
                unsafe_allow_html=True,
            )
            if st.button("Ask this →", key=f"dash_{i}", use_container_width=True):
                _new_chat()
                st.session_state.pending_question = question
                st.rerun()


def render_schema_page(chat: ChatDatabase):
    st.markdown("## 🔍 Explore Schema")
    st.caption("Live structure of the Chinook database.")
    if not chat.chat_db_manager:
        st.error("Database not connected.")
        return
    try:
        schema = chat.chat_db_manager.get_schema_info()
        current_table = None
        for line in schema.splitlines():
            if line.startswith("Table:"):
                current_table = line.replace("Table:", "").strip()
                st.markdown(f'<div class="schema-table-name">📋 {current_table}</div>',
                            unsafe_allow_html=True)
            elif line.strip() and current_table:
                st.markdown(f'<div class="schema-table">{line.strip()}</div>',
                            unsafe_allow_html=True)
    except Exception as e:
        st.error(f"Could not load schema: {e}")


def render_saved(history: HistoryManager):
    st.markdown("## 💾 Saved Queries")
    saved = history.get_saved()
    if not saved:
        st.info("No saved queries yet. After an answer, click 'Save Query' to bookmark it.")
        return
    for entry in saved:
        with st.container():
            st.markdown(
                f'<div class="saved-card">'
                f'<h4>{entry["question"]}</h4>'
                f'<p>{entry.get("answer","")[:120]}…</p>'
                f'</div>',
                unsafe_allow_html=True,
            )
            c1, c2 = st.columns([4, 1])
            if entry.get("sql"):
                with c1:
                    with st.expander("SQL"):
                        st.code(entry["sql"], language="sql")
            if c2.button("Delete", key=f"del_saved_{entry['id']}"):
                history.delete_saved(entry["id"])
                st.rerun()


def render_favorites(history: HistoryManager):
    st.markdown("## ⭐ Favorites")
    favs = history.get_favorites()
    if not favs:
        st.info("No favorites yet. Star a conversation from the chat.")
        return
    for s in favs:
        with st.container():
            st.markdown(
                f'<div class="saved-card"><h4>{s["title"]}</h4>'
                f'<p style="font-size:11px;color:#7a8bb0">{s["updated_at"][:10]}</p></div>',
                unsafe_allow_html=True,
            )
            c1, c2 = st.columns([3, 1])
            if c1.button("Load conversation", key=f"load_fav_{s['id']}"):
                _load_session(s)
                st.rerun()
            if c2.button("Unstar", key=f"unfav_{s['id']}"):
                history.remove_favorite(s["id"])
                st.rerun()


def render_chat(chat: ChatDatabase, history: HistoryManager,
                interaction_method: str, llm_provider: str, temperature: float,
                intent_filter: bool):
    """Main chat page — processes pending questions, renders history, handles input."""

    # ── Handle question from dashboard card ───────────────────────────────────
    pending = st.session_state.pop("pending_question", None)
    if pending:
        _handle_query(pending, chat, history, interaction_method, llm_provider,
                      temperature, intent_filter)

    # ── Render existing messages ───────────────────────────────────────────────
    if not st.session_state.messages:
        st.markdown("### New conversation")
        st.caption("Ask anything about the Chinook music-store database.")

    for i, message in enumerate(st.session_state.messages):
        with st.chat_message(message["role"]):
            if message["role"] == "assistant" and i in st.session_state.message_meta:
                _render_assistant(message, st.session_state.message_meta[i], history)
            else:
                st.write(message["content"])

    # ── Chat input ─────────────────────────────────────────────────────────────
    if query := st.chat_input("Ask a question about your database…"):
        _handle_query(query, chat, history, interaction_method, llm_provider,
                      temperature, intent_filter)
        st.rerun()


# ── Chat helpers ──────────────────────────────────────────────────────────────

def _new_chat():
    """Reset session state to start a fresh conversation."""
    st.session_state.session_id = str(uuid.uuid4())
    st.session_state.messages = []
    st.session_state.message_meta = {}
    st.session_state.previous_sql = ""
    st.session_state.current_page = "chat"


def _load_session(session: dict):
    """Restore a saved session into session state."""
    st.session_state.session_id = session["id"]
    st.session_state.messages = session.get("messages", [])
    st.session_state.message_meta = {
        int(k): v for k, v in session.get("message_meta", {}).items()
    }
    st.session_state.previous_sql = session.get("previous_sql", "")
    st.session_state.current_page = "chat"


def _handle_query(query: str, chat: ChatDatabase, history: HistoryManager,
                  interaction_method: str, llm_provider: str, temperature: float,
                  intent_filter: bool):
    """Classify → rewrite → run pipeline → save to history."""
    history_lines = [
        f"{'User' if m['role']=='user' else 'Assistant'}: {m['content']}"
        for m in st.session_state.messages[-6:]
    ]
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
        if intent_filter:
            should_process = chat.classify_prompt(query)
            if not should_process:
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": "This doesn't appear to be a database question.",
                })
                return

        async def _process():
            intent = await chat.classify_intent_llm(
                query, conversation_history, st.session_state.previous_sql, config
            )
            config.intent = intent

            if intent == "schema_question":
                schema = chat.chat_db_manager.get_schema_info() if chat.chat_db_manager else ""
                answer_text = "Here's the current database schema:\n\n" + schema if schema else "Schema unavailable."
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

    # Persist to history file
    history.upsert_session(
        session_id=st.session_state.session_id,
        messages=st.session_state.messages,
        message_meta=st.session_state.message_meta,
        previous_sql=st.session_state.previous_sql,
    )


def _render_assistant(message: dict, meta: dict, history: HistoryManager):
    """Render assistant message with metric strip + Answer / Details tabs."""
    result  = meta["result"]
    scores  = meta.get("scores", {})
    intent  = meta.get("intent", "new_question")
    raw     = result.get("raw_results", [])
    tables  = result.get("tables", [])
    attempts = result.get("attempts", 1)

    # Metric chips
    chips = ""
    if raw:
        chips += f'<span class="mchip">Rows <b>{len(raw)}</b></span>'
    if tables:
        chips += f'<span class="mchip">Tables <b>{len(tables)}</b></span>'
    chips += f'<span class="mchip">Attempts <b>{attempts}</b></span>'
    if scores:
        avg = sum(scores.values()) / len(scores)
        chips += f'<span class="mchip">Score <b>{avg:.2f}</b></span>'
    st.markdown(chips, unsafe_allow_html=True)

    # Tabs
    t_answer, t_details = st.tabs(["Answer", "How we got this answer"])

    with t_answer:
        st.write(message["content"])
        if raw:
            try:
                df = pd.DataFrame(raw)
                if df.columns.dtype == int or all(isinstance(c, int) for c in df.columns):
                    col_names = result.get("columns", [])
                    if col_names:
                        df.columns = col_names[:len(df.columns)]
                st.dataframe(df, use_container_width=True)
            except Exception:
                pass

        # Save Query / Favorite buttons
        c1, c2 = st.columns([1, 1])
        sql = result.get("sql")
        if sql and c1.button("💾 Save Query", key=f"save_{id(meta)}"):
            history.save_query(
                question=st.session_state.messages[
                    max(i for i, m in enumerate(st.session_state.messages) if m["role"] == "user")
                ]["content"],
                sql=sql,
                answer=message["content"],
            )
            st.toast("Query saved!")
        if c2.button("⭐ Favorite chat", key=f"fav_{id(meta)}"):
            history.add_favorite(st.session_state.session_id)
            st.toast("Added to favorites!")

    with t_details:
        # Intent badge
        badge_map = {
            "new_question": ("b-new",      "new question"),
            "followup":     ("b-followup", "follow-up"),
            "schema_question": ("b-schema","schema lookup"),
        }
        cls, lbl = badge_map.get(intent, ("b-new", intent))
        badges = f'<span class="badge {cls}">{lbl}</span>'
        rewritten = result.get("rewritten_query")
        if rewritten:
            badges += '<span class="badge b-rewrite">rewritten</span>'
        st.markdown(badges, unsafe_allow_html=True)

        if rewritten:
            st.caption(f'"{rewritten}"')
            st.divider()

        if scores:
            sc = st.columns(len(scores))
            for j, (name, value) in enumerate(scores.items()):
                icon = "🟢" if value >= 1.0 else "🟡" if value >= 0.8 else "🔴"
                sc[j].metric(name.replace("_", " ").title(), f"{icon} {value:.2f}")
            st.divider()

        if attempts > 1:
            st.warning(f"SQL self-corrected after {attempts} attempt(s)")

        if sql:
            st.markdown("**Generated SQL**")
            st.code(sql, language="sql")
            col_a, col_b = st.columns(2)
            if tables:
                col_a.markdown("**Tables**\n" + " ".join(f"`{t}`" for t in tables))
            cols = result.get("columns", [])
            if cols:
                col_b.markdown("**Columns**\n" + " ".join(f"`{c}`" for c in cols))
        else:
            st.info("No SQL generated — answered from schema directly.")


# ── Top bar ──────────────────────────────────────────────────────────────────

def render_topbar(chat: ChatDatabase) -> tuple[str, str, float, bool]:
    """
    Renders the right-panel top bar.
    Left: Mode selector + LLM + Temperature.
    Right: DB connection status dot.
    Returns (interaction_method, llm_provider, temperature, intent_filter).
    """
    conn = chat.check_connections()
    db_ok    = conn["db"]
    vec_ok   = conn["vecdb"]
    both_ok  = db_ok and vec_ok

    dot_cls  = "green" if both_ok else "red"
    dot_text = "Connected" if both_ok else ("DB error" if not db_ok else "VecDB error")

    left, right = st.columns([3, 1])

    with left:
        c1, c2, c3, c4 = st.columns([2, 2, 2, 2])
        with c1:
            interaction_method = st.selectbox(
                "Mode",
                ["Hybrid (RAG + TAG)", "Standard"],
                key="topbar_mode",
                label_visibility="collapsed",
            )
        with c2:
            llm_provider = st.selectbox(
                "LLM",
                ["OpenAI", "Claude"],
                key="topbar_llm",
                label_visibility="collapsed",
            )
        with c3:
            temperature = st.slider(
                "Temp", 0.0, 1.0, 0.1, 0.05,
                key="topbar_temp",
                label_visibility="collapsed",
            )
        with c4:
            intent_filter = st.toggle(
                "Intent filter",
                value=st.session_state.get("intent_filter", False),
                key="topbar_intent",
                help="Pre-filter non-DB questions with a local ML classifier",
            )
            st.session_state.intent_filter = intent_filter

    with right:
        st.markdown(
            f'<div style="text-align:right;padding-top:6px;">'
            f'<span class="conn-dot {dot_cls}"></span>'
            f'<span style="font-size:13px;color:{"#10b981" if both_ok else "#ef4444"};font-weight:600;">'
            f'{dot_text}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

    # Normalise mode label → internal key used by pipelines
    mode = "Standard" if interaction_method == "Standard" else "Hybrid"
    return mode, llm_provider, temperature, intent_filter


# ── Sidebar ───────────────────────────────────────────────────────────────────

NAV = [
    ("dashboard", "📊", "Dashboard"),
    ("schema",    "🔍", "Explore Schema"),
    ("saved",     "💾", "Saved Queries"),
    ("favorites", "⭐", "Favorites"),
]


def render_sidebar(history: HistoryManager):
    """Draw the Claude-style left panel."""
    with st.sidebar:
        # Logo
        st.markdown(
            """
            <div style="display:flex;align-items:center;gap:10px;padding:4px 0 18px 0;">
              <div style="width:38px;height:38px;border-radius:11px;
                          background:linear-gradient(135deg,#7c3aed,#4f46e5);
                          display:flex;align-items:center;justify-content:center;font-size:20px;">
                🤖
              </div>
              <div>
                <div style="font-size:16px;font-weight:700;color:#f0f4ff;line-height:1.2;">Chat2DB</div>
                <div style="font-size:11px;color:#7a8bb0;">AI SQL Analyst</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # New Question
        if st.button("＋  New Question", use_container_width=True):
            _new_chat()
            st.rerun()

        st.divider()

        # Nav items
        current = st.session_state.get("current_page", "dashboard")
        for page_id, icon, label in NAV:
            active_mark = "▶ " if current == page_id else "     "
            if st.button(f"{active_mark}{icon}  {label}", key=f"nav_{page_id}",
                         use_container_width=True):
                st.session_state.current_page = page_id
                st.rerun()

        st.divider()

        # Conversation history (last 5)
        recent = history.get_recent(5)
        if recent:
            st.markdown(
                '<div style="font-size:11px;font-weight:700;color:#7a8bb0;'
                'text-transform:uppercase;letter-spacing:.8px;margin-bottom:6px;">'
                '🕐  History</div>',
                unsafe_allow_html=True,
            )
            for s in recent:
                title = s["title"][:46] + ("…" if len(s["title"]) > 46 else "")
                st.markdown(
                    f'<div class="hist-item">• {title}</div>',
                    unsafe_allow_html=True,
                )
                if st.button("Load", key=f"hist_{s['id']}", use_container_width=False):
                    _load_session(s)
                    st.rerun()


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    st.set_page_config(
        page_title="Chat2DB",
        page_icon="🤖",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

    # Session state
    if "session_id"    not in st.session_state: st.session_state.session_id    = str(uuid.uuid4())
    if "messages"      not in st.session_state: st.session_state.messages      = []
    if "message_meta"  not in st.session_state: st.session_state.message_meta  = {}
    if "previous_sql"  not in st.session_state: st.session_state.previous_sql  = ""
    if "current_page"  not in st.session_state: st.session_state.current_page  = "dashboard"
    if "intent_filter" not in st.session_state: st.session_state.intent_filter = False

    history = HistoryManager()
    chat    = ChatDatabase()

    # ── Sidebar ────────────────────────────────────────────────────────────────
    render_sidebar(history)

    # ── Top bar (right panel) ─────────────────────────────────────────────────
    interaction_method, llm_provider, temperature, intent_filter = render_topbar(chat)

    # ── Page routing ───────────────────────────────────────────────────────────
    page = st.session_state.current_page

    if page == "dashboard":
        render_dashboard()
    elif page == "chat":
        render_chat(chat, history, interaction_method, llm_provider,
                    temperature, st.session_state.intent_filter)
    elif page == "schema":
        render_schema_page(chat)
    elif page == "saved":
        render_saved(history)
    elif page == "favorites":
        render_favorites(history)


if __name__ == "__main__":
    main()
