"""
Tests for evaluation.py — LLM Judge, judge lessons routing, and eval history.

RAGAS calls are mocked. Judge calls are mocked via AsyncOpenAI patch.
"""
import json
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from helpers import make_openai_response


def _judge_response(scores: dict) -> str:
    lines = []
    for key, val in scores.items():
        lines.append(f"{key.upper()}: {val}")
    return "\n".join(lines)


DEFAULT_JUDGE_SCORES = {
    "BEGINNER_FRIENDLINESS": 4,
    "PATTERN_ACCURACY": 5,
    "SOLUTION_CORRECTNESS": 4,
    "EXPLANATION_QUALITY": 3,
    "COMPLEXITY_ACCURACY": 4,
    "QUIZ_QUALITY": 5,
    "OVERALL": 4,
    "SUMMARY": "Clarify the explanation walkthrough step by step.",
}


class TestLLMJudge:

    @pytest.mark.asyncio
    async def test_judge_parses_all_6_dimensions(self):
        from evaluation import run_llm_judge_evaluation
        mock_client = AsyncMock()
        mock_client.chat.completions.create.return_value = make_openai_response(
            _judge_response(DEFAULT_JUDGE_SCORES)
        )
        with patch("evaluation.AsyncOpenAI", return_value=mock_client):
            result = await run_llm_judge_evaluation("problem", "pattern", "solution", "complexity")

        assert result["beginner_friendliness"] == 4
        assert result["pattern_accuracy"] == 5
        assert result["solution_correctness"] == 4
        assert result["explanation_quality"] == 3
        assert result["complexity_accuracy"] == 4
        assert result["quiz_quality"] == 5
        assert result["overall"] == 4

    @pytest.mark.asyncio
    async def test_judge_parses_summary(self):
        from evaluation import run_llm_judge_evaluation
        mock_client = AsyncMock()
        mock_client.chat.completions.create.return_value = make_openai_response(
            _judge_response(DEFAULT_JUDGE_SCORES)
        )
        with patch("evaluation.AsyncOpenAI", return_value=mock_client):
            result = await run_llm_judge_evaluation("problem", "pattern", "solution", "complexity")

        assert "Clarify" in result["summary"]

    @pytest.mark.asyncio
    async def test_judge_returns_error_when_no_api_key(self, monkeypatch):
        from evaluation import run_llm_judge_evaluation
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        result = await run_llm_judge_evaluation("problem", "pattern", "solution", "complexity")
        assert result.get("error") is not None

    @pytest.mark.asyncio
    async def test_judge_error_on_api_failure(self):
        from evaluation import run_llm_judge_evaluation
        mock_client = AsyncMock()
        mock_client.chat.completions.create.side_effect = Exception("rate limit")
        with patch("evaluation.AsyncOpenAI", return_value=mock_client):
            result = await run_llm_judge_evaluation("problem", "pattern", "solution", "complexity")
        assert result.get("error") is not None

    @pytest.mark.asyncio
    async def test_judge_uses_gpt4o_mini(self):
        from evaluation import run_llm_judge_evaluation
        mock_client = AsyncMock()
        mock_client.chat.completions.create.return_value = make_openai_response(
            _judge_response(DEFAULT_JUDGE_SCORES)
        )
        with patch("evaluation.AsyncOpenAI", return_value=mock_client):
            await run_llm_judge_evaluation("problem", "pattern", "solution", "complexity")

        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["model"] == "gpt-4o-mini"


