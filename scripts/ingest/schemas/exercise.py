"""Pydantic schemas for exercise card generation and entity resolution."""

from typing import Literal

from pydantic import BaseModel, Field


class MechanicsTags(BaseModel):
    is_closed_chain: bool = Field(
        description="True if the distal segment is fixed during motion (e.g., squat, push-up). False for open-chain (e.g., leg extension, straight leg raise)."
    )
    has_axial_load: bool = Field(
        description="True if body weight or external load compresses the spine or joint axially (e.g., standing exercises, loaded carries, squats)."
    )
    is_high_impact: bool = Field(
        description="True if the exercise involves jumping, landing, or rapid change of direction (e.g., box jumps, agility drills, plyometrics)."
    )
    requires_overhead_motion: bool = Field(
        description="True if the arm or load must travel above shoulder height (e.g., overhead press, pull-up, shoulder elevation exercises)."
    )


class ExerciseCard(BaseModel):
    thought_process: str = Field(
        description=(
            "Think step-by-step before filling other fields: "
            "1. What is the standardized medical name? "
            "2. Which body parts and movement pattern are involved? "
            "3. Classify each mechanics tag with a brief justification. "
            "4. Identify primary muscles, exercise category, unilateral/bilateral, difficulty, and required equipment."
        )
    )
    canonical_name: str = Field(
        description="Standardized medical/clinical name in English. Title Case. (e.g., 'Straight Leg Raise', 'Isometric Quadriceps Set')."
    )
    aliases: list[str] = Field(
        default_factory=list,
        description="All known raw names and synonyms that map to this exercise.",
    )
    primary_body_parts: list[str] = Field(
        default_factory=list,
        description="Anatomical regions primarily involved (e.g., ['Knee', 'Quadriceps']).",
    )
    patient_instructions: str = Field(
        description="Clear, numbered execution steps written FOR THE PATIENT. English. 3-6 steps."
    )
    patient_instructions_uk: str | None = Field(
        default=None,
        description="Ukrainian translation of patient_instructions. Leave null — reserved for future localization pass.",
    )
    mechanics_tags: MechanicsTags = Field(
        description="Boolean biomechanical classification tags."
    )
    target_muscles: list[str] = Field(
        default_factory=list,
        description="Primary muscles engaged (e.g., ['Quadriceps', 'Gluteus Medius']).",
    )
    exercise_category: Literal[
        "Strength", "Stretch", "Mobility/ROM", "Balance/Proprioception", "Plyometric"
    ] = Field(description="Functional classification of the movement pattern.")
    is_unilateral: bool = Field(
        description="True if the exercise isolates one limb at a time. False for bilateral movements."
    )
    difficulty_level: Literal["Beginner", "Intermediate", "Advanced"] = Field(
        description="Relative difficulty based on balance demands, coordination, and load."
    )
    equipment_needed: list[str] = Field(
        default_factory=list,
        description="Required equipment. Use ['None'] if bodyweight only.",
    )


class EntityResolutionDecision(BaseModel):
    thought_process: str = Field(
        description=(
            "Compare the new raw_name against each candidate carefully. "
            "Are they truly the same movement (same muscle, same joint, same chain type)? "
            "Small wording/abbreviation variations → MERGE. "
            "Different equipment, load, joint range, or movement type → CREATE_NEW."
        )
    )
    decision: Literal["MERGE", "CREATE_NEW"] = Field(
        description="MERGE if the raw_name is a clinical synonym of an existing exercise. CREATE_NEW otherwise."
    )
    merge_target_id: str | None = Field(
        default=None,
        description="The exercise_id (filename without .json) of the existing exercise to merge into. Required when decision is MERGE, null otherwise.",
    )
