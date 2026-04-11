PATTERNS = [
    {
        "id": 1,
        "name": "Two Pointers",
        "description": "Use two indices that move toward each other (or in the same direction) to scan an array/string in a single pass — turning O(n²) brute force into O(n).",
        "when_to_use": [
            "Array or string is sorted (or can be sorted)",
            "Finding a pair that satisfies a sum/difference condition",
            "Comparing elements from both ends simultaneously",
            "Removing duplicates in-place",
        ],
        "template": """\
left, right = 0, len(arr) - 1
while left < right:
    current_sum = arr[left] + arr[right]
    if current_sum == target:
        return [left, right]
    elif current_sum < target:
        left += 1
    else:
        right -= 1""",
        "examples": [
            {"name": "Two Sum II (#167)", "url": "https://leetcode.com/problems/two-sum-ii-input-array-is-sorted/"},
            {"name": "3Sum (#15)", "url": "https://leetcode.com/problems/3sum/"},
            {"name": "Container With Most Water (#11)", "url": "https://leetcode.com/problems/container-with-most-water/"},
            {"name": "Valid Palindrome (#125)", "url": "https://leetcode.com/problems/valid-palindrome/"},
        ],
    },
    {
        "id": 2,
        "name": "Sliding Window",
        "description": "Maintain a window (subarray or substring) that expands and contracts as you move through the array. Avoids recomputing the whole window from scratch on each step.",
        "when_to_use": [
            "Finding longest/shortest subarray or substring satisfying a condition",
            "Finding maximum/minimum sum of a contiguous subarray of size k",
            "Problems with 'at most k distinct elements' or 'no repeating characters'",
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
            {"name": "Maximum Average Subarray I (#643)", "url": "https://leetcode.com/problems/maximum-average-subarray-i/"},
            {"name": "Permutation in String (#567)", "url": "https://leetcode.com/problems/permutation-in-string/"},
        ],
    },
    {
        "id": 3,
        "name": "Fast & Slow Pointers",
        "description": "Two pointers move at different speeds through a linked list or array. The fast pointer moves 2 steps while slow moves 1. When fast reaches the end, slow is at the middle — or if there's a cycle, they eventually meet.",
        "when_to_use": [
            "Detecting a cycle in a linked list",
            "Finding the middle of a linked list",
            "Finding the start of a cycle",
            "Detecting duplicates using index-as-value arrays",
        ],
        "template": """\
slow = head
fast = head

while fast and fast.next:
    slow = slow.next
    fast = fast.next.next
    if slow == fast:
        return True   # cycle detected

return False""",
        "examples": [
            {"name": "Linked List Cycle (#141)", "url": "https://leetcode.com/problems/linked-list-cycle/"},
            {"name": "Find the Duplicate Number (#287)", "url": "https://leetcode.com/problems/find-the-duplicate-number/"},
            {"name": "Middle of the Linked List (#876)", "url": "https://leetcode.com/problems/middle-of-the-linked-list/"},
            {"name": "Happy Number (#202)", "url": "https://leetcode.com/problems/happy-number/"},
        ],
    },
    {
        "id": 4,
        "name": "Binary Search",
        "description": "Cut the search space in half each step by comparing the middle element to the target. Works on sorted arrays and any problem where you can eliminate half the possibilities per step.",
        "when_to_use": [
            "Array is sorted",
            "Finding an element in O(log n)",
            "Problem asks for 'minimum value that satisfies X' — binary search on the answer",
            "Search space can be halved with a condition check",
        ],
        "template": """\
left, right = 0, len(arr) - 1

while left <= right:
    mid = (left + right) // 2
    if arr[mid] == target:
        return mid
    elif arr[mid] < target:
        left = mid + 1
    else:
        right = mid - 1

return -1""",
        "examples": [
            {"name": "Binary Search (#704)", "url": "https://leetcode.com/problems/binary-search/"},
            {"name": "Search in Rotated Sorted Array (#33)", "url": "https://leetcode.com/problems/search-in-rotated-sorted-array/"},
            {"name": "Find Minimum in Rotated Sorted Array (#153)", "url": "https://leetcode.com/problems/find-minimum-in-rotated-sorted-array/"},
            {"name": "Koko Eating Bananas (#875)", "url": "https://leetcode.com/problems/koko-eating-bananas/"},
        ],
    },
    {
        "id": 5,
        "name": "BFS (Breadth-First Search)",
        "description": "Explore a graph or tree level by level using a queue. Guarantees the shortest path in unweighted graphs. Process all nodes at distance d before any node at distance d+1.",
        "when_to_use": [
            "Shortest path in an unweighted graph or grid",
            "Level-order traversal of a tree",
            "Finding the minimum number of steps/moves",
            "Spreading problems (infection, fire, water)",
        ],
        "template": """\
from collections import deque

queue = deque([start])
visited = {start}

while queue:
    node = queue.popleft()
    if node == target:
        return distance
    for neighbor in graph[node]:
        if neighbor not in visited:
            visited.add(neighbor)
            queue.append(neighbor)""",
        "examples": [
            {"name": "Binary Tree Level Order Traversal (#102)", "url": "https://leetcode.com/problems/binary-tree-level-order-traversal/"},
            {"name": "Word Ladder (#127)", "url": "https://leetcode.com/problems/word-ladder/"},
            {"name": "Number of Islands (#200)", "url": "https://leetcode.com/problems/number-of-islands/"},
            {"name": "Rotting Oranges (#994)", "url": "https://leetcode.com/problems/rotting-oranges/"},
        ],
    },
    {
        "id": 6,
        "name": "DFS (Depth-First Search)",
        "description": "Explore as deep as possible along one branch before backtracking. Uses a stack (or recursion). Great for path finding, connected components, and tree traversals.",
        "when_to_use": [
            "Exploring all paths or possibilities",
            "Checking connectivity in a graph",
            "Tree traversals (preorder, inorder, postorder)",
            "Detecting cycles in a directed graph",
        ],
        "template": """\
def dfs(node, visited):
    if node in visited:
        return
    visited.add(node)
    # process node
    for neighbor in graph[node]:
        dfs(neighbor, visited)

visited = set()
dfs(start, visited)""",
        "examples": [
            {"name": "Number of Islands (#200)", "url": "https://leetcode.com/problems/number-of-islands/"},
            {"name": "Clone Graph (#133)", "url": "https://leetcode.com/problems/clone-graph/"},
            {"name": "Path Sum (#112)", "url": "https://leetcode.com/problems/path-sum/"},
            {"name": "Course Schedule (#207)", "url": "https://leetcode.com/problems/course-schedule/"},
        ],
    },
    {
        "id": 7,
        "name": "Backtracking",
        "description": "Build a solution incrementally, abandoning a path as soon as you determine it can't lead to a valid answer. Think of it as DFS with pruning.",
        "when_to_use": [
            "Generating all permutations, combinations, or subsets",
            "Constraint satisfaction problems (N-Queens, Sudoku)",
            "Finding all valid paths",
            "Word search on a grid",
        ],
        "template": """\
def backtrack(start, current):
    if is_solution(current):
        result.append(current[:])
        return
    for choice in choices(start):
        current.append(choice)        # make choice
        backtrack(start + 1, current) # recurse
        current.pop()                 # undo choice

result = []
backtrack(0, [])
return result""",
        "examples": [
            {"name": "Permutations (#46)", "url": "https://leetcode.com/problems/permutations/"},
            {"name": "Subsets (#78)", "url": "https://leetcode.com/problems/subsets/"},
            {"name": "Combination Sum (#39)", "url": "https://leetcode.com/problems/combination-sum/"},
            {"name": "N-Queens (#51)", "url": "https://leetcode.com/problems/n-queens/"},
        ],
    },
    {
        "id": 8,
        "name": "Dynamic Programming",
        "description": "Break a problem into overlapping subproblems and store results to avoid recomputation. Two approaches: top-down (memoization) and bottom-up (tabulation).",
        "when_to_use": [
            "Problem asks for maximum/minimum/count of something",
            "Overlapping subproblems (same subproblem solved multiple times)",
            "Optimal substructure (optimal solution built from optimal sub-solutions)",
            "Classic signals: 'number of ways', 'minimum cost', 'longest subsequence'",
        ],
        "template": """\
# Bottom-up tabulation
dp = [0] * (n + 1)
dp[0] = base_case

for i in range(1, n + 1):
    for j in range(i):
        dp[i] = max(dp[i], dp[j] + transition(j, i))

return dp[n]""",
        "examples": [
            {"name": "Climbing Stairs (#70)", "url": "https://leetcode.com/problems/climbing-stairs/"},
            {"name": "Coin Change (#322)", "url": "https://leetcode.com/problems/coin-change/"},
            {"name": "Longest Common Subsequence (#1143)", "url": "https://leetcode.com/problems/longest-common-subsequence/"},
            {"name": "House Robber (#198)", "url": "https://leetcode.com/problems/house-robber/"},
        ],
    },
    {
        "id": 9,
        "name": "Monotonic Stack",
        "description": "A stack that is always maintained in sorted (increasing or decreasing) order. When a new element breaks the order, pop elements until it's restored. Great for 'next greater/smaller element' problems.",
        "when_to_use": [
            "Next greater/smaller element to the right or left",
            "Largest rectangle in a histogram",
            "Stock span problems",
            "Any problem involving finding nearest smaller/larger values",
        ],
        "template": """\
stack = []  # stores indices
result = [-1] * len(arr)

for i in range(len(arr)):
    # pop while stack top is smaller than current
    while stack and arr[stack[-1]] < arr[i]:
        idx = stack.pop()
        result[idx] = arr[i]  # arr[i] is next greater for idx
    stack.append(i)

return result""",
        "examples": [
            {"name": "Next Greater Element I (#496)", "url": "https://leetcode.com/problems/next-greater-element-i/"},
            {"name": "Daily Temperatures (#739)", "url": "https://leetcode.com/problems/daily-temperatures/"},
            {"name": "Largest Rectangle in Histogram (#84)", "url": "https://leetcode.com/problems/largest-rectangle-in-histogram/"},
            {"name": "Car Fleet (#853)", "url": "https://leetcode.com/problems/car-fleet/"},
        ],
    },
    {
        "id": 10,
        "name": "Top K Elements",
        "description": "Use a heap to efficiently track the K largest or K smallest elements without sorting the entire array. A min-heap of size K gives you the K largest; a max-heap gives you the K smallest.",
        "when_to_use": [
            "Finding Kth largest or Kth smallest element",
            "Top K frequent elements",
            "K closest points to origin",
            "Any problem where you need the best K out of N",
        ],
        "template": """\
import heapq

# K largest elements using min-heap of size K
heap = []
for num in nums:
    heapq.heappush(heap, num)
    if len(heap) > k:
        heapq.heappop(heap)  # remove smallest

return heap[0]  # Kth largest""",
        "examples": [
            {"name": "Kth Largest Element in an Array (#215)", "url": "https://leetcode.com/problems/kth-largest-element-in-an-array/"},
            {"name": "Top K Frequent Elements (#347)", "url": "https://leetcode.com/problems/top-k-frequent-elements/"},
            {"name": "K Closest Points to Origin (#973)", "url": "https://leetcode.com/problems/k-closest-points-to-origin/"},
            {"name": "Find K Pairs with Smallest Sums (#373)", "url": "https://leetcode.com/problems/find-k-pairs-with-smallest-sums/"},
        ],
    },
    {
        "id": 11,
        "name": "Merge Intervals",
        "description": "Sort intervals by start time, then scan through merging any overlapping ones. The key insight: two intervals overlap if the start of one is <= end of the other.",
        "when_to_use": [
            "Problems with ranges or intervals that may overlap",
            "Meeting room scheduling",
            "Finding gaps or free time slots",
            "Inserting a new interval into an existing sorted list",
        ],
        "template": """\
intervals.sort(key=lambda x: x[0])
merged = [intervals[0]]

for start, end in intervals[1:]:
    if start <= merged[-1][1]:
        # overlap — extend the last merged interval
        merged[-1][1] = max(merged[-1][1], end)
    else:
        merged.append([start, end])

return merged""",
        "examples": [
            {"name": "Merge Intervals (#56)", "url": "https://leetcode.com/problems/merge-intervals/"},
            {"name": "Insert Interval (#57)", "url": "https://leetcode.com/problems/insert-interval/"},
            {"name": "Non-overlapping Intervals (#435)", "url": "https://leetcode.com/problems/non-overlapping-intervals/"},
            {"name": "Meeting Rooms II (#253)", "url": "https://leetcode.com/problems/meeting-rooms-ii/"},
        ],
    },
    {
        "id": 12,
        "name": "Prefix Sum",
        "description": "Precompute a running sum array so any subarray sum can be computed in O(1). prefix[i] = sum of arr[0..i-1]. Sum of arr[l..r] = prefix[r+1] - prefix[l].",
        "when_to_use": [
            "Multiple range sum queries",
            "Subarray sum equals K",
            "Counting subarrays with a given sum",
            "2D grid sum queries",
        ],
        "template": """\
# Build prefix sum
prefix = [0] * (len(arr) + 1)
for i, num in enumerate(arr):
    prefix[i + 1] = prefix[i] + num

# Query: sum of arr[l..r]
def range_sum(l, r):
    return prefix[r + 1] - prefix[l]""",
        "examples": [
            {"name": "Range Sum Query - Immutable (#303)", "url": "https://leetcode.com/problems/range-sum-query-immutable/"},
            {"name": "Subarray Sum Equals K (#560)", "url": "https://leetcode.com/problems/subarray-sum-equals-k/"},
            {"name": "Product of Array Except Self (#238)", "url": "https://leetcode.com/problems/product-of-array-except-self/"},
            {"name": "Contiguous Array (#525)", "url": "https://leetcode.com/problems/contiguous-array/"},
        ],
    },
    {
        "id": 13,
        "name": "Cyclic Sort",
        "description": "When array values are in range [1, n], each number belongs at index value-1. Scan through, and if a number isn't at its correct index, swap it there. Runs in O(n) with O(1) space.",
        "when_to_use": [
            "Array contains numbers in range [1, n] or [0, n-1]",
            "Finding missing numbers, duplicate numbers, or the smallest missing positive",
            "Rearranging array elements to their 'correct' positions",
        ],
        "template": """\
i = 0
while i < len(nums):
    correct = nums[i] - 1  # where this number belongs
    if nums[i] != nums[correct]:
        nums[i], nums[correct] = nums[correct], nums[i]  # swap
    else:
        i += 1

# Now scan for the missing number
for i, num in enumerate(nums):
    if num != i + 1:
        return i + 1""",
        "examples": [
            {"name": "Find All Numbers Disappeared in an Array (#448)", "url": "https://leetcode.com/problems/find-all-numbers-disappeared-in-an-array/"},
            {"name": "Find All Duplicates in an Array (#442)", "url": "https://leetcode.com/problems/find-all-duplicates-in-an-array/"},
            {"name": "Missing Number (#268)", "url": "https://leetcode.com/problems/missing-number/"},
            {"name": "First Missing Positive (#41)", "url": "https://leetcode.com/problems/first-missing-positive/"},
        ],
    },
    {
        "id": 14,
        "name": "Topological Sort",
        "description": "Order nodes in a directed acyclic graph (DAG) so that every edge goes from earlier to later. Uses BFS with in-degree counts (Kahn's algorithm) or DFS with a stack.",
        "when_to_use": [
            "Ordering tasks with dependencies (course schedule, build order)",
            "Detecting cycles in a directed graph",
            "Reconstructing sequences from dependency rules",
        ],
        "template": """\
from collections import deque

# Build graph and in-degree count
graph = defaultdict(list)
in_degree = {i: 0 for i in range(n)}
for u, v in prerequisites:
    graph[u].append(v)
    in_degree[v] += 1

# Start with all nodes that have no dependencies
queue = deque([n for n in in_degree if in_degree[n] == 0])
order = []

while queue:
    node = queue.popleft()
    order.append(node)
    for neighbor in graph[node]:
        in_degree[neighbor] -= 1
        if in_degree[neighbor] == 0:
            queue.append(neighbor)

return order if len(order) == n else []  # empty = cycle exists""",
        "examples": [
            {"name": "Course Schedule (#207)", "url": "https://leetcode.com/problems/course-schedule/"},
            {"name": "Course Schedule II (#210)", "url": "https://leetcode.com/problems/course-schedule-ii/"},
            {"name": "Alien Dictionary (#269)", "url": "https://leetcode.com/problems/alien-dictionary/"},
            {"name": "Task Scheduler (#621)", "url": "https://leetcode.com/problems/task-scheduler/"},
        ],
    },
    {
        "id": 15,
        "name": "Union Find (Disjoint Set)",
        "description": "Efficiently group elements into sets and check if two elements belong to the same set. Two operations: find (which set?) and union (merge two sets). Near O(1) per operation with path compression.",
        "when_to_use": [
            "Grouping nodes into connected components",
            "Detecting cycles in undirected graphs",
            "Dynamic connectivity (edges added one by one)",
            "Counting distinct groups/islands",
        ],
        "template": """\
parent = list(range(n))
rank = [0] * n

def find(x):
    if parent[x] != x:
        parent[x] = find(parent[x])  # path compression
    return parent[x]

def union(x, y):
    px, py = find(x), find(y)
    if px == py:
        return False  # already connected
    if rank[px] < rank[py]:
        px, py = py, px
    parent[py] = px
    if rank[px] == rank[py]:
        rank[px] += 1
    return True""",
        "examples": [
            {"name": "Number of Connected Components (#323)", "url": "https://leetcode.com/problems/number-of-connected-components-in-an-undirected-graph/"},
            {"name": "Redundant Connection (#684)", "url": "https://leetcode.com/problems/redundant-connection/"},
            {"name": "Accounts Merge (#721)", "url": "https://leetcode.com/problems/accounts-merge/"},
            {"name": "Graph Valid Tree (#261)", "url": "https://leetcode.com/problems/graph-valid-tree/"},
        ],
    },
    {
        "id": 16,
        "name": "Trie (Prefix Tree)",
        "description": "A tree where each node represents one character of a string. All strings sharing a prefix share the same path from the root. Enables O(m) search/insert where m = word length.",
        "when_to_use": [
            "Autocomplete or prefix matching",
            "Dictionary word search",
            "Word search on a grid (Word Search II)",
            "Finding all words with a common prefix",
        ],
        "template": """\
class TrieNode:
    def __init__(self):
        self.children = {}
        self.is_end = False

class Trie:
    def __init__(self):
        self.root = TrieNode()

    def insert(self, word):
        node = self.root
        for ch in word:
            if ch not in node.children:
                node.children[ch] = TrieNode()
            node = node.children[ch]
        node.is_end = True

    def search(self, word):
        node = self.root
        for ch in word:
            if ch not in node.children:
                return False
            node = node.children[ch]
        return node.is_end""",
        "examples": [
            {"name": "Implement Trie (#208)", "url": "https://leetcode.com/problems/implement-trie-prefix-tree/"},
            {"name": "Word Search II (#212)", "url": "https://leetcode.com/problems/word-search-ii/"},
            {"name": "Design Add and Search Words Data Structure (#211)", "url": "https://leetcode.com/problems/design-add-and-search-words-data-structure/"},
            {"name": "Replace Words (#648)", "url": "https://leetcode.com/problems/replace-words/"},
        ],
    },
    {
        "id": 17,
        "name": "Two Heaps",
        "description": "Maintain two heaps — a max-heap for the lower half and a min-heap for the upper half. The tops of both heaps always give you the median instantly. Rebalance after each insert.",
        "when_to_use": [
            "Continuously finding the median of a stream of numbers",
            "Sliding window median",
            "Problems requiring the 'middle' element dynamically",
        ],
        "template": """\
import heapq

lo = []  # max-heap (negate values)
hi = []  # min-heap

def add_num(num):
    heapq.heappush(lo, -num)
    heapq.heappush(hi, -heapq.heappop(lo))  # balance
    if len(lo) < len(hi):
        heapq.heappush(lo, -heapq.heappop(hi))

def find_median():
    if len(lo) > len(hi):
        return -lo[0]
    return (-lo[0] + hi[0]) / 2.0""",
        "examples": [
            {"name": "Find Median from Data Stream (#295)", "url": "https://leetcode.com/problems/find-median-from-data-stream/"},
            {"name": "Sliding Window Median (#480)", "url": "https://leetcode.com/problems/sliding-window-median/"},
            {"name": "IPO (#502)", "url": "https://leetcode.com/problems/ipo/"},
        ],
    },
    {
        "id": 18,
        "name": "Subsets / Combinations",
        "description": "Generate all subsets or combinations by making a binary choice at each step: include this element or skip it. Often implemented with backtracking or bit manipulation.",
        "when_to_use": [
            "Generate all subsets of a set",
            "Find all combinations that sum to a target",
            "Enumerate all possible groupings",
            "Power set problems",
        ],
        "template": """\
def backtrack(start, current):
    result.append(current[:])  # add current subset
    for i in range(start, len(nums)):
        current.append(nums[i])
        backtrack(i + 1, current)
        current.pop()

result = []
backtrack(0, [])
return result""",
        "examples": [
            {"name": "Subsets (#78)", "url": "https://leetcode.com/problems/subsets/"},
            {"name": "Subsets II (#90)", "url": "https://leetcode.com/problems/subsets-ii/"},
            {"name": "Combination Sum (#39)", "url": "https://leetcode.com/problems/combination-sum/"},
            {"name": "Palindrome Partitioning (#131)", "url": "https://leetcode.com/problems/palindrome-partitioning/"},
        ],
    },
    {
        "id": 19,
        "name": "Bit Manipulation",
        "description": "Use bitwise operations (AND, OR, XOR, shifts) to solve problems at the binary level. XOR is especially powerful: a ^ a = 0 and a ^ 0 = a, so XORing all elements cancels pairs.",
        "when_to_use": [
            "Finding the single non-duplicate in a list of pairs (XOR trick)",
            "Checking if a number is a power of 2",
            "Counting set bits (Hamming weight)",
            "Problems involving binary representations",
        ],
        "template": """\
# XOR trick: find the single number
result = 0
for num in nums:
    result ^= num  # pairs cancel out
return result

# Check power of 2
def is_power_of_two(n):
    return n > 0 and (n & (n - 1)) == 0

# Count set bits
def count_bits(n):
    count = 0
    while n:
        count += n & 1
        n >>= 1
    return count""",
        "examples": [
            {"name": "Single Number (#136)", "url": "https://leetcode.com/problems/single-number/"},
            {"name": "Counting Bits (#338)", "url": "https://leetcode.com/problems/counting-bits/"},
            {"name": "Reverse Bits (#190)", "url": "https://leetcode.com/problems/reverse-bits/"},
            {"name": "Number of 1 Bits (#191)", "url": "https://leetcode.com/problems/number-of-1-bits/"},
        ],
    },
    {
        "id": 20,
        "name": "Divide & Conquer",
        "description": "Split the problem into two halves, solve each half recursively, then combine the results. The classic examples are merge sort and quick sort. Time complexity is usually O(n log n).",
        "when_to_use": [
            "Sorting algorithms (merge sort, quick sort)",
            "Maximum subarray (Kadane's can also solve this, but D&C is O(n log n))",
            "Closest pair of points",
            "Problems where splitting in half and merging is natural",
        ],
        "template": """\
def divide_and_conquer(arr, left, right):
    if left >= right:
        return base_case

    mid = (left + right) // 2

    left_result = divide_and_conquer(arr, left, mid)
    right_result = divide_and_conquer(arr, mid + 1, right)

    return combine(left_result, right_result)""",
        "examples": [
            {"name": "Maximum Subarray (#53)", "url": "https://leetcode.com/problems/maximum-subarray/"},
            {"name": "Sort an Array (#912)", "url": "https://leetcode.com/problems/sort-an-array/"},
            {"name": "Median of Two Sorted Arrays (#4)", "url": "https://leetcode.com/problems/median-of-two-sorted-arrays/"},
            {"name": "The Skyline Problem (#218)", "url": "https://leetcode.com/problems/the-skyline-problem/"},
        ],
    },
]
