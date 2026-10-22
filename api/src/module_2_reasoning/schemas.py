from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# FilteredTestResult is kept for the filter pipeline; ClinicalSummary no longer embeds it.


class FlaggedParameter(BaseModel):
    parameter: str
    value: float | None = None
    left: float | None = None
    right: float | None = None
    unit: str | None = None
    norm: list[float] | None = None
    asymmetry_percent: float | None = None
    asymmetry_norm_max: float | None = None
    flag_reason: str  # "above_norm" | "below_norm" | "asymmetry" | "no_norm"


class FilteredTestResult(BaseModel):
    test_name: str
    flagged_params: list[FlaggedParameter] = Field(default_factory=list)
    interpretation_uk: str | None = None
    recommendations_uk: str | None = None
    has_norm_data: bool


class ClinicalSummary(BaseModel):
    # CoT field MUST come first — project convention
    thought_process: str = Field(
        description="Step-by-step reasoning before producing findings and key_concerns."
    )
    patient_context: str = Field(
        description="2-3 sentence English description of the patient: age, gender, activity level, and overall clinical picture."
    )
    findings: list[str] = Field(
        description=(
            "One English paragraph per test. "
            "MUST enumerate EVERY parameter that is outside the norm by name, measured value, and norm range. "
            "For bilateral tests include left and right values separately. "
            "For asymmetry flags include the asymmetry % and the allowed max. "
            "For no-norm tests translate the Ukrainian interpretation in full. "
            "Do not skip or summarise away any flagged parameter."
        )
    )
    key_concerns: list[str] = Field(
        description="Top 3-5 cross-test clinical conclusions in English identifying patterns across tests."
    )
    full_patient_summary: str = Field(
        description=(
            "A comprehensive narrative paragraph (200-400 words) written in English for a physiotherapist. "
            "Synthesise all test findings into a coherent clinical picture: describe the patient's postural profile, "
            "strength deficits, range-of-motion limitations, balance findings, and any dental/sensory involvement. "
            "Reference specific measurements where relevant. Conclude with the most clinically urgent priorities."
        )
    )


class ProtocolQuery(BaseModel):
    body_part: Literal[
        "Knee",
        "Shoulder",
        "Spine",
        "Core_Pelvis",
        "Hip",
        "Foot_Ankle",
        "Elbow",
        "Wrist_Hand",
        "Head_Neck_TMJ",
        "General_Body_Multijoint",
    ] = Field(
        description="Primary anatomical region — used for ChromaDB metadata filter."
    )
    treatment_type: Literal[
        "Non-Operative", "Post-Operative", "Prevention", "Assessment", "Unknown"
    ] = Field(
        default="Non-Operative",
        description=(
            "Treatment type filter. Default is 'Non-Operative'. "
            "Use 'Post-Operative' only if surgery is explicitly mentioned in the clinical context. "
            "Use 'Prevention' for injury prevention programs. "
            "Use 'Assessment' for evaluation/test-only protocols. "
            "Use 'Unknown' only if the context is genuinely ambiguous."
        ),
    )
    keywords: str = Field(
        description="Space-separated clinical search terms for the vector DB query."
    )


class ProtocolQueryList(BaseModel):
    queries: list[ProtocolQuery] = Field(
        description="4–6 distinct, atomic queries covering each key concern."
    )


class PrescribedExercise(BaseModel):
    raw_name_from_protocol: str = Field(
        description="Exact exercise name as it appears in the protocol text, without dosage modifiers."
    )
    specifications: str | None = Field(
        default=None,
        description="Dosage, sets/reps, technique cues, or other modifiers from the protocol.",
    )
    clinical_rationale: str | None = Field(
        default=None,
        description="Why this exercise is prescribed for THIS specific patient.",
    )
    source_protocol_id: str | None = Field(
        default=None,
        description="parent_id of the protocol this exercise was sourced from (e.g., 'shoulder-biceps-tenotomy').",
    )
    source_section_title: str | None = Field(
        default=None,
        description="Section/phase title within the source protocol (e.g., 'Phase 2: Early Active Motion').",
    )