class TestJudgeLessonsRouting:

    def test_low_score_routes_to_correct_agent(self, tmp_path):
        from evaluation import save_judge_lessons
        with patch("evaluation.JUDGE_LESSONS_FILE", tmp_path / "j.json"):
            added = save_judge_lessons({
                "beginner_friendliness": 2,
                "pattern_accuracy": 5,
                "solution_correctness": 5,
                "explanation_quality": 5,
                "complexity_accuracy": 5,
                "quiz_quality": 5,
                "overall": 3,
                "summary": "use simpler words",
                "error": None,
            }, "Test Problem")
        assert "solution" in added
        assert "classifier" not in added

    def test_pattern_accuracy_low_routes_to_classifier(self, tmp_path):
        from evaluation import save_judge_lessons
        with patch("evaluation.JUDGE_LESSONS_FILE", tmp_path / "j.json"):
            added = save_judge_lessons({
                "beginner_friendliness": 5,
                "pattern_accuracy": 2,
                "solution_correctness": 5,
                "explanation_quality": 5,
                "complexity_accuracy": 5,
                "quiz_quality": 5,
                "overall": 4,
                "summary": "wrong pattern identified",
                "error": None,
            }, "Interleaving String")
        assert "classifier" in added

    def test_complexity_accuracy_low_routes_to_complexity(self, tmp_path):
        from evaluation import save_judge_lessons
        with patch("evaluation.JUDGE_LESSONS_FILE", tmp_path / "j.json"):
            added = save_judge_lessons({
                "beginner_friendliness": 5,
                "pattern_accuracy": 5,
                "solution_correctness": 5,
                "explanation_quality": 5,
                "complexity_accuracy": 2,
                "quiz_quality": 2,
                "overall": 3,
                "summary": "complexity explanation wrong",
                "error": None,
            }, "Test")
        assert "complexity" in added

    def test_high_scores_produce_no_lessons(self, tmp_path):
        from evaluation import save_judge_lessons
        with patch("evaluation.JUDGE_LESSONS_FILE", tmp_path / "j.json"):
            added = save_judge_lessons({
                "beginner_friendliness": 4,
                "pattern_accuracy": 4,
                "solution_correctness": 5,
                "explanation_quality": 4,
                "complexity_accuracy": 5,
                "quiz_quality": 4,
                "overall": 4,
                "summary": "great output",
                "error": None,
            }, "Test")
        assert added == {}

    def test_lessons_capped_at_5_per_agent(self, tmp_path):
        from evaluation import save_judge_lessons
        j_file = tmp_path / "j.json"
        with patch("evaluation.JUDGE_LESSONS_FILE", j_file):
            for i in range(7):
                save_judge_lessons({
                    "beginner_friendliness": 2,
                    "pattern_accuracy": 5,
                    "solution_correctness": 5,
                    "explanation_quality": 5,
                    "complexity_accuracy": 5,
                    "quiz_quality": 5,
                    "overall": 2,
                    "summary": f"issue {i}",
                    "error": None,
                }, f"Problem {i}")
            data = json.loads(j_file.read_text())
        assert len(data.get("solution", [])) <= 5

    def test_error_result_writes_nothing(self, tmp_path):
        from evaluation import save_judge_lessons
        j_file = tmp_path / "j.json"
        with patch("evaluation.JUDGE_LESSONS_FILE", j_file):
            added = save_judge_lessons({"error": "API failed"}, "Test")
        assert added == {}
        assert not j_file.exists()


class TestEvalHistory:

    def test_save_eval_result_creates_file(self, tmp_path):
        from evaluation import save_eval_result
        with patch("evaluation.EVAL_HISTORY_FILE", tmp_path / "eval_history.json"):
            save_eval_result({"timestamp": "2026-01-01", "problem_title": "Test"})
            assert (tmp_path / "eval_history.json").exists()

    def test_save_eval_result_appends(self, tmp_path):
        from evaluation import save_eval_result, load_eval_history
        h_file = tmp_path / "eval_history.json"
        with patch("evaluation.EVAL_HISTORY_FILE", h_file):
            save_eval_result({"problem_title": "A"})
            save_eval_result({"problem_title": "B"})
            history = load_eval_history()
        assert len(history) == 2

    def test_eval_history_capped_at_50(self, tmp_path):
        from evaluation import save_eval_result, load_eval_history
        h_file = tmp_path / "eval_history.json"
        with patch("evaluation.EVAL_HISTORY_FILE", h_file):
            for i in range(55):
                save_eval_result({"problem_title": f"Problem {i}"})
            history = load_eval_history()
        assert len(history) == 50

    def test_load_eval_history_returns_empty_when_no_file(self, tmp_path):
        from evaluation import load_eval_history
        with patch("evaluation.EVAL_HISTORY_FILE", tmp_path / "nonexistent.json"):
            history = load_eval_history()
        assert history == []
