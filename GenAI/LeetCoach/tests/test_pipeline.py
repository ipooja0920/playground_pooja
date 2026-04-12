"""
Tests for the full pipeline wiring in agents.py — run_pipeline().

All LLM agents are mocked. Tests verify orchestration logic:
  - Which agents run, skip, or fail
  - What keys are set in the results dict
  - What entries appear in the log
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from helpers import make_critic_response, make_classifier_response


def _make_agents(
    browser_result="Problem text here",
    browser_fail=False,
    pattern_result=None,
    critic_result=None,
    solution_result="Solution text here",
    complexity_result="Complexity text here",
):
    """Build a mock agents dict for run_pipeline."""
    pattern_result = pattern_result or make_classifier_response("Dynamic Programming")
    critic_result = critic_result or make_critic_response(score=5)

    browser_llm = AsyncMock()
    if browser_fail:
        browser_llm.generate_str.side_effect = Exception("scraping failed")
    else:
        browser_llm.generate_str.return_value = browser_result

    classifier_llm = AsyncMock()
    classifier_llm.generate_str.return_value = pattern_result

    classifier_critic_llm = AsyncMock()
    classifier_critic_llm.generate_str.return_value = make_critic_response(score=5)

    solution_llm = AsyncMock()
    solution_llm.generate_str.return_value = solution_result

    complexity_llm = AsyncMock()
    complexity_llm.generate_str.return_value = complexity_result

    critic_llm = AsyncMock()
    critic_llm.generate_str.return_value = critic_result

    return {
        "browser_llm": browser_llm,
        "classifier_llm": classifier_llm,
        "classifier_critic_llm": classifier_critic_llm,
        "solution_llm": solution_llm,
        "complexity_llm": complexity_llm,
        "critic_llm": critic_llm,
    }


def _patch_pipeline(tmp_path):
    """Patch file paths and AsyncOpenAI so no real I/O or API calls happen."""
    from helpers import make_classifier_response, make_critic_response
    mock_client = AsyncMock()
    mock_client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content=make_classifier_response("Dynamic Programming")))]
    )
    return [
        patch("agents.CORRECTIONS_FILE", tmp_path / "c.json"),
        patch("agents.FEEDBACK_FILE", tmp_path / "f.json"),
        patch("agents.FEEDBACK_RULES_FILE", tmp_path / "r.json"),
        patch("agents.JUDGE_LESSONS_FILE", tmp_path / "j.json"),
        patch("agents.get_pattern_knowledge_for_classifier", return_value=""),
        patch("agents.AsyncOpenAI", return_value=mock_client),
    ]


import contextlib

@contextlib.contextmanager
def pipeline_context(tmp_path):
    patches = _patch_pipeline(tmp_path)
    for p in patches:
        p.start()
    try:
        yield
    finally:
        for p in patches:
            p.stop()


class TestPipelineHappyPath:

    @pytest.mark.asyncio
    async def test_full_pipeline_returns_all_keys(self, tmp_path):
        with pipeline_context(tmp_path):
            from agents import run_pipeline
            agents = _make_agents()
            results, log = await run_pipeline("https://leetcode.com/problems/two-sum/", agents)
        assert results["problem_text"] is not None
        assert results["pattern"] is not None
        assert results["solution"] is not None
        assert results["complexity"] is not None
        assert results["needs_fallback"] is False

    @pytest.mark.asyncio
    async def test_all_agents_logged_as_success(self, tmp_path):
        with pipeline_context(tmp_path):
            from agents import run_pipeline
            agents = _make_agents()
            results, log = await run_pipeline("https://leetcode.com/problems/two-sum/", agents)
        statuses = {e["agent"]: e["status"] for e in log}
        assert statuses.get("Browser Agent") == "success"
        assert statuses.get("Solution Agent") == "success"
        assert statuses.get("Complexity Agent") == "success"

    @pytest.mark.asyncio
    async def test_fallback_text_skips_browser_agent(self, tmp_path):
        with pipeline_context(tmp_path):
            from agents import run_pipeline
            agents = _make_agents()
            results, log = await run_pipeline(
                "https://leetcode.com/problems/two-sum/", agents,
                fallback_text="Given an array of integers..."
            )
        browser_entry = next(e for e in log if e["agent"] == "Browser Agent")
        assert browser_entry["status"] == "skipped"
        assert results["problem_text"] == "Given an array of integers..."


class TestPipelineFailures:

    @pytest.mark.asyncio
    async def test_browser_failure_sets_needs_fallback(self, tmp_path):
        with pipeline_context(tmp_path):
            from agents import run_pipeline
            agents = _make_agents(browser_fail=True)
            results, log = await run_pipeline("https://leetcode.com/problems/two-sum/", agents)
        assert results["needs_fallback"] is True

    @pytest.mark.asyncio
    async def test_browser_failure_skips_downstream_agents(self, tmp_path):
        with pipeline_context(tmp_path):
            from agents import run_pipeline
            agents = _make_agents(browser_fail=True)
            results, log = await run_pipeline("https://leetcode.com/problems/two-sum/", agents)
        skipped = [e["agent"] for e in log if e["status"] == "skipped"]
        assert "Planner Agent" in skipped or "Classifier Agent" in skipped

    @pytest.mark.asyncio
    async def test_classifier_failure_skips_solution_and_complexity(self, tmp_path):
        with pipeline_context(tmp_path):
            from agents import run_pipeline
            agents = _make_agents()
            # Make the gpt-4o classifier call fail
            import agents as ag
            original = ag.run_classifier_direct
            async def boom(*a, **kw):
                raise Exception("classifier error")
            ag.run_classifier_direct = boom
            try:
                results, log = await run_pipeline("https://leetcode.com/problems/two-sum/", agents)
            finally:
                ag.run_classifier_direct = original

        statuses = {e["agent"]: e["status"] for e in log}
        assert statuses.get("Classifier Agent") == "failed"
        assert statuses.get("Solution Agent") == "skipped"
        assert statuses.get("Complexity Agent") == "skipped"

    @pytest.mark.asyncio
    async def test_solution_failure_skips_complexity(self, tmp_path):
        with pipeline_context(tmp_path):
            from agents import run_pipeline
            agents = _make_agents()
            agents["solution_llm"].generate_str.side_effect = Exception("LLM error")
            results, log = await run_pipeline("https://leetcode.com/problems/two-sum/", agents)

        statuses = {e["agent"]: e["status"] for e in log}
        assert statuses.get("Solution Agent") == "failed"
        assert statuses.get("Complexity Agent") == "skipped"


class TestPipelineLog:

    @pytest.mark.asyncio
    async def test_log_entries_have_required_keys(self, tmp_path):
        with pipeline_context(tmp_path):
            from agents import run_pipeline
            agents = _make_agents()
            _, log = await run_pipeline("https://leetcode.com/problems/two-sum/", agents)
        for entry in log:
            assert "agent" in entry
            assert "status" in entry
            assert "details" in entry
            assert "duration" in entry
            assert "corrections" in entry

    @pytest.mark.asyncio
    async def test_planner_strategy_stored_in_results(self, tmp_path):
        with pipeline_context(tmp_path):
            from agents import run_pipeline
            agents = _make_agents()
            results, _ = await run_pipeline("https://leetcode.com/problems/two-sum/", agents)
        assert results.get("planner_strategy") in ("full", "simplified")

    @pytest.mark.asyncio
    async def test_self_corrected_agent_has_multiple_log_attempts(self, tmp_path):
        with pipeline_context(tmp_path):
            from agents import run_pipeline
            agents = _make_agents()
            # Make general critic score low on first try so solution retries
            agents["critic_llm"].generate_str.side_effect = [
                make_critic_response(score=2, suggestion="use simpler words"),  # solution attempt 1
                make_critic_response(score=5),                                  # solution attempt 2
                make_critic_response(score=5),                                  # complexity
            ]
            results, log = await run_pipeline("https://leetcode.com/problems/two-sum/", agents)

        solution_entry = next(e for e in log if e["agent"] == "Solution Agent")
        assert len(solution_entry["corrections"]) == 2
