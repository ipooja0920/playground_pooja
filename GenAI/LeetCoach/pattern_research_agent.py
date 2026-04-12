"""
Pattern Research Agent for LeetCoach.

Triggered when a user flags the classifier's pattern as wrong.
Uses gpt-4o to:
  1. Identify the correct pattern + specific sub-pattern
  2. Extract the key signal that should have triggered it
  3. Write a lesson to pattern_knowledge.json for future classifier runs

pattern_knowledge.json structure:
{
  "Dynamic Programming": [
    {
      "problem": "Interleaving String (#97)",
      "sub_pattern": "2D / Grid DP",
      "why": "Two strings being interleaved — dp[i][j] = can we form s3 using s1[0..i] and s2[0..j]",
      "signal": "Two string inputs + interleaving/matching/forming = 2D DP, NOT Sliding Window",
      "wrong_pattern": "Sliding Window",
      "timestamp": "2026-04-11T..."
    }
  ]
}
"""

import json
import re
from pathlib import Path
from datetime import datetime
from openai import AsyncOpenAI

from patterns import PATTERNS

PATTERN_KNOWLEDGE_FILE = Path(__file__).parent / "pattern_knowledge.json"
MODEL_FULL = "gpt-4o"

# Build sub-pattern context from patterns.py for the research agent
def _build_sub_pattern_context() -> str:
    lines = []
    for p in PATTERNS:
        sub_patterns = p.get("sub_patterns", [])
        if sub_patterns:
            lines.append(f"\n**{p['name']}** sub-patterns:")
            for sp in sub_patterns:
                lines.append(f"  - {sp['name']}: {sp['signal']} (e.g. {sp['example']})")
        else:
            signals = "; ".join(p["when_to_use"][:3])
            lines.append(f"\n**{p['name']}**: {signals}")
    return "\n".join(lines)


_SUB_PATTERN_CONTEXT = _build_sub_pattern_context()

RESEARCH_INSTRUCTION = f"""
You are an expert algorithm pattern researcher for a LeetCode teaching tool.

Your job: given a LeetCode problem (and optionally the wrong pattern that was picked),
identify the correct pattern AND the specific sub-pattern, then explain exactly what
signal in the problem should trigger that pattern.

Here are the 20 patterns and their sub-patterns:
{_SUB_PATTERN_CONTEXT}

Respond in EXACTLY this JSON format (no extra text, valid JSON only):
{{
  "correct_pattern": "<exact pattern name from the 20 above>",
  "sub_pattern": "<specific sub-pattern name, or 'N/A' if no sub-pattern applies>",
  "why": "<1-2 sentences: what in this problem indicates this pattern>",
  "signal": "<the key phrase/clue in the problem that should trigger this pattern — be very specific>",
  "classifier_lesson": "<one sentence telling the classifier what mistake to avoid on similar problems>"
}}
"""


def load_pattern_knowledge() -> dict:
    if PATTERN_KNOWLEDGE_FILE.exists():
        with open(PATTERN_KNOWLEDGE_FILE) as f:
            return json.load(f)
    return {}


def save_pattern_knowledge(pattern_name: str, entry: dict):
    """Append a lesson to pattern_knowledge.json under the correct pattern."""
    knowledge = load_pattern_knowledge()
    if pattern_name not in knowledge:
        knowledge[pattern_name] = []

    # Deduplicate by problem title
    problem = entry.get("problem", "")
    knowledge[pattern_name] = [k for k in knowledge[pattern_name] if k.get("problem") != problem]
    knowledge[pattern_name].append(entry)
    knowledge[pattern_name] = knowledge[pattern_name][-10:]  # keep last 10 per pattern

    with open(PATTERN_KNOWLEDGE_FILE, "w") as f:
        json.dump(knowledge, f, indent=2)


def get_pattern_knowledge_for_classifier() -> str:
    """
    Return formatted pattern knowledge block to inject into the classifier instruction.
    Pulls the most recent lesson per pattern (max 6 patterns, 1 lesson each to keep context short).
    """
    knowledge = load_pattern_knowledge()
    if not knowledge:
        return ""

    lines = ["\n\n**Pattern research lessons — apply these to avoid past mistakes:**"]
    count = 0
    for pattern_name, entries in knowledge.items():
        if not entries or count >= 6:
            break
        latest = entries[-1]
        signal   = latest.get("signal", "")
        lesson   = latest.get("classifier_lesson", "")
        sub      = latest.get("sub_pattern", "")
        sub_note = f" [{sub}]" if sub and sub != "N/A" else ""
        lines.append(f"- {pattern_name}{sub_note}: {signal} — {lesson}")
        count += 1

    return "\n".join(lines)


async def run_pattern_research(
    problem_text: str,
    problem_title: str = "",
    wrong_pattern: str = "",
    user_correction: str = "",
) -> dict:
    """
    Run the Pattern Research Agent.

    Args:
        problem_text:    Full problem description
        problem_title:   Problem title (for tagging the lesson)
        wrong_pattern:   What the classifier incorrectly identified
        user_correction: Optional — what the user says the correct pattern is

    Returns:
        dict with keys: correct_pattern, sub_pattern, why, signal,
                        classifier_lesson, lesson_saved, error
    """
    client = AsyncOpenAI()

    user_msg_parts = [f"LeetCode Problem:\n{problem_text[:1200]}"]
    if wrong_pattern:
        user_msg_parts.append(f"\nThe classifier incorrectly identified: **{wrong_pattern}**")
    if user_correction:
        user_msg_parts.append(f"\nThe user says the correct pattern is: **{user_correction}**")
    user_msg_parts.append("\nResearch and identify the correct pattern and sub-pattern.")

    user_msg = "\n".join(user_msg_parts)

    try:
        response = await client.chat.completions.create(
            model=MODEL_FULL,
            messages=[
                {"role": "system", "content": RESEARCH_INSTRUCTION},
                {"role": "user",   "content": user_msg},
            ],
            temperature=0,
            max_tokens=500,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content.strip()
        data = json.loads(raw)
    except Exception as e:
        return {"error": str(e), "lesson_saved": False}

    # Validate the pattern name against our list
    valid_names = {p["name"] for p in PATTERNS}
    correct_pattern = data.get("correct_pattern", "")
    if correct_pattern not in valid_names:
        # Try case-insensitive match
        match = next((p["name"] for p in PATTERNS if p["name"].lower() == correct_pattern.lower()), None)
        if match:
            correct_pattern = match
            data["correct_pattern"] = correct_pattern
        else:
            data["error"] = f"Research agent returned unknown pattern: '{correct_pattern}'"
            data["lesson_saved"] = False
            return data

    # Build the knowledge entry
    title = problem_title or problem_text.strip().split("\n")[0][:80]
    entry = {
        "problem":            title,
        "sub_pattern":        data.get("sub_pattern", "N/A"),
        "why":                data.get("why", ""),
        "signal":             data.get("signal", ""),
        "classifier_lesson":  data.get("classifier_lesson", ""),
        "wrong_pattern":      wrong_pattern,
        "timestamp":          datetime.now().isoformat(),
    }

    save_pattern_knowledge(correct_pattern, entry)
    data["lesson_saved"] = True
    data["error"] = None
    return data
