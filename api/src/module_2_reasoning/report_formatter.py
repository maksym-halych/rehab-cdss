"""Report Formatter — English report generation + Ukrainian translation + markdown rendering."""

from __future__ import annotations

import json

from langchain_openai import ChatOpenAI

from .schemas import EnglishRehabilitationReport, RehabilitationReport

from module_2_reasoning._retry import invoke_structured


ENGLISH_REPORT_PROMPT = """\
You are a senior physiotherapist writing a formal English rehabilitation report.

PATIENT INFO (age, gender, activity level — NO names or IDs):
{patient_info_json}

CLINICAL SUMMARY (English, from prior pipeline step):
{clinical_summary_json}

TREATMENT PLAN (enriched with exercise DB data):
{enriched_plan_json}

INSTRUCTIONS:
1. Begin with 'thought_process' — your step-by-step reasoning (not rendered).
2. 'report_title': Always output exactly "Individualized Rehabilitation Plan".
   Do NOT include patient name, date, or any PII.
3. 'patient_context': 2-4 sentences describing age, activity level, and
   relevant history from clinical_summary. NO names/IDs.
4. 'clinical_findings': Synthesize from clinical_summary.findings ONLY.
   Do NOT copy raw parameter values, floats, or norm ranges.
   Describe findings at a functional level (e.g., "significant right-sided
   hip flexion strength deficit identified in dynamometry").
5. 'key_concerns': Directly map from clinical_summary.key_concerns.
   Rephrase for report readability but preserve clinical meaning.
6. 'global_precautions': Copy from enriched_plan.global_precautions verbatim.
7. For each phase in enriched_plan:
   - 'phase_title', 'phase_goals', 'phase_precautions', 'progression_criteria':
     copy from enriched_plan verbatim.
   - 'clinical_interventions': copy from enriched_plan verbatim.
   - For each exercise:
     - 'exercise_name': use canonical_name from enriched_plan if mapped,
       otherwise raw_name_from_protocol.
     - 'patient_instructions': copy VERBATIM from enriched_plan.
       Do NOT rewrite, summarize, or adapt safety-critical instructions.
     - 'specifications': copy from enriched_plan verbatim.
     - 'clinical_rationale': explain at FUNCTIONAL level why this exercise
       addresses this patient's concerns. Reference key_concerns by name.
       Do NOT quote exact parameter values or percentages.
     - 'source_protocol_id': copy from enriched_plan VERBATIM.
     - 'source_section_title': copy from enriched_plan VERBATIM.
8. 'summary_recommendations': concluding paragraph for the treating
   physiotherapist.
"""


