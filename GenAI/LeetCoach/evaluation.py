"""
Evaluation module for LeetCoach.

Phase 1:
  - RAGAS: Faithfulness + Answer Relevancy on the solution section
  - LLM-as-Judge: Multi-dimension scoring (6 criteria, 1-5 each)

Phase 2:
  - Pattern accuracy check against ground_truth.py dataset
  - Evaluation history saved to eval_history.json for trend tracking
"""

import os
import re
import json
import asyncio
from pathlib import Path
from datetime import datetime
from openai import AsyncOpenAI

from ground_truth import check_pattern_accuracy

EVAL_HISTORY_FILE = Path(__file__).parent / "eval_history.json"

# Try importing RAGAS — graceful fallback if unavailable
try:
    from ragas import evaluate as ragas_evaluate, EvaluationDataset, SingleTurnSample
    from ragas.metrics.collections import Faithfulness, ResponseRelevancy
    RAGAS_AVAILABLE = True
except Exception:
    RAGAS_AVAILABLE = False


# --------------------------------------------------------------------------- #
#  History store
# --------------------------------------------------------------------------- #

def load_eval_history() -> list:
    if EVAL_HISTORY_FILE.exists():
        with open(EVAL_HISTORY_FILE) as f:
            return json.load(f)
    return []

def save_eval_result(result: dict):
    history = load_eval_history()
    history.append(result)
    history = history[-50:]  # keep last 50 runs
    with open(EVAL_HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)


# --------------------------------------------------------------------------- #
#  RAGAS Evaluation
# --------------------------------------------------------------------------- #

def run_ragas_evaluation(problem_title: str, solution_text: str, problem_text: str) -> dict:
    """
    Run RAGAS faithfulness + answer_relevancy on the solution.
    - question  = problem title
    - answer    = solution text (explanation + code)
    - contexts  = scraped problem text (what the agent had access to)

    Returns dict with scores or error message.
    """
    if not RAGAS_AVAILABLE:
        return {"error": "RAGAS not installed. Run: pip install ragas"}

    if not os.getenv("OPENAI_API_KEY"):
        return {"error": "OpenAI API key not set"}

    try:
        sample = SingleTurnSample(
            user_input=problem_title,
            response=solution_text,
            retrieved_contexts=[problem_text],
        )
        dataset = EvaluationDataset(samples=[sample])
        result = ragas_evaluate(dataset=dataset, metrics=[Faithfulness(), ResponseRelevancy()])
        scores = result.to_pandas()
        return {
            "faithfulness":     round(float(scores["faithfulness"].iloc[0]), 3),
            "answer_relevancy": round(float(scores["response_relevancy"].iloc[0]), 3),
            "error": None,
        }
    except Exception as e:
        return {"error": str(e)}


# --------------------------------------------------------------------------- #
#  Multi-Dimension LLM-as-Judge
# --------------------------------------------------------------------------- #

LLM_JUDGE_PROMPT = """You are an expert evaluator assessing an AI-generated LeetCode explanation.
The target audience is absolute beginners — people who just started coding.

Score each dimension from 1 to 5:

1. BEGINNER_FRIENDLINESS: Does it use simple words, analogies, and avoid jargon? Would a 5-year-old follow along?
2. PATTERN_ACCURACY: Is the identified algorithm pattern actually correct for this problem?
3. SOLUTION_CORRECTNESS: Is the solution logically correct? Does it actually solve the problem?
4. EXPLANATION_QUALITY: Does the walkthrough match the code? No made-up steps?
5. COMPLEXITY_ACCURACY: Is the Big O analysis correct? Is the reasoning sound?
6. QUIZ_QUALITY: Are the 2 quiz questions educational and testing the right concept?

Respond in EXACTLY this format (no extra text):
BEGINNER_FRIENDLINESS: [1-5]
PATTERN_ACCURACY: [1-5]
SOLUTION_CORRECTNESS: [1-5]
EXPLANATION_QUALITY: [1-5]
COMPLEXITY_ACCURACY: [1-5]
QUIZ_QUALITY: [1-5]
OVERALL: [1-5]
SUMMARY: [one sentence — the most important thing to improve]

Scoring guide:
5 = Excellent
4 = Good, minor issues
3 = Acceptable but noticeable problems
2 = Poor, significant issues
1 = Wrong or completely unhelpful
"""

