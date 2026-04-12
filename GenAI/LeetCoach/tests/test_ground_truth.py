"""
Tests for ground_truth.py — pattern accuracy checking and URL normalization.
No LLM calls.
"""
import pytest
from ground_truth import check_pattern_accuracy, GROUND_TRUTH


class TestGroundTruthDataset:

    def test_dataset_is_non_empty(self):
        assert len(GROUND_TRUTH) > 0

    def test_all_entries_have_required_fields(self):
        for url, data in GROUND_TRUTH.items():
            assert "title" in data, f"{url} missing title"
            assert "accepted_patterns" in data, f"{url} missing accepted_patterns"
            assert "number" in data, f"{url} missing number"

    def test_all_accepted_patterns_are_lists(self):
        for url, data in GROUND_TRUTH.items():
            assert isinstance(data["accepted_patterns"], list)
            assert len(data["accepted_patterns"]) >= 1

    def test_all_urls_are_leetcode(self):
        for url in GROUND_TRUTH:
            assert "leetcode.com/problems/" in url

    def test_covers_at_least_10_different_patterns(self):
        all_patterns = set()
        for data in GROUND_TRUTH.values():
            all_patterns.update(data["accepted_patterns"])
        assert len(all_patterns) >= 10


class TestCheckPatternAccuracy:

    def test_known_url_exact_match_correct(self):
        result = check_pattern_accuracy(
            "Dynamic Programming",
            "https://leetcode.com/problems/climbing-stairs/"
        )
        assert result["in_ground_truth"] is True
        assert result["is_correct"] is True

    def test_known_url_exact_match_wrong_pattern(self):
        result = check_pattern_accuracy(
            "Sliding Window",
            "https://leetcode.com/problems/climbing-stairs/"
        )
        assert result["in_ground_truth"] is True
        assert result["is_correct"] is False

    def test_unknown_url_returns_not_in_ground_truth(self):
        result = check_pattern_accuracy(
            "Dynamic Programming",
            "https://leetcode.com/problems/some-made-up-problem/"
        )
        assert result["in_ground_truth"] is False
        assert result["is_correct"] is None

    def test_url_trailing_slash_normalized(self):
        """URL with and without trailing slash should both hit the same entry."""
        result_with = check_pattern_accuracy(
            "Dynamic Programming",
            "https://leetcode.com/problems/climbing-stairs/"
        )
        result_without = check_pattern_accuracy(
            "Dynamic Programming",
            "https://leetcode.com/problems/climbing-stairs"
        )
        assert result_with["in_ground_truth"] == result_without["in_ground_truth"]
        assert result_with["is_correct"] == result_without["is_correct"]

    def test_url_query_params_stripped(self):
        result = check_pattern_accuracy(
            "Dynamic Programming",
            "https://leetcode.com/problems/climbing-stairs/?lang=python"
        )
        assert result["in_ground_truth"] is True

    def test_slug_fuzzy_match(self):
        """Matching by slug alone should work even if scheme differs."""
        result = check_pattern_accuracy(
            "Dynamic Programming",
            "https://leetcode.com/problems/climbing-stairs"
        )
        assert result["in_ground_truth"] is True

    def test_case_insensitive_pattern_match(self):
        result = check_pattern_accuracy(
            "dynamic programming",
            "https://leetcode.com/problems/climbing-stairs/"
        )
        assert result["is_correct"] is True

    def test_partial_pattern_match(self):
        """'Dynamic Programming (2D DP)' should still match 'Dynamic Programming'."""
        result = check_pattern_accuracy(
            "Dynamic Programming (2D DP)",
            "https://leetcode.com/problems/climbing-stairs/"
        )
        assert result["is_correct"] is True

    def test_multi_accepted_pattern_either_is_correct(self):
        """Problems with multiple accepted patterns accept any of them."""
        # Number of Islands accepts BFS or DFS or Union Find
        result_bfs = check_pattern_accuracy(
            "BFS (Breadth-First Search)",
            "https://leetcode.com/problems/number-of-islands/"
        )
        result_dfs = check_pattern_accuracy(
            "DFS (Depth-First Search)",
            "https://leetcode.com/problems/number-of-islands/"
        )
        assert result_bfs["is_correct"] is True
        assert result_dfs["is_correct"] is True

    def test_result_includes_identified_pattern(self):
        result = check_pattern_accuracy(
            "Two Pointers",
            "https://leetcode.com/problems/two-sum-ii-input-array-is-sorted/"
        )
        assert result["identified"] == "Two Pointers"

    def test_result_includes_accepted_patterns_list(self):
        result = check_pattern_accuracy(
            "Two Pointers",
            "https://leetcode.com/problems/two-sum-ii-input-array-is-sorted/"
        )
        assert isinstance(result["accepted_patterns"], list)
        assert len(result["accepted_patterns"]) >= 1

    def test_unknown_url_returns_empty_accepted_patterns(self):
        result = check_pattern_accuracy(
            "Whatever",
            "https://leetcode.com/problems/nonexistent-problem/"
        )
        assert result["accepted_patterns"] == []