TRANSLATION_PROMPT = """\
You are a senior Ukrainian physical therapist translating a structured \
English rehabilitation report to formal Ukrainian medical register.

ENGLISH REPORT (structured JSON — translate field by field):
{english_report_json}

INSTRUCTIONS:

1. Begin with 'thought_process' — key translation decisions (not rendered).

2. CLINICAL REGISTER: Maintain strict, professional Ukrainian clinical \
language. DO NOT use:
   - Direct English calques or colloquialisms
   - Russian "Surzhik" forms
   Enforce these exact terminology standards:
   - Use 'Процедури фізичної терапії' or 'Терапевтичні заходи' \
(NOT 'Клінічні втручання')
   - Use 'Закрокування на степ/платформу' (NOT 'Зашагування')
   - Use 'Параметри виконання' or 'Обсяг навантаження' for dosage \
(NOT awkward calques)

3. MEDICAL TERMINOLOGY GLOSSARY:
   - ROM / Range of Motion → амплітуда рухів (АР)
   - Asymmetry → асиметрія
   - Deficit → дефіцит
   - Precaution → застереження
   - Contraindication → протипоказання
   - Strengthening → зміцнення
   - Stretching → розтягування
   - Mobility → мобільність
   - Proprioception → пропріоцепція
   - Manual therapy → мануальна терапія
   - Flexion/Extension → згинання/розгинання
   - Abduction/Adduction → відведення/приведення
   - Internal/External rotation → внутрішня/зовнішня ротація
   - Cervical/Thoracic/Lumbar → шийний/грудний/поперековий

4. EXERCISE NAME TRANSLATION RULE: Do NOT literally translate idiomatic \
English exercise names. Examples:
   - 'Clamshells' → 'Відведення стегна лежачи на боці з зігнутими колінами' \
(NEVER 'Мушлі')
   - 'Bird Dog' → 'Одночасне підняття протилежних руки та ноги з \
колінно-ліктьової позиції' (NEVER 'Птах-собака')
   - 'Deadbug' → 'Почергове випрямлення ніг лежачи на спині зі \
стабілізацією попереку' (NEVER 'Мертвий жук')
   If a direct clinical equivalent is unknown, translate the BIOMECHANICAL \
ACTION, not the English idiom. If truly untranslatable, keep the English \
name in parentheses after the Ukrainian description.

5. DEVICE PARAMETER NAMES: Use established Ukrainian medical terminology, \
not literal translations. Examples:
   - 'Spine Length' → 'Довжина хребта' (NOT 'Довжина спини')
   If a parameter is highly device-specific, preserve its standard clinical \
meaning in Ukrainian orthopedics.

6. ABBREVIATIONS AND UNITS — localize all:
   - 'ROM' → 'АР' (амплітуда рухів)
   - 'reps' / 'repetitions' → 'повторення'
   - 'sets' → 'серії'
   - 'sec' / 'seconds' → 'сек'
   - 'min' / 'minutes' → 'хв'
   Do NOT leave English abbreviations in the output.

7. NUMBERS: Preserve ALL integers and float values EXACTLY as they appear \
in the source.

8. 'report_title': Translate to 'Індивідуальний план реабілітації'.

9. SOURCE FIELDS ('source_protocol_id', 'source_section_title'):
   Copy VERBATIM from the English report. Do NOT translate — these are canonical identifiers.
"""


_HEADERS = {
    "uk": {
        "patient_context": "Контекст пацієнта",
        "clinical_findings": "Клінічні знахідки",
        "key_concerns": "Ключові проблеми",
        "global_precautions": "Загальні застереження",
        "rehab_plan": "План реабілітації",
        "goals": "Цілі:",
        "clinical_interventions": "Процедури фізичної терапії:",
        "exercises": "Вправи",
        "instructions": "Інструкції",
        "dosage": "Параметри виконання",
        "rationale": "Обґрунтування",
        "phase_precautions": "Застереження фази:",
        "progression_criteria": "Критерії прогресу:",
        "recommendations": "Рекомендації",
        "source": "Джерело",
        "protocol_sources": "Джерела протоколів",
        "ref_number": "№",
        "ref_protocol": "Протокол",
        "ref_section": "Розділ",
    },
    "en": {
        "patient_context": "Patient Context",
        "clinical_findings": "Clinical Findings",
        "key_concerns": "Key Concerns",
        "global_precautions": "Global Precautions",
        "rehab_plan": "Rehabilitation Plan",
        "goals": "Goals:",
        "clinical_interventions": "Clinical Interventions:",
        "exercises": "Exercises",
        "instructions": "Instructions",
        "dosage": "Specifications",
        "rationale": "Clinical Rationale",
        "phase_precautions": "Phase Precautions:",
        "progression_criteria": "Progression Criteria:",
        "recommendations": "Recommendations",
        "source": "Source",
        "protocol_sources": "Protocol Sources",
        "ref_number": "#",
        "ref_protocol": "Protocol",
        "ref_section": "Section",
    },
}


def generate_english_report(
    clinical_summary,
    enriched_plan: dict,
    patient_info: dict,
    llm: ChatOpenAI,
    fallback_llm: ChatOpenAI | None = None,
) -> EnglishRehabilitationReport:
    """Call LLM to produce a structured English rehabilitation report."""

    summary_json = json.dumps(
        clinical_summary.model_dump() if clinical_summary else {},
        ensure_ascii=False,
        indent=2,
    )
    plan_json = json.dumps(enriched_plan or {}, ensure_ascii=False, indent=2)
    patient_json = json.dumps(
        {key: patient_info[key] for key in ("age", "gender", "activity_level") if key in patient_info},
        ensure_ascii=False,
        indent=2,
    )

    prompt = ENGLISH_REPORT_PROMPT.format(
        patient_info_json=patient_json,
        clinical_summary_json=summary_json,
        enriched_plan_json=plan_json,
    )

    return invoke_structured(llm, EnglishRehabilitationReport, prompt, fallback_llm)


