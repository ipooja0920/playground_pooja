import time
import json
import re
from pathlib import Path
from datetime import datetime
from mcp_agent.agents.agent import Agent
from mcp_agent.workflows.llm.augmented_llm_openai import OpenAIAugmentedLLM
from mcp_agent.workflows.llm.augmented_llm import RequestParams

CORRECTIONS_FILE = Path(__file__).parent / "corrections.json"

# --------------------------------------------------------------------------- #
#  Corrections store — agents learn from past mistakes across sessions
# --------------------------------------------------------------------------- #

def load_corrections() -> dict:
    if CORRECTIONS_FILE.exists():
        with open(CORRECTIONS_FILE) as f:
            return json.load(f)
    return {"classifier": [], "solution": [], "complexity": []}

def save_correction(agent_name: str, issue: str, suggestion: str):
    corrections = load_corrections()
    if agent_name not in corrections:
        corrections[agent_name] = []
    corrections[agent_name].append({
        "timestamp": datetime.now().isoformat(),
        "issue": issue,
        "suggestion": suggestion,
    })
    corrections[agent_name] = corrections[agent_name][-5:]  # keep last 5 per agent
    with open(CORRECTIONS_FILE, "w") as f:
        json.dump(corrections, f, indent=2)

def get_lessons(agent_name: str) -> str:
    """Return past lesson strings to inject into agent instructions."""
    corrections = load_corrections()
    lessons = corrections.get(agent_name, [])[-3:]
    if not lessons:
        return ""
    lines = "\n".join(f"- {c['suggestion']}" for c in lessons)
    return f"\n\n**Lessons from past mistakes — always follow these:**\n{lines}"


# --------------------------------------------------------------------------- #
#  Agent instructions
# --------------------------------------------------------------------------- #

BROWSER_INSTRUCTION = """
You are a web scraping agent. Go to the given LeetCode problem URL and extract:
- Problem title and number
- Full problem description
- All examples with input, output, and explanation
- Constraints

Return only the raw problem content. Do not solve it.
"""

CLASSIFIER_INSTRUCTION = """
You are an algorithm pattern expert. Given a LeetCode problem, identify which pattern solves it.

Use this EXACT format:

## 🎯 Pattern
[Pattern name]

## Why This Pattern?
[2-3 short sentences. Mention specific clues from the problem that point to this pattern.
Write like you're explaining to a friend who just started coding. No jargon.]

## The Key Trick
Complete this sentence in one line: "The trick is to..."

## Difficulty
[Easy / Medium / Hard]
"""

SOLUTION_INSTRUCTION = """
You are an algorithm teacher who explains things like a patient friend, not a textbook.
Your explanations must be beginner-level — short sentences, no jargon, use → for conditions.

Use this EXACT format:

## 🧠 Intuition
[1-2 sentences. Explain the core idea. Pretend you're talking to someone who just learned arrays.
Use "we" — talk WITH the reader, not AT them.]

## 📋 How It Works
[Use → format for the logic. Short. Punchy. Like this:
- condition → what we do
- condition → what we do
- otherwise → what we do]

## ✅ Solution
```python
# clean, well-commented code here
```

## 🚶 Step-by-Step Walkthrough
[Walk through the code step by step. Each step = one sentence. Start with "We..."]

## 🧪 Edge Cases
[2-3 bullet points. Short.]
"""

COMPLEXITY_INSTRUCTION = """
You are an expert at explaining complexity in the simplest possible way.
No verbose headers. No "what it means in plain English". Just explain directly like a friend.

Use this EXACT format:

## ⏱ Time: O(?)
[One sentence — explain what O(?) means FOR THIS SPECIFIC PROBLEM. Not generic.
Example: "We visit every node exactly once, so if there are n nodes, we do n steps."]

## 💾 Space: O(?)
[One sentence — what memory do we use and why.]

## ⚡ Quick Take
- Time: O(?) — [5 words max]
- Space: O(?) — [5 words max]
"""

CRITIC_INSTRUCTION = """
You are a strict quality evaluator for algorithm explanations aimed at beginners.

Evaluate the given output on these criteria:
- Is it beginner-friendly? (no jargon, short sentences)
- Does it follow the required format?
- Is the explanation accurate?
- Is the tone friendly but professional?

Respond in EXACTLY this format (no extra text):
SCORE: [1-5]
ISSUES: [comma-separated issues, or "none"]
SUGGESTION: [one actionable sentence on how to improve it]

Scoring guide:
5 = Perfect — beginner-friendly, correct, right format
4 = Good — minor issues
3 = Acceptable — some jargon or slight verbosity
2 = Poor — too technical or confusing for beginners
1 = Wrong — incorrect or useless
"""


