"""Step 2 — ClinicalSummarizer: LLM translation + summarization via Gemini."""

from __future__ import annotations

import json

from langchain_openai import ChatOpenAI

from .schemas import ClinicalSummary, FilteredTestResult  # noqa: F401 FilteredTestResult used in type hint
from ._retry import invoke_structured


def summarize(
    filtered: list[FilteredTestResult],
    patient_info: dict,
    llm: ChatOpenAI,
    fallback_llm: ChatOpenAI | None = None,
) -> ClinicalSummary:
    """
    Translate Ukrainian clinical data and produce a structured English ClinicalSummary.

    The LLM receives only filtered data (noise already removed by Step 1).
    """
    age = patient_info.get("age", "unknown")
    gender_uk = patient_info.get("gender", "")
    gender = (
        "male" if "олов" in gender_uk else "female" if "інк" in gender_uk else gender_uk
    )
    activity = patient_info.get("activity_level", "unknown")

    # Serialize filtered data, excluding raw_filtered from ClinicalSummary recursion
    filtered_json = json.dumps(
        [fr.model_dump() for fr in filtered],
        ensure_ascii=False,
        indent=2,
    )

    prompt = f"""
<instructions>
    You are a clinical physiotherapy assistant producing structured English reports.
    Rules:
    1. Output MUST be in English only. Translate all Ukrainian text inline.
    2. Fill 'thought_process' FIRST — reason through each test before writing findings.
    3. 'findings' — one item per test in <filtered_data>:
       - For tests WITH flagged_params: you MUST list EVERY flagged parameter. For each one state:
           * the parameter name (translated to English)
           * the measured value (and left/right values if bilateral)
           * the norm range
           * the flag reason (below norm / above norm / asymmetry exceeded)
           * asymmetry_percent and asymmetry_norm_max if present
         Do NOT summarise, group, or skip any flagged parameter.
       - For tests with NO flagged_params but with interpretation_uk: translate the full interpretation text.
    4. 'key_concerns' — 3 to 5 cross-test patterns (e.g., right-side strength deficit, postural chain issues).
    5. 'full_patient_summary' — a comprehensive clinical narrative (200-400 words) for a physiotherapist.
       Cover: postural profile, strength deficits, range-of-motion limitations, balance/stability,
       dental/sensory involvement, and conclude with the most urgent clinical priorities.
       Reference specific measurements where relevant.
    6. 'patient_context' — 2-3 sentences: age, gender, activity level, overall clinical picture.
</instructions>

<patient_context>
Age: {age}
Gender: {gender}
Activity level: {activity}
</patient_context>

<filtered_data>
{filtered_json}
</filtered_data>
"""

    return invoke_structured(llm, ClinicalSummary, prompt, fallback_llm)
