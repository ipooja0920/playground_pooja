import asyncio
import os
from pathlib import Path
import yaml
import streamlit as st

# --------------------------------------------------------------------------- #
#  Load API key
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
st.markdown("Paste a LeetCode URL — get the pattern, a beginner-friendly solution, and a plain-English complexity breakdown.")

# --------------------------------------------------------------------------- #
#  Session state
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
if "last_url" not in st.session_state:
    st.session_state.last_url = ""

# --------------------------------------------------------------------------- #
#  Agent init
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
        return None, [{
            "agent": "Setup",
            "status": "failed",
            "details": "OpenAI API key not found. Add it to mcp_agent.secrets.yaml",
            "duration": 0,
            "corrections": [],
        }]
    error = await init_agents()
    if error:
        return None, [{
            "agent": "Setup",
            "status": "failed",
            "details": error,
            "duration": 0,
            "corrections": [],
        }]
    return await run_pipeline(url, st.session_state.agents)

# --------------------------------------------------------------------------- #
#  Tabs
# --------------------------------------------------------------------------- #
tab1, tab2, tab3 = st.tabs(["🔍 Problem Solver", "📚 Pattern Library", "🪵 Agent Log"])


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
        st.session_state.last_url = url_input.strip()

    st.button(
        "🚀 Analyze Problem",
        type="primary",
        use_container_width=True,
        disabled=st.session_state.is_processing or not url_input.strip(),
        on_click=start_run,
    )

    # Run pipeline
    if st.session_state.is_processing:
        with st.spinner("Running agents: Browser → Classifier → Solution → Complexity..."):
            results, log = st.session_state.loop.run_until_complete(
                run(st.session_state.last_url)
            )
        st.session_state.last_results = results
        st.session_state.last_log = log
        st.session_state.is_processing = False
        st.rerun()

    # Results
    if st.session_state.last_results and st.session_state.last_results.get("pattern"):
        results = st.session_state.last_results
        st.markdown("---")

        st.markdown("## 🎯 Pattern Match")
        st.markdown(results["pattern"])

        if results.get("solution"):
            st.markdown("---")
            st.markdown("## 💡 Solution")
            st.markdown(results["solution"])

        if results.get("complexity"):
            st.markdown("---")
            st.markdown("## ⏱ Complexity")
            st.markdown(results["complexity"])

    elif st.session_state.last_log:
        # Pipeline ran but no results — show top-level failure message
        failed = [e for e in st.session_state.last_log if e["status"] == "failed"]
        if failed:
            st.error(f"Pipeline failed at **{failed[0]['agent']}**: {failed[0]['details']}")
            st.info("Check the Agent Log tab for full details.")


# =========================================================================== #
#  TAB 2 — Pattern Library
# =========================================================================== #
with tab2:
    st.markdown("### All 20 Algorithmic Patterns")
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


# =========================================================================== #
#  TAB 3 — Agent Log
# =========================================================================== #
with tab3:
    st.markdown("### Agent Execution Log")

    if not st.session_state.last_log:
        st.info("No runs yet. Analyze a problem to see the agent log here.")
    else:
        log = st.session_state.last_log

        if st.session_state.last_url:
            st.caption(f"Last run: {st.session_state.last_url}")

        # Summary row counts
        success_count = sum(1 for e in log if e["status"] == "success")
        failed_count  = sum(1 for e in log if e["status"] == "failed")
        skipped_count = sum(1 for e in log if e["status"] == "skipped")
        corrected_count = sum(1 for e in log if len(e.get("corrections", [])) > 1)

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Agents Run", success_count + failed_count)
        col2.metric("Succeeded", success_count)
        col3.metric("Failed", failed_count)
        col4.metric("Self-Corrected", corrected_count)

        st.markdown("---")

        STATUS_ICON  = {"success": "✅", "failed": "❌", "skipped": "⏭️"}
        STATUS_COLOR = {"success": "green", "failed": "red", "skipped": "gray"}

        for entry in log:
            icon  = STATUS_ICON.get(entry["status"], "?")
            color = STATUS_COLOR.get(entry["status"], "gray")

            with st.expander(
                f"{icon} **{entry['agent']}** — {entry['details']}",
                expanded=(entry["status"] == "failed"),
            ):
                st.markdown(f"**Status:** :{color}[{entry['status'].upper()}]")
                st.markdown(f"**Duration:** {entry['duration']}s")
                st.markdown(f"**Details:** {entry['details']}")

                corrections = entry.get("corrections", [])
                if corrections:
                    st.markdown("**Self-Correction Attempts:**")
                    for attempt in corrections:
                        score = attempt.get("score", "?")
                        issues = attempt.get("issues", "none")
                        attempt_num = attempt.get("attempt", "?")
                        score_color = "green" if score >= 4 else ("orange" if score == 3 else "red")
                        st.markdown(
                            f"- Attempt {attempt_num}: Score :{score_color}[{score}/5] — {issues}"
                        )

                    if len(corrections) > 1:
                        st.success("Agent self-corrected and improved its output.")

        # Saved lessons section
        st.markdown("---")
        st.markdown("### 📖 Lessons Learned (Persistent)")
        st.caption("These are saved to corrections.json and injected into future runs automatically.")

        corrections_path = Path(__file__).parent / "corrections.json"
        if corrections_path.exists():
            import json
            with open(corrections_path) as f:
                all_corrections = json.load(f)

            has_any = any(len(v) > 0 for v in all_corrections.values())
            if has_any:
                for agent_name, lessons in all_corrections.items():
                    if lessons:
                        st.markdown(f"**{agent_name.capitalize()} Agent**")
                        for lesson in lessons:
                            st.markdown(f"- {lesson['suggestion']} *(saved {lesson['timestamp'][:10]})*")
            else:
                st.info("No lessons saved yet. They appear here after a self-correction.")
        else:
            st.info("No lessons saved yet.")

# --------------------------------------------------------------------------- #
#  Footer
# --------------------------------------------------------------------------- #
st.markdown("---")
st.write("Built with Streamlit, Playwright, and [MCP-Agent](https://www.github.com/lastmile-ai/mcp-agent) Framework ❤️")
