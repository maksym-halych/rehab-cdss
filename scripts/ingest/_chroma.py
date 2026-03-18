"""Shared ChromaDB document-building helpers for the ingest pipeline."""

from pathlib import Path
from typing import Any


def _get_exercises(section: dict) -> list[dict]:
    """Return exercise list tolerating both 'exercises' and 'patient_exercises' keys."""
    return section.get("patient_exercises") or section.get("exercises") or []


def build_protocol_doc(protocol: dict, section: dict, section_index: int) -> str:
    """Build document text for a protocol section for ChromaDB embedding."""
    raw = protocol.get("primary_body_parts") or [protocol.get("primary_body_part", "")]
    body_part = ", ".join(raw) if isinstance(raw, list) else raw
    treatment_type = protocol.get("treatment_type", "Unknown")
    conditions = ", ".join(protocol.get("target_conditions", []))

    global_flags = protocol.get("global_red_flags", [])
    global_flags_str = ", ".join(global_flags) if global_flags else "None"

    title = section.get("title", "")
    goals = ", ".join(section.get("goals", []))
    precautions = ", ".join(section.get("precautions", []))
    parts = []
    for ex in _get_exercises(section):
        name = ex.get("raw_name", "")
        rationale = ex.get("clinical_rationale") or ""
        if rationale:
            parts.append(f"{name} (for: {rationale})")
        else:
            parts.append(name)
    exercise_str = "; ".join(parts)
    interventions = ", ".join(section.get("clinical_interventions", []))

    return (
        f"[PROTOCOL CONTEXT]: {body_part} | Treatment: {treatment_type} | Conditions: {conditions}\n"
        f"[GLOBAL RED FLAGS]: {global_flags_str}\n"
        f"[SECTION]: {title} (Index: {section_index})\n"
        f"[PHASE GOALS]: {goals}\n"
        f"[PHASE PRECAUTIONS]: {precautions}\n"
        f"[CLINICAL INTERVENTIONS]: {interventions}\n"
        f"[EXERCISES]: {exercise_str}"
    )


def build_protocol_metadata(
    protocol: dict, section: dict, section_index: int, source_file: str
) -> dict[str, Any]:
    """Build metadata dict for a protocol section upsert."""
    raw = protocol.get("primary_body_parts") or [protocol.get("primary_body_part", "")]
    if isinstance(raw, list):
        body_parts_list = [x for x in raw if x]
    else:
        body_parts_list = [raw] if raw else []
    if not body_parts_list:
        body_parts_list = ["General_Body_Multijoint"]
    return {
        "parent_id": Path(source_file).stem,
        "source_file": source_file,
        "doc_type": protocol.get("doc_type", ""),
        "treatment_type": protocol.get("treatment_type", "Unknown"),
        "primary_body_parts": body_parts_list,
        "target_conditions": ", ".join(protocol.get("target_conditions", [])),
        "global_red_flags": ", ".join(protocol.get("global_red_flags", [])),
        "section_title": section.get("title", ""),
        "section_index": section_index,
        "goals": ", ".join(section.get("goals", [])),
        "precautions": ", ".join(section.get("precautions", [])),
        "progression_criteria": ", ".join(section.get("progression_criteria", [])),
    }


def build_exercise_doc(card: dict) -> str:
    """Build document text for an exercise card for ChromaDB embedding."""
    canonical = card.get("canonical_name", "")
    aliases = ", ".join(card.get("aliases", []))
    parts = ", ".join(card.get("primary_body_parts", []))
    instructions = card.get("patient_instructions", "")
    return f"{canonical}. Also known as: {aliases}. Body parts: {parts}. {instructions}"


def build_exercise_metadata(card: dict) -> dict[str, Any]:
    """Build full metadata dict for an exercise card upsert."""
    tags = card.get("mechanics_tags", {})
    return {
        "canonical_name": card.get("canonical_name", ""),
        "aliases": ", ".join(card.get("aliases", [])),
        "primary_body_parts": ", ".join(card.get("primary_body_parts", [])),
        "is_closed_chain": bool(tags.get("is_closed_chain", False)),
        "has_axial_load": bool(tags.get("has_axial_load", False)),
        "is_high_impact": bool(tags.get("is_high_impact", False)),
        "requires_overhead_motion": bool(tags.get("requires_overhead_motion", False)),
        "target_muscles": ", ".join(card.get("target_muscles", [])),
        "exercise_category": card.get("exercise_category", ""),
        "is_unilateral": bool(card.get("is_unilateral", False)),
        "difficulty_level": card.get("difficulty_level", ""),
        "equipment_needed": ", ".join(card.get("equipment_needed", [])),
    }
