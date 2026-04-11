import asyncio
import os
from pathlib import Path
import yaml
import streamlit as st

# --------------------------------------------------------------------------- #
#  Load API key from mcp_agent.secrets.yaml into environment
# --------------------------------------------------------------------------- #
def _load_secrets():
    secrets_path = Path(__file__).parent / "mcp_agent.secrets.yaml"
    if secrets_path.exists():
        with open(secrets_path) as f:
            secrets = yaml.safe_load(f) or {}
        api_key = secrets.get("openai", {}).get("api_key", "")
        if api_key and api_key != "YOUR_OPENAI_API_KEY":
            os.environ.setdefault("OPENAI_API_KEY", api_key)

_load_secrets()

from mcp_agent.app import MCPApp
from agents import setup_agents, run_pipeline
from patterns import PATTERNS

# --------------------------------------------------------------------------- #
#  Page config
# --------------------------------------------------------------------------- #
st.set_page_config(page_title="LeetCoach", page_icon="🧠", layout="wide")

st.markdown("# 🧠 LeetCoach")
st.markdown("AI-powered LeetCode preparation — pattern identification, optimized solutions, and plain-English complexity breakdowns.")

# --------------------------------------------------------------------------- #
#  Session state init
# --------------------------------------------------------------------------- #
if "initialized" not in st.session_state:
    st.session_state.initialized = False
    st.session_state.mcp_app = MCPApp(name="leetcoach")
    st.session_state.mcp_context = None
    st.session_state.mcp_agent_app = None
    st.session_state.agents = None
    st.session_state.loop = asyncio.new_event_loop()
    asyncio.set_event_loop(st.session_state.loop)

if "is_processing" not in st.session_state:
    st.session_state.is_processing = False
if "last_results" not in st.session_state:
    st.session_state.last_results = None
if "last_log" not in st.session_state:
    st.session_state.last_log = None

# --------------------------------------------------------------------------- #
#  Agent setup (runs once)
# --------------------------------------------------------------------------- #
async def init_agents():
    if not st.session_state.initialized:
        try:
            st.session_state.mcp_context = st.session_state.mcp_app.run()
            st.session_state.mcp_agent_app = await st.session_state.mcp_context.__aenter__()
            st.session_state.agents = await setup_agents(st.session_state.mcp_agent_app)
            st.session_state.initialized = True
        except Exception as e:
            return f"Initialization error: {str(e)}"
    return None

async def run(url: str):
    if not os.getenv("OPENAI_API_KEY"):
        return None, [{"agent": "Setup", "status": "failed",
                       "details": "OpenAI API key not found. Add it to mcp_agent.secrets.yaml", "duration": 0}]
    error = await init_agents()
    if error:
        return None, [{"agent": "Setup", "status": "failed", "details": error, "duration": 0}]
    return await run_pipeline(url, st.session_state.agents)

# --------------------------------------------------------------------------- #
#  Tabs
# --------------------------------------------------------------------------- #
tab1, tab2 = st.tabs(["🔍 Problem Solver", "📚 Pattern Library"])


# =========================================================================== #
#  TAB 1 — Problem Solver
# =========================================================================== #
with tab1:
    st.markdown("### Paste a LeetCode Problem URL")
    url_input = st.text_input(
        "LeetCode URL",
        placeholder="https://leetcode.com/problems/two-sum/",
        label_visibility="collapsed",
    )

    def start_run():
        st.session_state.is_processing = True

    st.button(
        "🚀 Analyze Problem",
        type="primary",
        use_container_width=True,
        disabled=st.session_state.is_processing or not url_input.strip(),
        on_click=start_run,
    )

    # Run the pipeline
    if st.session_state.is_processing:
        with st.spinner("Running 4-agent pipeline... (Browser → Classifier → Solution → Complexity)"):
            results, log = st.session_state.loop.run_until_complete(run(url_input.strip()))
        st.session_state.last_results = results
        st.session_state.last_log = log
        st.session_state.is_processing = False
        st.rerun()

    # Display results
    if st.session_state.last_results and st.session_state.last_results.get("pattern"):
        results = st.session_state.last_results

        st.markdown("---")

        # Section 1: Pattern
        st.markdown("## 🎯 Pattern Match")
        st.markdown(results["pattern"])

        # Section 2: Solution
        if results.get("solution"):
            st.markdown("---")
            st.markdown("## 💡 Solution")
            st.markdown(results["solution"])

        # Section 3: Complexity
        if results.get("complexity"):
            st.markdown("---")
            st.markdown("## ⏱ Complexity Analysis")
            st.markdown(results["complexity"])

    # Agent Failure Log — always shown after a run
    if st.session_state.last_log:
        st.markdown("---")
        st.markdown("### 🪵 Agent Execution Log")

        status_icon = {"success": "✅", "failed": "❌", "skipped": "⏭️"}
        status_color = {"success": "green", "failed": "red", "skipped": "gray"}

        cols = st.columns([2.5, 1.2, 4, 1])
        cols[0].markdown("**Agent**")
        cols[1].markdown("**Status**")
        cols[2].markdown("**Details**")
        cols[3].markdown("**Time (s)**")
        st.markdown("<hr style='margin:4px 0'>", unsafe_allow_html=True)

        for entry in st.session_state.last_log:
            icon = status_icon.get(entry["status"], "?")
            cols = st.columns([2.5, 1.2, 4, 1])
            cols[0].markdown(entry["agent"])
            cols[1].markdown(f":{status_color[entry['status']]}[{icon} {entry['status'].upper()}]")
            cols[2].markdown(entry["details"])
            cols[3].markdown(str(entry["duration"]))


# =========================================================================== #
#  TAB 2 — Pattern Library
# =========================================================================== #
with tab2:
    st.markdown("### All 20 Algorithmic Patterns")
    st.markdown("Each pattern below includes when to use it, a code template, and example LeetCode problems.")

    # Search / filter
    search = st.text_input("🔎 Search patterns", placeholder="e.g. sliding window, BFS, dynamic...")

    filtered = [
        p for p in PATTERNS
        if not search or search.lower() in p["name"].lower() or search.lower() in p["description"].lower()
    ]

    if not filtered:
        st.info("No patterns match your search.")

    for pattern in filtered:
        with st.expander(f"**{pattern['id']:02d}. {pattern['name']}**", expanded=False):
            st.markdown(f"**What it is:** {pattern['description']}")

            st.markdown("**When to use it:**")
            for signal in pattern["when_to_use"]:
                st.markdown(f"- {signal}")

            st.markdown("**Code template:**")
            st.code(pattern["template"], language="python")

            st.markdown("**Example problems:**")
            for ex in pattern["examples"]:
                st.markdown(f"- [{ex['name']}]({ex['url']})")


# --------------------------------------------------------------------------- #
#  Footer
# --------------------------------------------------------------------------- #
st.markdown("---")
st.write("Built with Streamlit, Playwright, and [MCP-Agent](https://www.github.com/lastmile-ai/mcp-agent) Framework ❤️")
