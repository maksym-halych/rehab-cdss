from unittest.mock import Mock

import pytest

from module_2_reasoning.exercise_mapper import map_exercises
from module_2_reasoning.schemas import DraftTreatmentPlan, PhasePlan, PrescribedExercise


def plan(name="Knee extension"):
    return DraftTreatmentPlan(
        thought_process="Synthetic fixture",
        precaution_analysis=[],
        global_precautions=["Demo only"],
        phases=[
            PhasePlan(
                phase_title="Demo phase",
                phase_goals=["Demo goal"],
                prescribed_exercises=[
                    PrescribedExercise(
                        raw_name_from_protocol=name,
                        specifications="Demo dosage",
                        source_protocol_id="synthetic-knee",
                        source_section_title="Demo phase",
                    )
                ],
            )
        ],
    )


def hit(name="Knee extension", distance=0.9, **metadata):
    return {
        "metadata": {"canonical_name": name, **metadata},
        "document": "Synthetic instructions",
        "distance": distance,
    }


def exercise(mapped):
    return mapped["phases"][0]["prescribed_exercises"][0]


@pytest.mark.parametrize(
    "candidate", [hit(), hit("Canonical demo", aliases="Other, Knee extension")]
)
def test_name_or_alias_match_beats_vector_distance(candidate):
    search = Mock(return_value=[candidate])
    original = plan()
    mapped = map_exercises(original, search)
    ex = exercise(mapped)
    assert ex["is_mapped"]
    assert ex["patient_instructions"] == "Synthetic instructions"
    assert ex["source_protocol_id"] == "synthetic-knee"
    assert ex["source_section_title"] == "Demo phase"
    assert ex["specifications"] == "Demo dosage"
    assert mapped["global_precautions"] == ["Demo only"]
    assert "is_mapped" not in original.phases[0].prescribed_exercises[0].model_dump()
    search.assert_called_once_with(query="Knee extension", n_results=5)


@pytest.mark.parametrize(
    "distance,expected", [(0.3999, True), (0.4, False), (0.4001, False)]
)
def test_strict_vector_threshold(distance, expected):
    ex = exercise(map_exercises(plan(), Mock(return_value=[hit("XYZ", distance)])))
    assert ex["is_mapped"] is expected
    assert ex["match_distance"] == distance


def test_later_name_match_wins_over_top_vector_hit():
    ex = exercise(
        map_exercises(
            plan(),
            Mock(
                return_value=[
                    hit("XYZ", 0.1),
                    hit("Knee extension", 0.9, is_high_impact=True),
                ]
            ),
        )
    )
    assert ex["canonical_name"] == "Knee extension"
    assert ex["match_distance"] == 0.9
    assert ex["mechanics_tags"]["is_high_impact"]


def test_empty_search_preserves_unmapped_exercise_without_inventing_instructions():
    ex = exercise(map_exercises(plan(), Mock(return_value=[])))
    assert not ex["is_mapped"]
    assert ex["match_distance"] is None
    assert ex["raw_name_from_protocol"] == "Knee extension"
    assert "patient_instructions" not in ex


def test_empty_plan_never_searches():
    draft = plan()
    draft.phases = []
    search = Mock()
    assert map_exercises(draft, search) == {
        "global_precautions": ["Demo only"],
        "phases": [],
    }
    search.assert_not_called()


@pytest.mark.parametrize("score,expected", [(84.99, False), (85, True)])
def test_fuzzy_threshold_is_inclusive(monkeypatch, score, expected):
    from module_2_reasoning import exercise_mapper

    monkeypatch.setattr(exercise_mapper.fuzz, "token_set_ratio", lambda *args: score)
    ex = exercise(map_exercises(plan(), Mock(return_value=[hit("XYZ", 0.9)])))
    assert ex["is_mapped"] is expected
