"""
Tests for pattern_research_agent.py.

All gpt-4o API calls are mocked — no real LLM calls.
"""
import json
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from helpers import make_openai_response


def _research_response(
    correct_pattern="Dynamic Programming",
    sub_pattern="2D / Grid DP",
    why="Two strings being compared — dp[i][j] encodes matching state.",
    signal="Two string inputs + interleaving/matching = 2D DP, NOT Sliding Window",
    classifier_lesson="Never pick Sliding Window when two strings are being interleaved or matched.",
) -> str:
    return json.dumps({
        "correct_pattern": correct_pattern,
        "sub_pattern": sub_pattern,
        "why": why,
        "signal": signal,
        "classifier_lesson": classifier_lesson,
    })


class TestRunPatternResearch:

    @pytest.mark.asyncio
    async def test_returns_correct_pattern_name(self, tmp_path):
        from pattern_research_agent import run_pattern_research
        mock_client = AsyncMock()
        mock_client.chat.completions.create.return_value = make_openai_response(
            _research_response("Dynamic Programming")
        )
        with patch("pattern_research_agent.AsyncOpenAI", return_value=mock_client), \
             patch("pattern_research_agent.PATTERN_KNOWLEDGE_FILE", tmp_path / "pk.json"):
            result = await run_pattern_research("problem text", "Interleaving String", "Sliding Window")

        assert result["correct_pattern"] == "Dynamic Programming"
        assert result["error"] is None

    @pytest.mark.asyncio
    async def test_returns_sub_pattern(self, tmp_path):
        from pattern_research_agent import run_pattern_research
        mock_client = AsyncMock()
        mock_client.chat.completions.create.return_value = make_openai_response(
            _research_response(sub_pattern="2D / Grid DP")
        )
        with patch("pattern_research_agent.AsyncOpenAI", return_value=mock_client), \
             patch("pattern_research_agent.PATTERN_KNOWLEDGE_FILE", tmp_path / "pk.json"):
            result = await run_pattern_research("problem text", "Interleaving String", "Sliding Window")

        assert result["sub_pattern"] == "2D / Grid DP"

    @pytest.mark.asyncio
    async def test_lesson_saved_to_knowledge_file(self, tmp_path):
        pk_file = tmp_path / "pk.json"
        from pattern_research_agent import run_pattern_research
        mock_client = AsyncMock()
        mock_client.chat.completions.create.return_value = make_openai_response(
            _research_response()
        )
        with patch("pattern_research_agent.AsyncOpenAI", return_value=mock_client), \
             patch("pattern_research_agent.PATTERN_KNOWLEDGE_FILE", pk_file):
            result = await run_pattern_research("problem text", "Interleaving String", "Sliding Window")

        assert result["lesson_saved"] is True
        assert pk_file.exists()
        data = json.loads(pk_file.read_text())
        assert "Dynamic Programming" in data
        assert len(data["Dynamic Programming"]) == 1

    @pytest.mark.asyncio
    async def test_deduplication_by_problem_title(self, tmp_path):
        pk_file = tmp_path / "pk.json"
        from pattern_research_agent import run_pattern_research
        mock_client = AsyncMock()
        mock_client.chat.completions.create.return_value = make_openai_response(
            _research_response()
        )
        with patch("pattern_research_agent.AsyncOpenAI", return_value=mock_client), \
             patch("pattern_research_agent.PATTERN_KNOWLEDGE_FILE", pk_file):
            # Save same problem twice
            await run_pattern_research("problem text", "Interleaving String", "Sliding Window")
            await run_pattern_research("problem text", "Interleaving String", "Backtracking")

        data = json.loads(pk_file.read_text())
        # Should still only have 1 entry for Interleaving String
        assert len(data["Dynamic Programming"]) == 1

    @pytest.mark.asyncio
    async def test_invalid_pattern_triggers_case_insensitive_correction(self, tmp_path):
        from pattern_research_agent import run_pattern_research
        mock_client = AsyncMock()
        # Return lowercase version — should be corrected to canonical name
        mock_client.chat.completions.create.return_value = make_openai_response(
            _research_response(correct_pattern="dynamic programming")
        )
        with patch("pattern_research_agent.AsyncOpenAI", return_value=mock_client), \
             patch("pattern_research_agent.PATTERN_KNOWLEDGE_FILE", tmp_path / "pk.json"):
            result = await run_pattern_research("problem text", "Interleaving String", "Sliding Window")

        assert result["correct_pattern"] == "Dynamic Programming"  # canonicalized

    @pytest.mark.asyncio
    async def test_unknown_pattern_triggers_discovery(self, tmp_path):
        """Unknown patterns auto-trigger discovery — not an error."""
        import patterns as patterns_module
        from pattern_research_agent import run_pattern_research
        mock_client = AsyncMock()
        # Call 1: research returns unknown pattern name
        # Call 2: _discover_and_save_new_pattern generates full definition
        mock_client.chat.completions.create.side_effect = [
            make_openai_response(_research_response(correct_pattern="Quantum Sort Algorithm")),
            make_openai_response(json.dumps({
                "name": "Quantum Sort Algorithm",
                "description": "A fictional pattern for testing.",
                "when_to_use": ["signal 1", "NOT something else"],
                "template": "pass",
                "examples": [
                    {"name": "Two Sum (#1)", "url": "https://leetcode.com/problems/two-sum/"},
                    {"name": "Reverse String (#344)", "url": "https://leetcode.com/problems/reverse-string/"},
                ],
            })),
        ]
        original_patterns = list(patterns_module.PATTERNS)
        try:
            with patch("pattern_research_agent.AsyncOpenAI", return_value=mock_client), \
                 patch("pattern_research_agent.PATTERN_KNOWLEDGE_FILE", tmp_path / "pk.json"), \
                 patch("pattern_research_agent.CUSTOM_PATTERNS_FILE", tmp_path / "custom.json"):
                result = await run_pattern_research("problem text", "Interleaving String", "Sliding Window")
        finally:
            # Restore PATTERNS so test-added entries don't pollute other tests
            patterns_module.PATTERNS[:] = original_patterns

        assert result.get("error") is None
        assert result.get("pattern_discovered") is True
        assert result["correct_pattern"] == "Quantum Sort Algorithm"
        assert (tmp_path / "custom.json").exists()

    @pytest.mark.asyncio
    async def test_unknown_pattern_discovery_failure_returns_error(self, tmp_path):
        """If both research and discovery fail, return an error."""
        import patterns as patterns_module
        from pattern_research_agent import run_pattern_research
        mock_client = AsyncMock()
        # Call 1: research returns unknown pattern
        # Call 2: discovery API fails
        mock_client.chat.completions.create.side_effect = [
            make_openai_response(_research_response(correct_pattern="Quantum Sort Algorithm")),
            Exception("API down"),
        ]
        original_patterns = list(patterns_module.PATTERNS)
        try:
            with patch("pattern_research_agent.AsyncOpenAI", return_value=mock_client), \
                 patch("pattern_research_agent.PATTERN_KNOWLEDGE_FILE", tmp_path / "pk.json"), \
                 patch("pattern_research_agent.CUSTOM_PATTERNS_FILE", tmp_path / "custom.json"):
                result = await run_pattern_research("problem text", "Interleaving String", "Sliding Window")
        finally:
            patterns_module.PATTERNS[:] = original_patterns

        assert result.get("error") is not None
        assert result.get("lesson_saved") is False

    @pytest.mark.asyncio
    async def test_api_failure_returns_error(self, tmp_path):
        from pattern_research_agent import run_pattern_research
        mock_client = AsyncMock()
        mock_client.chat.completions.create.side_effect = Exception("rate limit")
        with patch("pattern_research_agent.AsyncOpenAI", return_value=mock_client), \
             patch("pattern_research_agent.PATTERN_KNOWLEDGE_FILE", tmp_path / "pk.json"):
            result = await run_pattern_research("problem text", "Title", "wrong")

        assert result.get("error") is not None
        assert result["lesson_saved"] is False

    @pytest.mark.asyncio
    async def test_entry_includes_all_required_fields(self, tmp_path):
        pk_file = tmp_path / "pk.json"
        from pattern_research_agent import run_pattern_research
        mock_client = AsyncMock()
        mock_client.chat.completions.create.return_value = make_openai_response(
            _research_response()
        )
        with patch("pattern_research_agent.AsyncOpenAI", return_value=mock_client), \
             patch("pattern_research_agent.PATTERN_KNOWLEDGE_FILE", pk_file):
            await run_pattern_research("problem text", "Interleaving String", "Sliding Window")

        data = json.loads(pk_file.read_text())
        entry = data["Dynamic Programming"][0]
        for field in ["problem", "sub_pattern", "why", "signal", "classifier_lesson", "wrong_pattern", "timestamp"]:
            assert field in entry, f"Missing field '{field}' in saved entry"

    @pytest.mark.asyncio
    async def test_knowledge_capped_at_10_per_pattern(self, tmp_path):
        pk_file = tmp_path / "pk.json"
        from pattern_research_agent import run_pattern_research
        mock_client = AsyncMock()

        with patch("pattern_research_agent.AsyncOpenAI", return_value=mock_client), \
             patch("pattern_research_agent.PATTERN_KNOWLEDGE_FILE", pk_file):
            for i in range(13):
                mock_client.chat.completions.create.return_value = make_openai_response(
                    _research_response()
                )
                await run_pattern_research("problem text", f"Problem {i}", "Sliding Window")

        data = json.loads(pk_file.read_text())
        assert len(data.get("Dynamic Programming", [])) <= 10


