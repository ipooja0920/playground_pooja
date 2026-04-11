"""
Evaluation module for LeetCoach.

Phase 1:
  - RAGAS (3 targeted evaluations):
      1. Solution Faithfulness  — does the walkthrough match the actual code?
      2. Complexity Faithfulness — is the Big O explanation grounded in the code?
      3. Answer Relevancy        — does the solution address the problem asked?
  - LLM-as-Judge: Multi-dimension scoring (6 criteria, 1-5 each)

Phase 2:
  - Pattern accuracy check against ground_truth.py dataset (57 problems, all 20 patterns)
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

# Try importing RAGAS — graceful fallback if not installed
try:
    from ragas import evaluate as ragas_evaluate, EvaluationDataset, SingleTurnSample
    from ragas.metrics.collections import Faithfulness, ResponseRelevancy
    from ragas.llms import LangchainLLMWrapper
    from langchain_openai import ChatOpenAI
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
    history = history[-50:]
    with open(EVAL_HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)


# --------------------------------------------------------------------------- #
#  RAGAS Evaluation — 3 targeted evaluations
# --------------------------------------------------------------------------- #

def _make_ragas_llm():
    """Build a RAGAS-compatible LLM wrapper using gpt-4o-mini."""
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    return LangchainLLMWrapper(llm)


def _run_single_ragas(user_input: str, response: str, contexts: list, metrics: list) -> dict:
    """Run one RAGAS evaluation synchronously. Returns {metric_name: score, error: None}."""
    try:
        ragas_llm = _make_ragas_llm()
        for m in metrics:
            m.llm = ragas_llm

        sample = SingleTurnSample(
            user_input=user_input,
            response=response,
            retrieved_contexts=contexts,
        )
        dataset = EvaluationDataset(samples=[sample])
        result = ragas_evaluate(dataset=dataset, metrics=metrics)
        scores = result.to_pandas()
        out = {"error": None}
        for col in scores.columns:
            if col not in ("user_input", "response", "retrieved_contexts", "reference"):
                try:
                    out[col] = round(float(scores[col].iloc[0]), 3)
                except Exception:
                    pass
        return out
    except Exception as e:
        return {"error": str(e)}


def run_ragas_evaluations(
    problem_text: str,
    solution: str,
    complexity: str,
) -> dict:
    """
    Run 3 targeted RAGAS evaluations:

    1. solution_faithfulness  — walkthrough grounded in the code?
       user_input = problem, response = solution explanation, contexts = [solution code]

    2. complexity_faithfulness — Big O explanation grounded in the code?
       user_input = problem, response = complexity explanation, contexts = [solution code]

    3. answer_relevancy — does solution address the problem?
       user_input = problem, response = solution explanation, contexts = [] (not needed)

    Returns dict with all 3 scores.
    """
    if not RAGAS_AVAILABLE:
        return {"error": "RAGAS not installed. Run: pip install ragas langchain-openai"}
    if not os.getenv("OPENAI_API_KEY"):
        return {"error": "OpenAI API key not set"}

    # Extract just the code block from solution text to use as context
    code_match = re.search(r"```python(.+?)```", solution, re.DOTALL)
    code_context = code_match.group(1).strip() if code_match else solution[:800]

    # 1. Solution Faithfulness
    sol_faith = _run_single_ragas(
        user_input=problem_text[:600],
        response=solution[:1500],
        contexts=[code_context],
        metrics=[Faithfulness()],
    )

    # 2. Complexity Faithfulness
    comp_faith = _run_single_ragas(
        user_input=f"Explain the time and space complexity of this problem:\n{problem_text[:400]}",
        response=complexity[:800],
        contexts=[code_context],
        metrics=[Faithfulness()],
    )

    # 3. Answer Relevancy (no context needed)
    ans_relev = _run_single_ragas(
        user_input=problem_text[:600],
        response=solution[:1500],
        contexts=[problem_text[:600]],  # problem itself as context
        metrics=[ResponseRelevancy()],
    )

    return {
        "solution_faithfulness":   sol_faith.get("faithfulness"),
        "complexity_faithfulness": comp_faith.get("faithfulness"),
        "answer_relevancy":        ans_relev.get("response_relevancy"),
        "solution_faith_error":    sol_faith.get("error"),
        "comp_faith_error":        comp_faith.get("error"),
        "answer_relev_error":      ans_relev.get("error"),
    }


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
#  Full evaluation runner
# --------------------------------------------------------------------------- #

async def run_full_evaluation(
    url: str,
    problem_text: str,
    pattern: str,
    solution: str,
    complexity: str,
) -> dict:
    """
    Run all evaluations. LLM Judge runs async, RAGAS runs in a thread executor.
    """
    title_line  = problem_text.strip().split("\n")[0] if problem_text else "Unknown"
    problem_title = title_line[:120]

    pattern_name_match = re.search(r"##\s*🎯\s*Pattern\s*\n(.+)", pattern or "")
    pattern_name = pattern_name_match.group(1).strip() if pattern_name_match else (pattern or "")[:80]

    # LLM Judge (async) and RAGAS (sync in thread) run concurrently
    loop = asyncio.get_event_loop()

    judge_task = run_llm_judge_evaluation(problem_text, pattern, solution, complexity)
    ragas_task = loop.run_in_executor(
        None,
        run_ragas_evaluations,
        problem_text, solution, complexity,
    ) if RAGAS_AVAILABLE else asyncio.coroutine(lambda: {"error": "RAGAS not installed"})()

    judge_scores, ragas_scores = await asyncio.gather(judge_task, ragas_task)

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
