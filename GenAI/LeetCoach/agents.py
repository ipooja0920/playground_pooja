import time
import json
import re
from pathlib import Path
from datetime import datetime
from openai import AsyncOpenAI
from mcp_agent.agents.agent import Agent
from mcp_agent.workflows.llm.augmented_llm_openai import OpenAIAugmentedLLM
from mcp_agent.workflows.llm.augmented_llm import RequestParams
from patterns import PATTERNS
from pattern_research_agent import get_pattern_knowledge_for_classifier

CORRECTIONS_FILE    = Path(__file__).parent / "corrections.json"
FEEDBACK_FILE       = Path(__file__).parent / "feedback.json"
FEEDBACK_RULES_FILE = Path(__file__).parent / "feedback_rules.json"
JUDGE_LESSONS_FILE  = Path(__file__).parent / "judge_lessons.json"

# Model tiering — Planner uses gpt-4o, everything else gpt-4o-mini
MODEL_MINI = "gpt-4o-mini"
MODEL_FULL = "gpt-4o"


# --------------------------------------------------------------------------- #
#  Corrections store
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
    save_feedback_rule(agent_name, "negative", suggestion, issue)

def get_lessons(agent_name: str) -> str:
    corrections = load_corrections()
    lessons = corrections.get(agent_name, [])[-3:]
    if not lessons:
        return ""
    lines = "\n".join(f"- {c['suggestion']}" for c in lessons)
    return f"\n\n**Lessons from past mistakes — always follow these:**\n{lines}"


# --------------------------------------------------------------------------- #
#  Human feedback store
# --------------------------------------------------------------------------- #

def load_feedback() -> dict:
    if FEEDBACK_FILE.exists():
        with open(FEEDBACK_FILE) as f:
            return json.load(f)
    return {"classifier": {"positive": [], "negative": []},
            "solution":   {"positive": [], "negative": []},
            "complexity":  {"positive": [], "negative": []}}

def save_feedback(agent_name: str, sentiment: str, snippet: str, comment: str = ""):
    feedback = load_feedback()
    if agent_name not in feedback:
        feedback[agent_name] = {"positive": [], "negative": []}
    feedback[agent_name][sentiment].append({
        "timestamp": datetime.now().isoformat(),
        "snippet": snippet[:300],
        "comment": comment,
    })
    feedback[agent_name][sentiment] = feedback[agent_name][sentiment][-5:]
    with open(FEEDBACK_FILE, "w") as f:
        json.dump(feedback, f, indent=2)
    save_feedback_rule(agent_name, sentiment, comment, snippet)

def load_feedback_rules() -> dict:
    if FEEDBACK_RULES_FILE.exists():
        with open(FEEDBACK_RULES_FILE) as f:
            return json.load(f)
    return {"classifier": [], "solution": [], "complexity": []}

def _normalize_rule_text(text: str) -> str:
    text = re.sub(r"\s+", " ", (text or "").strip())
    return text.strip(" -:.")[:180]

def save_feedback_rule(agent_name: str, sentiment: str, comment: str = "", snippet: str = ""):
    rules = load_feedback_rules()
    if agent_name not in rules:
        rules[agent_name] = []
    raw_text = _normalize_rule_text(comment or snippet)
    if not raw_text:
        return
    prefix = "Do: " if sentiment == "positive" else "Avoid: "
    rule = prefix + raw_text
    existing = rules[agent_name]
    if rule in existing:
        existing.remove(rule)
    existing.append(rule)
    rules[agent_name] = existing[-5:]
    with open(FEEDBACK_RULES_FILE, "w") as f:
        json.dump(rules, f, indent=2)

def get_feedback_rules(agent_name: str) -> str:
    rules = load_feedback_rules()
    agent_rules = rules.get(agent_name, [])[-5:]
    if not agent_rules:
        return ""
    lines = "\n".join(f"- {rule}" for rule in agent_rules)
    return f"\n\n**Behavior rules learned from human feedback — follow these by default:**\n{lines}"

def get_feedback_context(agent_name: str) -> str:
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

def get_judge_lessons(agent_name: str) -> str:
    """Inject LLM Judge low-score feedback from past evaluation runs."""
    if not JUDGE_LESSONS_FILE.exists():
        return ""
    with open(JUDGE_LESSONS_FILE) as f:
        lessons = json.load(f)
    agent_lessons = lessons.get(agent_name, [])[-3:]
    if not agent_lessons:
        return ""
    lines = "\n".join(f"- {l}" for l in agent_lessons)
    return f"\n\n**Evaluation feedback from past runs — fix these issues:**\n{lines}"

