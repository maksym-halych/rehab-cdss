"""Deterministic exercise matching, shared by the graph and unit tests."""

from collections.abc import Callable

from rapidfuzz import fuzz

from .schemas import DraftTreatmentPlan


def map_exercises(draft_plan: DraftTreatmentPlan, search_exercises: Callable) -> dict:
    FUZZY_THRESHOLD = 85
    STRICT_VECTOR_THRESHOLD = 0.40

    enriched_phases: list[dict] = []
    mapped_count = 0
    unmapped_count = 0

    for phase in draft_plan.phases:
        enriched_exercises: list[dict] = []
        for ex in phase.prescribed_exercises:
            ex_dict = ex.model_dump()
            hits = search_exercises(query=ex.raw_name_from_protocol, n_results=5)

            best_hit = None
            raw_lower = ex.raw_name_from_protocol.lower()
            # Rule A: Fuzzy bypass — find first hit with fuzzy score >= 85
            # Checks canonical_name and all aliases
            for hit in hits:
                meta = hit["metadata"]
                names_to_check = [meta.get("canonical_name", "")]
                aliases_str = meta.get("aliases", "")
                if aliases_str:
                    names_to_check.extend(
                        a.strip() for a in aliases_str.split(",") if a.strip()
                    )
                for name in names_to_check:
                    score = fuzz.token_set_ratio(raw_lower, name.lower())
                    if score >= FUZZY_THRESHOLD:
                        best_hit = hit
                        break
                if best_hit is not None:
                    break

            # Rule B: Strict vector fallback — top hit with distance < 0.40
            if (
                best_hit is None
                and hits
                and hits[0]["distance"] < STRICT_VECTOR_THRESHOLD
            ):
                best_hit = hits[0]

            if best_hit is not None:
                meta = best_hit["metadata"]
                ex_dict["is_mapped"] = True
                ex_dict["canonical_name"] = meta.get("canonical_name", "")
                ex_dict["patient_instructions"] = best_hit.get("document", "")
                ex_dict["mechanics_tags"] = {
                    "is_closed_chain": meta.get("is_closed_chain", False),
                    "has_axial_load": meta.get("has_axial_load", False),
                    "is_high_impact": meta.get("is_high_impact", False),
                    "requires_overhead_motion": meta.get(
                        "requires_overhead_motion", False
                    ),
                }
                ex_dict["match_distance"] = best_hit["distance"]
                mapped_count += 1
            else:
                # Rule C: Miss
                ex_dict["is_mapped"] = False
                ex_dict["match_distance"] = hits[0]["distance"] if hits else None
                unmapped_count += 1
            enriched_exercises.append(ex_dict)

        enriched_phases.append(
            {
                "phase_title": phase.phase_title,
                "region_focus": phase.region_focus,
                "phase_goals": phase.phase_goals,
                "clinical_interventions": phase.clinical_interventions,
                "prescribed_exercises": enriched_exercises,
                "phase_precautions": phase.phase_precautions,
                "progression_criteria": phase.progression_criteria,
            }
        )

    enriched_plan = {
        "global_precautions": draft_plan.global_precautions,
        "phases": enriched_phases,
    }
    print(f"  Mapped {mapped_count} exercise(s), {unmapped_count} unmapped")
    return enriched_plan
