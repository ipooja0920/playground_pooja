# LeetCoach — Product Specification

---

## Overview

**LeetCoach** is an AI-powered LeetCode preparation assistant. Give it a LeetCode problem URL and it automatically fetches the problem, identifies which algorithmic pattern(s) solve it, generates the cleanest optimized solution with a plain-English explanation, and breaks down the time/space complexity in the simplest possible way.

It also includes a built-in **Pattern Library** — a browsable reference of every major algorithmic pattern, when to use it, and which LeetCode problems it applies to.

---

## What It Does

| You give it | What actually happens |
|-------------|----------------------|
| A LeetCode problem URL | Browser agent scrapes the problem title, description, examples, constraints |
| Scraped problem | Classifier agent identifies which pattern(s) apply and explains why |
| Pattern identified | Solution agent writes the most readable + optimized code with line-by-line explanation |
| Solution ready | Complexity agent explains time and space complexity in plain English |
| Any failure | Agent failure log shows exactly which agent failed, why, and at what step |

---

## How It Works

```
User pastes LeetCode URL
          │
          ▼
  Browser Agent (Playwright MCP)
  scrapes problem text, examples, constraints
          │
          ▼
  Classifier Agent (LLM)
  identifies pattern(s) + explains reasoning
          │
          ▼
  Solution Agent (LLM)
  writes optimized code + step-by-step explanation
          │
          ▼
  Complexity Agent (LLM)
  explains time/space complexity in plain English
          │
          ▼
  Streamlit UI renders full response
  + Agent Failure Log if anything went wrong
```

---

## Agents

### 1. Browser Agent
- **Tool:** Playwright MCP (tool calling)
- **Job:** Navigate to the LeetCode problem URL, extract problem title, description, examples, constraints
- **Failure mode:** URL unreachable, LeetCode login wall, scraping error

### 2. Classifier Agent
- **Job:** Read the scraped problem → identify which algorithmic pattern(s) apply → explain *why* this pattern fits
- **Output:** Pattern name(s), reasoning, confidence
- **Failure mode:** Problem too ambiguous, unsupported pattern

### 3. Solution Agent
- **Job:** Given the problem + pattern → write the most readable optimized solution → explain it line by line in plain English
- **Output:** Code block + explanation
- **Failure mode:** LLM generation error

### 4. Complexity Agent
- **Job:** Analyze the solution → explain time and space complexity in the simplest terms possible (no jargon)
- **Output:** Time complexity, space complexity, plain English explanation of *why*
- **Failure mode:** LLM generation error

---

## Pattern Library (20 Patterns)