def _compose_instruction(base: str, agent_name: str) -> str:
    extra = (
        get_lessons(agent_name)
        + get_judge_lessons(agent_name)
        + get_feedback_rules(agent_name)
        + get_feedback_context(agent_name)
    )
    if agent_name == "classifier":
        extra += get_pattern_knowledge_for_classifier()
    return base + extra


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

def _build_pattern_menu() -> str:
    """Build a grounded pattern reference from our 20 patterns for the classifier."""
    lines = []
    for p in PATTERNS:
        signals = "; ".join(p["when_to_use"])
        lines.append(f"{p['id']:02d}. {p['name']} — use when: {signals}")
    return "\n".join(lines)

_PATTERN_MENU = _build_pattern_menu()

# Pattern names as a set for fast validation
_VALID_PATTERN_NAMES = {p["name"].lower() for p in PATTERNS}

CLASSIFIER_INSTRUCTION = f"""
You are an algorithm pattern expert. Given a LeetCode problem, identify which pattern solves it.

You MUST pick EXACTLY ONE pattern from this list — no other patterns allowed:

{_PATTERN_MENU}

Decision rules for commonly confused patterns:
- Sliding Window vs Two Pointers: if the problem is about a contiguous subarray/substring → Sliding Window. If it's about pairs from both ends of a sorted array → Two Pointers.
- BFS vs DFS: if you need shortest path or level-by-level → BFS. If you need to explore all paths or detect cycles → DFS.
- DP vs Backtracking: if there are overlapping subproblems with optimal substructure → DP. If you're building all combinations/permutations explicitly → Backtracking.
- Cyclic Sort vs prefix/hash: if the problem has numbers in range [1, n] and asks for missing/duplicate → Cyclic Sort.

Use this EXACT format:

## 🎯 Pattern
[Pattern name — must be one of the 20 above, copied exactly]

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

CLASSIFIER_CRITIC_INSTRUCTION = """
You are an expert algorithm pattern reviewer. Your ONLY job is to verify that the correct pattern was chosen for a LeetCode problem.

Evaluate:
1. Is the identified pattern ACTUALLY correct for this problem? Not just plausible — actually the best fit?
2. Are the reasoning clues accurate and specific to this problem?
3. Is the pattern name exactly one of our 20 allowed patterns?

Common mistakes to catch:
- Picking Sliding Window for DP problems just because they involve strings/substrings
- Picking Two Pointers for problems that need a hash map (like Two Sum on unsorted arrays)
- Picking BFS/DFS when the problem needs DP (e.g. counting paths, interleaving)
- Picking Backtracking when DP works (overlapping subproblems = DP, not Backtracking)
- Any problem asking "can we form X from Y" or "number of ways" → almost always Dynamic Programming

Respond in EXACTLY this format (no extra text):
SCORE: [1-5]
ISSUES: [what specifically is wrong with the pattern choice, or "none"]
SUGGESTION: [one sentence — name the correct pattern if wrong, or "looks correct" if right]

Scoring guide:
5 = Pattern is definitely correct
4 = Pattern is reasonable, minor quibble
3 = Pattern is debatable, better option exists
2 = Pattern is probably wrong
1 = Pattern is clearly wrong
"""

PLANNER_INSTRUCTION = """
You are a strategic Orchestrator for a LeetCode teaching assistant.
Given a LeetCode problem description, decide the best teaching strategy.

Strategies:
- "full": Standard pipeline — classify pattern, generate solution, explain complexity.
  Use this for Medium/Hard problems or any problem with tricky edge cases.
- "simplified": Same pipeline but note this is a straightforward Easy problem.
  Use this ONLY for trivially Easy problems (under 10 lines, single loop, no edge cases).

