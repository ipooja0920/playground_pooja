import time
import json
import re
from pathlib import Path
from datetime import datetime
from mcp_agent.agents.agent import Agent
from mcp_agent.workflows.llm.augmented_llm_openai import OpenAIAugmentedLLM
from mcp_agent.workflows.llm.augmented_llm import RequestParams

CORRECTIONS_FILE = Path(__file__).parent / "corrections.json"
FEEDBACK_FILE    = Path(__file__).parent / "feedback.json"

# --------------------------------------------------------------------------- #
#  Corrections store — critic-driven, auto-saved after low scores
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
    corrections[agent_name] = corrections[agent_name][-5:]
    with open(CORRECTIONS_FILE, "w") as f:
        json.dump(corrections, f, indent=2)

def get_lessons(agent_name: str) -> str:
    corrections = load_corrections()
    lessons = corrections.get(agent_name, [])[-3:]
    if not lessons:
        return ""
    lines = "\n".join(f"- {c['suggestion']}" for c in lessons)
    return f"\n\n**Lessons from past mistakes — always follow these:**\n{lines}"


# --------------------------------------------------------------------------- #
#  Human feedback store — like/dislike + optional comment from the UI
# --------------------------------------------------------------------------- #

def load_feedback() -> dict:
    if FEEDBACK_FILE.exists():
        with open(FEEDBACK_FILE) as f:
            return json.load(f)
    return {"classifier": {"positive": [], "negative": []},
            "solution":   {"positive": [], "negative": []},
            "complexity":  {"positive": [], "negative": []}}

def save_feedback(agent_name: str, sentiment: str, snippet: str, comment: str = ""):
    """sentiment: 'positive' or 'negative'"""
    feedback = load_feedback()
    if agent_name not in feedback:
        feedback[agent_name] = {"positive": [], "negative": []}
    feedback[agent_name][sentiment].append({
        "timestamp": datetime.now().isoformat(),
        "snippet": snippet[:300],
        "comment": comment,
    })
    # Keep last 5 of each type per agent
    feedback[agent_name][sentiment] = feedback[agent_name][sentiment][-5:]
    with open(FEEDBACK_FILE, "w") as f:
        json.dump(feedback, f, indent=2)

def get_feedback_context(agent_name: str) -> str:
    """Build a prompt block from past human feedback to inject into agent instructions."""
    feedback = load_feedback()
    agent_fb = feedback.get(agent_name, {"positive": [], "negative": []})

    positives = agent_fb["positive"][-2:]
    negatives = agent_fb["negative"][-2:]

    if not positives and not negatives:
        return ""

    lines = []
    if positives:
        lines.append("\n**Users have loved this style before — match it:**")
        for fb in positives:
            comment = f' — user said: "{fb["comment"]}"' if fb["comment"] else ""
            lines.append(f'- Example: "{fb["snippet"][:150]}..."{comment}')

    if negatives:
        lines.append("\n**Users have disliked this style before — avoid it:**")
        for fb in negatives:
            comment = f' — user said: "{fb["comment"]}"' if fb["comment"] else ""
            lines.append(f'- Bad example: "{fb["snippet"][:150]}..."{comment}')

    return "\n" + "\n".join(lines)


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
[2-3 short sentences. Pretend you're explaining to a curious 10-year-old.
Point to specific clues in the problem. No jargon — if you use a word like "sorted", explain why that matters.]

## The Key Trick
Complete this sentence in one line: "The trick is to..."

## Difficulty
[Easy / Medium / Hard]
"""

SOLUTION_INSTRUCTION = """
You explain algorithms like you are talking to a 5-year-old who loves stories.
Use everyday analogies — toys, books, boxes, a line of people. Keep every sentence short.
Never use words like "iterate", "traverse", "pointer", "index" without explaining them first.

Use this EXACT format:

## 🧠 What Are We Trying To Do?
[1-2 sentences. Explain the problem in the simplest possible words.
Pretend the problem involves real objects a child would understand. No code words.]

## 💡 The Big Idea
[The core trick explained using an analogy from real life.
Start with "Imagine..." and use something a child would relate to — toys, snacks, books.]

## 📋 The Rules
[Use → to show the decisions the code makes. Super short:
- this situation → we do this
- that situation → we do that]

## ✅ The Code
```python
# well-commented code
```

## 🚶 Let's Walk Through It Together
[Walk through the code using the same analogy from The Big Idea.
Each step = one sentence. Start with "We...". Avoid technical words.
If you must use a technical word, explain it in brackets like: pointer [think of it as a finger pointing at a spot].]

## 🧪 Watch Out For
[2 edge cases. One sentence each. Simple words only.]
"""

COMPLEXITY_INSTRUCTION = """
You explain time complexity like you are talking to a curious 5-year-old.
Use counting stories. Use real-world analogies. Never say "logarithmic" or "amortized" without a story.

Use this EXACT format:

## ⏱ Time: O(?)
[Tell a counting story for THIS specific problem. Example style:
"Imagine you have a row of 5 toy boxes. We open each one exactly once to look inside.
5 boxes → 5 looks. 100 boxes → 100 looks. So the time grows with the number of boxes. That's O(n)."
Use the actual elements of this problem (array, nodes, characters, etc.) in your story.]

## 💾 Space: O(?)
[What extra memory do we use? Use an analogy — sticky notes, extra boxes, a notepad.
Example: "We only use one sticky note to remember our answer. It doesn't matter how big the input is —
we always use just that one sticky note. That's O(1)."]

## ⚡ Quick Take
- Time: O(?) — [5 words max]
- Space: O(?) — [5 words max]

## 🧪 Quick Quiz — Test Yourself!
Generate exactly 2 multiple choice questions about the complexity of THIS specific problem.
Make the questions test WHY the complexity is what it is, not just what it is.
Keep the question wording simple — a beginner should understand it.

Use this EXACT format for each question:

**Q1:** [question]
- A) [option]
- B) [option]
- C) [option]
ANSWER: [A, B, or C]
HINT: [one simple sentence hint — explain why the answer is correct]

**Q2:** [question]
- A) [option]
- B) [option]
- C) [option]
ANSWER: [A, B, or C]
HINT: [one simple sentence hint]
"""

CRITIC_INSTRUCTION = """
You are a strict quality evaluator for algorithm explanations aimed at 5-year-olds and absolute beginners.

Evaluate the given output on these criteria:
- Is it simple enough for a 5-year-old? (no jargon, uses analogies, short sentences)
- Does it follow the required format exactly?
- Is the explanation accurate?
- Does it use "we" to talk with the reader?

Respond in EXACTLY this format (no extra text):
SCORE: [1-5]
ISSUES: [comma-separated issues, or "none"]
SUGGESTION: [one actionable sentence on how to improve it]