def translate_report(
    english_report: EnglishRehabilitationReport,
    llm: ChatOpenAI,
    fallback_llm: ChatOpenAI | None = None,
) -> RehabilitationReport:
    """Translate structured English report to Ukrainian via LLM."""

    english_json = json.dumps(
        english_report.model_dump(),
        ensure_ascii=False,
        indent=2,
    )

    prompt = TRANSLATION_PROMPT.format(english_report_json=english_json)

    return invoke_structured(llm, RehabilitationReport, prompt, fallback_llm)


def render_markdown(report, lang: str = "uk") -> str:
    """Deterministically render a report (English or Ukrainian) to markdown."""
    headers = _HEADERS[lang]
    lines: list[str] = []

    # Pre-scan: build reference map for protocol source citations
    ref_map: dict[tuple[str, str | None], int] = {}
    for phase in report.phases:
        for ex in phase.exercises:
            pid = getattr(ex, "source_protocol_id", None)
            if pid:
                stitle = getattr(ex, "source_section_title", None)
                ref_key = (pid, stitle)
                if ref_key not in ref_map:
                    ref_map[ref_key] = len(ref_map) + 1

    lines.append(f"# {report.report_title}")
    lines.append("")

    lines.append(f"## {headers['patient_context']}")
    lines.append("")
    lines.append(report.patient_context)
    lines.append("")

    lines.append(f"## {headers['clinical_findings']}")
    lines.append("")
    for finding in report.clinical_findings:
        lines.append(finding)
        lines.append("")

    lines.append(f"## {headers['key_concerns']}")
    lines.append("")
    for concern in report.key_concerns:
        lines.append(f"- {concern}")
    lines.append("")

    lines.append(f"## {headers['global_precautions']}")
    lines.append("")
    for precaution in report.global_precautions:
        lines.append(f"- {precaution}")
    lines.append("")

    lines.append(f"## {headers['rehab_plan']}")
    lines.append("")

    for phase in report.phases:
        lines.append(f"### {phase.phase_title}")
        lines.append("")

        lines.append(f"**{headers['goals']}**")
        for goal in phase.phase_goals:
            lines.append(f"- {goal}")
        lines.append("")

        if phase.clinical_interventions:
            lines.append(f"**{headers['clinical_interventions']}**")
            for intervention in phase.clinical_interventions:
                lines.append(f"- {intervention}")
            lines.append("")

        if phase.exercises:
            lines.append(f"#### {headers['exercises']}")
            lines.append("")
            for ex in phase.exercises:
                pid = getattr(ex, "source_protocol_id", None)
                ref_num = ref_map.get((pid, getattr(ex, "source_section_title", None))) if pid else None
                suffix = f" [{ref_num}]" if ref_num else ""
                lines.append(f"**{ex.exercise_name}**{suffix}")
                lines.append(f"- {headers['instructions']}: {ex.patient_instructions}")
                if ex.specifications:
                    lines.append(f"- {headers['dosage']}: {ex.specifications}")
                lines.append(f"- {headers['rationale']}: {ex.clinical_rationale}")
                lines.append("")

        if phase.phase_precautions:
            lines.append(f"**{headers['phase_precautions']}**")
            for precaution in phase.phase_precautions:
                lines.append(f"- {precaution}")
            lines.append("")

        if phase.progression_criteria:
            lines.append(f"**{headers['progression_criteria']}**")
            for criterion in phase.progression_criteria:
                lines.append(f"- {criterion}")
            lines.append("")

    lines.append(f"## {headers['recommendations']}")
    lines.append("")
    lines.append(report.summary_recommendations)
    lines.append("")

    # Protocol sources reference table
    if ref_map:
        lines.append(f"## {headers['protocol_sources']}")
        lines.append("")
        lines.append(f"| {headers['ref_number']} | {headers['ref_protocol']} | {headers['ref_section']} |")
        lines.append("|---|----------|--------|")
        for (pid, stitle), num in sorted(ref_map.items(), key=lambda x: x[1]):
            readable = pid.replace("-", " ").replace("_", " ").title()
            section = stitle if stitle else "—"
            lines.append(f"| {num} | {readable} | {section} |")
        lines.append("")

    return "\n".join(lines)