Respond in EXACTLY this format (no extra text):
STRATEGY: [full|simplified]
REASONING: [one sentence why]
"""


# --------------------------------------------------------------------------- #
#  Agent builder helpers
# --------------------------------------------------------------------------- #

async def _build_browser_llm():
    agent = Agent(name="browser", instruction=BROWSER_INSTRUCTION, server_names=["playwright"])
    await agent.initialize()
    return await agent.attach_llm(OpenAIAugmentedLLM)

async def _build_classifier_llm():
    # mcp-agent model is set in config.yaml; we use direct OpenAI for gpt-4o classification
    agent = Agent(name="classifier", instruction=_compose_instruction(CLASSIFIER_INSTRUCTION, "classifier"), server_names=[])
    await agent.initialize()
    return await agent.attach_llm(OpenAIAugmentedLLM)

async def _build_classifier_critic_llm():
    agent = Agent(name="classifier_critic", instruction=CLASSIFIER_CRITIC_INSTRUCTION, server_names=[])
    await agent.initialize()
    return await agent.attach_llm(OpenAIAugmentedLLM)

async def _build_solution_llm():
    agent = Agent(name="solution", instruction=_compose_instruction(SOLUTION_INSTRUCTION, "solution"), server_names=[])
    await agent.initialize()
    return await agent.attach_llm(OpenAIAugmentedLLM)

async def _build_complexity_llm():
    agent = Agent(name="complexity", instruction=_compose_instruction(COMPLEXITY_INSTRUCTION, "complexity"), server_names=[])
    await agent.initialize()
    return await agent.attach_llm(OpenAIAugmentedLLM)

async def _build_critic_llm():
    agent = Agent(name="critic", instruction=CRITIC_INSTRUCTION, server_names=[])
    await agent.initialize()
    return await agent.attach_llm(OpenAIAugmentedLLM)


# --------------------------------------------------------------------------- #
#  Agent setup + refresh
# --------------------------------------------------------------------------- #

async def setup_agents(mcp_agent_app) -> dict:
    return {
        "browser_llm":           await _build_browser_llm(),
        "classifier_llm":        await _build_classifier_llm(),
        "classifier_critic_llm": await _build_classifier_critic_llm(),
        "solution_llm":          await _build_solution_llm(),
        "complexity_llm":        await _build_complexity_llm(),
        "critic_llm":            await _build_critic_llm(),
    }

async def refresh_agents(agents: dict, names: list = None) -> dict:
    """Rebuild selected agents with latest feedback/lessons injected."""
    names = names or ["classifier", "solution", "complexity"]
    for name in names:
        if name == "browser":
            agents["browser_llm"] = await _build_browser_llm()
        elif name == "classifier":
            agents["classifier_llm"]        = await _build_classifier_llm()
            agents["classifier_critic_llm"] = await _build_classifier_critic_llm()
        elif name == "solution":
            agents["solution_llm"] = await _build_solution_llm()
        elif name == "complexity":
            agents["complexity_llm"] = await _build_complexity_llm()
        elif name == "critic":
            agents["critic_llm"] = await _build_critic_llm()
    return agents


# --------------------------------------------------------------------------- #
#  Self-correction (Reflection pattern)
# --------------------------------------------------------------------------- #

def _parse_score(critique: str) -> tuple:
    try:
        score_m  = re.search(r"SCORE:\s*(\d)", critique)
        issues_m = re.search(r"ISSUES:\s*(.+)", critique)
        sugg_m   = re.search(r"SUGGESTION:\s*(.+)", critique)
        return (
            int(score_m.group(1)) if score_m else 3,
            issues_m.group(1).strip() if issues_m else "unknown",
            sugg_m.group(1).strip() if sugg_m else "",
        )
    except Exception:
        return 3, "parse error", ""

async def run_with_self_correction(agent_llm, critic_llm, message: str, agent_name: str, max_tokens: int = 2000) -> tuple:
    log = []
    result = await agent_llm.generate_str(
        message=message,
        request_params=RequestParams(use_history=False, maxTokens=max_tokens),
    )
    critique = await critic_llm.generate_str(
        message=f"Evaluate this output:\n\n{result}",
        request_params=RequestParams(use_history=False, maxTokens=300),
    )
    score, issues, suggestion = _parse_score(critique)
    log.append({"attempt": 1, "score": score, "issues": issues})

    if score <= 3:
        if suggestion:
            save_correction(agent_name, issues, suggestion)
        result = await agent_llm.generate_str(
            message=f"{message}\n\nYour previous attempt scored {score}/5. Issues: {issues}. Fix: {suggestion}. Try again.",
            request_params=RequestParams(use_history=False, maxTokens=max_tokens),
        )
        critique2 = await critic_llm.generate_str(
            message=f"Evaluate this output:\n\n{result}",
            request_params=RequestParams(use_history=False, maxTokens=300),
        )
        score2, issues2, _ = _parse_score(critique2)
        log.append({"attempt": 2, "score": score2, "issues": issues2})

    return result, log


# --------------------------------------------------------------------------- #
#  Individual section rerun (human dislike feedback)
# --------------------------------------------------------------------------- #

async def rerun_section(section: str, context: dict, agents: dict, feedback_comment: str = "") -> tuple:
    # Build feedback note — if comment mentions a specific pattern/answer, treat it as a correction
    if feedback_comment:
        feedback_note = (
            f"\n\nIMPORTANT: A user gave this feedback on the previous response: \"{feedback_comment}\"."
            " If the feedback specifies a correct answer or pattern, use that — the user is telling you"
            " what the right answer is. Otherwise rewrite to be simpler and more beginner-focused."
        )
    else:
        feedback_note = (
            "\n\nIMPORTANT: A user was unhappy with the previous response."
            " Please rewrite it — make it noticeably simpler, friendlier, and more beginner-focused."
        )

    if section == "classifier":
        message    = f"Here is the LeetCode problem:\n\n{context['problem_text']}{feedback_note}"
        llm        = agents["classifier_llm"]
        critic     = agents["classifier_critic_llm"]
        max_tokens = 800
    elif section == "solution":
        message    = f"Problem:\n{context['problem_text']}\n\nPattern:\n{context['pattern']}{feedback_note}"
        llm        = agents["solution_llm"]
        critic     = agents["critic_llm"]
        max_tokens = 2500
    else:
        message    = f"Problem:\n{context['problem_text']}\n\nSolution:\n{context['solution']}{feedback_note}"
        llm        = agents["complexity_llm"]
        critic     = agents["critic_llm"]
        max_tokens = 1000
    return await run_with_self_correction(llm, critic, message, section, max_tokens)


# --------------------------------------------------------------------------- #
#  Pattern validator — checks classifier output is one of our 20 patterns
# --------------------------------------------------------------------------- #

async def validate_and_fix_pattern(pattern_text: str, problem_text: str, classifier_llm) -> tuple:
    """
    Checks if the classifier picked a valid pattern from our list.
    If not, asks gpt-4o-mini to re-map it to the closest valid pattern and regenerate.
    Returns (final_pattern_text, was_corrected, original_name, corrected_name)
    """
    name_match = re.search(r"##\s*🎯\s*Pattern\s*\n(.+)", pattern_text)
    identified = name_match.group(1).strip() if name_match else ""

    # Strict exact match — strip parenthetical qualifiers like "(2D DP)", "(Top-Down)"
    # before comparing so "Dynamic Programming (2D DP)" → "Dynamic Programming"
    normalized = re.sub(r'\s*\(.*?\)', '', identified).strip().lower()
    is_valid = normalized in _VALID_PATTERN_NAMES

    if is_valid:
        # If the name had a qualifier, clean it up in the output
        if normalized != identified.lower():
            canonical = next(p["name"] for p in PATTERNS if p["name"].lower() == normalized)
            pattern_text = re.sub(
                r'(##\s*🎯\s*Pattern\s*\n).+',
                lambda m: m.group(1) + canonical,
                pattern_text,
            )
        return pattern_text, False, identified, identified

    # Not valid — ask the classifier to re-pick from the exact list
    valid_names = "\n".join(f"- {p['name']}" for p in PATTERNS)
    reclassify_msg = (
        f"The pattern you identified ('{identified}') is not in our allowed list.\n\n"
        f"Allowed patterns:\n{valid_names}\n\n"
        f"Re-classify this problem using ONLY one of the allowed patterns above.\n\n"
        f"Problem:\n{problem_text[:800]}"
    )
    fixed = await classifier_llm.generate_str(
        message=reclassify_msg,
        request_params=RequestParams(use_history=False, maxTokens=800),
    )
    fixed_match = re.search(r"##\s*🎯\s*Pattern\s*\n(.+)", fixed)
    corrected_name = fixed_match.group(1).strip() if fixed_match else identified

    return fixed, True, identified, corrected_name


# --------------------------------------------------------------------------- #
#  Hierarchical Orchestrator — Planner (gpt-4o) decides strategy
# --------------------------------------------------------------------------- #

async def run_classifier_direct(problem_text: str, agents: dict) -> tuple:
    """
    Run classification using gpt-4o directly (not mcp-agent) so we get
    stronger pattern reasoning. Self-corrects using the classifier critic.
    Returns (pattern_text, correction_log).
    """
    instruction = _compose_instruction(CLASSIFIER_INSTRUCTION, "classifier")
    client = AsyncOpenAI()
    log = []

    async def _call(msg: str) -> str:
        resp = await client.chat.completions.create(
            model=MODEL_FULL,
            messages=[
                {"role": "system", "content": instruction},
                {"role": "user", "content": msg},
            ],
            temperature=0,
            max_tokens=900,
        )
        return resp.choices[0].message.content.strip()

    result = await _call(f"Here is the LeetCode problem:\n\n{problem_text}")

    # Critique with the correctness-focused classifier critic
    critique = await agents["classifier_critic_llm"].generate_str(
        message=f"Problem:\n{problem_text[:600]}\n\nClassification output:\n{result}",
        request_params=RequestParams(use_history=False, maxTokens=300),
    )
    score, issues, suggestion = _parse_score(critique)
    log.append({"attempt": 1, "score": score, "issues": issues})

    if score <= 3:
        if suggestion:
            save_correction("classifier", issues, suggestion)
        result = await _call(
            f"Here is the LeetCode problem:\n\n{problem_text}\n\n"
            f"Your previous classification scored {score}/5. Issues: {issues}. "
            f"Fix: {suggestion}. Re-classify now."
        )
        critique2 = await agents["classifier_critic_llm"].generate_str(
            message=f"Problem:\n{problem_text[:600]}\n\nClassification output:\n{result}",
            request_params=RequestParams(use_history=False, maxTokens=300),
        )
        score2, issues2, _ = _parse_score(critique2)
        log.append({"attempt": 2, "score": score2, "issues": issues2})

    return result, log


async def run_planner(problem_text: str) -> dict:
    client = AsyncOpenAI()
    response = await client.chat.completions.create(
        model=MODEL_FULL,
        messages=[
            {"role": "system", "content": PLANNER_INSTRUCTION},
            {"role": "user", "content": f"Decide the teaching strategy for this problem:\n\n{problem_text[:800]}"},
        ],
        temperature=0,
        max_tokens=120,
    )
    raw = response.choices[0].message.content.strip()
    strategy_m  = re.search(r"STRATEGY:\s*(full|simplified)", raw, re.I)
    reasoning_m = re.search(r"REASONING:\s*(.+)", raw)
    return {
        "strategy":  strategy_m.group(1).lower() if strategy_m else "full",
        "reasoning": reasoning_m.group(1).strip() if reasoning_m else "",
    }


# --------------------------------------------------------------------------- #
#  Full pipeline runner
# --------------------------------------------------------------------------- #

async def run_pipeline(url: str, agents: dict, fallback_text: str = "") -> tuple:
    """
    Sequential pipeline:
    - Supervisor with Fallback: browser fail → user pastes text
    - Hierarchical Orchestrator: Planner (gpt-4o) decides strategy
    - Classifier → Solution → Complexity (all gpt-4o-mini, with self-correction)
    """
    log = []
    results = {
        "problem_text":      None,
        "pattern":           None,
        "solution":          None,
        "complexity":        None,
        "planner_strategy":  None,
        "planner_reasoning": None,
        "needs_fallback":    False,
    }

    # --- Browser / Fallback ---
    if fallback_text:
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
            results["needs_fallback"] = True
            for name in ["Planner Agent", "Classifier Agent", "Solution Agent", "Complexity Agent"]:
                log.append({"agent": name, "status": "skipped",
                            "details": "Skipped — Browser Agent failed", "duration": 0, "corrections": []})
            return results, log

    # --- Planner ---
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

    # --- Classifier (gpt-4o direct + correctness critic) ---
    t0 = time.time()
    try:
        pattern, corrections = await run_classifier_direct(results["problem_text"], agents)
        # Validate the pattern is one of our 20 — auto-fix if not
        pattern, was_corrected, original_name, corrected_name = await validate_and_fix_pattern(
            pattern, results["problem_text"], agents["classifier_llm"]
        )
        duration = round(time.time() - t0, 1)
        results["pattern"] = pattern
        retried = len(corrections) > 1
        correction_note = ""
        if was_corrected:
            correction_note = f" ⚠️ auto-corrected '{original_name}' → '{corrected_name}'"
        elif retried:
            correction_note = " (self-corrected)"
        log.append({"agent": "Classifier Agent", "status": "success",
                    "details": f"Pattern identified in {duration}s{correction_note}",
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
