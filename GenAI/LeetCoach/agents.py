import time
from mcp_agent.agents.agent import Agent
from mcp_agent.workflows.llm.augmented_llm_openai import OpenAIAugmentedLLM
from mcp_agent.workflows.llm.augmented_llm import RequestParams

# --------------------------------------------------------------------------- #
#  Agent instructions
# --------------------------------------------------------------------------- #

BROWSER_INSTRUCTION = """
You are a web scraping agent. Your only job is to visit a LeetCode problem URL
and extract the following in plain text:
  - Problem title and number
  - Full problem description
  - All examples (input, output, explanation)
  - Constraints

Do not solve the problem. Just return the raw problem content as clearly as possible.
"""

CLASSIFIER_INSTRUCTION = """
You are an expert algorithm pattern classifier with deep knowledge of all major
LeetCode problem-solving patterns.

Given a LeetCode problem, identify which algorithmic pattern(s) best solve it.

Respond in this exact format:

## Pattern(s) Identified
[Pattern name(s)]

## Why This Pattern Fits
[2-4 sentences explaining the tell-tale signs in this problem that point to this pattern.
Be specific — mention details from the problem description.]

## Difficulty
[Easy / Medium / Hard]

## Key Insight
[One sentence — the single most important thing to realize to solve this problem]
"""

SOLUTION_INSTRUCTION = """
You are an expert algorithm teacher who specializes in writing crystal-clear solutions
that anyone can understand.

Given a LeetCode problem and its pattern, write:
1. The most readable AND optimized solution in Python
2. A plain-English walkthrough — explain what each block of code does as if
   explaining to someone who just learned Python. No jargon.
3. Edge cases handled

Respond in this exact format:

## Solution

```python
# [your code here — well commented]
```

## How It Works (Plain English)
[Step-by-step explanation. Use simple words. Refer to specific lines of code.]

## Edge Cases
[List 2-3 edge cases and how the code handles them]
"""

COMPLEXITY_INSTRUCTION = """
You are an expert at explaining time and space complexity in the simplest possible way.

Given a solution to a LeetCode problem, explain its complexity without jargon.
Pretend you are explaining to someone who just heard the term "Big O" for the first time.

Respond in this exact format:

## Time Complexity: O(?)
**What it means in plain English:**
[Explain as if the person has never heard of Big O. Use analogies if helpful.
Example: "If the array has 10 elements it does ~30 steps, 100 elements → ~300 steps."]

**Why:**
[Walk through the code and count the operations — which loop causes what cost]

## Space Complexity: O(?)
**What it means in plain English:**
[How much extra memory does the code use as input grows?]

**Why:**
[Which variables, data structures, or call stack cause this memory usage]

## Quick Summary
[One sentence each for time and space in the simplest possible terms]
"""


# --------------------------------------------------------------------------- #
#  Agent setup (called once, stored in session state)
# --------------------------------------------------------------------------- #

async def setup_agents(mcp_agent_app):
    """
    Initialize all 4 agents and attach LLMs.
    Returns a dict: { "browser_llm", "classifier_llm", "solution_llm", "complexity_llm" }
    """
    agents = {}

    # --- Browser agent (uses Playwright MCP) ---
    browser = Agent(
        name="browser",
        instruction=BROWSER_INSTRUCTION,
        server_names=["playwright"],
    )
    await browser.initialize()
    agents["browser_llm"] = await browser.attach_llm(OpenAIAugmentedLLM)

    # --- Classifier agent (LLM only) ---
    classifier = Agent(
        name="classifier",
        instruction=CLASSIFIER_INSTRUCTION,
        server_names=[],
    )
    await classifier.initialize()
    agents["classifier_llm"] = await classifier.attach_llm(OpenAIAugmentedLLM)

    # --- Solution agent (LLM only) ---
    solution = Agent(
        name="solution",
        instruction=SOLUTION_INSTRUCTION,
        server_names=[],
    )
    await solution.initialize()
    agents["solution_llm"] = await solution.attach_llm(OpenAIAugmentedLLM)

    # --- Complexity agent (LLM only) ---
    complexity = Agent(
        name="complexity",
        instruction=COMPLEXITY_INSTRUCTION,
        server_names=[],
    )
    await complexity.initialize()
    agents["complexity_llm"] = await complexity.attach_llm(OpenAIAugmentedLLM)

    return agents


# --------------------------------------------------------------------------- #
#  Pipeline runner
# --------------------------------------------------------------------------- #

