# LeetCoach — Product Specification

---

## Overview

**LeetCoach** is an AI-powered LeetCode preparation assistant built for absolute beginners. Paste a LeetCode URL — or type a problem name — and it automatically fetches the problem, identifies the algorithmic pattern, generates a plain-English solution with analogies a 5-year-old can follow, and explains time/space complexity as a counting story with an interactive quiz.

The system learns from every run: human 👍/👎 feedback, LLM Judge low scores, and user-flagged wrong patterns are all persisted and automatically injected into future agent runs.

---

## Agent Count

LeetCoach uses **8 agents** across the pipeline:

| # | Agent | Type | Model |
|---|-------|------|-------|
| 1 | Browser Agent | Tool-calling (Playwright MCP) | `gpt-4o-mini` |
| 2 | Planner Agent | Orchestrator | `gpt-4o` |
| 3 | Classifier Agent | Specialist | `gpt-4o` |
| 4 | Classifier Critic | Internal reviewer | `gpt-4o-mini` |
| 5 | Solution Agent | Specialist | `gpt-4o-mini` |
| 6 | General Critic | Internal reviewer | `gpt-4o-mini` |
| 7 | Complexity Agent | Specialist | `gpt-4o-mini` |
| 8 | Pattern Research Agent | On-demand researcher | `gpt-4o` |

---

## Pipeline Architecture

```
User pastes URL  ──or──  User types keyword → Search → picks problem
          │
          ▼
  ╔═════════════════════════════════════════════╗
  ║  AGENT 1 — Browser Agent                   ║
  ║  Framework: mcp-agent + Playwright MCP      ║
  ║  Scrapes: title, description, examples,     ║
  ║           constraints from LeetCode URL     ║
  ║  Failure → Supervisor shows paste-text UI   ║
  ╚══════════════════════╤══════════════════════╝
                         │ problem_text
                         ▼
  ╔═════════════════════════════════════════════╗
  ║  AGENT 2 — Planner Agent                   ║
  ║  Model: gpt-4o (direct AsyncOpenAI)         ║
  ║  Reads problem → outputs strategy:          ║
  ║    "full"       → complete pipeline         ║
  ║    "simplified" → easy problem, noted       ║
  ╚══════════════════════╤══════════════════════╝
                         │ strategy + problem_text
                         ▼
  ╔═════════════════════════════════════════════╗
  ║  AGENT 3 — Classifier Agent                ║
  ║  Model: gpt-4o (direct AsyncOpenAI)         ║
  ║  Picks 1 of 20 patterns, explains why       ║
  ║  Grounded: full pattern menu injected       ║
  ║  Memory: pattern_knowledge.json injected    ║
  ╚══════════════════════╤══════════════════════╝
                         │ pattern output
                         ▼
  ╔═════════════════════════════════════════════╗
  ║  AGENT 4 — Classifier Critic               ║
  ║  Model: gpt-4o-mini (mcp-agent)             ║
  ║  Reviews: is the pattern factually correct? ║
  ║  Score ≥ 4 → pass                           ║
  ║  Score ≤ 3 → Classifier retries with fix    ║
  ╚══════════════════════╤══════════════════════╝
                         │ validated pattern
                         ▼
  ╔═════════════════════════════════════════════╗
  ║  AGENT 5 — Solution Agent                  ║
  ║  Model: gpt-4o-mini (mcp-agent)             ║
  ║  Writes beginner solution with analogies    ║
  ║  Input: problem_text + pattern              ║
  ╚══════════════════════╤══════════════════════╝
                         │ solution output
                         ▼
  ╔═════════════════════════════════════════════╗
  ║  AGENT 6 — General Critic                  ║
  ║  Model: gpt-4o-mini (mcp-agent)             ║
  ║  Reviews: beginner tone, format, accuracy   ║
  ║  Score ≥ 4 → pass                           ║
  ║  Score ≤ 3 → Solution Agent retries         ║
  ╚══════════════════════╤══════════════════════╝
                         │ validated solution
                         ▼
  ╔═════════════════════════════════════════════╗
  ║  AGENT 7 — Complexity Agent                ║
  ║  Model: gpt-4o-mini (mcp-agent)             ║
  ║  Explains Big O + generates 2-Q quiz        ║
  ║  Input: problem_text + solution             ║
  ║  Also reviewed by Agent 6 (General Critic)  ║
  ╚══════════════════════╤══════════════════════╝
                         │ complexity + quiz
                         ▼
               Streamlit UI renders results

  ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─
  ON-DEMAND (triggered by user after seeing results)
  ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─

  User clicks "🔬 Research Pattern" (pattern wrong)
                         │
                         ▼
  ╔═════════════════════════════════════════════╗
  ║  AGENT 8 — Pattern Research Agent          ║
  ║  Model: gpt-4o (direct AsyncOpenAI)         ║
  ║  Identifies correct pattern + sub-pattern   ║
  ║  Extracts the key signal that was missed     ║
  ║  Writes lesson → pattern_knowledge.json     ║
  ║  Refreshes Classifier Agent (Agent 3)       ║
  ╚═════════════════════════════════════════════╝
```

