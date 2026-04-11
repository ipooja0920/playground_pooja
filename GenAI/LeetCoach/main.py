import asyncio
import os
import re
import json
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
from agents import setup_agents, run_pipeline, rerun_section, save_feedback
from patterns import PATTERNS

# --------------------------------------------------------------------------- #
#  Page config
# --------------------------------------------------------------------------- #
st.set_page_config(page_title="LeetCoach", page_icon="🧠", layout="wide")
st.markdown("# 🧠 LeetCoach")
st.markdown("Paste a LeetCode URL — get the pattern, a beginner-friendly solution, and a plain-English complexity breakdown.")

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
if "last_url" not in st.session_state:
    st.session_state.last_url = ""
if "quiz_state" not in st.session_state:
    st.session_state.quiz_state = {}

# Feedback state — one per section
_SECTIONS = ["classifier", "solution", "complexity"]
if "fb" not in st.session_state:
    # fb[section] = {sentiment, show_comment, submitted, regenerating}
    st.session_state.fb = {
        s: {"sentiment": None, "show_comment": False, "submitted": False, "regenerating": False}
        for s in _SECTIONS
    }

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
        return None, [{"agent": "Setup", "status": "failed",
                       "details": "OpenAI API key not found.", "duration": 0, "corrections": []}]
    error = await init_agents()
    if error:
        return None, [{"agent": "Setup", "status": "failed",
                       "details": error, "duration": 0, "corrections": []}]
    return await run_pipeline(url, st.session_state.agents)

# --------------------------------------------------------------------------- #
#  Process any pending regenerations (must happen before tab rendering)
# --------------------------------------------------------------------------- #
for _section in _SECTIONS:
    if st.session_state.fb[_section]["regenerating"]:
        _comment = st.session_state.get(f"_comment_{_section}", "")
        _context = {
            "problem_text": (st.session_state.last_results or {}).get("problem_text", ""),
            "pattern":      (st.session_state.last_results or {}).get("pattern", ""),
            "solution":     (st.session_state.last_results or {}).get("solution", ""),
        }
        with st.spinner(f"Regenerating based on your feedback..."):
            _new_result, _ = st.session_state.loop.run_until_complete(
                rerun_section(_section, _context, st.session_state.agents, _comment)
            )
        # Map section name → result key
        _result_key = {"classifier": "pattern", "solution": "solution", "complexity": "complexity"}[_section]
        st.session_state.last_results[_result_key] = _new_result

        # Save as negative feedback
        save_feedback(_section, "negative", _new_result[:300], _comment)

        st.session_state.fb[_section]["regenerating"] = False
        st.session_state.fb[_section]["submitted"] = True
        st.session_state.quiz_state = {}  # reset quiz if complexity changed
        st.rerun()

