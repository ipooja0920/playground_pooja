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

    # Fast & Slow Pointers
    "https://leetcode.com/problems/linked-list-cycle/": {
        "title": "Linked List Cycle", "number": 141,
        "accepted_patterns": ["Fast & Slow Pointers"], "difficulty": "Easy",
    },
    "https://leetcode.com/problems/find-the-duplicate-number/": {
        "title": "Find the Duplicate Number", "number": 287,
        "accepted_patterns": ["Fast & Slow Pointers"], "difficulty": "Medium",
    },
    "https://leetcode.com/problems/middle-of-the-linked-list/": {
        "title": "Middle of the Linked List", "number": 876,
        "accepted_patterns": ["Fast & Slow Pointers"], "difficulty": "Easy",
    },

    # Merge Intervals
    "https://leetcode.com/problems/merge-intervals/": {
        "title": "Merge Intervals", "number": 56,
        "accepted_patterns": ["Merge Intervals"], "difficulty": "Medium",
    },
    "https://leetcode.com/problems/insert-interval/": {
        "title": "Insert Interval", "number": 57,
        "accepted_patterns": ["Merge Intervals"], "difficulty": "Medium",
    },
    "https://leetcode.com/problems/non-overlapping-intervals/": {
        "title": "Non-overlapping Intervals", "number": 435,
        "accepted_patterns": ["Merge Intervals"], "difficulty": "Medium",
    },

    # Prefix Sum
    "https://leetcode.com/problems/range-sum-query-immutable/": {
        "title": "Range Sum Query - Immutable", "number": 303,
        "accepted_patterns": ["Prefix Sum"], "difficulty": "Easy",
    },
    "https://leetcode.com/problems/subarray-sum-equals-k/": {
        "title": "Subarray Sum Equals K", "number": 560,
        "accepted_patterns": ["Prefix Sum"], "difficulty": "Medium",
    },
    "https://leetcode.com/problems/product-of-array-except-self/": {
        "title": "Product of Array Except Self", "number": 238,
        "accepted_patterns": ["Prefix Sum"], "difficulty": "Medium",
    },

    # Cyclic Sort
    "https://leetcode.com/problems/missing-number/": {
        "title": "Missing Number", "number": 268,
        "accepted_patterns": ["Cyclic Sort", "Bit Manipulation"], "difficulty": "Easy",
    },
    "https://leetcode.com/problems/find-all-numbers-disappeared-in-an-array/": {
        "title": "Find All Numbers Disappeared in an Array", "number": 448,
        "accepted_patterns": ["Cyclic Sort"], "difficulty": "Easy",
    },
    "https://leetcode.com/problems/find-all-duplicates-in-an-array/": {
        "title": "Find All Duplicates in an Array", "number": 442,
        "accepted_patterns": ["Cyclic Sort"], "difficulty": "Medium",
    },

    # Topological Sort
    "https://leetcode.com/problems/course-schedule/": {
        "title": "Course Schedule", "number": 207,
        "accepted_patterns": ["Topological Sort", "DFS (Depth-First Search)"], "difficulty": "Medium",
    },
    "https://leetcode.com/problems/course-schedule-ii/": {
        "title": "Course Schedule II", "number": 210,
        "accepted_patterns": ["Topological Sort"], "difficulty": "Medium",
    },
    "https://leetcode.com/problems/find-eventual-safe-states/": {
        "title": "Find Eventual Safe States", "number": 802,
        "accepted_patterns": ["Topological Sort", "DFS (Depth-First Search)"], "difficulty": "Medium",
    },

    # Union Find
    "https://leetcode.com/problems/redundant-connection/": {
        "title": "Redundant Connection", "number": 684,
        "accepted_patterns": ["Union Find (Disjoint Set)"], "difficulty": "Medium",
    },
    "https://leetcode.com/problems/accounts-merge/": {
        "title": "Accounts Merge", "number": 721,
        "accepted_patterns": ["Union Find (Disjoint Set)"], "difficulty": "Medium",
    },
    "https://leetcode.com/problems/number-of-provinces/": {
        "title": "Number of Provinces", "number": 547,
        "accepted_patterns": ["Union Find (Disjoint Set)", "DFS (Depth-First Search)"], "difficulty": "Medium",
    },

    # Trie
    "https://leetcode.com/problems/implement-trie-prefix-tree/": {
        "title": "Implement Trie (Prefix Tree)", "number": 208,
        "accepted_patterns": ["Trie (Prefix Tree)"], "difficulty": "Medium",
    },
    "https://leetcode.com/problems/design-add-and-search-words-data-structure/": {
        "title": "Design Add and Search Words Data Structure", "number": 211,
        "accepted_patterns": ["Trie (Prefix Tree)"], "difficulty": "Medium",
    },
    "https://leetcode.com/problems/word-search-ii/": {
        "title": "Word Search II", "number": 212,
        "accepted_patterns": ["Trie (Prefix Tree)", "Backtracking"], "difficulty": "Hard",
    },

    # Two Heaps
    "https://leetcode.com/problems/find-median-from-data-stream/": {
        "title": "Find Median from Data Stream", "number": 295,
        "accepted_patterns": ["Two Heaps"], "difficulty": "Hard",
    },
    "https://leetcode.com/problems/ipo/": {
        "title": "IPO", "number": 502,
        "accepted_patterns": ["Two Heaps", "Top K Elements"], "difficulty": "Hard",
    },

    # Subsets / Combinations
    "https://leetcode.com/problems/subsets-ii/": {
        "title": "Subsets II", "number": 90,
        "accepted_patterns": ["Subsets / Combinations", "Backtracking"], "difficulty": "Medium",
    },
    "https://leetcode.com/problems/palindrome-partitioning/": {
        "title": "Palindrome Partitioning", "number": 131,
        "accepted_patterns": ["Subsets / Combinations", "Backtracking"], "difficulty": "Medium",
    },
    "https://leetcode.com/problems/letter-combinations-of-a-phone-number/": {
        "title": "Letter Combinations of a Phone Number", "number": 17,
        "accepted_patterns": ["Subsets / Combinations", "Backtracking"], "difficulty": "Medium",
    },

    # Bit Manipulation
    "https://leetcode.com/problems/single-number/": {
        "title": "Single Number", "number": 136,
        "accepted_patterns": ["Bit Manipulation"], "difficulty": "Easy",
    },
    "https://leetcode.com/problems/number-of-1-bits/": {
        "title": "Number of 1 Bits", "number": 191,
        "accepted_patterns": ["Bit Manipulation"], "difficulty": "Easy",
    },
    "https://leetcode.com/problems/counting-bits/": {
        "title": "Counting Bits", "number": 338,
        "accepted_patterns": ["Bit Manipulation", "Dynamic Programming"], "difficulty": "Easy",
    },
    "https://leetcode.com/problems/reverse-bits/": {
        "title": "Reverse Bits", "number": 190,
        "accepted_patterns": ["Bit Manipulation"], "difficulty": "Easy",
    },

    # Divide & Conquer
    "https://leetcode.com/problems/maximum-subarray/": {
        "title": "Maximum Subarray", "number": 53,
        "accepted_patterns": ["Divide & Conquer", "Dynamic Programming"], "difficulty": "Medium",
    },
    "https://leetcode.com/problems/sort-an-array/": {
        "title": "Sort an Array", "number": 912,
        "accepted_patterns": ["Divide & Conquer"], "difficulty": "Medium",
    },
    "https://leetcode.com/problems/median-of-two-sorted-arrays/": {
        "title": "Median of Two Sorted Arrays", "number": 4,
        "accepted_patterns": ["Divide & Conquer", "Binary Search"], "difficulty": "Hard",
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