---

## Agents — Full Reference

### 1. Browser Agent
- **Framework:** `mcp-agent` + Playwright MCP tool server
- **Model:** `gpt-4o-mini` (set in `mcp_agent.config.yaml`)
- **Job:** Navigate to the LeetCode URL, extract title, problem number, description, all examples with input/output/explanation, and constraints
- **Failure mode:** If scraping fails (login wall, CAPTCHA, Playwright error), sets `needs_fallback=True`. The Supervisor UI then shows a text area so the user can paste the problem manually and resume the pipeline

---

### 2. Planner Agent
- **Model:** `gpt-4o` (direct `AsyncOpenAI` call — not mcp-agent)
- **Job:** Read the problem text, output `STRATEGY: full` or `STRATEGY: simplified`
  - `full` → run the complete pipeline
  - `simplified` → note this is a trivially easy problem (single loop, under 10 lines)
- **Output:** Strategy + one-sentence reasoning, shown in Agent Log tab
- **Failure mode:** Defaults to `full` strategy silently

---

### 3. Classifier Agent
- **Model:** `gpt-4o` (direct `AsyncOpenAI` call — stronger reasoning than mini for pattern identification)
- **Grounding:** Injected with all 20 pattern names + `when_to_use` signals at prompt time, so it can **only** pick from the allowed list
- **Sub-pattern awareness:** Classifier instruction includes decision rules for the 4 most commonly confused pairs:
  - Sliding Window vs Two Pointers
  - BFS vs DFS
  - DP vs Backtracking (key rule: "number of ways / can we form X" = DP, not Backtracking)
  - Cyclic Sort vs prefix/hash
- **Self-correction:** After generating output, the **Classifier Critic** (gpt-4o-mini) scores correctness 1–5. If ≤ 3, the Classifier retries with the critique injected
- **Pattern Validator:** After generation, strips parenthetical qualifiers like `(2D DP)` before matching against `_VALID_PATTERN_NAMES`. If still invalid, asks classifier to re-pick from the exact list
- **Pattern Knowledge injection:** Lessons from `pattern_knowledge.json` (written by Pattern Research Agent) are injected into every classifier run, teaching it what mistakes were made on similar problems before

---

### 4. Classifier Critic (internal)
- **Model:** `gpt-4o-mini` (mcp-agent)
- **Job:** Correctness-only review — is this the right pattern? Not style.
- **Scores on:** Pattern correctness, reasoning accuracy, pattern name validity
- **Common mistakes it checks for:**
  - Sliding Window for string DP problems
  - Two Pointers for hash map problems
  - BFS/DFS when counting paths/ways needs DP
  - Backtracking when overlapping subproblems = DP
- **Differs from General Critic:** General Critic checks beginner-friendliness and format; Classifier Critic checks if the answer is factually right

---

### 5. Solution Agent
- **Model:** `gpt-4o-mini` (mcp-agent)
- **Job:** Given problem + pattern → write the cleanest solution with a story-based explanation
- **Tone:** Uses "Imagine..." analogies, "we" to include the reader, explains every technical word in brackets, short sentences only
- **Self-correction:** Reviewed by General Critic. Retries if score ≤ 3
- **Output format:** What Are We Trying To Do → The Big Idea → The Rules (→ format) → Code → Walk Through → Watch Out For