async def run_llm_judge_evaluation(
    problem_text: str,
    pattern: str,
    solution: str,
    complexity: str,
) -> dict:
    """
    Multi-dimension LLM-as-Judge evaluation using direct OpenAI API.
    Returns dict of dimension scores + summary, or error.
    """
    if not os.getenv("OPENAI_API_KEY"):
        return {"error": "OpenAI API key not set"}

    full_output = f"""
=== PROBLEM ===
{problem_text[:1000]}

=== PATTERN IDENTIFIED ===
{pattern}

=== SOLUTION ===
{solution}

=== COMPLEXITY ===
{complexity}
"""

    try:
        client = AsyncOpenAI()
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": LLM_JUDGE_PROMPT},
                {"role": "user", "content": f"Evaluate this output:\n{full_output}"},
            ],
            temperature=0,
            max_tokens=400,
        )
        raw = response.choices[0].message.content.strip()

        def _extract(label):
            m = re.search(rf"{label}:\s*(\d)", raw)
            return int(m.group(1)) if m else None

        summary_match = re.search(r"SUMMARY:\s*(.+)", raw)

        return {
            "beginner_friendliness": _extract("BEGINNER_FRIENDLINESS"),
            "pattern_accuracy":      _extract("PATTERN_ACCURACY"),
            "solution_correctness":  _extract("SOLUTION_CORRECTNESS"),
            "explanation_quality":   _extract("EXPLANATION_QUALITY"),
            "complexity_accuracy":   _extract("COMPLEXITY_ACCURACY"),
            "quiz_quality":          _extract("QUIZ_QUALITY"),
            "overall":               _extract("OVERALL"),
            "summary":               summary_match.group(1).strip() if summary_match else "",
            "error": None,
        }
    except Exception as e:
        return {"error": str(e)}


# --------------------------------------------------------------------------- #
#  Full evaluation runner (called from main.py on demand)
# --------------------------------------------------------------------------- #

async def run_full_evaluation(
    url: str,
    problem_text: str,
    pattern: str,
    solution: str,
    complexity: str,
) -> dict:
    """
    Run all Phase 1 + Phase 2 evaluations in parallel where possible.
    Returns a combined result dict saved to eval_history.json.
    """
    # Extract problem title from first line of scraped text
    title_line = problem_text.strip().split("\n")[0] if problem_text else "Unknown"
    problem_title = title_line[:120]

    # Extract pattern name (first line after ## 🎯 Pattern)
    pattern_name_match = re.search(r"##\s*🎯\s*Pattern\s*\n(.+)", pattern or "")
    pattern_name = pattern_name_match.group(1).strip() if pattern_name_match else (pattern or "")[:80]

    # Run LLM judge and pattern accuracy check in parallel
    judge_task = run_llm_judge_evaluation(problem_text, pattern, solution, complexity)
    judge_scores = await judge_task

    # RAGAS runs synchronously (not async-friendly), run in thread
    ragas_scores = {}
    if RAGAS_AVAILABLE:
        loop = asyncio.get_event_loop()
        ragas_scores = await loop.run_in_executor(
            None,
            run_ragas_evaluation,
            problem_title, solution, problem_text
        )
    else:
        ragas_scores = {"error": "RAGAS not installed"}

    # Pattern accuracy (sync, instant)
    pattern_accuracy = check_pattern_accuracy(pattern_name, url)

    result = {
        "timestamp":        datetime.now().isoformat(),
        "url":              url,
        "problem_title":    problem_title,
        "ragas":            ragas_scores,
        "llm_judge":        judge_scores,
        "pattern_accuracy": pattern_accuracy,
    }

    save_eval_result(result)
    return result
