from unittest.mock import Mock

import pytest

from module_2_reasoning import retrieval


@pytest.fixture
def collections(monkeypatch):
    protocols, exercises = Mock(), Mock()
    empty = {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}
    protocols.query.return_value = exercises.query.return_value = empty
    monkeypatch.setattr(retrieval, "get_collections", lambda: (protocols, exercises))
    return protocols, exercises


def test_exercise_exclusions_reach_database(collections):
    _, exercises = collections
    assert (
        retrieval.search_exercises(
            "demo", exclude_high_impact=True, exclude_axial_load=True
        )
        == []
    )
    exercises.query.assert_called_once_with(
        query_texts=["demo"],
        n_results=10,
        where={
            "$and": [
                {"is_high_impact": {"$eq": False}},
                {"has_axial_load": {"$eq": False}},
            ]
        },
    )


def test_single_and_no_exclusion_filters(collections):
    _, exercises = collections
    retrieval.search_exercises("demo", exclude_axial_load=True)
    assert exercises.query.call_args.kwargs["where"] == {
        "has_axial_load": {"$eq": False}
    }
    retrieval.search_exercises("demo")
    assert "where" not in exercises.query.call_args.kwargs


def test_protocol_search_preserves_hits_and_filters(collections):
    protocols, _ = collections
    protocols.query.return_value = {
        "ids": [["demo"]],
        "documents": [["Synthetic content"]],
        "metadatas": [[{"doc_type": "Guideline_General"}]],
        "distances": [[0.2]],
    }
    hits = retrieval.search_protocols(
        "demo",
        n_results=2,
        body_part="Knee",
        treatment_type="Non-Operative",
        doc_type="Guideline_General",
    )
    assert hits == [
        {
            "id": "demo",
            "document": "Synthetic content",
            "metadata": {"doc_type": "Guideline_General"},
            "distance": 0.2,
        }
    ]
    assert len(protocols.query.call_args.kwargs["where"]["$and"]) == 3
    retrieval.search_protocols("demo")
    assert "where" not in protocols.query.call_args.kwargs


def test_protocol_sections_are_sorted_and_empty_exercises_removed(collections):
    protocols, _ = collections
    protocols.get.return_value = {
        "ids": ["late", "empty", "early"],
        "documents": [
            "[EXERCISES]: Demo movement",
            "[EXERCISES]: ",
            "Synthetic content",
        ],
        "metadatas": [
            {"section_index": 2, "primary_body_parts": ["Knee", "Hip"]},
            {"section_index": 1},
            {"section_index": 0},
        ],
    }
    result = retrieval.fetch_full_protocol("synthetic-protocol")
    assert [s["id"] for s in result["sections"]] == ["early", "late"]
    assert result["primary_body_parts"] == "Knee, Hip"
    protocols.get.return_value = {"ids": []}
    assert retrieval.fetch_full_protocol("missing") == {}


@pytest.mark.parametrize(
    "value,expected",
    [(None, ""), ([], ""), (["Knee", "", "Hip"], "Knee, Hip"), ("Knee", "Knee")],
)
def test_body_part_metadata(value, expected):
    assert retrieval.body_parts_to_str(value) == expected