---

### 6. Complexity Agent
- **Model:** `gpt-4o-mini` (mcp-agent)
- **Job:** Explain time and space complexity using counting stories with real elements from the problem (not abstract "n"). Generate a 2-question multiple-choice quiz testing *why* the complexity is what it is
- **Self-correction:** Reviewed by General Critic. Retries if score ≤ 3
- **Output format:** Time story → Space story → Quick Take → Quiz (Q1 + Q2 with A/B/C options, ANSWER, HINT)

---

### 7. General Critic (internal)
- **Model:** `gpt-4o-mini` (mcp-agent)
- **Job:** Reviews Solution and Complexity agent output for beginner-friendliness, format compliance, accuracy, and use of "we" tone
- **Scoring:** 1–5. If ≤ 3 → original agent retries with critique injected. Lesson saved to `corrections.json`

---

### 8. Pattern Research Agent
- **Model:** `gpt-4o` (direct `AsyncOpenAI` call)
- **Trigger:** User clicks "🔬 Research Pattern" in the Pattern section expander after getting a wrong pattern
- **Job:**
  1. Reads the problem text + wrong pattern (pre-filled) + optional user correction
  2. Identifies the correct pattern **and** the specific sub-pattern (e.g. "2D Grid DP" within Dynamic Programming)
  3. Extracts the exact signal in the problem that should have triggered the correct pattern
  4. Writes a compact lesson to `pattern_knowledge.json`
  5. Refreshes the Classifier Agent in the current session so the next run immediately benefits
- **Sub-pattern library:** Uses all sub-patterns defined in `patterns.py` (DFS sub-types, DP sub-types, Backtracking sub-types, BFS sub-types) as grounding context
- **Output shown in UI:** Correct pattern → sub-pattern → why → signal → lesson saved confirmation

---

## Feedback — Which Section Affects Which Agents

This table answers: "if the user gives feedback on X, which agents learn from it and how?"

### Section → Agent Routing

| Section user gives feedback on | Agents that receive the feedback | Agents that are rebuilt immediately |
|-------------------------------|----------------------------------|-------------------------------------|
| **Pattern** (👍 or 👎) | Agent 3 — Classifier | Agent 3 + Agent 4 (Classifier Critic rebuilt too) |
| **Solution** (👍 or 👎) | Agent 5 — Solution | Agent 5 |
| **Complexity** (👍 or 👎) | Agent 7 — Complexity | Agent 7 |

> Agents 4, 6 (the Critics) and Agent 2 (Planner) never receive direct human feedback — they are internal reviewers only.
> Agent 8 (Pattern Research) is triggered separately and writes to `pattern_knowledge.json`, which feeds Agent 3.

---

### How Feedback Enters Each Agent's Instruction

Every agent's instruction is assembled by `_compose_instruction(base, agent_name)` at rebuild time. The feedback layers stack in this order:

```
Agent Instruction =
  [1] Base instruction (role, format, tone rules)
    +
  [2] Critic lessons from corrections.json
      "Lessons from past mistakes — always follow these:"
      e.g. "- Use an analogy in The Big Idea section"
    +
  [3] Judge lessons from judge_lessons.json
      "Evaluation feedback from past runs — fix these issues:"
      e.g. "- [Judge on 'Interleaving String'] Explanation Quality scored 2/5"
    +
  [4] Feedback rules from feedback_rules.json
      "Behavior rules learned from human feedback — follow these by default:"
      e.g. "- Do: use toy box analogies"
           "- Avoid: one-word explanations with no story"
    +
  [5] Feedback context from feedback.json
      "Users have loved this style before — match it:"
      e.g. - Example: "Imagine you have a row of toy boxes..."
      "Users have disliked this style before — avoid it:"
      e.g. - Bad example: "Use two pointers, one at each end..."

  [6] Pattern Knowledge (Classifier only) from pattern_knowledge.json
      "Pattern research lessons — apply these to avoid past mistakes:"
      e.g. "- Dynamic Programming [2D Grid DP]: Two string inputs + interleaving = 2D DP, NOT Sliding Window"
```

