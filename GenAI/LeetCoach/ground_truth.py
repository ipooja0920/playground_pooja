"""
Ground truth dataset — 25 well-known LeetCode problems with correct patterns.
Used for Phase 2 pattern accuracy evaluation.

Pattern names must match the names in patterns.py.
Multiple accepted patterns are listed where a problem can be solved with more than one approach.
"""

GROUND_TRUTH = {
    # Two Pointers
    "https://leetcode.com/problems/two-sum-ii-input-array-is-sorted/": {
        "title": "Two Sum II - Input Array Is Sorted", "number": 167,
        "accepted_patterns": ["Two Pointers"], "difficulty": "Medium",
    },
    "https://leetcode.com/problems/3sum/": {
        "title": "3Sum", "number": 15,
        "accepted_patterns": ["Two Pointers"], "difficulty": "Medium",
    },
    "https://leetcode.com/problems/container-with-most-water/": {
        "title": "Container With Most Water", "number": 11,
        "accepted_patterns": ["Two Pointers"], "difficulty": "Medium",
    },
    "https://leetcode.com/problems/valid-palindrome/": {
        "title": "Valid Palindrome", "number": 125,
        "accepted_patterns": ["Two Pointers"], "difficulty": "Easy",
    },

    # Sliding Window
    "https://leetcode.com/problems/longest-substring-without-repeating-characters/": {
        "title": "Longest Substring Without Repeating Characters", "number": 3,
        "accepted_patterns": ["Sliding Window"], "difficulty": "Medium",
    },
    "https://leetcode.com/problems/minimum-window-substring/": {
        "title": "Minimum Window Substring", "number": 76,
        "accepted_patterns": ["Sliding Window"], "difficulty": "Hard",
    },
    "https://leetcode.com/problems/permutation-in-string/": {
        "title": "Permutation in String", "number": 567,
        "accepted_patterns": ["Sliding Window"], "difficulty": "Medium",
    },

    # Binary Search
    "https://leetcode.com/problems/binary-search/": {
        "title": "Binary Search", "number": 704,
        "accepted_patterns": ["Binary Search"], "difficulty": "Easy",
    },
    "https://leetcode.com/problems/search-in-rotated-sorted-array/": {
        "title": "Search in Rotated Sorted Array", "number": 33,
        "accepted_patterns": ["Binary Search"], "difficulty": "Medium",
    },
    "https://leetcode.com/problems/koko-eating-bananas/": {
        "title": "Koko Eating Bananas", "number": 875,
        "accepted_patterns": ["Binary Search"], "difficulty": "Medium",
    },

    # BFS / DFS
    "https://leetcode.com/problems/number-of-islands/": {
        "title": "Number of Islands", "number": 200,
        "accepted_patterns": ["BFS (Breadth-First Search)", "DFS (Depth-First Search)", "Union Find (Disjoint Set)"],
        "difficulty": "Medium",
    },
    "https://leetcode.com/problems/binary-tree-level-order-traversal/": {
        "title": "Binary Tree Level Order Traversal", "number": 102,
        "accepted_patterns": ["BFS (Breadth-First Search)"], "difficulty": "Medium",
    },
    "https://leetcode.com/problems/rotting-oranges/": {
        "title": "Rotting Oranges", "number": 994,
        "accepted_patterns": ["BFS (Breadth-First Search)"], "difficulty": "Medium",
    },

    # Backtracking
    "https://leetcode.com/problems/permutations/": {
        "title": "Permutations", "number": 46,
        "accepted_patterns": ["Backtracking"], "difficulty": "Medium",
    },
    "https://leetcode.com/problems/combination-sum/": {
        "title": "Combination Sum", "number": 39,
        "accepted_patterns": ["Backtracking", "Subsets / Combinations"], "difficulty": "Medium",
    },
    "https://leetcode.com/problems/subsets/": {
        "title": "Subsets", "number": 78,
        "accepted_patterns": ["Subsets / Combinations", "Backtracking"], "difficulty": "Medium",
    },

    # Dynamic Programming
    "https://leetcode.com/problems/climbing-stairs/": {
        "title": "Climbing Stairs", "number": 70,
        "accepted_patterns": ["Dynamic Programming"], "difficulty": "Easy",
    },
    "https://leetcode.com/problems/coin-change/": {
        "title": "Coin Change", "number": 322,
        "accepted_patterns": ["Dynamic Programming"], "difficulty": "Medium",
    },
    "https://leetcode.com/problems/house-robber/": {
        "title": "House Robber", "number": 198,
        "accepted_patterns": ["Dynamic Programming"], "difficulty": "Medium",
    },
    "https://leetcode.com/problems/longest-common-subsequence/": {
        "title": "Longest Common Subsequence", "number": 1143,
        "accepted_patterns": ["Dynamic Programming"], "difficulty": "Medium",
    },

    # Monotonic Stack
    "https://leetcode.com/problems/daily-temperatures/": {
        "title": "Daily Temperatures", "number": 739,
        "accepted_patterns": ["Monotonic Stack"], "difficulty": "Medium",
    },
    "https://leetcode.com/problems/largest-rectangle-in-histogram/": {
        "title": "Largest Rectangle in Histogram", "number": 84,
        "accepted_patterns": ["Monotonic Stack"], "difficulty": "Hard",
    },

    # Top K Elements
    "https://leetcode.com/problems/kth-largest-element-in-an-array/": {
        "title": "Kth Largest Element in an Array", "number": 215,
        "accepted_patterns": ["Top K Elements"], "difficulty": "Medium",
    },
    "https://leetcode.com/problems/top-k-frequent-elements/": {
        "title": "Top K Frequent Elements", "number": 347,
        "accepted_patterns": ["Top K Elements"], "difficulty": "Medium",
    },

    # Linked List Cycle (Fast & Slow Pointers)
    "https://leetcode.com/problems/linked-list-cycle/": {
        "title": "Linked List Cycle", "number": 141,
        "accepted_patterns": ["Fast & Slow Pointers"], "difficulty": "Easy",
    },
}


def check_pattern_accuracy(identified_pattern: str, problem_url: str) -> dict:
    """
    Check if the identified pattern matches the ground truth for a known problem.

    Returns:
        dict with keys: in_ground_truth, is_correct, identified, accepted_patterns, title
    """
    # Normalize URL (strip trailing slash, query params)
    normalized_url = problem_url.rstrip("/").split("?")[0]
    if not normalized_url.endswith("/"):
        normalized_url += "/"

    # Try exact match first
    entry = GROUND_TRUTH.get(normalized_url)

    # Try without trailing slash
    if not entry:
        entry = GROUND_TRUTH.get(normalized_url.rstrip("/"))

    # Try fuzzy match by URL path
    if not entry:
        for url, data in GROUND_TRUTH.items():
            if any(
                segment in normalized_url
                for segment in url.rstrip("/").split("/")[-2:]
                if len(segment) > 3
            ):
                entry = data
                break

    if not entry:
        return {
            "in_ground_truth": False,
            "is_correct": None,
            "identified": identified_pattern,
            "accepted_patterns": [],
            "title": "Unknown problem",
        }

    # Case-insensitive substring match for flexibility
    identified_lower = identified_pattern.lower()
    is_correct = any(
        accepted.lower() in identified_lower or identified_lower in accepted.lower()
        for accepted in entry["accepted_patterns"]
    )

    return {
        "in_ground_truth": True,
        "is_correct": is_correct,
        "identified": identified_pattern,
        "accepted_patterns": entry["accepted_patterns"],
        "title": entry["title"],
        "difficulty": entry["difficulty"],
    }