class TestGetPatternKnowledge:

    def test_returns_empty_when_file_missing(self, tmp_path):
        from pattern_research_agent import get_pattern_knowledge_for_classifier
        with patch("pattern_research_agent.PATTERN_KNOWLEDGE_FILE", tmp_path / "nonexistent.json"):
            result = get_pattern_knowledge_for_classifier()
        assert result == ""

    def test_returns_formatted_block_when_knowledge_exists(self, tmp_path):
        pk_file = tmp_path / "pk.json"
        pk_file.write_text(json.dumps({
            "Dynamic Programming": [{
                "problem": "Interleaving String",
                "sub_pattern": "2D / Grid DP",
                "signal": "two strings = 2D DP",
                "classifier_lesson": "never pick Sliding Window for two-string problems",
                "why": "dp[i][j] encodes matching state",
                "wrong_pattern": "Sliding Window",
                "timestamp": "2026-04-12T00:00:00",
            }]
        }))
        from pattern_research_agent import get_pattern_knowledge_for_classifier
        with patch("pattern_research_agent.PATTERN_KNOWLEDGE_FILE", pk_file):
            result = get_pattern_knowledge_for_classifier()

        assert "Dynamic Programming" in result
        assert "Pattern research lessons" in result
        assert "two strings = 2D DP" in result

    def test_returns_at_most_6_pattern_entries(self, tmp_path):
        pk_file = tmp_path / "pk.json"
        # Create 8 patterns with knowledge
        from patterns import PATTERNS
        data = {}
        for p in PATTERNS[:8]:
            data[p["name"]] = [{
                "problem": "test", "sub_pattern": "x",
                "signal": f"signal for {p['name']}",
                "classifier_lesson": "lesson", "why": "why",
                "wrong_pattern": "wrong", "timestamp": "2026-01-01",
            }]
        pk_file.write_text(json.dumps(data))

        from pattern_research_agent import get_pattern_knowledge_for_classifier
        with patch("pattern_research_agent.PATTERN_KNOWLEDGE_FILE", pk_file):
            result = get_pattern_knowledge_for_classifier()

        # Count how many pattern names appear
        from patterns import PATTERNS as ALL
        count = sum(1 for p in ALL[:8] if p["name"] in result)
        assert count <= 6