### Concrete Example — Pattern Feedback

```
User gives 👎 on Pattern with comment: "This should be Dynamic Programming, not Sliding Window"
                    │
    ┌───────────────┼──────────────────────────────┐
    │               │                              │
    ▼               ▼                              ▼
feedback.json   feedback_rules.json         [same session]
writes:         writes:                    Agent 3 (Classifier) rebuilt
{               "Avoid: This should        Agent 4 (Classifier Critic) rebuilt
  classifier:   be Dynamic Programming,    with updated instructions
  negative: [   not Sliding Window"
   snippet,                                Next run: Classifier instruction
   comment                                 includes layers [2]–[5] above
  ]
}
                                           During THIS regeneration:
                                           Classifier prompt also includes:
                                           "IMPORTANT: A user gave this feedback:
                                            'This should be Dynamic Programming,
                                             not Sliding Window.'
                                            Use that — the user is telling you
                                            the right answer."
                    │
                    ▼
        Cascade regeneration triggered:
        Pattern (Agent 3+4) → Solution (Agent 5+6) → Complexity (Agent 7+6)
        All three sections regenerated with the corrected pattern
```

### Concrete Example — Solution Feedback

```
User gives 👍 on Solution with comment: "loved the toy box analogy"
                    │
    ┌───────────────┼──────────────────────────────┐
    │               │                              │
    ▼               ▼                              ▼
feedback.json   feedback_rules.json         [same session]
writes:         writes:                    Agent 5 (Solution) rebuilt
{               "Do: loved the toy         with updated instructions
  solution:     box analogy"
  positive: [                              Next run: Solution instruction
   snippet,                                includes layer [4]:
   comment                                "Do: loved the toy box analogy"
  ]                                        and layer [5]:
}                                          "Users have loved this style:
                                            [snippet of the good output]"
                    │
                    ▼
        No regeneration — section stays as is
        Agent 5 only — Solution does NOT cascade to Complexity on positive feedback
```

---

## Feedback Loop — Full Flow

### 👍 Positive Feedback

```
User clicks 👍 on a section (Pattern / Solution / Complexity)
          │
          ▼
  Optional: user types a comment e.g. "loved the analogy"
          │
          ▼
  save_feedback(agent_name, "positive", snippet, comment)
  → writes to feedback.json (raw example)
  → save_feedback_rule(agent_name, "positive", comment)
     → "Do: loved the analogy" saved to feedback_rules.json
          │
          ▼
  refresh_agents([agent_name])
  → agent is rebuilt immediately in this Streamlit session
  → next run's instruction includes:
     "Users have loved this style before — match it: [example]"
     "Do: [rule]"
          │
          ▼
  No regeneration — the section stays as is
  UI shows: "Thanks for the 👍 — future runs will lean toward this style"
```

### 👎 Negative Feedback

```
User clicks 👎 on a section (Pattern / Solution / Complexity)
          │
          ▼
  Optional: user types a correction e.g. "this is Dynamic Programming"
          │
          ▼
  User clicks "Submit & Regenerate Section 🔄"
          │
          ▼
  save_feedback(agent_name, "negative", snippet, comment)
  → writes to feedback.json (raw example)
  → save_feedback_rule(agent_name, "negative", comment)
     → "Avoid: [snippet/comment]" saved to feedback_rules.json
          │
          ▼
  refresh_agents([agent_name])
  → agent rebuilt with latest rules injected into instruction
          │
          ▼
  Cascade regeneration:
  ┌─────────────────────────────────────────────────────┐
  │ Section disliked → what gets regenerated             │
  ├──────────────────┬──────────────────────────────────┤
  │ Pattern (👎)     │ Pattern → Solution → Complexity  │
  │ Solution (👎)    │ Solution → Complexity            │
  │ Complexity (👎)  │ Complexity only                  │
  └──────────────────┴──────────────────────────────────┘
          │
          ▼
  If user's comment contains a correction (e.g. "this is DP"):
  → Agent instruction includes:
     "IMPORTANT: A user gave this feedback: '[comment]'.
      If the feedback specifies a correct answer or pattern,
      use that — the user is telling you what the right answer is."
  → The correction IS the answer, not just a style note
          │
          ▼
  UI shows: "✅ [Section] feedback saved and used to regenerate the section"
```

