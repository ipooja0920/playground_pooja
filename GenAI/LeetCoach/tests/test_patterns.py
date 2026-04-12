"""
Tests for patterns.py and the pattern menu/validator built in agents.py.

No LLM calls — pure data validation.
"""
import pytest
from patterns import PATTERNS
from agents import _VALID_PATTERN_NAMES, _PATTERN_MENU


REQUIRED_PATTERN_FIELDS = {"id", "name", "description", "when_to_use", "template", "examples"}
REQUIRED_EXAMPLE_FIELDS = {"name", "url"}
REQUIRED_SUB_PATTERN_FIELDS = {"name", "signal", "example"}


class TestPatternLibraryStructure:

    def test_exactly_21_patterns(self):
        assert len(PATTERNS) == 21

    def test_all_required_fields_present(self):
        for p in PATTERNS:
            missing = REQUIRED_PATTERN_FIELDS - p.keys()
            assert not missing, f"Pattern '{p.get('name')}' missing fields: {missing}"

    def test_no_duplicate_ids(self):
        ids = [p["id"] for p in PATTERNS]
        assert len(ids) == len(set(ids)), "Duplicate pattern IDs found"

    def test_no_duplicate_names(self):
        names = [p["name"] for p in PATTERNS]
        assert len(names) == len(set(names)), "Duplicate pattern names found"

    def test_ids_are_sequential_1_to_21(self):
        ids = sorted(p["id"] for p in PATTERNS)
        assert ids == list(range(1, 22))

    def test_all_names_are_non_empty_strings(self):
        for p in PATTERNS:
            assert isinstance(p["name"], str) and p["name"].strip()

    def test_all_descriptions_are_non_empty(self):
        for p in PATTERNS:
            assert isinstance(p["description"], str) and len(p["description"]) > 10

    def test_when_to_use_is_non_empty_list(self):
        for p in PATTERNS:
            assert isinstance(p["when_to_use"], list) and len(p["when_to_use"]) >= 1

    def test_template_is_non_empty_string(self):
        for p in PATTERNS:
            assert isinstance(p["template"], str) and len(p["template"]) > 5

    def test_examples_have_required_fields(self):
        for p in PATTERNS:
            for ex in p["examples"]:
                missing = REQUIRED_EXAMPLE_FIELDS - ex.keys()
                assert not missing, f"Pattern '{p['name']}' example missing fields: {missing}"

    def test_example_urls_are_leetcode(self):
        for p in PATTERNS:
            for ex in p["examples"]:
                assert "leetcode.com/problems/" in ex["url"], (
                    f"Pattern '{p['name']}' example URL doesn't look like LeetCode: {ex['url']}"
                )

    def test_each_pattern_has_at_least_2_examples(self):
        for p in PATTERNS:
            assert len(p["examples"]) >= 2, f"Pattern '{p['name']}' has fewer than 2 examples"


