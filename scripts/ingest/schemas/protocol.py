"""Pydantic schemas for clinical protocol extraction."""

from typing import List, Literal, Optional

from pydantic import BaseModel, Field

from .body_parts import BODY_PARTS_LITERAL


class ExerciseItem(BaseModel):
    raw_name: str = Field(
        description="The exact name of the exercise as written in the text. Do not generalize (e.g. use 'Y-Balance Test', not 'Balance exercises')."
    )
    specifications: Optional[str] = Field(
        default=None,
        description="Technique details, dosage, or constraints (e.g., 'palm up', '3x10 reps', 'isometric'). Leave null if not specified.",
    )
    clinical_rationale: Optional[str] = Field(
        default=None,
        description=(
            "The specific clinical purpose or target fault for THIS exercise "
            "mentioned in the text (e.g., 'to inhibit upper traps', "
            "'to correct anterior pelvic tilt', 'to reduce shoulder protraction'). "
            "Leave null if not stated."
        ),
    )


class ClinicalSection(BaseModel):
    title: str = Field(
        description="Name of the phase or section (e.g., 'Phase 1: 0-2 Weeks' or 'Conservative Management')."
    )
    goals: List[str] = Field(
        default_factory=list,
        description="Goals to achieve during this phase (e.g., 'Reduce edema', 'Restore ROM').",
    )
    precautions: List[str] = Field(
        default_factory=list,
        description="Phase-specific warnings or limits (e.g., 'Limit ROM to 90 deg', 'Avoid active extension').",
    )
    progression_criteria: List[str] = Field(
        default_factory=list,
        description="Requirements to move to the next phase or start an activity (e.g., 'Must perform 20 heel raises without pain').",
    )
    clinical_interventions: List[str] = Field(
        default_factory=list,
        description="Treatments performed BY the clinician (e.g., 'Ice', 'Joint mobilizations', 'Soft tissue massage', 'Game Ready').",
    )
    patient_exercises: List[ExerciseItem] = Field(
        default_factory=list,
        description=(
            "Active or passive physical movements performed BY THE PATIENT. MUST BE SPLIT into individual exercises. "
            "For corrective protocols, extract clinical_rationale when the text states the purpose (e.g., 'to inhibit upper traps', 'for glute activation')."
        ),
    )


class ClinicalProtocol(BaseModel):
    thought_process: str = Field(
        description="Think step-by-step before answering: 1. Is this a valid clinical text? 2. What is the document type? 3. Identify phases. 4. Differentiate red flags vs progression criteria."
    )
    is_valid_clinical_source: bool = Field(
        description="Set to false if the text is just a questionnaire, reference list, or administrative noise."
    )
    doc_type: Literal[
        "Protocol_Phased", "Guideline_General", "Test_Instruction", "Irrelevant"
    ] = Field(description="Classify the format of the document.")
    treatment_type: Literal[
        "Non-Operative", "Post-Operative", "Prevention", "Assessment", "Unknown"
    ] = Field(
        description=(
            "Classify the treatment approach. Use 'Post-Operative' ONLY if surgery or "
            "surgical repair is explicitly mentioned. Use 'Non-Operative' for conservative "
            "management without surgery. Use 'Prevention' for injury prevention programs. "
            "Use 'Assessment' for evaluation/test-only documents. Use 'Unknown' if unclear."
        )
    )
    primary_body_parts: List[BODY_PARTS_LITERAL] = Field(
        description=(
            "All anatomical regions this protocol targets. "
            "If a document covers multiple joints (e.g., shoulder AND elbow), "
            "list ALL applicable regions. Do not restrict to one."
        )
    )
    target_conditions: List[str] = Field(
        default_factory=list,
        description=(
            "Diagnoses OR Biomechanical Deficits treated by this protocol "
            "(e.g., ['ACL Tear', 'Dynamic Knee Valgus', 'H:Q Ratio Deficit', "
            "'Strength Asymmetry', 'Postural Kyphosis']). Include functional problems."
        ),
    )
    global_red_flags: List[str] = Field(
        default_factory=list,
        description="Absolute contraindications applicable to the WHOLE protocol (e.g., 'No open kinetic chain hamstring curls for 12 weeks').",
    )
    sections: List[ClinicalSection] = Field(
        default_factory=list,
        description="The core clinical logic broken down into phases or logical sections.",
    )