Scoring guide:
5 = Perfect — a child could understand it, correct, right format
4 = Good — minor issues
3 = Acceptable — slightly too technical or missing analogies
2 = Poor — uses jargon or confusing for beginners
1 = Wrong — incorrect or not useful
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
        instruction=CLASSIFIER_INSTRUCTION + get_lessons("classifier") + get_feedback_context("classifier"),
        server_names=[],
    )
    await classifier.initialize()
    agents["classifier_llm"] = await classifier.attach_llm(OpenAIAugmentedLLM)

    solution = Agent(
        name="solution",
        instruction=SOLUTION_INSTRUCTION + get_lessons("solution") + get_feedback_context("solution"),
        server_names=[],
    )
    await solution.initialize()
    agents["solution_llm"] = await solution.attach_llm(OpenAIAugmentedLLM)

    complexity = Agent(
        name="complexity",
        instruction=COMPLEXITY_INSTRUCTION + get_lessons("complexity") + get_feedback_context("complexity"),
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
    try:
        score_match      = re.search(r"SCORE:\s*(\d)", critique)
        issues_match     = re.search(r"ISSUES:\s*(.+)", critique)
        suggestion_match = re.search(r"SUGGESTION:\s*(.+)", critique)
        score      = int(score_match.group(1)) if score_match else 3
        issues     = issues_match.group(1).strip() if issues_match else "unknown"
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
    correction_log = []

    result = await agent_llm.generate_str(
        message=message,
        request_params=RequestParams(use_history=False, maxTokens=max_tokens),
    )

    critique = await critic_llm.generate_str(
        message=f"Evaluate this output:\n\n{result}",
        request_params=RequestParams(use_history=False, maxTokens=300),
    )
    score, issues, suggestion = _parse_score(critique)
    correction_log.append({"attempt": 1, "score": score, "issues": issues})

    if score <= 3:
        if suggestion:
            save_correction(agent_name, issues, suggestion)

        retry_message = (
            f"{message}\n\n"
            f"Your previous attempt scored {score}/5. Issues: {issues}. "
            f"Fix: {suggestion}. Try again and address these issues."
        )
        result = await agent_llm.generate_str(
            message=retry_message,
            request_params=RequestParams(use_history=False, maxTokens=max_tokens),
        )
        critique2 = await critic_llm.generate_str(
            message=f"Evaluate this output:\n\n{result}",
            request_params=RequestParams(use_history=False, maxTokens=300),
        )
        score2, issues2, _ = _parse_score(critique2)
        correction_log.append({"attempt": 2, "score": score2, "issues": issues2})

    return result, correction_log


# --------------------------------------------------------------------------- #
#  Individual section rerun (triggered by human dislike feedback)
# --------------------------------------------------------------------------- #

# Maps section name → result key
SECTION_KEY = {"classifier": "pattern", "solution": "solution", "complexity": "complexity"}

async def rerun_section(
    section: str,
    context: dict,
    agents: dict,
    feedback_comment: str = "",
) -> tuple[str, list]:
    """
    Re-run a single agent with human dislike feedback injected.
    section: 'classifier' | 'solution' | 'complexity'
    context: dict with problem_text, pattern, solution
    """
    feedback_note = (
        f"\n\nIMPORTANT: A user was unhappy with the previous response."
        f" Their feedback: \"{feedback_comment or 'no specific comment'}\"."
        " Please rewrite it — make it noticeably simpler, friendlier, and more beginner-focused."
    )

    if section == "classifier":
        message    = f"Here is the LeetCode problem:\n\n{context['problem_text']}{feedback_note}"
        llm        = agents["classifier_llm"]
        max_tokens = 800
    elif section == "solution":
        message    = f"Problem:\n{context['problem_text']}\n\nPattern:\n{context['pattern']}{feedback_note}"
        llm        = agents["solution_llm"]
        max_tokens = 2500
    else:  # complexity
        message    = f"Problem:\n{context['problem_text']}\n\nSolution:\n{context['solution']}{feedback_note}"
        llm        = agents["complexity_llm"]
        max_tokens = 1000

    return await run_with_self_correction(llm, agents["critic_llm"], message, section, max_tokens)


# --------------------------------------------------------------------------- #
#  Full pipeline runner
# --------------------------------------------------------------------------- #

async def run_pipeline(url: str, agents: dict) -> tuple[dict, list]:
    log = []
    results = {"problem_text": None, "pattern": None, "solution": None, "complexity": None}

    # --- Browser ---
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
        log.append({"agent": "Browser Agent", "status": "success",
                    "details": f"Scraped problem in {duration}s", "duration": duration, "corrections": []})
    except Exception as e:
        duration = round(time.time() - t0, 1)
        log.append({"agent": "Browser Agent", "status": "failed",
                    "details": str(e), "duration": duration, "corrections": []})
        for name in ["Classifier Agent", "Solution Agent", "Complexity Agent"]:
            log.append({"agent": name, "status": "skipped",
                        "details": "Skipped — Browser Agent failed", "duration": 0, "corrections": []})
        return results, log

    # --- Classifier ---
    t0 = time.time()
    try:
        pattern, corrections = await run_with_self_correction(
            agents["classifier_llm"], agents["critic_llm"],
            message=f"Here is the LeetCode problem:\n\n{results['problem_text']}",
            agent_name="classifier", max_tokens=800,
        )
        duration = round(time.time() - t0, 1)
        results["pattern"] = pattern
        retried = len(corrections) > 1
        log.append({"agent": "Classifier Agent", "status": "success",
                    "details": f"Pattern identified in {duration}s" + (" (self-corrected)" if retried else ""),
                    "duration": duration, "corrections": corrections})
    except Exception as e:
        duration = round(time.time() - t0, 1)
        log.append({"agent": "Classifier Agent", "status": "failed",
                    "details": str(e), "duration": duration, "corrections": []})
        for name in ["Solution Agent", "Complexity Agent"]:
            log.append({"agent": name, "status": "skipped",
                        "details": "Skipped — Classifier Agent failed", "duration": 0, "corrections": []})
        return results, log

    # --- Solution ---
    t0 = time.time()
    try:
        solution, corrections = await run_with_self_correction(
            agents["solution_llm"], agents["critic_llm"],
            message=f"Problem:\n{results['problem_text']}\n\nPattern:\n{results['pattern']}",
            agent_name="solution", max_tokens=2500,
        )
        duration = round(time.time() - t0, 1)
        results["solution"] = solution
        retried = len(corrections) > 1
        log.append({"agent": "Solution Agent", "status": "success",
                    "details": f"Solution generated in {duration}s" + (" (self-corrected)" if retried else ""),
                    "duration": duration, "corrections": corrections})
    except Exception as e:
        duration = round(time.time() - t0, 1)
        log.append({"agent": "Solution Agent", "status": "failed",
                    "details": str(e), "duration": duration, "corrections": []})
        log.append({"agent": "Complexity Agent", "status": "skipped",
                    "details": "Skipped — Solution Agent failed", "duration": 0, "corrections": []})
        return results, log

    # --- Complexity ---
    t0 = time.time()
    try:
        complexity, corrections = await run_with_self_correction(
            agents["complexity_llm"], agents["critic_llm"],
            message=f"Problem:\n{results['problem_text']}\n\nSolution:\n{results['solution']}",
            agent_name="complexity", max_tokens=1000,
        )
        duration = round(time.time() - t0, 1)
        results["complexity"] = complexity
        retried = len(corrections) > 1
        log.append({"agent": "Complexity Agent", "status": "success",
                    "details": f"Complexity explained in {duration}s" + (" (self-corrected)" if retried else ""),
                    "duration": duration, "corrections": corrections})
    except Exception as e:
        duration = round(time.time() - t0, 1)
        log.append({"agent": "Complexity Agent", "status": "failed",
                    "details": str(e), "duration": duration, "corrections": []})

    return results, log