class PhasePlan(BaseModel):
    phase_title: str = Field(
        description=(
            "Temporal phase name (e.g., 'Phase 1 — Acute / Protective', "
            "'Phase 2 — Intermediate / Strengthening'). "
            "Do NOT include body-region names in the title."
        )
    )
    region_focus: list[str] = Field(
        default_factory=list,
        description=(
            "Body regions actively addressed in this phase "
            "(e.g., ['Knee', 'Shoulder']). Empty for single-region patients."
        ),
    )
    phase_goals: list[str] = Field(description="Goals for this phase.")
    clinical_interventions: list[str] = Field(
        default_factory=list,
        description="Non-exercise clinical interventions (modalities, manual therapy, etc.).",
    )
    prescribed_exercises: list[PrescribedExercise] = Field(default_factory=list)
    phase_precautions: list[str] = Field(
        default_factory=list,
        description="Phase-specific precautions and contraindications from the source protocol.",
    )
    progression_criteria: list[str] = Field(
        default_factory=list,
        description=(
            "Criteria that must be met before advancing to the next phase. "
            "For multi-region plans, each criterion MUST begin with the region name "
            "in brackets (e.g., '[Knee]: full extension without pain', "
            "'[Shoulder]: pain-free overhead reach')."
        ),
    )


class PrecautionFilter(BaseModel):
    original_precaution: str = Field(
        description="The exact precaution text from the source protocol's global_red_flags."
    )
    source_protocol: str = Field(
        description="The parent_id of the protocol this precaution came from."
    )
    category: Literal["disease_specific", "procedure_device_specific", "biomechanical"] = Field(
        description=(
            "'disease_specific' = relates to a systemic/neurological condition "
            "(e.g., Stroke, Cancer, BPPV, Meniere's, Spinal Cord Injury); "
            "'procedure_device_specific' = relates to a surgical procedure or medical device "
            "(e.g., Canalith Repositioning, post-op corset, surgical drain); "
            "'biomechanical' = ROM limit, load restriction, pain threshold, movement precaution, "
            "ergonomic advice, postural limits, prolonged sitting/standing warnings "
            "(e.g., avoid flexion > 90 deg, no impact activities, weight-bearing as tolerated, "
            "avoid prolonged sitting). "
            "FAIL-SAFE: If uncertain about category, classify as 'biomechanical' to ensure retention."
        )
    )
    is_applicable_to_patient: bool = Field(
        description=(
            "True ONLY if: (a) category='biomechanical' — always retain; OR "
            "(b) category='disease_specific' AND the patient actually has this condition; OR "
            "(c) category='procedure_device_specific' AND the procedure/device is in the patient's history "
            "or you are prescribing it in this plan. False otherwise."
        )
    )
    reason: str = Field(
        description="1-2 sentence justification for the applicability decision."
    )


class DraftTreatmentPlan(BaseModel):
    # CoT field MUST come first — project convention
    thought_process: str = Field(
        description="Step-by-step reasoning before producing the treatment plan."
    )
    precaution_analysis: list[PrecautionFilter] = Field(
        description=(
            "Evaluate UNIQUE global_red_flags across all retrieved protocols. "
            "First DEDUPLICATE — if the same precaution appears in multiple protocols, "
            "analyze it only ONCE and list all source protocols in source_protocol. "
            "Classify each and decide applicability. "
            "This analysis MUST be completed before populating global_precautions."
        )
    )
    global_precautions: list[str] = Field(
        description=(
            "ONLY precautions where precaution_analysis[].is_applicable_to_patient is True. "
            "Aggregate semantically similar items into single bullets (e.g., merge all "
            "'avoid mobilization when...' conditions into one). "
            "Include only the most critical, high-impact precautions — keep the list "
            "concise and actionable for quick clinical review."
        )
    )
    phases: list[PhasePlan] = Field(
        description=(
            "Temporally ordered integrated treatment phases (target: 3-5 phases). "
            "Each phase represents a time period, NOT a body region. "
            "For multi-region patients, each phase includes exercises for ALL relevant regions."
        )
    )


# --- RAG Loop Schemas ---


class ProtocolEvaluation(BaseModel):
    protocol_id: str = Field(description="The parent_id of the protocol.")
    is_relevant: bool
    reason_for_rejection: str | None = Field(
        default=None, description="If False, briefly explain why."
    )


class GraderOutput(BaseModel):
    thought_process: str = Field(
        description="Evaluate target conditions against the patient summary."
    )
    evaluations: list[ProtocolEvaluation]


class RewrittenQueries(BaseModel):
    thought_process: str
    queries: list[ProtocolQuery]