### 📥 LLM Judge Feedback (from Evaluation Tab)

```
User runs evaluation → LLM Judge scores 6 dimensions 1–5
          │
          ▼
  Low scores (≤ 3) detected on any dimension
  → "📥 Apply Judge Feedback to Future Runs" button shown
          │
          ▼
  User clicks Apply
          │
          ▼
  save_judge_lessons(judge_scores, problem_title)
  → routes each low-scoring dimension to the responsible agent:
    ┌──────────────────────────┬────────────────┐
    │ Dimension                │ Agent          │
    ├──────────────────────────┼────────────────┤
    │ beginner_friendliness    │ solution       │
    │ solution_correctness     │ solution       │
    │ explanation_quality      │ solution       │
    │ complexity_accuracy      │ complexity     │
    │ quiz_quality             │ complexity     │
    │ pattern_accuracy         │ classifier     │
    └──────────────────────────┴────────────────┘
  → lesson written to judge_lessons.json per agent (last 5 kept)
          │
          ▼
  refresh_agents([affected agents])
  → agents rebuilt immediately
  → next run's instruction includes:
     "Evaluation feedback from past runs — fix these issues:
      - [Judge on 'Problem Title'] [Dimension] scored 2/5 — [summary]"
```

---

## Memory System — Persistence Files

| File | Written by | Read by | Purpose |
|------|-----------|--------|---------|
| `feedback.json` | Human 👍👎 | Agent Log UI | Raw likes/dislikes/comments per agent (last 5 each) |
| `feedback_rules.json` | `save_feedback_rule()` | `_compose_instruction()` | Compact "Do/Avoid" rules injected into agent instructions |
| `corrections.json` | General + Classifier Critics | `get_lessons()` | Lessons from low critic scores, injected into future runs |
| `judge_lessons.json` | LLM Judge (Evaluation tab) | `get_judge_lessons()` | Per-dimension lessons from low Judge scores |
| `pattern_knowledge.json` | Pattern Research Agent | `get_pattern_knowledge_for_classifier()` | Sub-pattern lessons injected into Classifier |
| `eval_history.json` | `run_full_evaluation()` | Evaluation tab history | Last 50 evaluation results for trend tracking |

### How memory stacks in every agent instruction

```
_compose_instruction(base, agent_name):
    base instruction
    + Critic lessons from corrections.json        ← "Lessons from past mistakes"
    + Judge lessons from judge_lessons.json        ← "Evaluation feedback from past runs"
    + Feedback rules from feedback_rules.json      ← "Behavior rules learned from human feedback"
    + Feedback context from feedback.json          ← positive/negative examples
    [+ Pattern Knowledge from pattern_knowledge.json]  ← classifier only
```

---

## Pattern Library — 20 Patterns with Sub-Patterns

Each pattern has: description, when-to-use signals (including NOT signals), sub-patterns, code template, example problems.

| # | Pattern | Key Sub-Patterns |
|---|---------|-----------------|
| 1 | Two Pointers | — |
| 2 | Sliding Window | — |
| 3 | Fast & Slow Pointers | — |
| 4 | Binary Search | — |
| 5 | BFS | Multi-source BFS, 0-1 BFS, BFS on implicit graph |
| 6 | DFS | Tree DFS, Island/Flood Fill DFS, Cycle Detection DFS, Memoized DFS |
| 7 | Backtracking | Permutations, Combinations/Subsets, Grid/Matrix, Constraint Satisfaction |
| 8 | Dynamic Programming | 1D Linear DP, 2D/Grid DP, Knapsack DP, Interval DP, Tree DP, String DP |
| 9 | Monotonic Stack | — |
| 10 | Top K Elements | — |
| 11 | Merge Intervals | — |
| 12 | Prefix Sum | — |
| 13 | Cyclic Sort | — |
| 14 | Topological Sort | — |
| 15 | Union Find (Disjoint Set) | — |
| 16 | Trie (Prefix Tree) | — |
| 17 | Two Heaps | — |
| 18 | Subsets / Combinations | — |
| 19 | Bit Manipulation | — |
| 20 | Divide & Conquer | — |

