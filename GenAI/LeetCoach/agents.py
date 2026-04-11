import asyncio
import time
import json
import re
from pathlib import Path
from datetime import datetime
from openai import AsyncOpenAI
from mcp_agent.agents.agent import Agent
from mcp_agent.workflows.llm.augmented_llm_openai import OpenAIAugmentedLLM
from mcp_agent.workflows.llm.augmented_llm import RequestParams

CORRECTIONS_FILE = Path(__file__).parent / "corrections.json"
FEEDBACK_FILE    = Path(__file__).parent / "feedback.json"

# --------------------------------------------------------------------------- #
#  Model tiering — cheap agents use mini, heavy reasoning uses full
# --------------------------------------------------------------------------- #
MODEL_MINI = "gpt-4o-mini"   # Browser, Classifier, Devil's Advocate, Critic, Complexity
MODEL_FULL = "gpt-4o"        # Planner, Solution B, Debate Judge


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

# --- NEW: Multi-agent pattern instructions ---

PLANNER_INSTRUCTION = """
You are a strategic Orchestrator for a LeetCode teaching assistant.
Given a LeetCode problem description, decide the best teaching strategy.

Strategies:
- "full": Use the complete pipeline — debate pattern classification, generate two competing solutions, pick the better one.
  Use this for Medium/Hard problems or any problem with multiple valid approaches.
- "simplified": Quick pipeline — classify directly, generate one solution.
  Use this ONLY for trivially Easy problems (under 10 lines, single loop, no edge cases).

Respond in EXACTLY this format (no extra text):
STRATEGY: [full|simplified]
REASONING: [one sentence why]
"""

DEVILS_ADVOCATE_INSTRUCTION = """
You are a Devil's Advocate who challenges algorithm pattern classifications.
Given a LeetCode problem and a proposed pattern, argue why a DIFFERENT pattern might be more appropriate.
Be specific — cite exact clues in the problem statement. Keep it concise.

Respond in EXACTLY this format (no extra text):
CHALLENGE: [2 sentences arguing for a different approach]
ALTERNATIVE: [alternative pattern name]
"""

DEBATE_JUDGE_INSTRUCTION = """
You are an expert algorithm judge settling a debate about which pattern best solves a LeetCode problem.

You receive:
1. The problem
2. A proposed pattern with reasoning
3. A devil's advocate challenge proposing an alternative

Pick the single most appropriate pattern for this problem. Be decisive.

Respond in EXACTLY this format (no extra text):
FINAL_PATTERN: [pattern name — must be one of the two debated patterns]
REASONING: [2 sentences — cite specific problem clues that settle the debate]
"""


# --------------------------------------------------------------------------- #
#  Direct OpenAI helpers (model tiering — gpt-4o for heavy reasoning)
# --------------------------------------------------------------------------- #

async def _call_openai(model: str, system: str, user: str, max_tokens: int = 500) -> str:
    client = AsyncOpenAI()
    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.3,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content.strip()


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
#  Self-correction helper (Reflection Pattern)
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

SECTION_KEY = {"classifier": "pattern", "solution": "solution", "complexity": "complexity"}

async def rerun_section(
    section: str,
    context: dict,
    agents: dict,
    feedback_comment: str = "",
) -> tuple[str, list]:
    """Re-run a single agent with human dislike feedback injected."""
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
#  Pattern 3: Hierarchical Orchestrator — Planner decides strategy (gpt-4o)
# --------------------------------------------------------------------------- #

async def run_planner(problem_text: str) -> dict:
    """Planner agent decides pipeline strategy before any other agent runs."""
    raw = await _call_openai(
        model=MODEL_FULL,
        system=PLANNER_INSTRUCTION,
        user=f"Decide the teaching strategy for this problem:\n\n{problem_text[:800]}",
        max_tokens=120,
    )
    strategy_match  = re.search(r"STRATEGY:\s*(full|simplified)", raw, re.I)
    reasoning_match = re.search(r"REASONING:\s*(.+)", raw)
    return {
        "strategy":  strategy_match.group(1).lower() if strategy_match else "full",
        "reasoning": reasoning_match.group(1).strip() if reasoning_match else "",
    }