async def run_pipeline(url: str, agents: dict) -> tuple[dict, list]:
    """
    Run the 4-agent pipeline sequentially.

    Returns:
        results: dict with keys problem_text, pattern, solution, complexity
        log:     list of dicts with keys agent, status, details, duration
    """
    log = []
    results = {
        "problem_text": None,
        "pattern": None,
        "solution": None,
        "complexity": None,
    }

    # ------------------------------------------------------------------ #
    # Agent 1 — Browser: scrape the LeetCode problem
    # ------------------------------------------------------------------ #
    t0 = time.time()
    try:
        problem_text = await agents["browser_llm"].generate_str(
            message=(
                f"Go to this LeetCode problem URL: {url}\n"
                "Extract the full problem: title, number, description, all examples, and constraints."
            ),
            request_params=RequestParams(use_history=False, maxTokens=3000),
        )
        duration = round(time.time() - t0, 1)
        results["problem_text"] = problem_text
        log.append({
            "agent": "Browser Agent",
            "status": "success",
            "details": f"Scraped problem in {duration}s",
            "duration": duration,
        })
    except Exception as e:
        duration = round(time.time() - t0, 1)
        log.append({
            "agent": "Browser Agent",
            "status": "failed",
            "details": str(e),
            "duration": duration,
        })
        # All downstream agents are skipped if browser fails
        for name in ["Classifier Agent", "Solution Agent", "Complexity Agent"]:
            log.append({
                "agent": name,
                "status": "skipped",
                "details": "Skipped — Browser Agent failed",
                "duration": 0,
            })
        return results, log

    # ------------------------------------------------------------------ #
    # Agent 2 — Classifier: identify the pattern
    # ------------------------------------------------------------------ #
    t0 = time.time()
    try:
        pattern = await agents["classifier_llm"].generate_str(
            message=f"Here is the LeetCode problem:\n\n{results['problem_text']}",
            request_params=RequestParams(use_history=False, maxTokens=1000),
        )
        duration = round(time.time() - t0, 1)
        results["pattern"] = pattern
        log.append({
            "agent": "Classifier Agent",
            "status": "success",
            "details": f"Pattern identified in {duration}s",
            "duration": duration,
        })
    except Exception as e:
        duration = round(time.time() - t0, 1)
        log.append({
            "agent": "Classifier Agent",
            "status": "failed",
            "details": str(e),
            "duration": duration,
        })
        for name in ["Solution Agent", "Complexity Agent"]:
            log.append({
                "agent": name,
                "status": "skipped",
                "details": "Skipped — Classifier Agent failed",
                "duration": 0,
            })
        return results, log

    # ------------------------------------------------------------------ #
    # Agent 3 — Solution: write the code + explanation
    # ------------------------------------------------------------------ #
    t0 = time.time()
    try:
        solution = await agents["solution_llm"].generate_str(
            message=(
                f"Problem:\n{results['problem_text']}\n\n"
                f"Pattern identified:\n{results['pattern']}"
            ),
            request_params=RequestParams(use_history=False, maxTokens=3000),
        )
        duration = round(time.time() - t0, 1)
        results["solution"] = solution
        log.append({
            "agent": "Solution Agent",
            "status": "success",
            "details": f"Solution generated in {duration}s",
            "duration": duration,
        })
    except Exception as e:
        duration = round(time.time() - t0, 1)
        log.append({
            "agent": "Solution Agent",
            "status": "failed",
            "details": str(e),
            "duration": duration,
        })
        log.append({
            "agent": "Complexity Agent",
            "status": "skipped",
            "details": "Skipped — Solution Agent failed",
            "duration": 0,
        })
        return results, log

    # ------------------------------------------------------------------ #
    # Agent 4 — Complexity: explain time/space complexity
    # ------------------------------------------------------------------ #
    t0 = time.time()
    try:
        complexity = await agents["complexity_llm"].generate_str(
            message=(
                f"Problem:\n{results['problem_text']}\n\n"
                f"Solution:\n{results['solution']}"
            ),
            request_params=RequestParams(use_history=False, maxTokens=1000),
        )
        duration = round(time.time() - t0, 1)
        results["complexity"] = complexity
        log.append({
            "agent": "Complexity Agent",
            "status": "success",
            "details": f"Complexity explained in {duration}s",
            "duration": duration,
        })
    except Exception as e:
        duration = round(time.time() - t0, 1)
        log.append({
            "agent": "Complexity Agent",
            "status": "failed",
            "details": str(e),
            "duration": duration,
        })

    return results, log