# --------------------------------------------------------------------------- #
#  Agent setup
# --------------------------------------------------------------------------- #

async def setup_agents(mcp_agent_app):
    """Initialize all agents. Returns dict of LLMs."""
    agents = {}

    browser = Agent(name="browser", instruction=BROWSER_INSTRUCTION, server_names=["playwright"])
    await browser.initialize()
    agents["browser_llm"] = await browser.attach_llm(OpenAIAugmentedLLM)

    classifier = Agent(
        name="classifier",
        instruction=CLASSIFIER_INSTRUCTION + get_lessons("classifier"),
        server_names=[],
    )
    await classifier.initialize()
    agents["classifier_llm"] = await classifier.attach_llm(OpenAIAugmentedLLM)

    solution = Agent(
        name="solution",
        instruction=SOLUTION_INSTRUCTION + get_lessons("solution"),
        server_names=[],
    )
    await solution.initialize()
    agents["solution_llm"] = await solution.attach_llm(OpenAIAugmentedLLM)

    complexity = Agent(
        name="complexity",
        instruction=COMPLEXITY_INSTRUCTION + get_lessons("complexity"),
        server_names=[],
    )
    await complexity.initialize()
    agents["complexity_llm"] = await complexity.attach_llm(OpenAIAugmentedLLM)

    critic = Agent(name="critic", instruction=CRITIC_INSTRUCTION, server_names=[])
    await critic.initialize()
    agents["critic_llm"] = await critic.attach_llm(OpenAIAugmentedLLM)

    return agents


# --------------------------------------------------------------------------- #
#  Self-correction helper
# --------------------------------------------------------------------------- #

def _parse_score(critique: str) -> tuple[int, str, str]:
    """Extract score, issues, suggestion from critic output."""
    try:
        score_match = re.search(r"SCORE:\s*(\d)", critique)
        issues_match = re.search(r"ISSUES:\s*(.+)", critique)
        suggestion_match = re.search(r"SUGGESTION:\s*(.+)", critique)
        score = int(score_match.group(1)) if score_match else 3
        issues = issues_match.group(1).strip() if issues_match else "unknown"
        suggestion = suggestion_match.group(1).strip() if suggestion_match else ""
        return score, issues, suggestion
    except Exception:
        return 3, "parse error", ""


async def run_with_self_correction(
    agent_llm,
    critic_llm,
    message: str,
    agent_name: str,
    max_tokens: int = 2000,
) -> tuple[str, list]:
    """
    Run an agent, have the critic evaluate, retry once if score <= 3.
    Returns (final_output, correction_log_entries).
    """
    correction_log = []

    # First attempt
    result = await agent_llm.generate_str(
        message=message,
        request_params=RequestParams(use_history=False, maxTokens=max_tokens),
    )

    # Critic evaluation
    critique = await critic_llm.generate_str(
        message=f"Evaluate this output:\n\n{result}",
        request_params=RequestParams(use_history=False, maxTokens=300),
    )
    score, issues, suggestion = _parse_score(critique)

    correction_log.append({
        "attempt": 1,
        "score": score,
        "issues": issues,
    })

    if score <= 3:
        # Save lesson for future sessions
        if suggestion:
            save_correction(agent_name, issues, suggestion)

        # Retry with critique context
        retry_message = (
            f"{message}\n\n"
            f"Your previous attempt scored {score}/5. Issues: {issues}. "
            f"Fix: {suggestion}. Try again and address these issues."
        )
        result = await agent_llm.generate_str(
            message=retry_message,
            request_params=RequestParams(use_history=False, maxTokens=max_tokens),
        )

        # Re-evaluate
        critique2 = await critic_llm.generate_str(
            message=f"Evaluate this output:\n\n{result}",
            request_params=RequestParams(use_history=False, maxTokens=300),
        )
        score2, issues2, _ = _parse_score(critique2)
        correction_log.append({
            "attempt": 2,
            "score": score2,
            "issues": issues2,
        })

    return result, correction_log


# --------------------------------------------------------------------------- #
#  Pipeline runner
# --------------------------------------------------------------------------- #

