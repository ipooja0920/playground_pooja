"""Shared helper functions for LeetCoach tests — importable by all test files."""
from unittest.mock import MagicMock


def make_openai_response(content: str):
    """Build a minimal mock that looks like an openai ChatCompletion response."""
    r = MagicMock()
    r.choices[0].message.content = content
    return r


def make_critic_response(score: int = 5, issues: str = "none", suggestion: str = "looks good") -> str:
    return f"SCORE: {score}\nISSUES: {issues}\nSUGGESTION: {suggestion}"


def make_classifier_response(pattern: str = "Dynamic Programming") -> str:
    return (
        f"## 🎯 Pattern\n{pattern}\n\n"
        "## Why This Pattern?\nBecause the problem has overlapping subproblems.\n\n"
        "## The Key Trick\nThe trick is to store results so we don't recompute.\n\n"
        "## Difficulty\nMedium"
    )
