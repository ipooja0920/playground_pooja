"""
Tests for rerun_section() — the feedback cascade triggered by 👎.

Verifies:
  - Which agents are called for each section
  - Correction comment is injected into the prompt
  - Generic "rewrite simpler" note used when no comment
  - Classifier rerun uses classifier_critic (not general critic)
"""
import pytest
from unittest.mock import AsyncMock, patch, call
from helpers import make_critic_response, make_classifier_response


def _make_agents():
    return {
        "classifier_llm": AsyncMock(),
        "classifier_critic_llm": AsyncMock(),
        "solution_llm": AsyncMock(),
        "complexity_llm": AsyncMock(),
        "critic_llm": AsyncMock(),
    }


def _patch_files(tmp_path):
    import contextlib
    @contextlib.contextmanager
    def ctx():
        with patch("agents.CORRECTIONS_FILE", tmp_path / "c.json"), \
             patch("agents.FEEDBACK_FILE", tmp_path / "f.json"), \
             patch("agents.FEEDBACK_RULES_FILE", tmp_path / "r.json"), \
             patch("agents.JUDGE_LESSONS_FILE", tmp_path / "j.json"):
            yield
    return ctx()


class TestRerunSectionClassifier:

    @pytest.mark.asyncio
    async def test_classifier_rerun_uses_classifier_critic(self, tmp_path):
        with _patch_files(tmp_path):
            from agents import rerun_section
            agents = _make_agents()
            agents["classifier_llm"].generate_str.return_value = make_classifier_response("Dynamic Programming")
            agents["classifier_critic_llm"].generate_str.return_value = make_critic_response(score=5)

            await rerun_section("classifier", {"problem_text": "some problem", "pattern": "", "solution": ""}, agents)

            agents["classifier_critic_llm"].generate_str.assert_called()
            agents["critic_llm"].generate_str.assert_not_called()

    @pytest.mark.asyncio
    async def test_correction_comment_injected_into_classifier_prompt(self, tmp_path):
        with _patch_files(tmp_path):
            from agents import rerun_section
            agents = _make_agents()
            agents["classifier_llm"].generate_str.return_value = make_classifier_response("Dynamic Programming")
            agents["classifier_critic_llm"].generate_str.return_value = make_critic_response(score=5)

            await rerun_section(
                "classifier",
                {"problem_text": "some problem", "pattern": "", "solution": ""},
                agents,
                feedback_comment="this is Dynamic Programming not Sliding Window"
            )

            call_args = agents["classifier_llm"].generate_str.call_args
            message = call_args.kwargs.get("message") or call_args.args[0]
            assert "Dynamic Programming not Sliding Window" in message
            assert "IMPORTANT" in message

    @pytest.mark.asyncio
    async def test_no_comment_uses_generic_rewrite_note(self, tmp_path):
        with _patch_files(tmp_path):
            from agents import rerun_section
            agents = _make_agents()
            agents["classifier_llm"].generate_str.return_value = make_classifier_response("Dynamic Programming")
            agents["classifier_critic_llm"].generate_str.return_value = make_critic_response(score=5)

            await rerun_section(
                "classifier",
                {"problem_text": "some problem", "pattern": "", "solution": ""},
                agents,
                feedback_comment=""
            )

            call_args = agents["classifier_llm"].generate_str.call_args
            message = call_args.kwargs.get("message") or call_args.args[0]
            assert "unhappy" in message.lower() or "simpler" in message.lower()


class TestRerunSectionSolution:

    @pytest.mark.asyncio
    async def test_solution_rerun_uses_general_critic(self, tmp_path):
        with _patch_files(tmp_path):
            from agents import rerun_section
            agents = _make_agents()
            agents["solution_llm"].generate_str.return_value = "new solution text"
            agents["critic_llm"].generate_str.return_value = make_critic_response(score=5)

            await rerun_section(
                "solution",
                {"problem_text": "problem", "pattern": "DP", "solution": "old solution"},
                agents
            )

            agents["critic_llm"].generate_str.assert_called()
            agents["classifier_critic_llm"].generate_str.assert_not_called()

    @pytest.mark.asyncio
    async def test_solution_rerun_includes_pattern_in_prompt(self, tmp_path):
        with _patch_files(tmp_path):
            from agents import rerun_section
            agents = _make_agents()
            agents["solution_llm"].generate_str.return_value = "new solution"
            agents["critic_llm"].generate_str.return_value = make_critic_response(score=5)

            await rerun_section(
                "solution",
                {"problem_text": "problem text", "pattern": "Dynamic Programming", "solution": "old"},
                agents
            )

            call_args = agents["solution_llm"].generate_str.call_args
            message = call_args.kwargs.get("message") or call_args.args[0]
            assert "Dynamic Programming" in message

    @pytest.mark.asyncio
    async def test_solution_feedback_comment_injected(self, tmp_path):
        with _patch_files(tmp_path):
            from agents import rerun_section
            agents = _make_agents()
            agents["solution_llm"].generate_str.return_value = "new solution"
            agents["critic_llm"].generate_str.return_value = make_critic_response(score=5)

            await rerun_section(
                "solution",
                {"problem_text": "problem", "pattern": "DP", "solution": "old"},
                agents,
                feedback_comment="please use more toy box analogies"
            )

            call_args = agents["solution_llm"].generate_str.call_args
            message = call_args.kwargs.get("message") or call_args.args[0]
            assert "toy box analogies" in message


class TestRerunSectionComplexity:

    @pytest.mark.asyncio
    async def test_complexity_rerun_uses_general_critic(self, tmp_path):
        with _patch_files(tmp_path):
            from agents import rerun_section
            agents = _make_agents()
            agents["complexity_llm"].generate_str.return_value = "new complexity"
            agents["critic_llm"].generate_str.return_value = make_critic_response(score=5)

            await rerun_section(
                "complexity",
                {"problem_text": "problem", "pattern": "DP", "solution": "solution text"},
                agents
            )

            agents["critic_llm"].generate_str.assert_called()

    @pytest.mark.asyncio
    async def test_complexity_rerun_includes_solution_in_prompt(self, tmp_path):
        with _patch_files(tmp_path):
            from agents import rerun_section
            agents = _make_agents()
            agents["complexity_llm"].generate_str.return_value = "new complexity"
            agents["critic_llm"].generate_str.return_value = make_critic_response(score=5)

            await rerun_section(
                "complexity",
                {"problem_text": "problem", "pattern": "DP", "solution": "my solution code here"},
                agents
            )

            call_args = agents["complexity_llm"].generate_str.call_args
            message = call_args.kwargs.get("message") or call_args.args[0]
            assert "my solution code here" in message

    @pytest.mark.asyncio
    async def test_rerun_returns_tuple_of_text_and_log(self, tmp_path):
        with _patch_files(tmp_path):
            from agents import rerun_section
            agents = _make_agents()
            agents["complexity_llm"].generate_str.return_value = "complexity result"
            agents["critic_llm"].generate_str.return_value = make_critic_response(score=5)

            result, log = await rerun_section(
                "complexity",
                {"problem_text": "p", "pattern": "DP", "solution": "s"},
                agents
            )

            assert isinstance(result, str)
            assert isinstance(log, list)
            assert len(log) >= 1
