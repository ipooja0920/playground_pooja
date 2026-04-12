"""
Tests for Classifier Agent logic in agents.py.

All OpenAI API calls are mocked — no real LLM calls, no API credits used.
"""
import json
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from helpers import make_openai_response, make_critic_response, make_classifier_response


def _async_response(content: str):
    """Build a coroutine-safe mock for AsyncOpenAI."""
    mock = AsyncMock()
    mock.chat.completions.create.return_value = make_openai_response(content)
    return mock


# --------------------------------------------------------------------------- #
#  CLASSIFIER_INSTRUCTION content
# --------------------------------------------------------------------------- #

class TestClassifierInstruction:

    def test_instruction_contains_all_pattern_names(self):
        from agents import CLASSIFIER_INSTRUCTION
        from patterns import PATTERNS
        for p in PATTERNS:
            assert p["name"] in CLASSIFIER_INSTRUCTION, (
                f"Pattern '{p['name']}' missing from CLASSIFIER_INSTRUCTION"
            )

    def test_instruction_contains_sliding_window_vs_two_pointers_rule(self):
        from agents import CLASSIFIER_INSTRUCTION
        lower = CLASSIFIER_INSTRUCTION.lower()
        assert "sliding window" in lower and "two pointers" in lower

    def test_instruction_contains_dp_vs_backtracking_rule(self):
        from agents import CLASSIFIER_INSTRUCTION
        lower = CLASSIFIER_INSTRUCTION.lower()
        assert "dp" in lower or "dynamic programming" in lower
        assert "backtracking" in lower

    def test_instruction_contains_bfs_vs_dfs_rule(self):
        from agents import CLASSIFIER_INSTRUCTION
        lower = CLASSIFIER_INSTRUCTION.lower()
        assert "bfs" in lower and "dfs" in lower

    def test_classifier_critic_instruction_catches_sliding_window_for_dp(self):
        from agents import CLASSIFIER_CRITIC_INSTRUCTION
        lower = CLASSIFIER_CRITIC_INSTRUCTION.lower()
        assert "sliding window" in lower and ("dp" in lower or "dynamic" in lower)

    def test_classifier_critic_instruction_catches_number_of_ways(self):
        from agents import CLASSIFIER_CRITIC_INSTRUCTION
        lower = CLASSIFIER_CRITIC_INSTRUCTION.lower()
        assert "number of ways" in lower or "can we form" in lower

    def test_instruction_contains_greedy_vs_dp_rule(self):
        from agents import CLASSIFIER_INSTRUCTION
        lower = CLASSIFIER_INSTRUCTION.lower()
        assert "greedy" in lower and ("dp" in lower or "dynamic programming" in lower)

    def test_classifier_critic_instruction_catches_dp_for_greedy(self):
        from agents import CLASSIFIER_CRITIC_INSTRUCTION
        lower = CLASSIFIER_CRITIC_INSTRUCTION.lower()
        assert "greedy" in lower and ("dp" in lower or "dynamic programming" in lower)


# --------------------------------------------------------------------------- #
#  validate_and_fix_pattern
# --------------------------------------------------------------------------- #

class TestValidateAndFixPattern:

    @pytest.mark.asyncio
    async def test_valid_pattern_passes_unchanged(self):
        from agents import validate_and_fix_pattern
        text = make_classifier_response("Dynamic Programming")
        mock_llm = AsyncMock()
        result, was_corrected, original, corrected = await validate_and_fix_pattern(
            text, "some problem", mock_llm
        )
        assert was_corrected is False
        assert original == "Dynamic Programming"

    @pytest.mark.asyncio
    async def test_qualifier_stripped_and_canonicalized(self):
        from agents import validate_and_fix_pattern
        text = make_classifier_response("Dynamic Programming (2D DP)")
        mock_llm = AsyncMock()
        result, was_corrected, original, corrected = await validate_and_fix_pattern(
            text, "some problem", mock_llm
        )
        # Should pass (valid after stripping qualifier) but original name had qualifier
        assert was_corrected is False
        assert "Dynamic Programming" in result
        # Qualifier should be cleaned from the output
        assert "(2D DP)" not in result

    @pytest.mark.asyncio
    async def test_invalid_pattern_triggers_reclassification(self):
        from agents import validate_and_fix_pattern
        text = make_classifier_response("Quantum Sort")
        mock_llm = AsyncMock()
        mock_llm.generate_str.return_value = make_classifier_response("Dynamic Programming")
        result, was_corrected, original, corrected = await validate_and_fix_pattern(
            text, "some problem", mock_llm
        )
        assert was_corrected is True
        assert original == "Quantum Sort"
        mock_llm.generate_str.assert_called_once()

    @pytest.mark.asyncio
    async def test_all_valid_patterns_pass_without_reclassification(self):
        from agents import validate_and_fix_pattern
        from patterns import PATTERNS
        mock_llm = AsyncMock()
        mock_llm.generate_str.return_value = make_classifier_response("Dynamic Programming")
        for p in PATTERNS:
            text = make_classifier_response(p["name"])
            _, was_corrected, _, _ = await validate_and_fix_pattern(
                text, "problem", mock_llm
            )
            assert was_corrected is False, f"'{p['name']}' incorrectly flagged as invalid"
        # Verify the reclassify LLM was never called for any valid pattern
        mock_llm.generate_str.assert_not_called()


# --------------------------------------------------------------------------- #
#  run_classifier_direct — model and self-correction wiring
# --------------------------------------------------------------------------- #

