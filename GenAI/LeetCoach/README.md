# LeetCoach

> For full architecture, agent details, feedback system, pattern library, evaluation design, and test documentation, see the [**Product Specification**](PRODUCT_SPEC.md).

---

An AI-powered LeetCode coach for absolute beginners. Paste a LeetCode URL and get:

- The **algorithmic pattern** behind the problem (1 of 25, with sub-pattern precision)
- A **beginner-friendly solution** explained with plain-English analogies
- A **Big O complexity breakdown** told as a counting story, with a 2-question quiz
- **Evaluation scores** from RAGAS (Faithfulness + Answer Relevancy) and an LLM Judge (6 dimensions)

The system learns from every run — human 👍/👎 feedback, critic low scores, and LLM Judge results are all persisted and automatically injected into future runs.

---

## Quick Start

**Prerequisites:** Python 3.10+, Node.js 18+, OpenAI API key

```bash
# Install dependencies
pip install -r requirements.txt

# Install Playwright browser (for LeetCode scraping)
npx playwright install chromium

# Set your API key
cp mcp_agent.secrets.yaml.example mcp_agent.secrets.yaml
# Edit mcp_agent.secrets.yaml and paste your key

# Run tests (136 tests, all mocked — no API credits used)
python -m pytest tests/ -v

# Start the app
streamlit run main.py
```

Open [http://localhost:8501](http://localhost:8501).

---

## How It Works

LeetCoach runs an **8-agent pipeline** on every problem:

| # | Agent | Model | Job |
|---|-------|-------|-----|
| 1 | Browser Agent | `gpt-4o-mini` | Scrapes LeetCode URL via Playwright MCP |
| 2 | Planner Agent | `gpt-4o` | Decides full vs. simplified pipeline strategy |
| 3 | Classifier Agent | `gpt-4o` | Identifies the algorithmic pattern (1 of 25) |
| 4 | Classifier Critic | `gpt-4o-mini` | Scores pattern correctness; triggers retry if ≤ 3/5 |
| 5 | Solution Agent | `gpt-4o-mini` | Writes beginner solution with story-based analogies |
| 6 | General Critic | `gpt-4o-mini` | Scores tone and format; triggers retry if ≤ 3/5 |
| 7 | Complexity Agent | `gpt-4o-mini` | Explains Big O + generates 2-Q quiz |
| 8 | Pattern Research Agent | `gpt-4o` | On-demand: identifies correct pattern + saves lesson |

---

## Pattern Library

25 built-in algorithmic patterns, each with sub-patterns, `when_to_use` signals, NOT signals (to prevent cross-pattern confusion), a Python code template, and 4 LeetCode examples:

| # | Pattern |
|---|---------|
| 1 | Prefix Sums |
| 2 | Sliding Window |
| 3 | Stacks and Queues |
| 4 | Fast and Slow Pointers |
| 5 | Top K Frequent Elements |
| 6 | Binary Search (and Variants) |
| 7 | Graph Traversals (BFS, DFS) |
| 8 | Backtracking & Recursive Search |
| 9 | Path Sum & Root-to-Leaf Techniques |
| 10 | String Manipulation & Regular Expressions |
| 11 | Dynamic Programming (Knapsack, Range DP) |
| 12 | Kth Largest/Smallest Elements (Heaps / QuickSelect) |
| 13 | Linked List Techniques (Dummy Node, In-place Reversal) |
| 14 | Graph Algorithms (DAGs, MSTs, Shortest Paths) |
| 15 | Binary Trees & BSTs (Traversal, Construction) |
| 16 | Design Problems (LRU Cache, Twitter) |
| 17 | Expression Evaluation (Two Stacks) |
| 18 | Hashmaps & Frequency Counting |
| 19 | Greedy & Interval Partitioning |
| 20 | Monotonic Stack / Queue |
| 21 | Sorting-Based Patterns |
| 22 | Merge K Sorted Lists |
| 23 | Divide and Conquer |
| 24 | Merge Intervals |
| 25 | Two Pointers |

The Pattern Research Agent can auto-discover and add new patterns at runtime — saved to `custom_patterns.json` and loaded on every future startup.

---

## Learning System

Every run feeds a persistent memory system that improves future classifications:

| File | Written by | Used for |
|------|-----------|---------|
| `feedback.json` | Human 👍/👎 | Positive/negative style examples injected into agents |
| `feedback_rules.json` | Human feedback | Compact "Do/Avoid" rules per agent |
| `corrections.json` | Critic agents | Lessons from low critic scores |
| `judge_lessons.json` | LLM Judge | Per-dimension lessons from low evaluation scores |
| `pattern_knowledge.json` | Pattern Research Agent | Sub-pattern lessons injected into Classifier |
| `custom_patterns.json` | Pattern Research Agent | Full definitions for auto-discovered patterns |
| `eval_history.json` | Evaluation tab | Last 50 evaluation results for trend tracking |

---

## UI Tabs

- **Problem Solver** — main pipeline, per-section feedback (👍/👎), Pattern Research expander, interactive quiz
- **Pattern Library** — searchable view of all 25 patterns with sub-patterns, signals, templates, and example links
- **Agent Log** — per-agent status, duration, self-correction attempts, feedback rules, critic lessons
- **Evaluation** — RAGAS scores, LLM Judge 6-dimension scorecard, ground-truth pattern accuracy, history chart

---

## Test Suite

**136 tests, 0 failures.** All LLM calls are mocked — no real API calls.

```bash
python -m pytest tests/ -v
```

| Module | Tests | Covers |
|--------|-------|--------|
| `test_patterns.py` | 29 | 25-pattern library structure, sub-patterns, NOT signals |
| `test_feedback.py` | 20 | Feedback store, rules, judge lessons, instruction composition |
| `test_classifier.py` | 17 | Classifier instruction, pattern validator, self-correction |
| `test_evaluation.py` | 13 | LLM Judge parsing, lesson routing, eval history |
| `test_pattern_research_agent.py` | 13 | Research, auto-discovery, file isolation |
| `test_ground_truth.py` | 12 | Ground truth dataset, URL matching, pattern accuracy |
| `test_pipeline.py` | 10 | Full pipeline: happy path, failures, fallback |
| `test_regeneration.py` | 9 | `rerun_section()` cascade for all three sections |

---

## Project Structure

```
LeetCoach/
├── main.py                        # Streamlit app (4 tabs, quiz, feedback UI, evaluation)
├── agents.py                      # All agent logic: pipeline, self-correction, feedback, memory
├── patterns.py                    # 25 built-in patterns + loads custom_patterns.json
├── pattern_research_agent.py      # Pattern Research Agent (research, discovery, knowledge files)
├── evaluation.py                  # RAGAS + LLM Judge + ground truth accuracy check
├── ground_truth.py                # ~65 hand-labeled problems for pattern accuracy evaluation
├── mcp_agent.config.yaml          # MCP config (model, logging, Playwright)
├── mcp_agent.secrets.yaml.example # API key template
├── requirements.txt               # Python dependencies
├── pytest.ini                     # asyncio_mode = auto
├── tests/                         # 136 tests, all mocked
└── PRODUCT_SPEC.md                # Full technical specification
```

---

## Dependencies

```
streamlit>=1.28.0
mcp-agent>=0.0.14
openai>=1.0.0
pyyaml>=6.0
ragas>=0.4.0
datasets>=2.14.0
langchain-openai>=0.1.0
```

Node: `npx @playwright/mcp@latest` (auto-launched by mcp-agent)