# --- English Report Schemas (report_generator_node output) ---


class EnglishReportExerciseSection(BaseModel):
    exercise_name: str = Field(
        description="Canonical exercise name from enriched_plan if mapped, otherwise raw_name_from_protocol."
    )
    patient_instructions: str = Field(
        description="Full exercise instructions copied VERBATIM from enriched_plan. Do NOT rewrite."
    )
    specifications: str | None = Field(
        default=None, description="Sets/reps/duration from enriched_plan."
    )
    clinical_rationale: str = Field(
        description="Functional-level explanation of why this exercise addresses this patient's concerns. No exact parameter values."
    )
    source_protocol_id: str | None = Field(
        default=None,
        description="parent_id of the protocol this exercise was sourced from (e.g., 'shoulder-biceps-tenotomy').",
    )
    source_section_title: str | None = Field(
        default=None,
        description="Section/phase title within the source protocol (e.g., 'Phase 2: Early Active Motion').",
    )


class EnglishReportPhaseSection(BaseModel):
    phase_title: str
    phase_goals: list[str]
    clinical_interventions: list[str]
    exercises: list[EnglishReportExerciseSection]
    phase_precautions: list[str]
    progression_criteria: list[str]


class EnglishRehabilitationReport(BaseModel):
    # CoT field MUST come first — project convention
    thought_process: str = Field(
        description="Step-by-step reasoning before producing the report (not rendered)."
    )
    report_title: str = Field(
        description="Static title: 'Individualized Rehabilitation Plan'. No PII."
    )
    patient_context: str = Field(
        description="2-4 sentences describing age, activity level, and relevant history. NO names or IDs."
    )
    clinical_findings: list[str] = Field(
        description="One paragraph per test describing findings at a functional level. No raw parameter values or norm ranges."
    )
    key_concerns: list[str] = Field(
        description="3-5 cross-test clinical conclusions mapped from clinical_summary.key_concerns."
    )
    global_precautions: list[str] = Field(
        description="Copied verbatim from enriched_plan.global_precautions."
    )
    phases: list[EnglishReportPhaseSection] = Field(
        description="Treatment phases with exercises."
    )
    summary_recommendations: str = Field(
        description="Concluding recommendations paragraph for the treating physiotherapist."
    )


# --- Report Formatter Schemas (Ukrainian — final output) ---


class ReportExerciseSection(BaseModel):
    exercise_name: str = Field(
        description="Canonical or raw exercise name in Ukrainian."
    )
    patient_instructions: str = Field(
        description="Full exercise instructions translated to Ukrainian."
    )
    specifications: str | None = Field(
        default=None, description="Sets/reps/duration in Ukrainian."
    )
    clinical_rationale: str = Field(
        description="Why this exercise is prescribed for this specific patient, in Ukrainian."
    )
    source_protocol_id: str | None = Field(
        default=None,
        description="parent_id of the protocol this exercise was sourced from. NOT translated — pass through verbatim from English report.",
    )
    source_section_title: str | None = Field(
        default=None,
        description="Section/phase title within the source protocol. NOT translated — pass through verbatim from English report.",
    )


class ReportPhaseSection(BaseModel):
    phase_title: str
    phase_goals: list[str]
    clinical_interventions: list[str]
    exercises: list[ReportExerciseSection]
    phase_precautions: list[str]
    progression_criteria: list[str]


class RehabilitationReport(BaseModel):
    # CoT field MUST come first — project convention
    thought_process: str = Field(
        description="Step-by-step reasoning before producing the report (not rendered)."
    )
    report_title: str = Field(
        description="Report title in Ukrainian, e.g. 'Індивідуальний план реабілітації'."
    )
    patient_context: str = Field(
        description="2-4 sentences describing the patient context in Ukrainian."
    )
    clinical_findings: list[str] = Field(
        description="One paragraph per test describing findings in Ukrainian."
    )
    key_concerns: list[str] = Field(
        description="3-5 cross-test clinical conclusions in Ukrainian."
    )
    global_precautions: list[str] = Field(
        description="Aggregated precautions/contraindications in Ukrainian."
    )
    phases: list[ReportPhaseSection] = Field(
        description="Treatment phases with exercises, in Ukrainian."
    )
    summary_recommendations: str = Field(
        description="Concluding recommendations paragraph in Ukrainian."
    )