| # | Pattern | Example Problems |
|---|---------|-----------------|
| 1 | Two Pointers | Two Sum II (#167), 3Sum (#15), Container With Most Water (#11) |
| 2 | Sliding Window | Longest Substring Without Repeating Characters (#3), Maximum Average Subarray (#643) |
| 3 | Fast & Slow Pointers | Linked List Cycle (#141), Find the Duplicate Number (#287) |
| 4 | Binary Search | Search in Rotated Sorted Array (#33), Find Minimum in Rotated Sorted Array (#153) |
| 5 | BFS | Binary Tree Level Order Traversal (#102), Word Ladder (#127) |
| 6 | DFS | Number of Islands (#200), Clone Graph (#133) |
| 7 | Backtracking | Permutations (#46), Subsets (#78), N-Queens (#51) |
| 8 | Dynamic Programming | Climbing Stairs (#70), Coin Change (#322), Longest Common Subsequence (#1143) |
| 9 | Monotonic Stack | Next Greater Element (#496), Daily Temperatures (#739), Largest Rectangle in Histogram (#84) |
| 10 | Top K Elements | Kth Largest Element in an Array (#215), Top K Frequent Elements (#347) |
| 11 | Merge Intervals | Merge Intervals (#56), Insert Interval (#57), Meeting Rooms II (#253) |
| 12 | Prefix Sum | Range Sum Query (#303), Subarray Sum Equals K (#560) |
| 13 | Cyclic Sort | Find All Duplicates in an Array (#442), Find the Missing Number (#268) |
| 14 | Topological Sort | Course Schedule (#207), Alien Dictionary (#269) |
| 15 | Union Find | Number of Connected Components (#323), Redundant Connection (#684) |
| 16 | Trie | Implement Trie (#208), Word Search II (#212) |
| 17 | Two Heaps | Find Median from Data Stream (#295), Sliding Window Median (#480) |
| 18 | Subsets / Combinations | Subsets (#78), Combination Sum (#39), Palindrome Partitioning (#131) |
| 19 | Bit Manipulation | Single Number (#136), Counting Bits (#338), Reverse Bits (#190) |
| 20 | Divide & Conquer | Merge Sort, Quick Sort, Maximum Subarray (#53) |

---

## Tech Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **UI** | Streamlit | Web interface, pattern library, problem solver, failure log |
| **Agent Framework** | `mcp-agent` | Connects LLMs to MCP tool servers |
| **LLM** | OpenAI `gpt-4o-mini` | All agent reasoning (classify, solve, explain) |
| **Browser Control** | Playwright (`@playwright/mcp`) | Scrapes LeetCode problem content |
| **MCP Server** | `npx @playwright/mcp@latest` | Runs Playwright as an MCP tool server |
| **Async** | `asyncio` | Handles async multi-agent pipeline inside Streamlit |

---

## APIs and Prerequisites

| Requirement | Purpose | How to Get |
|-------------|---------|-----------|
| `OPENAI_API_KEY` | Powers all LLM agents | [platform.openai.com/api-keys](https://platform.openai.com/api-keys) |
| **Node.js + npm** | Runs Playwright MCP server | [nodejs.org](https://nodejs.org) |
| **Playwright browsers** | Chromium for scraping | `playwright install` after pip install |

---

## Streamlit UI — Sections

### Tab 1: Pattern Library
- Dropdown or expander for each of the 20 patterns
- Each pattern shows:
  - What it is (1-2 sentences)
  - When to use it (tell-tale signs in a problem)
  - Template/pseudocode
  - Example problems with links

### Tab 2: Problem Solver
- **Input:** LeetCode problem URL text field
- **Run button:** Triggers the 4-agent pipeline
- **Results rendered in 3 sections:**
  1. Pattern Match — which pattern(s) apply and why
  2. Solution — code block + plain-English explanation
  3. Complexity — time/space breakdown in simple terms
- **Agent Failure Log** (always visible at the bottom):
  - Shows which agent ran, its status (success/failed), and error details if any
  - Displayed as a table or expandable log entries
  - Color-coded: green = success, red = failed

---

## Project Structure

```
LeetCoach/
├── main.py                         # Streamlit app — UI, tabs, agent pipeline
├── patterns.py                     # Pattern library data (20 patterns, examples, explanations)
├── agents.py                       # Agent definitions and pipeline logic
├── mcp_agent.config.yaml           # MCP config — model, logging, Playwright server
├── mcp_agent.secrets.yaml          # API key (gitignored)
├── mcp_agent.secrets.yaml.example  # Template
├── requirements.txt                # Python dependencies
└── PRODUCT_SPEC.md                 # This file
```

---

## Agent Failure Log — UI Design

```
┌─────────────────────────────────────────────────────────────┐
│  Agent Execution Log                                         │
├───────────────┬──────────┬──────────────────────────────────┤
│ Agent         │ Status   │ Details                          │
├───────────────┼──────────┼──────────────────────────────────┤
│ Browser Agent │ ✅ OK    │ Scraped problem in 2.3s          │
│ Classifier    │ ✅ OK    │ Pattern: Two Pointers            │
│ Solution      │ ❌ FAIL  │ LLM timeout after 30s            │
│ Complexity    │ ⏭ SKIP  │ Skipped — Solution agent failed  │
└───────────────┴──────────┴──────────────────────────────────┘
```

---

## Error Handling

| Error | Behaviour |
|-------|-----------|
| LeetCode login wall / CAPTCHA | Browser agent fails gracefully, logs error, prompts user to paste problem text manually |
| OpenAI API key missing | Clear error before any execution |
| LLM generation failure | Agent marked as failed in log, pipeline continues where possible |
| Invalid URL | Validated before running pipeline |
| Playwright not installed | Clear error with install instructions |

---

## Limitations

- LeetCode may require login for some problems — if scraping fails, user can paste problem text directly
- Solution quality depends on GPT-4o-mini — hard problems may need GPT-4o for best results
- Pattern classification is probabilistic — some problems belong to multiple patterns
- No code execution — solution is generated but not run/validated automatically