**NOT signals** are embedded in each pattern's `when_to_use` list to prevent cross-pattern confusion. Examples:
- BFS: "NOT for counting paths or number-of-ways problems — those need DP"
- DFS: "NOT when you need shortest path — use BFS instead"
- Backtracking: "NOT for counting solutions — if only the COUNT is needed, use DP"
- Dynamic Programming: "NOT for generating ALL solutions (use Backtracking) — DP only counts or optimizes"

---

## Evaluation — Tab 4

### RAGAS Metrics (automated, on-demand)
Uses `LangchainLLMWrapper` + `EvaluationDataset.from_list()` — same pattern as RAGPythonApp.

| Metric | What it measures | Context used |
|--------|-----------------|-------------|
| **Faithfulness** | Does the walkthrough stay faithful to the code? No invented steps? | Code block extracted from solution as retrieved context |
| **Response Relevancy** | Does the solution actually address the problem asked? On-topic, non-redundant? | Problem text as user_input |

### LLM-as-Judge (6 dimensions)
gpt-4o-mini scores each dimension 1–5:

| Dimension | What it checks |
|-----------|--------------|
| Beginner Friendliness | Simple words, analogies, no jargon |
| Pattern Accuracy | Is the pattern actually correct? |
| Solution Correctness | Is the logic right? Does it solve the problem? |
| Explanation Quality | Does the walkthrough match the code? |
| Complexity Accuracy | Is the Big O analysis correct and well-reasoned? |
| Quiz Quality | Are the 2 questions educational and testing the right concept? |

Low scores (≤ 3) surface a button to apply the feedback to future runs → routes lesson to the responsible agent via `judge_lessons.json`.

### Pattern Accuracy (Ground Truth)
Checks against a dataset of 57 hand-labeled problems. **Only shown when the problem is in the dataset** — no noisy "not found" messages for unknown problems.

---

## Streamlit UI — Tabs

### Tab 1: Problem Solver
- **Input:** URL text field + "Analyze Problem" button
- **Results rendered in 3 sections with per-section feedback:**

  | Section | 👍 Effect | 👎 Effect |
  |---------|-----------|----------|
  | Pattern | Saves positive style example | Regenerates Pattern → Solution → Complexity |
  | Solution | Saves positive style example | Regenerates Solution → Complexity |
  | Complexity | Saves positive style example | Regenerates Complexity only |

- **Pattern Research expander:** Always visible below the Pattern section. If the pattern is wrong, user can type the correct one, click "Research Pattern" → gpt-4o researches the correct sub-pattern and saves a lesson
- **Fallback UI:** Appears only when Browser Agent fails — text area to paste the problem manually
- **Interactive Quiz:** A/B/C radio buttons per question, "Check Answer" button reveals correct/incorrect + hint

### Tab 2: Pattern Library
- Search bar filtering by name or description
- Each of the 20 patterns shows: description, when-to-use signals, **sub-patterns** (where defined), code template, example problem links

### Tab 3: Agent Log
- Summary metrics: Steps Run / Succeeded / Failed / Self-Corrected
- Planner Strategy + Model shown
- Per-agent expandable rows with duration, status, self-correction attempt scores
- Human Feedback Log (raw)
- Learned Feedback Rules (compact)
- Critic Lessons Learned (from `corrections.json`)

### Tab 4: Evaluation
- "Evaluate This Run" button (only enabled after a problem is analyzed)
- RAGAS: Faithfulness + Response Relevancy scores
- LLM Judge: 6-dimension scorecard + overall + summary sentence
- "Apply Judge Feedback" button for low-scoring dimensions
- Evaluation History: last 10 runs in a table + Overall Score trend line chart

---

## Model Tiering