# --------------------------------------------------------------------------- #
#  Pattern 2: Debate Pattern — Classifier → Devil's Advocate → Judge
# --------------------------------------------------------------------------- #

async def run_debate_classification(problem_text: str, agents: dict) -> dict:
    """
    Debate pattern for pattern classification:
    1. Classifier (gpt-4o-mini via mcp-agent) proposes a pattern
    2. Devil's Advocate (gpt-4o-mini direct) challenges it
    3. Judge (gpt-4o direct) picks the final pattern
    """
    log_entries = []

    # Step 1: Classifier
    t0 = time.time()
    initial_pattern, corrections = await run_with_self_correction(
        agents["classifier_llm"], agents["critic_llm"],
        message=f"Here is the LeetCode problem:\n\n{problem_text}",
        agent_name="classifier", max_tokens=800,
    )
    duration = round(time.time() - t0, 1)

    # Extract pattern name from initial classification
    name_match = re.search(r"##\s*🎯\s*Pattern\s*\n(.+)", initial_pattern)
    initial_pattern_name = name_match.group(1).strip() if name_match else initial_pattern[:80]
    log_entries.append({
        "agent": "Classifier Agent",
        "status": "success",
        "details": f"Initial pattern proposal: {initial_pattern_name}",
        "duration": duration,
        "corrections": corrections,
    })

    # Step 2: Devil's Advocate (gpt-4o-mini — cheap challenger)
    t0 = time.time()
    advocate_raw = await _call_openai(
        model=MODEL_MINI,
        system=DEVILS_ADVOCATE_INSTRUCTION,
        user=(
            f"Problem:\n{problem_text[:600]}\n\n"
            f"Proposed Pattern: {initial_pattern_name}\n\n"
            f"Reasoning:\n{initial_pattern[:400]}"
        ),
        max_tokens=200,
    )
    duration = round(time.time() - t0, 1)
    challenge_match = re.search(r"CHALLENGE:\s*(.+?)(?=ALTERNATIVE:|$)", advocate_raw, re.DOTALL)
    alt_match       = re.search(r"ALTERNATIVE:\s*(.+)", advocate_raw)
    challenge       = challenge_match.group(1).strip() if challenge_match else ""
    alternative     = alt_match.group(1).strip() if alt_match else ""

    # Step 3: Debate Judge (gpt-4o — heavyweight decider)
    # Only run judge if devil's advocate proposed a genuinely different pattern
    debate_happened = bool(
        alternative
        and alternative.lower() not in initial_pattern_name.lower()
        and initial_pattern_name.lower() not in alternative.lower()
    )
    log_entries.append({
        "agent": "Devil's Advocate",
        "status": "success",
        "details": (
            f"Challenged with alternative pattern '{alternative}'"
            if debate_happened else
            "Agreed with the original pattern"
        ),
        "duration": duration,
        "corrections": [],
    })

    if debate_happened:
        t0 = time.time()
        judge_raw = await _call_openai(
            model=MODEL_FULL,
            system=DEBATE_JUDGE_INSTRUCTION,
            user=(
                f"Problem:\n{problem_text[:600]}\n\n"
                f"Proposed Pattern: {initial_pattern_name}\n"
                f"Reasoning:\n{initial_pattern[:400]}\n\n"
                f"Devil's Advocate:\n{advocate_raw[:300]}"
            ),
            max_tokens=200,
        )
        duration = round(time.time() - t0, 1)
        final_match   = re.search(r"FINAL_PATTERN:\s*(.+)", judge_raw)
        reason_match  = re.search(r"REASONING:\s*(.+)", judge_raw)
        final_name    = final_match.group(1).strip() if final_match else initial_pattern_name
        judge_reasoning = reason_match.group(1).strip() if reason_match else ""

        # If judge picked the alternative, re-classify under that pattern name
        if final_name.strip().lower() != initial_pattern_name.strip().lower():
            reclassified = await agents["classifier_llm"].generate_str(
                message=(
                    f"Classify this problem using the '{final_name}' pattern.\n\n"
                    f"{problem_text}\n\n"
                    "Follow the exact format with ## 🎯 Pattern, ## Why This Pattern?, ## The Key Trick, ## Difficulty."
                ),
                request_params=RequestParams(use_history=False, maxTokens=800),
            )
            final_pattern = reclassified
        else:
            final_pattern = initial_pattern
        log_entries.append({
            "agent": "Debate Judge",
            "status": "success",
            "details": f"Selected '{final_name}' as the final pattern",
            "duration": duration,
            "corrections": [],
        })
    else:
        final_pattern   = initial_pattern
        judge_reasoning = ""
        debate_happened = False
        log_entries.append({
            "agent": "Debate Judge",
            "status": "skipped",
            "details": "Skipped — no meaningful disagreement to resolve",
            "duration": 0,
            "corrections": [],
        })

    return {
        "final_pattern":       final_pattern,
        "initial_pattern_name": initial_pattern_name,
        "challenge":           challenge,
        "alternative":         alternative,
        "judge_reasoning":     judge_reasoning,
        "debate_happened":     debate_happened,
        "corrections":         corrections,
        "log_entries":         log_entries,
    }