class TestRunClassifierDirect:

    @pytest.mark.asyncio
    async def test_uses_gpt4o_model(self, tmp_path):
        with patch("agents.CORRECTIONS_FILE", tmp_path / "c.json"), \
             patch("agents.FEEDBACK_FILE", tmp_path / "f.json"), \
             patch("agents.FEEDBACK_RULES_FILE", tmp_path / "r.json"), \
             patch("agents.JUDGE_LESSONS_FILE", tmp_path / "j.json"), \
             patch("agents.get_pattern_knowledge_for_classifier", return_value=""):

            from agents import run_classifier_direct

            mock_client = AsyncMock()
            mock_client.chat.completions.create.return_value = make_openai_response(
                make_classifier_response("Dynamic Programming")
            )

            mock_critic = AsyncMock()
            mock_critic.generate_str.return_value = make_critic_response(score=5)

            agents = {"classifier_critic_llm": mock_critic}

            with patch("agents.AsyncOpenAI", return_value=mock_client):
                result, log = await run_classifier_direct("problem text", agents)

            call_kwargs = mock_client.chat.completions.create.call_args.kwargs
            assert call_kwargs["model"] == "gpt-4o"

    @pytest.mark.asyncio
    async def test_uses_temperature_zero(self, tmp_path):
        with patch("agents.CORRECTIONS_FILE", tmp_path / "c.json"), \
             patch("agents.FEEDBACK_FILE", tmp_path / "f.json"), \
             patch("agents.FEEDBACK_RULES_FILE", tmp_path / "r.json"), \
             patch("agents.JUDGE_LESSONS_FILE", tmp_path / "j.json"), \
             patch("agents.get_pattern_knowledge_for_classifier", return_value=""):

            from agents import run_classifier_direct

            mock_client = AsyncMock()
            mock_client.chat.completions.create.return_value = make_openai_response(
                make_classifier_response("Dynamic Programming")
            )
            mock_critic = AsyncMock()
            mock_critic.generate_str.return_value = make_critic_response(score=5)

            with patch("agents.AsyncOpenAI", return_value=mock_client):
                await run_classifier_direct("problem text", {"classifier_critic_llm": mock_critic})

            call_kwargs = mock_client.chat.completions.create.call_args.kwargs
            assert call_kwargs["temperature"] == 0

    @pytest.mark.asyncio
    async def test_no_retry_when_critic_scores_high(self, tmp_path):
        with patch("agents.CORRECTIONS_FILE", tmp_path / "c.json"), \
             patch("agents.FEEDBACK_FILE", tmp_path / "f.json"), \
             patch("agents.FEEDBACK_RULES_FILE", tmp_path / "r.json"), \
             patch("agents.JUDGE_LESSONS_FILE", tmp_path / "j.json"), \
             patch("agents.get_pattern_knowledge_for_classifier", return_value=""):

            from agents import run_classifier_direct

            mock_client = AsyncMock()
            mock_client.chat.completions.create.return_value = make_openai_response(
                make_classifier_response("Dynamic Programming")
            )
            mock_critic = AsyncMock()
            mock_critic.generate_str.return_value = make_critic_response(score=5)

            with patch("agents.AsyncOpenAI", return_value=mock_client):
                result, log = await run_classifier_direct("problem", {"classifier_critic_llm": mock_critic})

            # Only 1 attempt logged when score is high
            assert len(log) == 1
            assert mock_client.chat.completions.create.call_count == 1

    @pytest.mark.asyncio
    async def test_retries_when_critic_scores_low(self, tmp_path):
        with patch("agents.CORRECTIONS_FILE", tmp_path / "c.json"), \
             patch("agents.FEEDBACK_FILE", tmp_path / "f.json"), \
             patch("agents.FEEDBACK_RULES_FILE", tmp_path / "r.json"), \
             patch("agents.JUDGE_LESSONS_FILE", tmp_path / "j.json"), \
             patch("agents.get_pattern_knowledge_for_classifier", return_value=""):

            from agents import run_classifier_direct

            mock_client = AsyncMock()
            mock_client.chat.completions.create.return_value = make_openai_response(
                make_classifier_response("Dynamic Programming")
            )
            mock_critic = AsyncMock()
            # First critique low, second high
            mock_critic.generate_str.side_effect = [
                make_critic_response(score=2, issues="wrong pattern", suggestion="use DP"),
                make_critic_response(score=5),
            ]

            with patch("agents.AsyncOpenAI", return_value=mock_client):
                result, log = await run_classifier_direct("problem", {"classifier_critic_llm": mock_critic})

            assert len(log) == 2
            assert mock_client.chat.completions.create.call_count == 2

    @pytest.mark.asyncio
    async def test_correction_saved_when_critic_scores_low(self, tmp_path):
        c_file = tmp_path / "c.json"
        with patch("agents.CORRECTIONS_FILE", c_file), \
             patch("agents.FEEDBACK_FILE", tmp_path / "f.json"), \
             patch("agents.FEEDBACK_RULES_FILE", tmp_path / "r.json"), \
             patch("agents.JUDGE_LESSONS_FILE", tmp_path / "j.json"), \
             patch("agents.get_pattern_knowledge_for_classifier", return_value=""):

            from agents import run_classifier_direct

            mock_client = AsyncMock()
            mock_client.chat.completions.create.return_value = make_openai_response(
                make_classifier_response("Dynamic Programming")
            )
            mock_critic = AsyncMock()
            mock_critic.generate_str.side_effect = [
                make_critic_response(score=2, suggestion="use DP not Sliding Window"),
                make_critic_response(score=4),
            ]

            with patch("agents.AsyncOpenAI", return_value=mock_client):
                await run_classifier_direct("problem", {"classifier_critic_llm": mock_critic})

            assert c_file.exists()
            data = json.loads(c_file.read_text())
            assert len(data.get("classifier", [])) >= 1
