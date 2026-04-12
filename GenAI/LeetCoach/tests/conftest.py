"""
Shared pytest configuration for LeetCoach tests.

- Adds LeetCoach root + tests/ to sys.path so all modules are importable.
- Sets a dummy OPENAI_API_KEY so agents.py can be imported without a real key.
- Configures pytest-asyncio for async test support.
- Provides shared fixtures: tmp file paths, sample data strings.
"""
import os
import sys
import pytest

# Make LeetCoach root and tests/ both importable
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))  # LeetCoach/
sys.path.insert(0, os.path.dirname(__file__))                   # LeetCoach/tests/

os.environ.setdefault("OPENAI_API_KEY", "sk-test-dummy-key-for-unit-tests")


# --------------------------------------------------------------------------- #
#  Fixtures
# --------------------------------------------------------------------------- #

@pytest.fixture
def sample_problem_text():
    return (
        "72. Edit Distance\n\n"
        "Given two strings word1 and word2, return the minimum number of operations "
        "required to convert word1 to word2.\n\n"
        "Example 1:\nInput: word1 = 'horse', word2 = 'ros'\nOutput: 3\n\n"
        "Constraints:\n0 <= word1.length, word2.length <= 500"
    )


@pytest.fixture
def sample_pattern_text():
    from helpers import make_classifier_response
    return make_classifier_response("Dynamic Programming")


@pytest.fixture
def sample_solution_text():
    return (
        "## 🧠 What Are We Trying To Do?\nConvert one word to another.\n\n"
        "## 💡 The Big Idea\nImagine a grid of boxes...\n\n"
        "## 📋 The Rules\n- match → do nothing\n- mismatch → try insert/delete/replace\n\n"
        "## ✅ The Code\n```python\ndef minDistance(word1, word2):\n    m, n = len(word1), len(word2)\n"
        "    dp = [[0]*(n+1) for _ in range(m+1)]\n    return dp[m][n]\n```\n\n"
        "## 🚶 Let's Walk Through It Together\nWe build a table...\n\n"
        "## 🧪 Watch Out For\nEmpty strings. Both empty."
    )


@pytest.fixture
def sample_complexity_text():
    return (
        "## ⏱ Time: O(m×n)\nImagine a grid with m rows and n columns...\n\n"
        "## 💾 Space: O(m×n)\nWe use a full grid as a notepad...\n\n"
        "## ⚡ Quick Take\n- Time: O(m×n) — grid fill\n- Space: O(m×n) — full grid\n\n"
        "## 🧪 Quick Quiz — Test Yourself!\n"
        "**Q1:** Why is time O(m×n)?\n- A) We visit each cell once\n- B) We sort\n- C) We recurse\n"
        "ANSWER: A\nHINT: Every cell computed exactly once.\n\n"
        "**Q2:** Can space be improved?\n- A) No\n- B) Yes, to O(n)\n- C) Yes, to O(1)\n"
        "ANSWER: B\nHINT: Only need current and previous row."
    )