# --------------------------------------------------------------------------- #
#  Pattern 1: Competitive Pattern — Solution A (mini) vs B (gpt-4o), Critic picks
# --------------------------------------------------------------------------- #

async def run_competitive_solution(problem_text: str, pattern: str, agents: dict) -> dict:
    """
    Two solutions compete:
    - Solution A: gpt-4o-mini via mcp-agent (conservative, standard approach)
    - Solution B: gpt-4o direct (creative/optimized approach)
    Critic picks the winner.
    """
    base_msg = f"Problem:\n{problem_text}\n\nPattern:\n{pattern}"
    log_entries = []

    async def _run_solution_b() -> tuple[str, float]:
        t0 = time.time()
        result = await _call_openai(
            model=MODEL_FULL,
            system=SOLUTION_INSTRUCTION + get_feedback_context("solution"),
            user=base_msg + "\n\nApproach: Creative — use the most elegant or optimized implementation. May differ slightly from the textbook approach if it's clearer.",
            max_tokens=2500,
        )
        return result, round(time.time() - t0, 1)

    # Run Solution A (gpt-4o-mini) and Solution B (gpt-4o) in parallel
    t0 = time.time()
    sol_a_task = run_with_self_correction(
        agents["solution_llm"], agents["critic_llm"],
        message=base_msg + "\n\nApproach: Conservative — use the most common, textbook implementation of this pattern.",
        agent_name="solution", max_tokens=2500,
    )
    (sol_a, corrections_a), (sol_b, duration_b) = await asyncio.gather(sol_a_task, _run_solution_b())
    duration_a = round(time.time() - t0, 1)
    log_entries.append({
        "agent": "Solution Agent A",
        "status": "success",
        "details": f"Conservative solution generated with {MODEL_MINI}",
        "duration": duration_a,
        "corrections": corrections_a,
    })
    log_entries.append({
        "agent": "Solution Agent B",
        "status": "success",
        "details": f"Heavy-reasoning solution generated with {MODEL_FULL}",
        "duration": duration_b,
        "corrections": [],
    })

    # Critic picks the winner (gpt-4o-mini is sufficient for comparison)
    t0 = time.time()
    critic_pick = await agents["critic_llm"].generate_str(
        message=(
            "You are judging two algorithm explanations aimed at absolute beginners.\n"
            "Pick the one that is simpler, clearer, and uses better analogies.\n\n"
            f"PROBLEM:\n{problem_text[:400]}\n\n"
            f"--- SOLUTION A ---\n{sol_a[:1000]}\n\n"
            f"--- SOLUTION B ---\n{sol_b[:1000]}\n\n"
            "Respond in EXACTLY this format:\n"
            "WINNER: [A or B]\n"
            "REASON: [one sentence why — focus on beginner-friendliness]\n"
        ),
        request_params=RequestParams(use_history=False, maxTokens=100),
    )
    duration = round(time.time() - t0, 1)

    winner_match = re.search(r"WINNER:\s*([AB])", critic_pick, re.I)
    reason_match = re.search(r"REASON:\s*(.+)", critic_pick)
    winner = winner_match.group(1).upper() if winner_match else "A"
    reason = reason_match.group(1).strip() if reason_match else ""
    log_entries.append({
        "agent": "Solution Critic",
        "status": "success",
        "details": f"Picked Solution {winner} as winner",
        "duration": duration,
        "corrections": [],
    })

    return {
        "solution":      sol_a if winner == "A" else sol_b,
        "winner":        winner,
        "winner_reason": reason,
        "corrections_a": corrections_a,
        "model_a":       MODEL_MINI,
        "model_b":       MODEL_FULL,
        "log_entries":   log_entries,
    }


