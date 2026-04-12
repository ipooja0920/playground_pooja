"""
Tests for the feedback / memory store in agents.py.

All file I/O is redirected to tmp_path — no real files are touched.
No LLM calls.
"""
import json
import pytest
from pathlib import Path
from unittest.mock import patch


# --------------------------------------------------------------------------- #
#  Helpers — patch the file paths inside agents module
# --------------------------------------------------------------------------- #

def _patch_files(corrections=None, feedback=None, rules=None, judge=None):
    """Context manager that redirects all 4 store paths to tmp files."""
    patches = []
    if corrections:
        patches.append(patch("agents.CORRECTIONS_FILE", corrections))
    if feedback:
        patches.append(patch("agents.FEEDBACK_FILE", feedback))
    if rules:
        patches.append(patch("agents.FEEDBACK_RULES_FILE", rules))
    if judge:
        patches.append(patch("agents.JUDGE_LESSONS_FILE", judge))
    return patches


import contextlib

@contextlib.contextmanager
def patched_files(tmp_path):
    c = tmp_path / "corrections.json"
    f = tmp_path / "feedback.json"
    r = tmp_path / "feedback_rules.json"
    j = tmp_path / "judge_lessons.json"
    with (
        patch("agents.CORRECTIONS_FILE", c),
        patch("agents.FEEDBACK_FILE", f),
        patch("agents.FEEDBACK_RULES_FILE", r),
        patch("agents.JUDGE_LESSONS_FILE", j),
    ):
        yield {"corrections": c, "feedback": f, "rules": r, "judge": j}


# --------------------------------------------------------------------------- #
#  Corrections store
# --------------------------------------------------------------------------- #

class TestCorrectionsStore:

    def test_save_and_load_correction(self, tmp_path):
        with patched_files(tmp_path):
            from agents import save_correction, load_corrections
            save_correction("classifier", "wrong pattern", "use DP not Sliding Window")
            data = load_corrections()
            assert len(data["classifier"]) == 1
            assert data["classifier"][0]["suggestion"] == "use DP not Sliding Window"

    def test_corrections_capped_at_5(self, tmp_path):
        with patched_files(tmp_path):
            from agents import save_correction, load_corrections
            for i in range(7):
                save_correction("classifier", f"issue {i}", f"fix {i}")
            data = load_corrections()
            assert len(data["classifier"]) == 5

    def test_corrections_include_timestamp(self, tmp_path):
        with patched_files(tmp_path):
            from agents import save_correction, load_corrections
            save_correction("solution", "issue", "fix")
            data = load_corrections()
            assert "timestamp" in data["solution"][0]

    def test_get_lessons_empty_when_no_file(self, tmp_path):
        with patched_files(tmp_path):
            from agents import get_lessons
            result = get_lessons("classifier")
            assert result == ""

    def test_get_lessons_returns_formatted_block(self, tmp_path):
        with patched_files(tmp_path):
            from agents import save_correction, get_lessons
            save_correction("classifier", "bad pattern", "always check for DP first")
            result = get_lessons("classifier")
            assert "always check for DP first" in result
            assert "Lessons from past mistakes" in result

    def test_get_lessons_returns_max_3(self, tmp_path):
        with patched_files(tmp_path):
            from agents import save_correction, get_lessons
            for i in range(5):
                save_correction("classifier", f"issue {i}", f"fix {i}")
            result = get_lessons("classifier")
            assert result.count("fix") <= 3


# --------------------------------------------------------------------------- #
#  Feedback + rules store
# --------------------------------------------------------------------------- #

