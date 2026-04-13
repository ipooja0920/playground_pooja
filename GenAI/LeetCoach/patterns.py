PATTERNS = [
    # ------------------------------------------------------------------ #
    #  1. Prefix Sums
    # ------------------------------------------------------------------ #
    {
        "id": 1,
        "name": "Prefix Sums",
        "description": "Precompute a running total so any subarray sum can be answered in O(1). The key insight: sum(i, j) = prefix[j+1] - prefix[i].",
        "when_to_use": [
            "Range sum queries: 'sum of elements from index i to j'",
            "Subarray with a target sum (pair prefix[j] - prefix[i] == target → use a hash map)",
            "Count subarrays meeting a condition (sum, XOR, product)",
            "2D grid range sum queries",
            "NOT when the array is modified frequently — use a Segment Tree instead",
        ],
        "sub_patterns": [
            {
                "name": "1D Prefix Sum",
                "signal": "Range sum on a flat array; prefix[i] = prefix[i-1] + arr[i-1]",
                "example": "Range Sum Query (#303)",
            },
            {
                "name": "Prefix Sum + Hash Map",
                "signal": "Count subarrays with sum == k; store prefix sum frequencies",
                "example": "Subarray Sum Equals K (#560)",
            },
            {
                "name": "2D Prefix Sum",
                "signal": "Rectangle sum in a matrix; prefix[r][c] built from four neighbors",
                "example": "Range Sum Query 2D (#304)",
            },
        ],
        "template": """\
# 1D prefix sum
n = len(nums)
prefix = [0] * (n + 1)
for i in range(n):
    prefix[i + 1] = prefix[i] + nums[i]

# sum of nums[l..r] (inclusive)
def range_sum(l, r):
    return prefix[r + 1] - prefix[l]

# --- Prefix sum + hash map (count subarrays with sum == k) ---
from collections import defaultdict
count = 0
running = 0
freq = defaultdict(int)
freq[0] = 1
for num in nums:
    running += num
    count += freq[running - k]
    freq[running] += 1""",
        "examples": [
            {"name": "Range Sum Query - Immutable (#303)", "url": "https://leetcode.com/problems/range-sum-query-immutable/"},
            {"name": "Subarray Sum Equals K (#560)", "url": "https://leetcode.com/problems/subarray-sum-equals-k/"},
            {"name": "Product of Array Except Self (#238)", "url": "https://leetcode.com/problems/product-of-array-except-self/"},
            {"name": "Find Pivot Index (#724)", "url": "https://leetcode.com/problems/find-pivot-index/"},
        ],
    },

    # ------------------------------------------------------------------ #
    #  2. Sliding Window
    # ------------------------------------------------------------------ #
    {
        "id": 2,
        "name": "Sliding Window",
        "description": "Maintain a window (subarray or substring) that expands and contracts as you move through the array. Avoids recomputing the whole window on each step — O(n) instead of O(n²).",
        "when_to_use": [
            "Longest/shortest contiguous subarray or substring satisfying a condition",
            "Maximum/minimum sum of a subarray of fixed size k",
            "'At most k distinct elements', 'no repeating characters', 'contains all characters of t'",
            "NOT for non-contiguous subsequences — use DP instead",
            "NOT when order of elements doesn't matter — use a hash map instead",
        ],
        "sub_patterns": [
            {
                "name": "Fixed-Size Window",
                "signal": "Window size k is given; slide one step at a time",
                "example": "Maximum Average Subarray I (#643)",
            },
            {
                "name": "Variable-Size Window",
                "signal": "Expand right, shrink left when window violates condition",
                "example": "Longest Substring Without Repeating Characters (#3)",
            },
        ],
        "template": """\
left = 0
window = {}   # or a counter, sum, etc.
result = 0

for right in range(len(s)):
    # expand: add s[right] to window
    window[s[right]] = window.get(s[right], 0) + 1

    # shrink: while window is invalid, move left
    while len(window) > k:
        window[s[left]] -= 1
        if window[s[left]] == 0:
            del window[s[left]]
        left += 1

    result = max(result, right - left + 1)
return result""",
        "examples": [
            {"name": "Longest Substring Without Repeating Characters (#3)", "url": "https://leetcode.com/problems/longest-substring-without-repeating-characters/"},
            {"name": "Minimum Window Substring (#76)", "url": "https://leetcode.com/problems/minimum-window-substring/"},
            {"name": "Longest Repeating Character Replacement (#424)", "url": "https://leetcode.com/problems/longest-repeating-character-replacement/"},
            {"name": "Maximum Average Subarray I (#643)", "url": "https://leetcode.com/problems/maximum-average-subarray-i/"},
        ],
    },

    # ------------------------------------------------------------------ #
    #  3. Stacks and Queues
    # ------------------------------------------------------------------ #
    {
        "id": 3,
        "name": "Stacks and Queues",
        "description": "Use a stack (LIFO) to track 'what came before' or match pairs, and a queue (FIFO) to process items in arrival order. Stacks excel at bracket matching, undo operations, and DFS; queues excel at BFS and scheduling.",
        "when_to_use": [
            "Matching open/close pairs: parentheses, brackets, HTML tags",
            "Tracking the 'previous state' to undo or compare (stack)",
            "Processing items level by level or in arrival order (queue)",
            "Implementing recursive algorithms iteratively (stack replaces call stack)",
            "Daily Temperatures style: 'next greater element' problems",
            "NOT when random access is needed — use an array or deque",
        ],
        "sub_patterns": [
            {
                "name": "Bracket Matching Stack",
                "signal": "Push open brackets, pop and verify on close brackets",
                "example": "Valid Parentheses (#20)",
            },
            {
                "name": "Min/Max Stack",
                "signal": "Augment stack with a parallel min/max tracker",
                "example": "Min Stack (#155)",
            },
            {
                "name": "Queue with Two Stacks",
                "signal": "Simulate FIFO with two LIFO stacks",
                "example": "Implement Queue using Stacks (#232)",
            },
        ],
        "template": """\
# --- Stack: bracket matching ---
stack = []
pairs = {')': '(', '}': '{', ']': '['}
for ch in s:
    if ch in '({[':
        stack.append(ch)
    elif not stack or stack[-1] != pairs[ch]:
        return False
    else:
        stack.pop()
return len(stack) == 0

# --- Min Stack ---
class MinStack:
    def __init__(self):
        self.stack = []      # (value, current_min)
    def push(self, val):
        min_val = min(val, self.stack[-1][1] if self.stack else val)
        self.stack.append((val, min_val))
    def pop(self):   self.stack.pop()
    def top(self):   return self.stack[-1][0]
    def getMin(self): return self.stack[-1][1]""",
        "examples": [
            {"name": "Valid Parentheses (#20)", "url": "https://leetcode.com/problems/valid-parentheses/"},
            {"name": "Min Stack (#155)", "url": "https://leetcode.com/problems/min-stack/"},
            {"name": "Implement Queue using Stacks (#232)", "url": "https://leetcode.com/problems/implement-queue-using-stacks/"},
            {"name": "Daily Temperatures (#739)", "url": "https://leetcode.com/problems/daily-temperatures/"},
        ],
    },

    # ------------------------------------------------------------------ #
    #  4. Fast and Slow Pointers
    # ------------------------------------------------------------------ #
    {
        "id": 4,
        "name": "Fast and Slow Pointers",
        "description": "Use two pointers moving at different speeds through a sequence. The slow pointer moves one step at a time; the fast pointer moves two. If they ever meet, there's a cycle. If not, the slow pointer ends up at the middle.",
        "when_to_use": [
            "Detecting a cycle in a linked list or sequence",
            "Finding the middle of a linked list in one pass",
            "Finding the start of a cycle",
            "Detecting a 'happy number' (cycle in digit-sum sequence)",
            "NOT for arrays that support random access — use index math instead",
        ],
        "template": """\
slow, fast = head, head
# detect cycle
while fast and fast.next:
    slow = slow.next
    fast = fast.next.next
    if slow == fast:
        return True   # cycle detected
return False

# --- find middle ---
slow, fast = head, head
while fast and fast.next:
    slow = slow.next
    fast = fast.next.next
# slow is now at the middle""",
        "examples": [
            {"name": "Linked List Cycle (#141)", "url": "https://leetcode.com/problems/linked-list-cycle/"},
            {"name": "Find the Duplicate Number (#287)", "url": "https://leetcode.com/problems/find-the-duplicate-number/"},
            {"name": "Happy Number (#202)", "url": "https://leetcode.com/problems/happy-number/"},
            {"name": "Middle of the Linked List (#876)", "url": "https://leetcode.com/problems/middle-of-the-linked-list/"},
        ],
    },

    # ------------------------------------------------------------------ #
    #  5. Top K Frequent Elements
    # ------------------------------------------------------------------ #
    {
        "id": 5,
        "name": "Top K Frequent Elements",
        "description": "Use a min-heap of size k to track the k largest/most-frequent items in O(n log k). Alternatively, bucket sort achieves O(n) when frequencies are bounded.",
        "when_to_use": [
            "Find the k largest, smallest, or most frequent elements",
            "Streaming data where you can't sort everything",
            "K closest points to origin",
            "NOT when k == n (just sort the whole array)",
            "NOT when you need the exact kth element efficiently — use QuickSelect instead",
        ],
        "sub_patterns": [
            {
                "name": "Min-Heap of Size K",
                "signal": "Push each element; pop when heap exceeds k; remaining elements are top-k",
                "example": "Top K Frequent Elements (#347)",
            },
            {
                "name": "Bucket Sort by Frequency",
                "signal": "Frequency can't exceed n; put elements in frequency buckets, scan from end",
                "example": "Top K Frequent Elements (#347) — O(n) solution",
            },
        ],
        "template": """\
import heapq
from collections import Counter

# min-heap approach: O(n log k)
freq = Counter(nums)
heap = []
for num, count in freq.items():
    heapq.heappush(heap, (count, num))
    if len(heap) > k:
        heapq.heappop(heap)
return [num for count, num in heap]

# --- bucket sort approach: O(n) ---
freq = Counter(nums)
buckets = [[] for _ in range(len(nums) + 1)]
for num, count in freq.items():
    buckets[count].append(num)
result = []
for i in range(len(buckets) - 1, 0, -1):
    result.extend(buckets[i])
    if len(result) >= k:
        break
return result[:k]""",
        "examples": [
            {"name": "Top K Frequent Elements (#347)", "url": "https://leetcode.com/problems/top-k-frequent-elements/"},
            {"name": "K Closest Points to Origin (#973)", "url": "https://leetcode.com/problems/k-closest-points-to-origin/"},
            {"name": "Sort Characters By Frequency (#451)", "url": "https://leetcode.com/problems/sort-characters-by-frequency/"},
            {"name": "Kth Largest Element in a Stream (#703)", "url": "https://leetcode.com/problems/kth-largest-element-in-a-stream/"},
        ],
    },

    # ------------------------------------------------------------------ #
    #  6. Binary Search (and Variants)
    # ------------------------------------------------------------------ #
    {
        "id": 6,
        "name": "Binary Search (and Variants)",
        "description": "Repeatedly halve the search space by comparing the midpoint to the target. Works on any monotone condition — not just sorted arrays. O(log n) per search.",
        "when_to_use": [
            "Array is sorted (or implicitly sorted / monotone)",
            "'Find the minimum X such that condition(X) is true' — binary search on the answer",
            "Rotated sorted array (modified binary search)",
            "Find first/last occurrence of a value",
            "NOT on unsorted data where sorting cost would outweigh the benefit",
        ],
        "sub_patterns": [
            {
                "name": "Classic Binary Search",
                "signal": "Sorted array, find exact target",
                "example": "Binary Search (#704)",
            },
            {
                "name": "Binary Search on Answer",
                "signal": "'Minimum/maximum X such that a condition holds' — search the answer space",
                "example": "Koko Eating Bananas (#875), Capacity To Ship Packages (#1011)",
            },
            {
                "name": "Rotated Array Search",
                "signal": "One half is always sorted; decide which half target falls in",
                "example": "Search in Rotated Sorted Array (#33)",
            },
            {
                "name": "Left/Right Boundary",
                "signal": "Find first or last occurrence; bias mid toward one side",
                "example": "Find First and Last Position (#34)",
            },
        ],
        "template": """\
# Classic binary search
left, right = 0, len(nums) - 1
while left <= right:
    mid = (left + right) // 2
    if nums[mid] == target:
        return mid
    elif nums[mid] < target:
        left = mid + 1
    else:
        right = mid - 1
return -1

# --- Binary search on the answer ---
def condition(x):
    # return True if x is feasible
    ...

left, right = min_possible, max_possible
while left < right:
    mid = (left + right) // 2
    if condition(mid):
        right = mid        # mid might be answer; search left
    else:
        left = mid + 1
return left""",
        "examples": [
            {"name": "Binary Search (#704)", "url": "https://leetcode.com/problems/binary-search/"},
            {"name": "Search in Rotated Sorted Array (#33)", "url": "https://leetcode.com/problems/search-in-rotated-sorted-array/"},
            {"name": "Koko Eating Bananas (#875)", "url": "https://leetcode.com/problems/koko-eating-bananas/"},
            {"name": "Find First and Last Position (#34)", "url": "https://leetcode.com/problems/find-first-and-last-position-of-element-in-sorted-array/"},
        ],
    },

    # ------------------------------------------------------------------ #
    #  7. Graph Traversals (BFS, DFS)
    # ------------------------------------------------------------------ #
    {
        "id": 7,
        "name": "Graph Traversals (BFS, DFS)",
        "description": "BFS explores level by level using a queue — guaranteed shortest path in unweighted graphs. DFS explores as deep as possible using a stack/recursion — ideal for connectivity, cycles, and exhaustive path search.",
        "when_to_use": [
            "BFS: shortest path in unweighted graph, level-order traversal, minimum steps",
            "BFS: spreading problems — infection, water, fire reaching all cells",
            "DFS: connected components, cycle detection, flood fill, topological order",
            "DFS: all paths from source to destination",
            "Both: number of islands, graph coloring, reachability",
            "NOT BFS for counting all paths or number-of-ways — use DP",
            "NOT DFS for guaranteed shortest path — use BFS or Dijkstra",
        ],
        "sub_patterns": [
            {
                "name": "BFS — Shortest Path / Level Order",
                "signal": "Use a deque; track visited; expand layer by layer",
                "example": "Word Ladder (#127), Binary Tree Level Order (#102)",
            },
            {
                "name": "Multi-Source BFS",
                "signal": "Start BFS from multiple sources simultaneously (add all to queue at once)",
                "example": "01 Matrix (#542), Rotting Oranges (#994)",
            },
            {
                "name": "DFS — Connected Components / Flood Fill",
                "signal": "Recursively visit all neighbors; mark visited to avoid revisiting",
                "example": "Number of Islands (#200), Flood Fill (#733)",
            },
            {
                "name": "DFS — Cycle Detection",
                "signal": "Track 'in current path' state (gray/white/black coloring)",
                "example": "Course Schedule (#207), Detect Cycle in Directed Graph",
            },
        ],
        "template": """\
from collections import deque

# --- BFS ---
def bfs(graph, start):
    visited = {start}
    queue = deque([start])
    steps = 0
    while queue:
        for _ in range(len(queue)):   # process level by level
            node = queue.popleft()
            for neighbor in graph[node]:
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)
        steps += 1
    return steps

# --- DFS (iterative) ---
def dfs(graph, start):
    visited = set()
    stack = [start]
    while stack:
        node = stack.pop()
        if node in visited:
            continue
        visited.add(node)
        for neighbor in graph[node]:
            stack.append(neighbor)

# --- DFS (recursive) ---
def dfs_rec(node, visited, graph):
    visited.add(node)
    for neighbor in graph[node]:
        if neighbor not in visited:
            dfs_rec(neighbor, visited, graph)""",
        "examples": [
            {"name": "Number of Islands (#200)", "url": "https://leetcode.com/problems/number-of-islands/"},
            {"name": "Word Ladder (#127)", "url": "https://leetcode.com/problems/word-ladder/"},
            {"name": "Clone Graph (#133)", "url": "https://leetcode.com/problems/clone-graph/"},
            {"name": "Rotting Oranges (#994)", "url": "https://leetcode.com/problems/rotting-oranges/"},
        ],
    },

    # ------------------------------------------------------------------ #
    #  8. Backtracking & Recursive Search
    # ------------------------------------------------------------------ #
    {
        "id": 8,
        "name": "Backtracking & Recursive Search",
        "description": "Explore all possibilities by building candidates incrementally and abandoning ('backtracking') as soon as a candidate can't lead to a valid solution. Used to generate all valid combinations, permutations, or configurations.",
        "when_to_use": [
            "Generate ALL valid combinations, permutations, subsets, or paths",
            "Constraint satisfaction: N-Queens, Sudoku, word search on a grid",
            "Problems with 'find all solutions' or 'list all ways'",
            "NOT when only the COUNT of solutions is needed — use DP instead",
            "NOT when memoization eliminates recomputation — use DFS + memo (top-down DP)",
        ],
        "sub_patterns": [
            {
                "name": "Permutations",
                "signal": "All orderings of elements; swap in-place or use 'used' array",
                "example": "Permutations (#46), Permutations II (#47)",
            },
            {
                "name": "Combinations / Subsets",
                "signal": "Choose k elements from n; use a start index to avoid duplicates",
                "example": "Subsets (#78), Combination Sum (#39)",
            },
            {
                "name": "Grid / Matrix Search",
                "signal": "Try all 4 directions; mark cell visited, recurse, unmark on return",
                "example": "Word Search (#79), N-Queens (#51)",
            },
            {
                "name": "Constraint Satisfaction",
                "signal": "Place one item per row/column/box; check validity before recursing",
                "example": "Sudoku Solver (#37), N-Queens (#51)",
            },
        ],
        "template": """\
def backtrack(start, path, result):
    # base case: valid complete solution
    if len(path) == k:
        result.append(path[:])
        return

    for i in range(start, len(nums)):
        # skip duplicates (if array is sorted)
        if i > start and nums[i] == nums[i - 1]:
            continue

        path.append(nums[i])
        backtrack(i + 1, path, result)   # i+1 = no reuse; i = allow reuse
        path.pop()   # undo the choice (backtrack)

result = []
nums.sort()          # sort to handle duplicates cleanly
backtrack(0, [], result)
return result""",
        "examples": [
            {"name": "Subsets (#78)", "url": "https://leetcode.com/problems/subsets/"},
            {"name": "Permutations (#46)", "url": "https://leetcode.com/problems/permutations/"},
            {"name": "Combination Sum (#39)", "url": "https://leetcode.com/problems/combination-sum/"},
            {"name": "Word Search (#79)", "url": "https://leetcode.com/problems/word-search/"},
        ],
    },

    # ------------------------------------------------------------------ #
    #  9. Path Sum & Root-to-Leaf Techniques
    # ------------------------------------------------------------------ #
    {
        "id": 9,
        "name": "Path Sum & Root-to-Leaf Techniques",
        "description": "Recursively accumulate a value (sum, product, string) along paths from the root to leaves in a tree. Check conditions at leaves or anywhere along the path.",
        "when_to_use": [
            "Does any root-to-leaf path sum to a target?",
            "Find all root-to-leaf paths with a given sum",
            "Build a number from root-to-leaf digits",
            "Maximum/minimum path sum in a binary tree (may go through any node)",
            "NOT for paths between arbitrary nodes — track global max separately",
        ],
        "sub_patterns": [
            {
                "name": "Existence Check",
                "signal": "Subtract node value from target; return True at leaf when remaining == 0",
                "example": "Path Sum (#112)",
            },
            {
                "name": "Collect All Paths",
                "signal": "DFS with a running path list; copy to result at leaf",
                "example": "Path Sum II (#113)",
            },
            {
                "name": "Path as Number",
                "signal": "running = running * 10 + node.val; add to total at leaf",
                "example": "Sum Root to Leaf Numbers (#129)",
            },
            {
                "name": "Max Path Through Any Node",
                "signal": "At each node compute left_gain + right_gain; update global max; return node.val + max(gain)",
                "example": "Binary Tree Maximum Path Sum (#124)",
            },
        ],
        "template": """\
def hasPathSum(root, target):
    if not root:
        return False
    if not root.left and not root.right:   # leaf
        return root.val == target
    return (hasPathSum(root.left,  target - root.val) or
            hasPathSum(root.right, target - root.val))

# --- Collect all paths ---
def pathSum(root, target):
    result = []
    def dfs(node, remaining, path):
        if not node:
            return
        path.append(node.val)
        if not node.left and not node.right and remaining == node.val:
            result.append(path[:])
        dfs(node.left,  remaining - node.val, path)
        dfs(node.right, remaining - node.val, path)
        path.pop()
    dfs(root, target, [])
    return result""",
        "examples": [
            {"name": "Path Sum (#112)", "url": "https://leetcode.com/problems/path-sum/"},
            {"name": "Path Sum II (#113)", "url": "https://leetcode.com/problems/path-sum-ii/"},
            {"name": "Sum Root to Leaf Numbers (#129)", "url": "https://leetcode.com/problems/sum-root-to-leaf-numbers/"},
            {"name": "Binary Tree Maximum Path Sum (#124)", "url": "https://leetcode.com/problems/binary-tree-maximum-path-sum/"},
        ],
    },

    # ------------------------------------------------------------------ #
    #  10. String Manipulation & Regular Expressions
    # ------------------------------------------------------------------ #
    {
        "id": 10,
        "name": "String Manipulation & Regular Expressions",
        "description": "Apply character-level operations, pattern matching, or structural transformations to strings. Covers anagram detection, palindrome checking, encoding, and regex-style matching.",
        "when_to_use": [
            "Anagram / permutation detection (sort or count characters)",
            "Palindrome checking (two pointers from ends, or expand from center)",
            "String encoding / decoding (run-length encoding, base-X)",
            "Wildcard or regex matching ('.' matches any char, '*' means zero or more)",
            "Longest common prefix, word reversal, Roman numerals",
            "NOT for substring search with long patterns — use KMP or Rabin-Karp",
        ],
        "sub_patterns": [
            {
                "name": "Frequency / Anagram",
                "signal": "Count character frequencies; compare or use sliding window over a fixed-size count",
                "example": "Valid Anagram (#242), Group Anagrams (#49)",
            },
            {
                "name": "Two-Pointer Palindrome",
                "signal": "Left and right pointers moving inward; compare characters",
                "example": "Valid Palindrome (#125), Palindromic Substrings (#647)",
            },
            {
                "name": "Expand Around Center",
                "signal": "For each center (n + n-1 centers), expand while chars match",
                "example": "Longest Palindromic Substring (#5)",
            },
            {
                "name": "DP Pattern Matching",
                "signal": "dp[i][j] = does s[:i] match p[:j]; handle '.' and '*' transitions",
                "example": "Regular Expression Matching (#10), Wildcard Matching (#44)",
            },
        ],
        "template": """\
# --- Anagram check ---
from collections import Counter
def is_anagram(s, t):
    return Counter(s) == Counter(t)

# --- Longest palindromic substring (expand around center) ---
def longest_palindrome(s):
    def expand(l, r):
        while l >= 0 and r < len(s) and s[l] == s[r]:
            l -= 1; r += 1
        return s[l+1:r]   # last valid window

    result = ""
    for i in range(len(s)):
        odd  = expand(i, i)       # odd-length palindrome
        even = expand(i, i + 1)   # even-length palindrome
        result = max(result, odd, even, key=len)
    return result""",
        "examples": [
            {"name": "Valid Anagram (#242)", "url": "https://leetcode.com/problems/valid-anagram/"},
            {"name": "Group Anagrams (#49)", "url": "https://leetcode.com/problems/group-anagrams/"},
            {"name": "Longest Palindromic Substring (#5)", "url": "https://leetcode.com/problems/longest-palindromic-substring/"},
            {"name": "Valid Palindrome (#125)", "url": "https://leetcode.com/problems/valid-palindrome/"},
        ],
    },

    # ------------------------------------------------------------------ #
    #  11. Dynamic Programming (Knapsack, Range DP)
    # ------------------------------------------------------------------ #
    {
        "id": 11,
        "name": "Dynamic Programming (Knapsack, Range DP)",
        "description": "Break a problem into overlapping subproblems and store results to avoid recomputation. Two styles: top-down (memoization) and bottom-up (tabulation). Covers 1D, 2D, Knapsack, interval, and string DP.",
        "when_to_use": [
            "Problem asks for maximum/minimum/count of something with overlapping subproblems",
            "Optimal substructure: optimal solution built from optimal sub-solutions",
            "Classic signals: 'number of ways', 'minimum cost', 'longest subsequence', 'can we form X'",
            "Two strings involved and you need matching/alignment — almost always 2D DP",
            "NOT for generating ALL solutions (use Backtracking) — DP only counts or optimizes",
            "NOT when a greedy single/double pass works — use Greedy instead",
        ],
        "sub_patterns": [
            {
                "name": "1D Linear DP",
                "signal": "dp[i] depends only on previous elements; Fibonacci-style",
                "example": "Climbing Stairs (#70), House Robber (#198)",
            },
            {
                "name": "2D / Grid DP",
                "signal": "dp[i][j] — two sequences, or grid path; two string inputs = almost always here",
                "example": "Longest Common Subsequence (#1143), Interleaving String (#97)",
            },
            {
                "name": "Knapsack DP",
                "signal": "Choose items with weight/value constraints; dp[i][w] or 1D rolling",
                "example": "Partition Equal Subset Sum (#416), Coin Change (#322)",
            },
            {
                "name": "Interval / Range DP",
                "signal": "dp[i][j] = answer for subarray [i..j]; fill by increasing length",
                "example": "Burst Balloons (#312), Palindrome Partitioning II (#132)",
            },
            {
                "name": "String DP",
                "signal": "Edit distance, regex, wildcard; transitions based on character match",
                "example": "Edit Distance (#72), Regular Expression Matching (#10)",
            },
        ],
        "template": """\
# --- 1D DP (Coin Change) ---
dp = [float('inf')] * (amount + 1)
dp[0] = 0
for coin in coins:
    for x in range(coin, amount + 1):
        dp[x] = min(dp[x], dp[x - coin] + 1)
return dp[amount] if dp[amount] != float('inf') else -1

# --- 2D DP (Longest Common Subsequence) ---
m, n = len(text1), len(text2)
dp = [[0] * (n + 1) for _ in range(m + 1)]
for i in range(1, m + 1):
    for j in range(1, n + 1):
        if text1[i-1] == text2[j-1]:
            dp[i][j] = dp[i-1][j-1] + 1
        else:
            dp[i][j] = max(dp[i-1][j], dp[i][j-1])
return dp[m][n]""",
        "examples": [
            {"name": "Climbing Stairs (#70)", "url": "https://leetcode.com/problems/climbing-stairs/"},
            {"name": "Coin Change (#322)", "url": "https://leetcode.com/problems/coin-change/"},
            {"name": "Longest Common Subsequence (#1143)", "url": "https://leetcode.com/problems/longest-common-subsequence/"},
            {"name": "Edit Distance (#72)", "url": "https://leetcode.com/problems/edit-distance/"},
        ],
    },

    # ------------------------------------------------------------------ #
    #  12. Kth Largest/Smallest Elements (Heaps / QuickSelect)
    # ------------------------------------------------------------------ #
    {
        "id": 12,
        "name": "Kth Largest/Smallest Elements (Heaps / QuickSelect)",
        "description": "Find the kth largest or smallest element without full sorting. A min-heap of size k runs in O(n log k). QuickSelect (partition-based) averages O(n) but worst-case O(n²).",
        "when_to_use": [
            "Find the exact kth largest or smallest element",
            "Median of a data stream (two heaps: max-heap for lower half, min-heap for upper)",
            "K closest points to a target value or origin",
            "NOT when k is close to n and you can afford to sort — just sort",
            "NOT for top-k frequent elements — use a frequency counter + heap",
        ],
        "sub_patterns": [
            {
                "name": "Min-Heap of Size K",
                "signal": "Maintain a min-heap; push each element, pop when size > k; root = kth largest",
                "example": "Kth Largest Element in an Array (#215)",
            },
            {
                "name": "QuickSelect",
                "signal": "Partition array around pivot; recurse only into the side that contains k",
                "example": "Kth Largest Element in an Array (#215) — O(n) average",
            },
            {
                "name": "Two-Heap Median",
                "signal": "Max-heap (lower half) + min-heap (upper half); balance sizes on each insert",
                "example": "Find Median from Data Stream (#295)",
            },
        ],
        "template": """\
import heapq
import random

# --- Min-heap of size k ---
heap = []
for num in nums:
    heapq.heappush(heap, num)
    if len(heap) > k:
        heapq.heappop(heap)
return heap[0]   # kth largest

# --- QuickSelect ---
def quickselect(nums, k):
    pivot = random.choice(nums)
    left   = [x for x in nums if x > pivot]
    middle = [x for x in nums if x == pivot]
    right  = [x for x in nums if x < pivot]
    if k <= len(left):
        return quickselect(left, k)
    elif k <= len(left) + len(middle):
        return pivot
    else:
        return quickselect(right, k - len(left) - len(middle))""",
        "examples": [
            {"name": "Kth Largest Element in an Array (#215)", "url": "https://leetcode.com/problems/kth-largest-element-in-an-array/"},
            {"name": "Find Median from Data Stream (#295)", "url": "https://leetcode.com/problems/find-median-from-data-stream/"},
            {"name": "K Closest Points to Origin (#973)", "url": "https://leetcode.com/problems/k-closest-points-to-origin/"},
            {"name": "Kth Largest Element in a Stream (#703)", "url": "https://leetcode.com/problems/kth-largest-element-in-a-stream/"},
        ],
    },

    # ------------------------------------------------------------------ #
    #  13. Linked List Techniques (Dummy Node, In-place Reversal)
    # ------------------------------------------------------------------ #
    {
        "id": 13,
        "name": "Linked List Techniques (Dummy Node, In-place Reversal)",
        "description": "Manipulate linked lists using pointer tricks: a dummy head simplifies edge cases, in-place reversal avoids extra space, and two pointers find the nth-from-end in one pass.",
        "when_to_use": [
            "Reverse a linked list or a sublist of it",
            "Remove nth node from end (two pointers with a gap of n)",
            "Merge two sorted linked lists",
            "Detect and find the start of a cycle",
            "Reorder or partition a linked list",
            "NOT when random access is needed — linked lists are O(n) per access",
        ],
        "sub_patterns": [
            {
                "name": "Dummy Head",
                "signal": "Create a dummy node before head to simplify insertions/deletions at the front",
                "example": "Merge Two Sorted Lists (#21), Remove Nth Node (#19)",
            },
            {
                "name": "In-place Reversal",
                "signal": "prev=None, curr=head; iterate: next=curr.next, curr.next=prev, prev=curr, curr=next",
                "example": "Reverse Linked List (#206), Reverse Nodes in k-Group (#25)",
            },
            {
                "name": "Two-Pointer Gap",
                "signal": "Advance fast pointer n steps ahead; then move both until fast hits end",
                "example": "Remove Nth Node From End (#19)",
            },
        ],
        "template": """\
# --- In-place reversal ---
def reverse(head):
    prev, curr = None, head
    while curr:
        nxt = curr.next
        curr.next = prev
        prev = curr
        curr = nxt
    return prev   # new head

# --- Dummy node (merge two sorted lists) ---
dummy = ListNode(0)
tail = dummy
while l1 and l2:
    if l1.val <= l2.val:
        tail.next = l1; l1 = l1.next
    else:
        tail.next = l2; l2 = l2.next
    tail = tail.next
tail.next = l1 or l2
return dummy.next

# --- Remove nth from end ---
dummy = ListNode(0, head)
fast = slow = dummy
for _ in range(n + 1):
    fast = fast.next
while fast:
    fast = fast.next; slow = slow.next
slow.next = slow.next.next
return dummy.next""",
        "examples": [
            {"name": "Reverse Linked List (#206)", "url": "https://leetcode.com/problems/reverse-linked-list/"},
            {"name": "Merge Two Sorted Lists (#21)", "url": "https://leetcode.com/problems/merge-two-sorted-lists/"},
            {"name": "Remove Nth Node From End of List (#19)", "url": "https://leetcode.com/problems/remove-nth-node-from-end-of-list/"},
            {"name": "Reorder List (#143)", "url": "https://leetcode.com/problems/reorder-list/"},
        ],
    },

    # ------------------------------------------------------------------ #
    #  14. Graph Algorithms (DAGs, MSTs, Shortest Paths)
    # ------------------------------------------------------------------ #
    {
        "id": 14,
        "name": "Graph Algorithms (DAGs, MSTs, Shortest Paths)",
        "description": "Advanced graph algorithms beyond simple traversal: Dijkstra for weighted shortest paths, Bellman-Ford for negative weights, Kruskal/Prim for minimum spanning trees, and Topological Sort for dependency ordering on DAGs.",
        "when_to_use": [
            "Shortest path with weighted edges (non-negative) → Dijkstra",
            "Shortest path with negative weights → Bellman-Ford",
            "Minimum cost to connect all nodes → Kruskal (sort edges) or Prim (grow from a node)",
            "Task ordering with prerequisites / detect cycle in directed graph → Topological Sort (Kahn's or DFS)",
            "NOT Dijkstra when edges are unweighted — plain BFS is faster",
        ],
        "sub_patterns": [
            {
                "name": "Dijkstra (Weighted Shortest Path)",
                "signal": "Min-heap of (cost, node); relax neighbors; stop when destination popped",
                "example": "Network Delay Time (#743), Cheapest Flights Within K Stops (#787)",
            },
            {
                "name": "Topological Sort (Kahn's BFS)",
                "signal": "Count in-degrees; push all zero-in-degree nodes to queue; process level by level",
                "example": "Course Schedule (#207), Course Schedule II (#210)",
            },
            {
                "name": "Union-Find / MST (Kruskal)",
                "signal": "Sort edges by weight; add edge if it doesn't create a cycle (use Union-Find)",
                "example": "Min Cost to Connect All Points (#1584)",
            },
            {
                "name": "Bellman-Ford",
                "signal": "Relax all edges V-1 times; detect negative cycle on Vth iteration",
                "example": "Cheapest Flights Within K Stops (#787) — K stops variant",
            },
        ],
        "template": """\
import heapq
from collections import defaultdict, deque

# --- Dijkstra ---
def dijkstra(graph, src, n):
    dist = [float('inf')] * (n + 1)
    dist[src] = 0
    heap = [(0, src)]
    while heap:
        d, u = heapq.heappop(heap)
        if d > dist[u]:
            continue
        for v, w in graph[u]:
            if dist[u] + w < dist[v]:
                dist[v] = dist[u] + w
                heapq.heappush(heap, (dist[v], v))
    return dist

# --- Topological Sort (Kahn's) ---
def topo_sort(n, prerequisites):
    indegree = [0] * n
    adj = defaultdict(list)
    for a, b in prerequisites:
        adj[b].append(a); indegree[a] += 1
    queue = deque(i for i in range(n) if indegree[i] == 0)
    order = []
    while queue:
        node = queue.popleft(); order.append(node)
        for nb in adj[node]:
            indegree[nb] -= 1
            if indegree[nb] == 0: queue.append(nb)
    return order if len(order) == n else []""",
        "examples": [
            {"name": "Course Schedule (#207)", "url": "https://leetcode.com/problems/course-schedule/"},
            {"name": "Course Schedule II (#210)", "url": "https://leetcode.com/problems/course-schedule-ii/"},
            {"name": "Network Delay Time (#743)", "url": "https://leetcode.com/problems/network-delay-time/"},
            {"name": "Min Cost to Connect All Points (#1584)", "url": "https://leetcode.com/problems/min-cost-to-connect-all-points/"},
        ],
    },

    # ------------------------------------------------------------------ #
    #  15. Binary Trees & BSTs (Traversal, Construction)
    # ------------------------------------------------------------------ #
    {
        "id": 15,
        "name": "Binary Trees & BSTs (Traversal, Construction)",
        "description": "Traverse binary trees (preorder/inorder/postorder/level-order) and exploit BST ordering properties. Reconstruct trees from traversal arrays; find LCA; validate BST structure.",
        "when_to_use": [
            "Tree traversal: in-order (sorted for BST), pre-order (copy), post-order (delete/height)",
            "Construct a tree from preorder + inorder (or postorder + inorder)",
            "Lowest Common Ancestor (LCA) of two nodes",
            "Validate BST (track allowed value range as you recurse)",
            "Serialize / deserialize a binary tree",
            "NOT for graphs with cycles — trees are acyclic; use Graph Traversal instead",
        ],
        "sub_patterns": [
            {
                "name": "Recursive DFS Traversal",
                "signal": "Visit left/right recursively; choose pre/in/post order based on what you need",
                "example": "Binary Tree Inorder Traversal (#94)",
            },
            {
                "name": "Level-Order (BFS)",
                "signal": "Use a queue; process all nodes at the same depth before going deeper",
                "example": "Binary Tree Level Order Traversal (#102)",
            },
            {
                "name": "Construct from Traversals",
                "signal": "Preorder[0] = root; find root in inorder to split left/right subtrees",
                "example": "Construct Binary Tree from Preorder and Inorder (#105)",
            },
            {
                "name": "BST Properties",
                "signal": "Inorder of BST is sorted; validate with (min_val, max_val) bounds",
                "example": "Validate Binary Search Tree (#98), Kth Smallest in BST (#230)",
            },
        ],
        "template": """\
# --- Inorder traversal (recursive) ---
def inorder(root):
    if not root:
        return []
    return inorder(root.left) + [root.val] + inorder(root.right)

# --- Level order (BFS) ---
from collections import deque
def level_order(root):
    if not root: return []
    result, queue = [], deque([root])
    while queue:
        level = []
        for _ in range(len(queue)):
            node = queue.popleft()
            level.append(node.val)
            if node.left:  queue.append(node.left)
            if node.right: queue.append(node.right)
        result.append(level)
    return result

# --- Validate BST ---
def is_valid_bst(root, lo=float('-inf'), hi=float('inf')):
    if not root: return True
    if not (lo < root.val < hi): return False
    return (is_valid_bst(root.left, lo, root.val) and
            is_valid_bst(root.right, root.val, hi))""",
        "examples": [
            {"name": "Binary Tree Inorder Traversal (#94)", "url": "https://leetcode.com/problems/binary-tree-inorder-traversal/"},
            {"name": "Binary Tree Level Order Traversal (#102)", "url": "https://leetcode.com/problems/binary-tree-level-order-traversal/"},
            {"name": "Validate Binary Search Tree (#98)", "url": "https://leetcode.com/problems/validate-binary-search-tree/"},
            {"name": "Construct Binary Tree from Preorder and Inorder Traversal (#105)", "url": "https://leetcode.com/problems/construct-binary-tree-from-preorder-and-inorder-traversal/"},
        ],
    },

    # ------------------------------------------------------------------ #
    #  16. Design Problems (LRU Cache, Twitter)
    # ------------------------------------------------------------------ #
    {
        "id": 16,
        "name": "Design Problems (LRU Cache, Twitter)",
        "description": "Combine multiple data structures to support a set of operations efficiently. Key insight: pair a hash map (O(1) lookup) with an ordered structure (doubly linked list or heap) to achieve O(1) or O(log n) for all required operations.",
        "when_to_use": [
            "Design a cache with eviction policy (LRU, LFU)",
            "Design a system supporting multiple operation types (get, put, tweet, follow)",
            "Need O(1) lookup + O(1) insert/delete → HashMap + Doubly Linked List",
            "Need O(1) lookup + ordered retrieval → HashMap + Heap or sorted structure",
            "NOT for simple CRUD — only when the combination of constraints requires cleverness",
        ],
        "sub_patterns": [
            {
                "name": "HashMap + Doubly Linked List (LRU)",
                "signal": "O(1) get and put with recency eviction; map key→node, list tracks order",
                "example": "LRU Cache (#146)",
            },
            {
                "name": "HashMap + Heap (Top-N Feed)",
                "signal": "Store items in heap per user; merge k heaps for news feed",
                "example": "Design Twitter (#355)",
            },
            {
                "name": "Trie-based Design",
                "signal": "Prefix lookups, autocomplete, dictionary; each node is a character",
                "example": "Design Add and Search Words (#211), Implement Trie (#208)",
            },
        ],
        "template": """\
# --- LRU Cache: OrderedDict shortcut ---
from collections import OrderedDict
class LRUCache:
    def __init__(self, capacity):
        self.cap = capacity
        self.cache = OrderedDict()

    def get(self, key):
        if key not in self.cache: return -1
        self.cache.move_to_end(key)
        return self.cache[key]

    def put(self, key, value):
        if key in self.cache:
            self.cache.move_to_end(key)
        self.cache[key] = value
        if len(self.cache) > self.cap:
            self.cache.popitem(last=False)   # evict LRU (front)""",
        "examples": [
            {"name": "LRU Cache (#146)", "url": "https://leetcode.com/problems/lru-cache/"},
            {"name": "Design Twitter (#355)", "url": "https://leetcode.com/problems/design-twitter/"},
            {"name": "Implement Trie (Prefix Tree) (#208)", "url": "https://leetcode.com/problems/implement-trie-prefix-tree/"},
            {"name": "Design Add and Search Words Data Structure (#211)", "url": "https://leetcode.com/problems/design-add-and-search-words-data-structure/"},
        ],
    },

    # ------------------------------------------------------------------ #
    #  17. Expression Evaluation (Two Stacks)
    # ------------------------------------------------------------------ #
    {
        "id": 17,
        "name": "Expression Evaluation (Two Stacks)",
        "description": "Evaluate arithmetic or logical expressions using two stacks: one for operands and one for operators. Handles operator precedence, parentheses, and nested expressions without building an explicit parse tree.",
        "when_to_use": [
            "Evaluate a math expression string: '3 + 2 * 5', '(1 + 2) * 3'",
            "Basic calculator with +, -, *, /, parentheses",
            "Evaluate Reverse Polish Notation (postfix)",
            "Decode nested strings: '3[a2[b]]' → 'ababbababb'",
            "NOT for simple one-operator expressions — just parse directly",
        ],
        "sub_patterns": [
            {
                "name": "Reverse Polish Notation (Postfix)",
                "signal": "Single stack; push numbers, pop two on operator",
                "example": "Evaluate Reverse Polish Notation (#150)",
            },
            {
                "name": "Two-Stack Infix Evaluation",
                "signal": "Operand stack + operator stack; apply higher/equal precedence ops before pushing",
                "example": "Basic Calculator II (#227)",
            },
            {
                "name": "Stack-Based Decode",
                "signal": "Push count/string on '[', pop and repeat on ']'",
                "example": "Decode String (#394)",
            },
        ],
        "template": """\
# --- Evaluate Reverse Polish Notation ---
stack = []
ops = {'+', '-', '*', '/'}
for token in tokens:
    if token not in ops:
        stack.append(int(token))
    else:
        b, a = stack.pop(), stack.pop()
        if token == '+': stack.append(a + b)
        elif token == '-': stack.append(a - b)
        elif token == '*': stack.append(a * b)
        else: stack.append(int(a / b))   # truncate toward zero
return stack[0]

# --- Decode String ---
stack = []
curr_str, curr_num = "", 0
for ch in s:
    if ch.isdigit():
        curr_num = curr_num * 10 + int(ch)
    elif ch == '[':
        stack.append((curr_str, curr_num))
        curr_str, curr_num = "", 0
    elif ch == ']':
        prev_str, num = stack.pop()
        curr_str = prev_str + num * curr_str
    else:
        curr_str += ch
return curr_str""",
        "examples": [
            {"name": "Evaluate Reverse Polish Notation (#150)", "url": "https://leetcode.com/problems/evaluate-reverse-polish-notation/"},
            {"name": "Basic Calculator (#224)", "url": "https://leetcode.com/problems/basic-calculator/"},
            {"name": "Basic Calculator II (#227)", "url": "https://leetcode.com/problems/basic-calculator-ii/"},
            {"name": "Decode String (#394)", "url": "https://leetcode.com/problems/decode-string/"},
        ],
    },

    # ------------------------------------------------------------------ #
    #  18. Hashmaps & Frequency Counting
    # ------------------------------------------------------------------ #
    {
        "id": 18,
        "name": "Hashmaps & Frequency Counting",
        "description": "Use a hash map for O(1) lookup, insertion, and deletion. Frequency counting detects duplicates, anagrams, and majority elements. Complement maps solve pair-sum problems without sorting.",
        "when_to_use": [
            "Two Sum style: store complement in a map, check on each step",
            "Count frequencies: most common element, majority vote, anagram grouping",
            "Longest consecutive sequence without sorting (O(n) with set)",
            "Caching / memoization of intermediate results",
            "NOT when order matters and you need sorted output — use sorted + binary search",
        ],
        "sub_patterns": [
            {
                "name": "Complement Map (Two Sum)",
                "signal": "For each element, check if target - element exists in map; then add element",
                "example": "Two Sum (#1), Three Sum (sort + two pointers)",
            },
            {
                "name": "Frequency Counter",
                "signal": "Count occurrences with Counter; compare maps or check thresholds",
                "example": "Valid Anagram (#242), Top K Frequent (#347)",
            },
            {
                "name": "Set for Consecutive Sequence",
                "signal": "Add all numbers to a set; for each number that is a sequence start (num-1 not in set), expand right",
                "example": "Longest Consecutive Sequence (#128)",
            },
        ],
        "template": """\
from collections import Counter, defaultdict

# --- Two Sum ---
def two_sum(nums, target):
    seen = {}
    for i, num in enumerate(nums):
        complement = target - num
        if complement in seen:
            return [seen[complement], i]
        seen[num] = i

# --- Frequency counter ---
freq = Counter(nums)   # {element: count}
most_common = freq.most_common(k)

# --- Longest Consecutive Sequence ---
num_set = set(nums)
best = 0
for num in num_set:
    if num - 1 not in num_set:   # sequence start
        length = 1
        while num + length in num_set:
            length += 1
        best = max(best, length)
return best""",
        "examples": [
            {"name": "Two Sum (#1)", "url": "https://leetcode.com/problems/two-sum/"},
            {"name": "Longest Consecutive Sequence (#128)", "url": "https://leetcode.com/problems/longest-consecutive-sequence/"},
            {"name": "Group Anagrams (#49)", "url": "https://leetcode.com/problems/group-anagrams/"},
            {"name": "Ransom Note (#383)", "url": "https://leetcode.com/problems/ransom-note/"},
        ],
    },

    # ------------------------------------------------------------------ #
    #  19. Greedy & Interval Partitioning
    # ------------------------------------------------------------------ #
    {
        "id": 19,
        "name": "Greedy & Interval Partitioning",
        "description": "Make the locally optimal choice at each step. Works when local decisions are final and don't need revisiting. Interval problems: sort by start or end time, then greedily assign to partitions.",
        "when_to_use": [
            "Assigning values based on neighbor comparisons (give more than neighbor if rating is higher)",
            "Interval scheduling: pick the earliest-ending interval to maximize non-overlapping count",
            "Interval partitioning: minimum rooms/machines needed for all intervals",
            "Jump Game style: track farthest reachable index greedily",
            "1 or 2 linear passes over the array are sufficient",
            "NOT when overlapping subproblems require look-back — use DP instead",
            "NOT when you need all solutions — use Backtracking",
        ],
        "sub_patterns": [
            {
                "name": "Two-Pass Greedy",
                "signal": "Left-to-right pass + right-to-left pass; take max at each position",
                "example": "Candy (#135)",
            },
            {
                "name": "Interval Scheduling (Earliest Deadline First)",
                "signal": "Sort by end time; greedily pick interval if it doesn't overlap last chosen",
                "example": "Non-overlapping Intervals (#435), Meeting Rooms (#252)",
            },
            {
                "name": "Interval Partitioning (Minimum Rooms)",
                "signal": "Sort by start time; use a min-heap of end times; pop if room is free, else add new",
                "example": "Meeting Rooms II (#253)",
            },
            {
                "name": "Jump Greedy",
                "signal": "Track max reachable index; update at every step",
                "example": "Jump Game (#55), Jump Game II (#45)",
            },
        ],
        "template": """\
# --- Two-pass greedy (Candy) ---
n = len(ratings)
candies = [1] * n
for i in range(1, n):
    if ratings[i] > ratings[i - 1]:
        candies[i] = candies[i - 1] + 1
for i in range(n - 2, -1, -1):
    if ratings[i] > ratings[i + 1]:
        candies[i] = max(candies[i], candies[i + 1] + 1)
return sum(candies)

# --- Interval partitioning (min rooms) ---
import heapq
intervals.sort()
heap = []   # end times of active intervals
for start, end in intervals:
    if heap and heap[0] <= start:
        heapq.heapreplace(heap, end)
    else:
        heapq.heappush(heap, end)
return len(heap)""",
        "examples": [
            {"name": "Candy (#135)", "url": "https://leetcode.com/problems/candy/"},
            {"name": "Jump Game (#55)", "url": "https://leetcode.com/problems/jump-game/"},
            {"name": "Meeting Rooms II (#253)", "url": "https://leetcode.com/problems/meeting-rooms-ii/"},
            {"name": "Non-overlapping Intervals (#435)", "url": "https://leetcode.com/problems/non-overlapping-intervals/"},
        ],
    },

    # ------------------------------------------------------------------ #
    #  20. Monotonic Stack / Queue
    # ------------------------------------------------------------------ #
    {
        "id": 20,
        "name": "Monotonic Stack / Queue",
        "description": "Maintain a stack (or deque) where elements are always in increasing or decreasing order. Pop elements that violate the order — those pops reveal 'next greater/smaller' relationships in O(n) total.",
        "when_to_use": [
            "Next greater element / next smaller element for each position",
            "Largest rectangle in histogram",
            "Sliding window maximum (monotonic deque)",
            "Stock span, daily temperatures, trapping rain water",
            "NOT for global max/min without the 'next' relationship — just scan linearly",
        ],
        "sub_patterns": [
            {
                "name": "Monotonic Decreasing Stack (Next Greater)",
                "signal": "Push index; when nums[i] > nums[stack top], pop and record answer",
                "example": "Daily Temperatures (#739), Next Greater Element I (#496)",
            },
            {
                "name": "Monotonic Increasing Stack (Next Smaller / Histogram)",
                "signal": "Pop when current element is smaller than top; compute area/span on pop",
                "example": "Largest Rectangle in Histogram (#84)",
            },
            {
                "name": "Monotonic Deque (Sliding Window Max)",
                "signal": "Maintain decreasing deque of indices; pop front if out of window, pop back if smaller than current",
                "example": "Sliding Window Maximum (#239)",
            },
        ],
        "template": """\
# --- Next greater element ---
result = [-1] * len(nums)
stack = []   # indices, decreasing values
for i, num in enumerate(nums):
    while stack and nums[stack[-1]] < num:
        idx = stack.pop()
        result[idx] = num
    stack.append(i)
return result

# --- Sliding window maximum (monotonic deque) ---
from collections import deque
dq = deque()   # stores indices, values decreasing
output = []
for i, num in enumerate(nums):
    while dq and nums[dq[-1]] < num:
        dq.pop()
    dq.append(i)
    if dq[0] < i - k + 1:   # window expired
        dq.popleft()
    if i >= k - 1:
        output.append(nums[dq[0]])
return output""",
        "examples": [
            {"name": "Daily Temperatures (#739)", "url": "https://leetcode.com/problems/daily-temperatures/"},
            {"name": "Largest Rectangle in Histogram (#84)", "url": "https://leetcode.com/problems/largest-rectangle-in-histogram/"},
            {"name": "Sliding Window Maximum (#239)", "url": "https://leetcode.com/problems/sliding-window-maximum/"},
            {"name": "Next Greater Element I (#496)", "url": "https://leetcode.com/problems/next-greater-element-i/"},
        ],
    },

    # ------------------------------------------------------------------ #
    #  21. Sorting-Based Patterns
    # ------------------------------------------------------------------ #
    {
        "id": 21,
        "name": "Sorting-Based Patterns",
        "description": "Sort first to unlock O(n log n) solutions to problems that would otherwise be O(n²). Sorting reveals adjacency, enables two-pointer pairing, and simplifies interval problems.",
        "when_to_use": [
            "Pairs or triplets summing to a target (sort + two pointers)",
            "Checking if intervals overlap (sort by start time, then scan)",
            "Counting inversions or relative order comparisons",
            "Custom ordering: sort by a derived key (length, frequency, value mod k)",
            "NOT when input is already sorted — skip the sort step",
            "NOT when O(n) is achievable (counting sort, bucket sort, hash map)",
        ],
        "sub_patterns": [
            {
                "name": "Sort + Two Pointers",
                "signal": "Sort; then use left/right pointers to find pairs with a target property",
                "example": "3Sum (#15), Two Sum II (#167)",
            },
            {
                "name": "Custom Sort Key",
                "signal": "Sort by a non-default key: lambda or __lt__; order defines the algorithm",
                "example": "Largest Number (#179), Sort Colors (#75)",
            },
            {
                "name": "Sort + Binary Search",
                "signal": "Sort the array; then binary search for targets or boundaries",
                "example": "Search a 2D Matrix (#74), Two Sum Less Than K",
            },
        ],
        "template": """\
# --- 3Sum (sort + two pointers) ---
nums.sort()
result = []
for i in range(len(nums) - 2):
    if i > 0 and nums[i] == nums[i-1]:
        continue   # skip duplicate
    left, right = i + 1, len(nums) - 1
    while left < right:
        total = nums[i] + nums[left] + nums[right]
        if total == 0:
            result.append([nums[i], nums[left], nums[right]])
            while left < right and nums[left] == nums[left+1]: left += 1
            while left < right and nums[right] == nums[right-1]: right -= 1
            left += 1; right -= 1
        elif total < 0: left += 1
        else: right -= 1
return result""",
        "examples": [
            {"name": "3Sum (#15)", "url": "https://leetcode.com/problems/3sum/"},
            {"name": "Sort Colors (#75)", "url": "https://leetcode.com/problems/sort-colors/"},
            {"name": "Largest Number (#179)", "url": "https://leetcode.com/problems/largest-number/"},
            {"name": "Meeting Rooms (#252)", "url": "https://leetcode.com/problems/meeting-rooms/"},
        ],
    },

    # ------------------------------------------------------------------ #
    #  22. Merge K Sorted Lists
    # ------------------------------------------------------------------ #
    {
        "id": 22,
        "name": "Merge K Sorted Lists",
        "description": "Merge k sorted sequences into one sorted sequence using a min-heap. The heap always holds the current smallest element from each list, giving O(n log k) total — far better than naive O(nk).",
        "when_to_use": [
            "Merge k sorted arrays, linked lists, or streams",
            "Find the smallest range covering at least one element from each of k sorted lists",
            "K-way external merge sort",
            "NOT when k == 2 — use a simple linear merge instead",
            "NOT when all elements fit in memory and k is small — just concatenate and sort",
        ],
        "template": """\
import heapq

# --- Merge k sorted linked lists ---
def mergeKLists(lists):
    heap = []
    for i, node in enumerate(lists):
        if node:
            heapq.heappush(heap, (node.val, i, node))

    dummy = ListNode(0)
    curr = dummy
    while heap:
        val, i, node = heapq.heappop(heap)
        curr.next = node
        curr = curr.next
        if node.next:
            heapq.heappush(heap, (node.next.val, i, node.next))
    return dummy.next

# --- Merge k sorted arrays ---
def merge_k_arrays(arrays):
    heap = [(arrays[i][0], i, 0) for i in range(len(arrays)) if arrays[i]]
    heapq.heapify(heap)
    result = []
    while heap:
        val, i, j = heapq.heappop(heap)
        result.append(val)
        if j + 1 < len(arrays[i]):
            heapq.heappush(heap, (arrays[i][j+1], i, j+1))
    return result""",
        "examples": [
            {"name": "Merge K Sorted Lists (#23)", "url": "https://leetcode.com/problems/merge-k-sorted-lists/"},
            {"name": "Find K Pairs with Smallest Sums (#373)", "url": "https://leetcode.com/problems/find-k-pairs-with-smallest-sums/"},
            {"name": "Smallest Range Covering Elements from K Lists (#632)", "url": "https://leetcode.com/problems/smallest-range-covering-elements-from-k-lists/"},
            {"name": "Kth Smallest Element in a Sorted Matrix (#378)", "url": "https://leetcode.com/problems/kth-smallest-element-in-a-sorted-matrix/"},
        ],
    },

    # ------------------------------------------------------------------ #
    #  23. Divide and Conquer
    # ------------------------------------------------------------------ #
    {
        "id": 23,
        "name": "Divide and Conquer",
        "description": "Split the problem into smaller independent subproblems, solve each recursively, then combine the results. Powers sorting algorithms (merge sort, quick sort) and many tree/array problems.",
        "when_to_use": [
            "Problem naturally splits into independent halves (merge sort, binary search)",
            "Maximum subarray via split at midpoint (crossing subarray check)",
            "Median of two sorted arrays",
            "Closest pair of points",
            "NOT when subproblems overlap (use DP instead — overlapping = DP, independent = D&C)",
        ],
        "template": """\
def divide_and_conquer(arr, left, right):
    if left >= right:
        return base_case_value

    mid = (left + right) // 2

    left_result  = divide_and_conquer(arr, left, mid)
    right_result = divide_and_conquer(arr, mid + 1, right)

    # combine step
    return combine(left_result, right_result)

# --- Maximum subarray (divide and conquer) ---
def max_subarray(nums, l, r):
    if l == r:
        return nums[l]
    mid = (l + r) // 2
    left_max  = max_subarray(nums, l, mid)
    right_max = max_subarray(nums, mid + 1, r)
    # crossing sum
    left_cross = right_cross = 0
    running = 0
    for i in range(mid, l - 1, -1):
        running += nums[i]; left_cross = max(left_cross, running)
    running = 0
    for i in range(mid + 1, r + 1):
        running += nums[i]; right_cross = max(right_cross, running)
    return max(left_max, right_max, left_cross + right_cross)""",
        "examples": [
            {"name": "Maximum Subarray (#53)", "url": "https://leetcode.com/problems/maximum-subarray/"},
            {"name": "Sort an Array (#912)", "url": "https://leetcode.com/problems/sort-an-array/"},
            {"name": "Median of Two Sorted Arrays (#4)", "url": "https://leetcode.com/problems/median-of-two-sorted-arrays/"},
            {"name": "The Skyline Problem (#218)", "url": "https://leetcode.com/problems/the-skyline-problem/"},
        ],
    },

    # ------------------------------------------------------------------ #
    #  24. Merge Intervals
    # ------------------------------------------------------------------ #
    {
        "id": 24,
        "name": "Merge Intervals",
        "description": "Sort intervals by start time, then scan linearly — merging each interval with the last one in the result if they overlap. Covers insertion, intersection, and gap-finding problems.",
        "when_to_use": [
            "Given a list of intervals: merge all overlapping ones",
            "Insert a new interval into a sorted non-overlapping list",
            "Find gaps between intervals (free time)",
            "Minimum number of arrows to burst balloons (intervals)",
            "NOT when intervals are already sorted and non-overlapping — just scan",
        ],
        "template": """\
# --- Merge Intervals ---
intervals.sort(key=lambda x: x[0])
merged = [intervals[0]]
for start, end in intervals[1:]:
    if start <= merged[-1][1]:           # overlaps
        merged[-1][1] = max(merged[-1][1], end)
    else:
        merged.append([start, end])
return merged

# --- Insert Interval ---
result = []
i = 0
# add all intervals that come before new_interval
while i < len(intervals) and intervals[i][1] < new_interval[0]:
    result.append(intervals[i]); i += 1
# merge overlapping intervals with new_interval
while i < len(intervals) and intervals[i][0] <= new_interval[1]:
    new_interval[0] = min(new_interval[0], intervals[i][0])
    new_interval[1] = max(new_interval[1], intervals[i][1])
    i += 1
result.append(new_interval)
result.extend(intervals[i:])
return result""",
        "examples": [
            {"name": "Merge Intervals (#56)", "url": "https://leetcode.com/problems/merge-intervals/"},
            {"name": "Insert Interval (#57)", "url": "https://leetcode.com/problems/insert-interval/"},
            {"name": "Minimum Number of Arrows to Burst Balloons (#452)", "url": "https://leetcode.com/problems/minimum-number-of-arrows-to-burst-balloons/"},
            {"name": "Employee Free Time (#759)", "url": "https://leetcode.com/problems/employee-free-time/"},
        ],
    },

    # ------------------------------------------------------------------ #
    #  25. Two Pointers
    # ------------------------------------------------------------------ #
    {
        "id": 25,
        "name": "Two Pointers",
        "description": "Use two indices moving toward each other (or in the same direction) to scan an array or string in a single pass — turning O(n²) brute force into O(n).",
        "when_to_use": [
            "Array or string is sorted (or can be sorted without losing information)",
            "Finding a pair that satisfies a sum/difference condition",
            "Comparing elements from both ends simultaneously",
            "Removing duplicates in-place",
            "Partitioning an array around a pivot",
            "NOT for non-contiguous subsequences — use DP or recursion",
        ],
        "sub_patterns": [
            {
                "name": "Opposite Direction (Converging)",
                "signal": "left starts at 0, right at end; move based on comparison",
                "example": "Two Sum II (#167), Container With Most Water (#11)",
            },
            {
                "name": "Same Direction (Slow/Fast)",
                "signal": "Slow pointer marks 'last valid'; fast pointer scans ahead",
                "example": "Remove Duplicates (#26), Move Zeroes (#283)",
            },
        ],
        "template": """\
# --- Converging two pointers (Two Sum on sorted array) ---
left, right = 0, len(arr) - 1
while left < right:
    current_sum = arr[left] + arr[right]
    if current_sum == target:
        return [left, right]
    elif current_sum < target:
        left += 1
    else:
        right -= 1

# --- Same-direction (remove duplicates in-place) ---
slow = 0
for fast in range(len(nums)):
    if fast == 0 or nums[fast] != nums[fast - 1]:
        nums[slow] = nums[fast]
        slow += 1
return slow""",
        "examples": [
            {"name": "Two Sum II - Input Array Is Sorted (#167)", "url": "https://leetcode.com/problems/two-sum-ii-input-array-is-sorted/"},
            {"name": "Container With Most Water (#11)", "url": "https://leetcode.com/problems/container-with-most-water/"},
            {"name": "3Sum (#15)", "url": "https://leetcode.com/problems/3sum/"},
            {"name": "Valid Palindrome (#125)", "url": "https://leetcode.com/problems/valid-palindrome/"},
        ],
    },
]

# --------------------------------------------------------------------------- #
#  Dynamically discovered patterns — loaded from custom_patterns.json
#  Written by the Pattern Research Agent when it encounters an unknown pattern.
# --------------------------------------------------------------------------- #
import json as _json
from pathlib import Path as _Path

_CUSTOM_PATTERNS_FILE = _Path(__file__).parent / "custom_patterns.json"

_REQUIRED_PATTERN_FIELDS = {"name", "description", "when_to_use", "template", "examples"}

def _load_custom_patterns():
    if not _CUSTOM_PATTERNS_FILE.exists():
        return
    try:
        custom = _json.loads(_CUSTOM_PATTERNS_FILE.read_text())
        existing_names = {p["name"] for p in PATTERNS}
        for p in custom:
            # Only load fully-formed pattern definitions
            if p.get("name") and p["name"] not in existing_names and _REQUIRED_PATTERN_FIELDS.issubset(p.keys()):
                PATTERNS.append(p)
                existing_names.add(p["name"])
    except Exception:
        pass

_load_custom_patterns()