# --------------------------------------------------------------------------- #
#  Full pipeline runner (with all 5 patterns wired in)
# --------------------------------------------------------------------------- #

async def run_pipeline(url: str, agents: dict, fallback_text: str = "") -> tuple[dict, list]:
    """
    Full pipeline with:
    - Pattern 4: Supervisor with Fallback (browser fail → fallback_text)
    - Pattern 3: Hierarchical Orchestrator (Planner decides full vs simplified)
    - Pattern 2: Debate (Classifier + Devil's Advocate + Judge)
    - Pattern 1: Competitive Solution (Solution A vs B, Critic picks)
    - Pattern 5: Model Tiering (gpt-4o-mini for cheap, gpt-4o for heavy)
    """
    log = []
    results = {
        "problem_text":      None,
        "pattern":           None,
        "solution":          None,
        "complexity":        None,
        "planner_strategy":  None,
        "planner_reasoning": None,
        "debate_summary":    None,
        "competitive_winner": None,
        "competitive_reason": None,
        "competitive_model_a": MODEL_MINI,
        "competitive_model_b": MODEL_FULL,
        "needs_fallback":    False,
    }

    # ----------------------------------------------------------------------- #
    #  Pattern 4: Supervisor with Fallback
    #  Browser agent runs; on failure, signal UI to collect manual paste
    # ----------------------------------------------------------------------- #
    if fallback_text:
        # User already pasted the problem text
        results["problem_text"] = fallback_text
        log.append({"agent": "Browser Agent", "status": "skipped",
                    "details": "Using manually pasted problem text (fallback mode).",
                    "duration": 0, "corrections": []})
    else:
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
            # Signal UI to show manual paste fallback instead of aborting
            results["needs_fallback"] = True
            for name in [
                "Planner Agent",
                "Classifier Agent",
                "Devil's Advocate",
                "Debate Judge",
                "Solution Agent A",
                "Solution Agent B",
                "Solution Critic",
                "Complexity Agent",
            ]:
                log.append({"agent": name, "status": "skipped",
                            "details": "Skipped — Browser Agent failed", "duration": 0, "corrections": []})
            return results, log

    # ----------------------------------------------------------------------- #
    #  Pattern 3: Hierarchical Orchestrator — Planner (gpt-4o) decides strategy
    # ----------------------------------------------------------------------- #
    t0 = time.time()
    try:
        planner = await run_planner(results["problem_text"])
        duration = round(time.time() - t0, 1)
        results["planner_strategy"]  = planner["strategy"]
        results["planner_reasoning"] = planner["reasoning"]
        log.append({"agent": "Planner Agent", "status": "success",
                    "details": f"Strategy: '{planner['strategy']}' — {planner['reasoning']}",
                    "duration": duration, "corrections": []})
    except Exception as e:
        duration = round(time.time() - t0, 1)
        results["planner_strategy"] = "full"
        log.append({"agent": "Planner Agent", "status": "failed",
                    "details": f"{e} (defaulting to full pipeline)",
                    "duration": duration, "corrections": []})

    strategy = results["planner_strategy"] or "full"

    # ----------------------------------------------------------------------- #
    #  Pattern 2: Debate Classification (if strategy=full)
    #  OR: simple classification (if simplified)
    # ----------------------------------------------------------------------- #
    t0 = time.time()
    try:
        if strategy == "full":
            debate = await run_debate_classification(results["problem_text"], agents)
            pattern = debate["final_pattern"]
            results["debate_summary"] = debate
            debate_tag = " (debate: " + ("judge ruled" if debate["debate_happened"] else "no challenge") + ")"
            log.extend(debate["log_entries"])
        else:
            pattern, corrections = await run_with_self_correction(
                agents["classifier_llm"], agents["critic_llm"],
                message=f"Here is the LeetCode problem:\n\n{results['problem_text']}",
                agent_name="classifier", max_tokens=800,
            )
            results["debate_summary"] = None
            debate_tag = ""
            log.append({"agent": "Classifier Agent", "status": "success",
                        "details": "Pattern identified without debate",
                        "duration": round(time.time() - t0, 1), "corrections": corrections})
            log.append({"agent": "Devil's Advocate", "status": "skipped",
                        "details": "Skipped — planner chose simplified pipeline",
                        "duration": 0, "corrections": []})
            log.append({"agent": "Debate Judge", "status": "skipped",
                        "details": "Skipped — planner chose simplified pipeline",
                        "duration": 0, "corrections": []})

        duration = round(time.time() - t0, 1)
        results["pattern"] = pattern
        log.append({"agent": "Pattern Pipeline", "status": "success",
                    "details": f"Pattern identified in {duration}s{debate_tag}",
                    "duration": duration, "corrections": []})
    except Exception as e:
        duration = round(time.time() - t0, 1)
        log.append({"agent": "Pattern Pipeline", "status": "failed",
                    "details": str(e), "duration": duration, "corrections": []})
        for name in ["Solution Agent A", "Solution Agent B", "Solution Critic", "Complexity Agent"]:
            log.append({"agent": name, "status": "skipped",
                        "details": "Skipped — pattern selection failed", "duration": 0, "corrections": []})
        return results, log

    # ----------------------------------------------------------------------- #
    #  Pattern 1: Competitive Solution (if strategy=full)
    #  OR: single solution (if simplified)
    # ----------------------------------------------------------------------- #
    t0 = time.time()
    try:
        if strategy == "full":
            competitive = await run_competitive_solution(
                results["problem_text"], results["pattern"], agents
            )
            solution = competitive["solution"]
            results["competitive_winner"] = competitive["winner"]
            results["competitive_reason"] = competitive["winner_reason"]
            results["competitive_model_a"] = competitive["model_a"]
            results["competitive_model_b"] = competitive["model_b"]
            comp_tag = f" (competitive: Solution {competitive['winner']} won)"
            log.extend(competitive["log_entries"])
        else:
            solution, corrections = await run_with_self_correction(
                agents["solution_llm"], agents["critic_llm"],
                message=f"Problem:\n{results['problem_text']}\n\nPattern:\n{results['pattern']}",
                agent_name="solution", max_tokens=2500,
            )
            comp_tag = ""
            log.append({"agent": "Solution Agent A", "status": "success",
                        "details": f"Single solution generated with {MODEL_MINI}",
                        "duration": round(time.time() - t0, 1), "corrections": corrections})
            log.append({"agent": "Solution Agent B", "status": "skipped",
                        "details": "Skipped — planner chose simplified pipeline",
                        "duration": 0, "corrections": []})
            log.append({"agent": "Solution Critic", "status": "skipped",
                        "details": "Skipped — planner chose simplified pipeline",
                        "duration": 0, "corrections": []})

        duration = round(time.time() - t0, 1)
        results["solution"] = solution
        log.append({"agent": "Solution Pipeline", "status": "success",
                    "details": f"Solution generated in {duration}s{comp_tag}",
                    "duration": duration, "corrections": []})
    except Exception as e:
        duration = round(time.time() - t0, 1)
        log.append({"agent": "Solution Pipeline", "status": "failed",
                    "details": str(e), "duration": duration, "corrections": []})
        log.append({"agent": "Complexity Agent", "status": "skipped",
                    "details": "Skipped — solution generation failed", "duration": 0, "corrections": []})
        return results, log

    # ----------------------------------------------------------------------- #
    #  Complexity Agent (gpt-4o-mini via mcp-agent, unchanged)
    # ----------------------------------------------------------------------- #
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