# --------------------------------------------------------------------------- #
#  Feedback UI helper
# --------------------------------------------------------------------------- #
def render_feedback(section: str, label: str):
    """Render 👍 👎 + optional comment below a result section."""
    state = st.session_state.fb[section]

    if state["submitted"]:
        if state["sentiment"] == "liked":
            st.caption("Thanks for the 👍 — noted for future runs!")
        else:
            st.caption("✅ Regenerated based on your feedback!")
        return

    st.markdown(f"<small>Was this {label} helpful?</small>", unsafe_allow_html=True)
    col1, col2, col_space = st.columns([1, 1, 10])

    def _like():
        state["sentiment"] = "liked"
        state["show_comment"] = True

    def _dislike():
        state["sentiment"] = "disliked"
        state["show_comment"] = True

    with col1:
        st.button("👍", key=f"like_{section}",
                  type="primary" if state["sentiment"] == "liked" else "secondary",
                  on_click=_like)
    with col2:
        st.button("👎", key=f"dislike_{section}",
                  type="primary" if state["sentiment"] == "disliked" else "secondary",
                  on_click=_dislike)

    if state["show_comment"]:
        comment = st.text_area(
            "Add a comment (optional)",
            placeholder="Tell us what you liked or what could be better...",
            height=80,
            key=f"comment_area_{section}",
        )
        submit_label = "Submit & Regenerate 🔄" if state["sentiment"] == "disliked" else "Submit Feedback"

        def _submit():
            st.session_state[f"_comment_{section}"] = comment
            if state["sentiment"] == "liked":
                save_feedback(section, "positive", "", comment)
                state["submitted"] = True
            else:
                state["regenerating"] = True

        st.button(submit_label, key=f"submit_{section}", type="primary", on_click=_submit)


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
        st.session_state.quiz_state = {}
        # Reset feedback for all sections
        for s in _SECTIONS:
            st.session_state.fb[s] = {
                "sentiment": None, "show_comment": False,
                "submitted": False, "regenerating": False,
            }

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

        # --- Pattern ---
        st.markdown("## 🎯 Pattern Match")
        st.markdown(results["pattern"])
        render_feedback("classifier", "pattern explanation")

        # --- Solution ---
        if results.get("solution"):
            st.markdown("---")
            st.markdown("## 💡 Solution")
            st.markdown(results["solution"])
            render_feedback("solution", "solution explanation")

        # --- Complexity + Quiz ---
        if results.get("complexity"):
            st.markdown("---")
            st.markdown("## ⏱ Complexity")

            complexity_text = results["complexity"]
            quiz_marker = "## 🧪 Quick Quiz"
            if quiz_marker in complexity_text:
                complexity_body = complexity_text[:complexity_text.index(quiz_marker)].strip()
                quiz_body       = complexity_text[complexity_text.index(quiz_marker):]
            else:
                complexity_body = complexity_text
                quiz_body       = ""

            st.markdown(complexity_body)
            render_feedback("complexity", "complexity explanation")

            # Quiz
            if quiz_body:
                st.markdown("---")
                st.markdown("## 🧪 Quick Quiz — Test Yourself!")
                st.caption("Try to answer before peeking at the hint.")

                q_blocks = re.findall(
                    r'\*\*Q(\d+):\*\*\s*(.+?)\n((?:\s*- [A-Ca-c]\).+\n)+)\s*ANSWER:\s*([A-Ca-c])\s*\nHINT:\s*(.+)',
                    quiz_body,
                    re.MULTILINE,
                )

                for q_num, question, options_raw, answer, hint in q_blocks:
                    q_key = f"q{q_num}"
                    options_parsed = re.findall(r'- ([A-Ca-c])\)\s*(.+)', options_raw)
                    options_dict   = {opt[0].upper(): opt[1].strip() for opt in options_parsed}
                    correct        = answer.strip().upper()

                    st.markdown(f"**Q{q_num}: {question.strip()}**")
                    radio_options = [f"{k}) {v}" for k, v in options_dict.items()]
                    selected = st.radio(
                        f"q{q_num}_radio",
                        options=radio_options,
                        index=None,
                        key=f"radio_{q_key}",
                        label_visibility="collapsed",
                    )

                    if st.button("Check Answer", key=f"check_{q_key}"):
                        st.session_state.quiz_state[q_key] = {
                            "selected": selected,
                            "checked": True,
                            "correct": correct,
                            "hint": hint.strip(),
                            "options": options_dict,
                        }

                    state = st.session_state.quiz_state.get(q_key, {})
                    if state.get("checked"):
                        if state["selected"] and state["selected"].startswith(state["correct"]):
                            st.success(f"Correct! {state['hint']}")
                        elif state["selected"]:
                            st.error(
                                f"Not quite. The answer is **{state['correct']}) "
                                f"{state['options'].get(state['correct'], '')}**"
                            )
                            st.info(f"Hint: {state['hint']}")
                        else:
                            st.warning("Pick an option first!")
                    st.markdown("")

    elif st.session_state.last_log:
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

        success_count   = sum(1 for e in log if e["status"] == "success")
        failed_count    = sum(1 for e in log if e["status"] == "failed")
        skipped_count   = sum(1 for e in log if e["status"] == "skipped")
        corrected_count = sum(1 for e in log if len(e.get("corrections", [])) > 1)

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Agents Run",     success_count + failed_count)
        col2.metric("Succeeded",      success_count)
        col3.metric("Failed",         failed_count)
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
                        score  = attempt.get("score", "?")
                        issues = attempt.get("issues", "none")
                        num    = attempt.get("attempt", "?")
                        score_color = "green" if score >= 4 else ("orange" if score == 3 else "red")
                        st.markdown(f"- Attempt {num}: Score :{score_color}[{score}/5] — {issues}")
                    if len(corrections) > 1:
                        st.success("Agent self-corrected and improved its output.")

        # Human feedback summary
        st.markdown("---")
        st.markdown("### 💬 Human Feedback Log")
        st.caption("Likes and dislikes saved from the UI — injected into future runs automatically.")

        feedback_path = Path(__file__).parent / "feedback.json"
        if feedback_path.exists():
            with open(feedback_path) as f:
                all_feedback = json.load(f)
            has_any = any(
                len(v.get("positive", [])) + len(v.get("negative", [])) > 0
                for v in all_feedback.values()
            )
            if has_any:
                for agent_name, fb in all_feedback.items():
                    positives = fb.get("positive", [])
                    negatives = fb.get("negative", [])
                    if positives or negatives:
                        st.markdown(f"**{agent_name.capitalize()} Agent**")
                        for p in positives:
                            comment = f' — "{p["comment"]}"' if p.get("comment") else ""
                            st.markdown(f"- 👍 {p['timestamp'][:10]}{comment}")
                        for n in negatives:
                            comment = f' — "{n["comment"]}"' if n.get("comment") else ""
                            st.markdown(f"- 👎 {n['timestamp'][:10]}{comment}")
            else:
                st.info("No human feedback yet. Use 👍 👎 buttons after analyzing a problem.")
        else:
            st.info("No human feedback yet.")

        # Critic lessons
        st.markdown("---")
        st.markdown("### 📖 Critic Lessons Learned")
        st.caption("Auto-saved when Critic scores output ≤ 3 — injected into future runs.")

        corrections_path = Path(__file__).parent / "corrections.json"
        if corrections_path.exists():
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
                st.info("No critic lessons yet.")
        else:
            st.info("No critic lessons yet.")


# --------------------------------------------------------------------------- #
#  Footer
# --------------------------------------------------------------------------- #
st.markdown("---")
st.write("Built with Streamlit, Playwright, and [MCP-Agent](https://www.github.com/lastmile-ai/mcp-agent) Framework ❤️")