async def run_pipeline(url: str, agents: dict) -> tuple[dict, list]:
    """
    Run the 4-agent pipeline with self-correction.

    Returns:
        results: dict with problem_text, pattern, solution, complexity
        log:     list of log entries per agent (status, details, duration, corrections)
    """
    log = []
    results = {
        "problem_text": None,
        "pattern": None,
        "solution": None,
        "complexity": None,
    }

    # ------------------------------------------------------------------ #
    # Agent 1 — Browser
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
            "corrections": [],
        })
    except Exception as e:
        duration = round(time.time() - t0, 1)
        log.append({
            "agent": "Browser Agent",
            "status": "failed",
            "details": str(e),
            "duration": duration,
            "corrections": [],
        })
        for name in ["Classifier Agent", "Solution Agent", "Complexity Agent"]:
            log.append({"agent": name, "status": "skipped",
                        "details": "Skipped — Browser Agent failed", "duration": 0, "corrections": []})
        return results, log

    # ------------------------------------------------------------------ #
    # Agent 2 — Classifier (with self-correction)
    # ------------------------------------------------------------------ #
    t0 = time.time()
    try:
        pattern, corrections = await run_with_self_correction(
            agents["classifier_llm"],
            agents["critic_llm"],
            message=f"Here is the LeetCode problem:\n\n{results['problem_text']}",
            agent_name="classifier",
            max_tokens=800,
        )
        duration = round(time.time() - t0, 1)
        results["pattern"] = pattern
        retried = len(corrections) > 1
        log.append({
            "agent": "Classifier Agent",
            "status": "success",
            "details": f"Pattern identified in {duration}s" + (" (self-corrected)" if retried else ""),
            "duration": duration,
            "corrections": corrections,
        })
    except Exception as e:
        duration = round(time.time() - t0, 1)
        log.append({
            "agent": "Classifier Agent",
            "status": "failed",
            "details": str(e),
            "duration": duration,
            "corrections": [],
        })
        for name in ["Solution Agent", "Complexity Agent"]:
            log.append({"agent": name, "status": "skipped",
                        "details": "Skipped — Classifier Agent failed", "duration": 0, "corrections": []})
        return results, log

    # ------------------------------------------------------------------ #
    # Agent 3 — Solution (with self-correction)
    # ------------------------------------------------------------------ #
    t0 = time.time()
    try:
        solution, corrections = await run_with_self_correction(
            agents["solution_llm"],
            agents["critic_llm"],
            message=(
                f"Problem:\n{results['problem_text']}\n\n"
                f"Pattern:\n{results['pattern']}"
            ),
            agent_name="solution",
            max_tokens=2500,
        )
        duration = round(time.time() - t0, 1)
        results["solution"] = solution
        retried = len(corrections) > 1
        log.append({
            "agent": "Solution Agent",
            "status": "success",
            "details": f"Solution generated in {duration}s" + (" (self-corrected)" if retried else ""),
            "duration": duration,
            "corrections": corrections,
        })
    except Exception as e:
        duration = round(time.time() - t0, 1)
        log.append({
            "agent": "Solution Agent",
            "status": "failed",
            "details": str(e),
            "duration": duration,
            "corrections": [],
        })
        log.append({"agent": "Complexity Agent", "status": "skipped",
                    "details": "Skipped — Solution Agent failed", "duration": 0, "corrections": []})
        return results, log

    # ------------------------------------------------------------------ #
    # Agent 4 — Complexity (with self-correction)
    # ------------------------------------------------------------------ #
    t0 = time.time()
    try:
        complexity, corrections = await run_with_self_correction(
            agents["complexity_llm"],
            agents["critic_llm"],
            message=(
                f"Problem:\n{results['problem_text']}\n\n"
                f"Solution:\n{results['solution']}"
            ),
            agent_name="complexity",
            max_tokens=600,
        )
        duration = round(time.time() - t0, 1)
        results["complexity"] = complexity
        retried = len(corrections) > 1
        log.append({
            "agent": "Complexity Agent",
            "status": "success",
            "details": f"Complexity explained in {duration}s" + (" (self-corrected)" if retried else ""),
            "duration": duration,
            "corrections": corrections,
        })
    except Exception as e:
        duration = round(time.time() - t0, 1)
        log.append({
            "agent": "Complexity Agent",
            "status": "failed",
            "details": str(e),
            "duration": duration,
            "corrections": [],
        })

    return results, log
