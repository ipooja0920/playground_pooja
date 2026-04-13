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

EVAL_HISTORY_FILE  = Path(__file__).parent / "eval_history.json"
JUDGE_LESSONS_FILE = Path(__file__).parent / "judge_lessons.json"

# Which Judge dimensions map to which agent
_DIMENSION_TO_AGENT = {
    "beginner_friendliness": "solution",
    "solution_correctness":  "solution",
    "explanation_quality":   "solution",
    "complexity_accuracy":   "complexity",
    "quiz_quality":          "complexity",
    "pattern_accuracy":      "classifier",
}

# Try importing RAGAS — graceful fallback if not installed
try:
    from ragas import evaluate as ragas_evaluate, EvaluationDataset
    from ragas.metrics import faithfulness, answer_relevancy
    from ragas.llms import LangchainLLMWrapper
    from ragas.embeddings import LangchainEmbeddingsWrapper
    from langchain_openai import ChatOpenAI, OpenAIEmbeddings
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
#  Judge lessons store — routes low-score feedback to the right agent
# --------------------------------------------------------------------------- #

def load_judge_lessons() -> dict:
    if JUDGE_LESSONS_FILE.exists():
        with open(JUDGE_LESSONS_FILE) as f:
            return json.load(f)
    return {"classifier": [], "solution": [], "complexity": []}

def save_judge_lessons(judge_scores: dict, problem_title: str = "") -> dict:
    """
    For each Judge dimension that scored ≤ 3, save a lesson to the relevant agent.
    Also always save the summary sentence to whichever agent(s) had the worst scores.

    Returns a dict of {agent_name: [lessons_added]} for display in UI.
    """
    if judge_scores.get("error"):
        return {}

    lessons = load_judge_lessons()
    summary = judge_scores.get("summary", "")
    added = {}

    # Route low-scoring dimensions to the relevant agent
    for dimension, agent_name in _DIMENSION_TO_AGENT.items():
        score = judge_scores.get(dimension)
        if score is not None and score <= 3:
            dim_label = dimension.replace("_", " ").title()
            lesson = f"[Judge on '{problem_title}'] {dim_label} scored {score}/5 — {summary}" if summary else f"[Judge] {dim_label} scored {score}/5 — improve this dimension."
            lesson = lesson[:250]

            if agent_name not in lessons:
                lessons[agent_name] = []

            # Deduplicate: remove older lesson for same dimension if present
            lessons[agent_name] = [l for l in lessons[agent_name] if dim_label not in l]
            lessons[agent_name].append(lesson)
            lessons[agent_name] = lessons[agent_name][-5:]  # keep last 5 per agent

            if agent_name not in added:
                added[agent_name] = []
            added[agent_name].append(lesson)

    with open(JUDGE_LESSONS_FILE, "w") as f:
        json.dump(lessons, f, indent=2)

    return added


def get_judge_lessons_for_agent(agent_name: str) -> str:
    """Return formatted lesson block for injection into agent instructions."""
    lessons = load_judge_lessons()
    agent_lessons = lessons.get(agent_name, [])[-3:]
    if not agent_lessons:
        return ""
    lines = "\n".join(f"- {l}" for l in agent_lessons)
    return f"\n\n**Evaluation feedback from past runs — fix these issues:**\n{lines}"


# --------------------------------------------------------------------------- #
#  RAGAS Evaluation — 2 meaningful metrics for LeetCoach
# --------------------------------------------------------------------------- #
#
#  LeetCoach is NOT a RAG pipeline, but RAGAS metrics still apply:
#
#  1. Faithfulness — does the solution walkthrough stay faithful to the code?
#     user_input = problem, response = full solution text, contexts = [code block]
#     (measures: did the explanation invent steps not in the code?)
#
#  2. Response Relevancy — does the solution actually address the problem asked?
#     user_input = problem, response = solution text, no contexts needed
#     (measures: is the answer on-topic and non-redundant?)
#
#  We intentionally skip Complexity Faithfulness — it requires a separate
#  sample and the complexity text is too short for reliable scoring.
# --------------------------------------------------------------------------- #

def run_ragas_evaluations(
    problem_text: str,
    solution: str,
) -> dict:
    if not RAGAS_AVAILABLE:
        return {"error": "RAGAS not installed. Run: pip install ragas langchain-openai"}
    if not os.getenv("OPENAI_API_KEY"):
        return {"error": "OpenAI API key not set"}

    # Extract just the code block to use as the "retrieved context"
    code_match = re.search(r"```python(.+?)```", solution, re.DOTALL)
    code_context = code_match.group(1).strip() if code_match else solution[:800]

    try:
        evaluator_llm = LangchainLLMWrapper(ChatOpenAI(model="gpt-4o-mini", api_key=os.getenv("OPENAI_API_KEY")))
        evaluator_emb = LangchainEmbeddingsWrapper(OpenAIEmbeddings(api_key=os.getenv("OPENAI_API_KEY")))

        samples = [
            {
                "user_input":          problem_text[:800],
                "response":            solution[:2000],
                "retrieved_contexts":  [code_context],
            }
        ]
        dataset = EvaluationDataset.from_list(samples)

        result = ragas_evaluate(
            dataset=dataset,
            metrics=[faithfulness, answer_relevancy],
            llm=evaluator_llm,
            embeddings=evaluator_emb,
        )

        scores = result.to_pandas()

        def _get(col):
            if col in scores.columns:
                val = scores[col].iloc[0]
                try:
                    f = float(val)
                    import math
                    return round(f, 3) if not math.isnan(f) else None
                except Exception:
                    return None
            return None

        return {
            "solution_faithfulness": _get("faithfulness"),
            "answer_relevancy":      _get("response_relevancy") or _get("answer_relevancy"),
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

    async def _no_ragas():
        return {"error": "RAGAS not installed"}

    ragas_task = loop.run_in_executor(
        None,
        run_ragas_evaluations,
        problem_text, solution,
    ) if RAGAS_AVAILABLE else _no_ragas()

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