class TestFeedbackStore:

    def test_save_positive_feedback(self, tmp_path):
        with patched_files(tmp_path) as files:
            from agents import save_feedback
            save_feedback("solution", "positive", "loved the analogy", "great toy box")
            data = json.loads(files["feedback"].read_text())
            assert len(data["solution"]["positive"]) == 1
            assert data["solution"]["positive"][0]["comment"] == "great toy box"

    def test_save_negative_feedback(self, tmp_path):
        with patched_files(tmp_path) as files:
            from agents import save_feedback
            save_feedback("classifier", "negative", "wrong pattern", "this is DP")
            data = json.loads(files["feedback"].read_text())
            assert len(data["classifier"]["negative"]) == 1

    def test_feedback_capped_at_5_per_sentiment(self, tmp_path):
        with patched_files(tmp_path) as files:
            from agents import save_feedback
            for i in range(7):
                save_feedback("solution", "positive", f"snippet {i}", f"comment {i}")
            data = json.loads(files["feedback"].read_text())
            assert len(data["solution"]["positive"]) == 5

    def test_save_feedback_rule_positive(self, tmp_path):
        with patched_files(tmp_path) as files:
            from agents import save_feedback_rule
            save_feedback_rule("solution", "positive", "use toy box analogies")
            data = json.loads(files["rules"].read_text())
            assert any("Do:" in r and "toy box" in r for r in data["solution"])

    def test_save_feedback_rule_negative(self, tmp_path):
        with patched_files(tmp_path) as files:
            from agents import save_feedback_rule
            save_feedback_rule("classifier", "negative", "wrong pattern")
            data = json.loads(files["rules"].read_text())
            assert any("Avoid:" in r for r in data["classifier"])

    def test_feedback_rule_deduplication(self, tmp_path):
        with patched_files(tmp_path) as files:
            from agents import save_feedback_rule
            save_feedback_rule("solution", "positive", "use analogies")
            save_feedback_rule("solution", "positive", "use analogies")
            data = json.loads(files["rules"].read_text())
            matching = [r for r in data["solution"] if "use analogies" in r]
            assert len(matching) == 1

    def test_feedback_rules_capped_at_5(self, tmp_path):
        with patched_files(tmp_path) as files:
            from agents import save_feedback_rule
            for i in range(7):
                save_feedback_rule("solution", "positive", f"rule number {i}")
            data = json.loads(files["rules"].read_text())
            assert len(data["solution"]) == 5

    def test_get_feedback_rules_empty_when_no_file(self, tmp_path):
        with patched_files(tmp_path):
            from agents import get_feedback_rules
            result = get_feedback_rules("solution")
            assert result == ""

    def test_get_feedback_rules_returns_formatted_block(self, tmp_path):
        with patched_files(tmp_path):
            from agents import save_feedback_rule, get_feedback_rules
            save_feedback_rule("solution", "positive", "use toy box analogies")
            result = get_feedback_rules("solution")
            assert "toy box" in result
            assert "Behavior rules" in result

    def test_get_feedback_context_empty_when_no_file(self, tmp_path):
        with patched_files(tmp_path):
            from agents import get_feedback_context
            result = get_feedback_context("solution")
            assert result == ""


# --------------------------------------------------------------------------- #
#  Judge lessons store
# --------------------------------------------------------------------------- #

class TestJudgeLessonsStore:

    def test_get_judge_lessons_empty_when_no_file(self, tmp_path):
        with patched_files(tmp_path):
            from agents import get_judge_lessons
            result = get_judge_lessons("solution")
            assert result == ""

    def test_get_judge_lessons_returns_formatted_block(self, tmp_path):
        with patched_files(tmp_path) as files:
            from agents import get_judge_lessons
            files["judge"].write_text(json.dumps({
                "solution": ["[Judge on 'Two Sum'] Beginner Friendliness scored 2/5 — use simpler words"]
            }))
            result = get_judge_lessons("solution")
            assert "Beginner Friendliness" in result
            assert "Evaluation feedback" in result

    def test_get_judge_lessons_returns_max_3(self, tmp_path):
        with patched_files(tmp_path) as files:
            from agents import get_judge_lessons
            files["judge"].write_text(json.dumps({
                "solution": [f"lesson {i}" for i in range(5)]
            }))
            result = get_judge_lessons("solution")
            # Only last 3 should appear
            assert "lesson 4" in result
            assert "lesson 0" not in result


# --------------------------------------------------------------------------- #
#  _compose_instruction stacks all layers
# --------------------------------------------------------------------------- #

class TestComposeInstruction:

    def test_compose_includes_base(self, tmp_path):
        with patched_files(tmp_path):
            from agents import _compose_instruction
            result = _compose_instruction("BASE_INSTRUCTION_TEXT", "solution")
            assert "BASE_INSTRUCTION_TEXT" in result

    def test_compose_includes_lessons_when_present(self, tmp_path):
        with patched_files(tmp_path):
            from agents import save_correction, _compose_instruction
            save_correction("solution", "issue", "always use toy box analogy")
            result = _compose_instruction("base", "solution")
            assert "toy box analogy" in result

    def test_compose_includes_judge_lessons_when_present(self, tmp_path):
        with patched_files(tmp_path) as files:
            from agents import _compose_instruction
            files["judge"].write_text(json.dumps({
                "solution": ["judge lesson about clarity"]
            }))
            result = _compose_instruction("base", "solution")
            assert "judge lesson about clarity" in result

    def test_compose_includes_feedback_rules_when_present(self, tmp_path):
        with patched_files(tmp_path):
            from agents import save_feedback_rule, _compose_instruction
            save_feedback_rule("solution", "positive", "keep sentences short")
            result = _compose_instruction("base", "solution")
            assert "keep sentences short" in result

    def test_compose_classifier_includes_pattern_knowledge(self, tmp_path):
        with patched_files(tmp_path):
            with patch("agents.get_pattern_knowledge_for_classifier",
                       return_value="\n\n**Pattern research lessons:**\n- DP: two strings = 2D DP"):
                from agents import _compose_instruction
                result = _compose_instruction("base", "classifier")
                assert "two strings = 2D DP" in result

    def test_compose_non_classifier_excludes_pattern_knowledge(self, tmp_path):
        with patched_files(tmp_path):
            with patch("agents.get_pattern_knowledge_for_classifier",
                       return_value="\n\n**Pattern research lessons:**\n- should not appear"):
                from agents import _compose_instruction
                result = _compose_instruction("base", "solution")
                assert "should not appear" not in result