| Agent | Model | Why |
|-------|-------|-----|
| Planner | `gpt-4o` | Strategy decisions need best reasoning |
| Classifier | `gpt-4o` | Pattern identification: surface-level keyword matching fails on hard problems |
| Pattern Research Agent | `gpt-4o` | Deep reasoning about sub-patterns and problem structure |
| Solution | `gpt-4o-mini` | Explanation writing — good quality at low cost |
| Complexity | `gpt-4o-mini` | Explanation writing — good quality at low cost |
| General Critic | `gpt-4o-mini` | Style evaluation — mini is sufficient |
| Classifier Critic | `gpt-4o-mini` | Correctness spot-check — mini is sufficient |
| LLM Judge | `gpt-4o-mini` | 6-dimension scoring — mini is sufficient |

Note: mcp-agent agents (`solution`, `complexity`, `critic`) use the model set in `mcp_agent.config.yaml`. Planner, Classifier, and Pattern Research Agent bypass mcp-agent and call `AsyncOpenAI` directly to use `gpt-4o`.

---

## Tech Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **UI** | Streamlit | Web interface, tabs, quiz, feedback buttons |
| **Agent Framework** | `mcp-agent` | Connects LLMs to MCP tool servers |
| **LLM** | OpenAI `gpt-4o` + `gpt-4o-mini` | Full model for reasoning-heavy agents, mini for the rest |
| **Browser Control** | Playwright (`@playwright/mcp`) | Scrapes LeetCode problem content |
| **Evaluation** | RAGAS + `langchain-openai` | Faithfulness + Response Relevancy scoring |
| **Async** | `asyncio` | Handles async multi-agent pipeline inside Streamlit |
| **HTTP** | `httpx` | LeetCode GraphQL API for keyword search (fallback from local dataset) |

---

## Project Structure

```
LeetCoach/
├── main.py                         # Streamlit app — 4 tabs, quiz, feedback UI, evaluation
├── agents.py                       # All agent logic: pipeline, self-correction, feedback, memory
├── patterns.py                     # 20 patterns with sub-patterns, signals, templates, examples
├── pattern_research_agent.py       # Pattern Research Agent — gpt-4o, writes to pattern_knowledge.json
├── evaluation.py                   # RAGAS + LLM Judge + ground truth accuracy check
├── ground_truth.py                 # 57 hand-labeled problems for pattern accuracy evaluation
├── feedback.json                   # Auto-generated — raw human likes/dislikes (gitignored)
├── feedback_rules.json             # Auto-generated — compact Do/Avoid rules (gitignored)
├── corrections.json                # Auto-generated — critic lessons across sessions (gitignored)
├── judge_lessons.json              # Auto-generated — LLM Judge low-score lessons (gitignored)
├── pattern_knowledge.json          # Auto-generated — Pattern Research Agent lessons (gitignored)
├── eval_history.json               # Auto-generated — last 50 evaluation results (gitignored)
├── mcp_agent.config.yaml           # MCP config — model, logging, Playwright server
├── mcp_agent.secrets.yaml          # API key (gitignored)
├── mcp_agent.secrets.yaml.example  # Template
├── requirements.txt                # Python dependencies
└── PRODUCT_SPEC.md                 # This file
```

---

## Error Handling

| Error | Behaviour |
|-------|-----------|
| LeetCode login wall / CAPTCHA | Browser Agent fails gracefully, Supervisor shows paste-text fallback |
| OpenAI API key missing | Clear error before any execution |
| LLM generation failure | Agent marked as failed in log, downstream agents skipped with log entry |
| Pattern not in allowed list | Validator auto-corrects by asking classifier to re-pick from exact list |
| RAGAS not installed | Evaluation tab shows install instructions, rest of app unaffected |
| Pattern Research Agent error | Error shown inline in expander, pipeline unaffected |

---

## Limitations

- LeetCode may require login for some problems — paste text fallback handles this
- Pattern classification is probabilistic — the 3-layer fix (gpt-4o + correctness critic + pattern knowledge) greatly improves accuracy but is not perfect
- No code execution — solution is generated but not run/validated automatically
- RAGAS scoring can be slow (10–20s) — it calls gpt-4o-mini as judge internally
- Pattern Research Agent requires a problem to already be analyzed in the current session before it can be triggered