class TestSubPatterns:

    def test_sub_patterns_are_list_when_present(self):
        for p in PATTERNS:
            if "sub_patterns" in p:
                assert isinstance(p["sub_patterns"], list)

    def test_sub_pattern_fields_are_complete(self):
        for p in PATTERNS:
            for sp in p.get("sub_patterns", []):
                missing = REQUIRED_SUB_PATTERN_FIELDS - sp.keys()
                assert not missing, (
                    f"Pattern '{p['name']}' sub-pattern '{sp.get('name')}' missing: {missing}"
                )

    def test_sub_pattern_names_are_non_empty(self):
        for p in PATTERNS:
            for sp in p.get("sub_patterns", []):
                assert sp["name"].strip(), f"Empty sub-pattern name in '{p['name']}'"

    def test_high_priority_patterns_have_sub_patterns(self):
        """BFS, DFS, Backtracking, Dynamic Programming must all have sub_patterns."""
        names_with_sub = {p["name"] for p in PATTERNS if p.get("sub_patterns")}
        for required in ["BFS (Breadth-First Search)", "DFS (Depth-First Search)",
                         "Backtracking", "Dynamic Programming"]:
            assert required in names_with_sub, f"'{required}' missing sub_patterns"

    def test_dp_has_2d_grid_sub_pattern(self):
        """Dynamic Programming must have a 2D/Grid DP sub-pattern (the Interleaving String fix)."""
        dp = next(p for p in PATTERNS if p["name"] == "Dynamic Programming")
        sub_names = [sp["name"] for sp in dp.get("sub_patterns", [])]
        assert any("2D" in n or "Grid" in n for n in sub_names), (
            "Dynamic Programming missing 2D/Grid DP sub-pattern"
        )

    def test_greedy_has_two_pass_sub_pattern(self):
        """Greedy must have a Two-Pass sub-pattern (the Candy fix)."""
        greedy = next(p for p in PATTERNS if p["name"] == "Greedy")
        sub_names = [sp["name"] for sp in greedy.get("sub_patterns", [])]
        assert any("Two-Pass" in n or "Two Pass" in n for n in sub_names), (
            "Greedy missing Two-Pass sub-pattern"
        )


class TestNotSignals:

    def test_bfs_has_not_signal_for_counting(self):
        bfs = next(p for p in PATTERNS if p["name"] == "BFS (Breadth-First Search)")
        signals = " ".join(bfs["when_to_use"]).lower()
        assert "not" in signals and ("dp" in signals or "count" in signals)

    def test_dfs_has_not_signal_for_shortest_path(self):
        dfs = next(p for p in PATTERNS if p["name"] == "DFS (Depth-First Search)")
        signals = " ".join(dfs["when_to_use"]).lower()
        assert "not" in signals

    def test_backtracking_has_not_signal_for_counting(self):
        bt = next(p for p in PATTERNS if p["name"] == "Backtracking")
        signals = " ".join(bt["when_to_use"]).lower()
        assert "not" in signals

    def test_dp_has_not_signal_for_generating_all(self):
        dp = next(p for p in PATTERNS if p["name"] == "Dynamic Programming")
        signals = " ".join(dp["when_to_use"]).lower()
        assert "not" in signals

    def test_dp_has_not_signal_for_greedy(self):
        """DP must warn against using DP when Greedy suffices."""
        dp = next(p for p in PATTERNS if p["name"] == "Dynamic Programming")
        signals = " ".join(dp["when_to_use"]).lower()
        assert "greedy" in signals

    def test_greedy_has_not_signal_for_dp(self):
        """Greedy must warn against using Greedy when overlapping subproblems need DP."""
        greedy = next(p for p in PATTERNS if p["name"] == "Greedy")
        signals = " ".join(greedy["when_to_use"]).lower()
        assert "not" in signals and "dp" in signals


class TestValidPatternNames:

    def test_valid_names_set_has_21_entries(self):
        assert len(_VALID_PATTERN_NAMES) == 21

    def test_all_pattern_names_in_valid_set(self):
        for p in PATTERNS:
            assert p["name"].lower() in _VALID_PATTERN_NAMES

    def test_pattern_menu_contains_all_names(self):
        for p in PATTERNS:
            assert p["name"] in _PATTERN_MENU

    def test_pattern_menu_contains_when_to_use_signals(self):
        """Menu should inject signals so classifier has context to pick correctly."""
        for p in PATTERNS:
            # At least one signal should appear somewhere in the menu
            assert any(sig[:20] in _PATTERN_MENU for sig in p["when_to_use"])

    def test_known_valid_pattern_accepted(self):
        assert "dynamic programming" in _VALID_PATTERN_NAMES

    def test_greedy_is_valid_pattern(self):
        assert "greedy" in _VALID_PATTERN_NAMES

    def test_made_up_pattern_not_in_valid_set(self):
        assert "quantum sort" not in _VALID_PATTERN_NAMES
