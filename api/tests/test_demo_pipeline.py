from copy import deepcopy
from unittest.mock import Mock
from zipfile import ZipFile

import pytest

from fakes import EXERCISE_HIT, PROTOCOL_HIT, FakeLLM
from module_2_reasoning import graph
from module_2_reasoning.docx_export import markdown_to_docx


@pytest.fixture
def external_services(monkeypatch):
    protocols = Mock(return_value=[deepcopy(PROTOCOL_HIT)])
    exercises = Mock(return_value=[deepcopy(EXERCISE_HIT)])
    monkeypatch.setattr(graph, "search_protocols", protocols)
    monkeypatch.setattr(graph, "search_exercises", exercises)
    monkeypatch.setattr(
        graph,
        "fetch_full_protocol",
        Mock(side_effect=AssertionError("Unexpected external lookup")),
    )
    return protocols, exercises


def initial_state(patient):
    data = deepcopy(patient)
    data["patient_info"].update(
        name="PRIVATE_NAME_SENTINEL",
        patient_code="PRIVATE_CODE_SENTINEL",
        birth_date="PRIVATE_DOB_SENTINEL",
    )
    return {
        "module1_data": data,
        "patient_info": data["patient_info"],
        "retries": 0,
        "grader_feedback": [],
    }


def test_synthetic_patient_reaches_markdown_and_docx_without_network(
    tmp_path, external_services, synthetic_patient
):
    llm = FakeLLM()
    steps = []
    state = graph.build_pipeline(llm, on_step_start=steps.append).invoke(
        initial_state(synthetic_patient)
    )
    assert steps == [
        "filter",
        "summarize",
        "query_generator",
        "protocol_retriever",
        "grader",
        "reasoner",
        "exercise_mapper",
        "report_formatter",
    ]
    assert sum(len(r.flagged_params) for r in state["filtered_results"]) > 0
    assert state["enriched_plan"]["phases"][0]["prescribed_exercises"][0]["is_mapped"]
    assert "# Synthetic demo report" in state["final_report"]
    assert EXERCISE_HIT["document"] in state["final_report"]
    assert "Synthetic Knee" in state["final_report"]
    assert "Test fixture" not in state["final_report"]
    assert all("PRIVATE_" not in prompt for _, prompt in llm.calls)
    assert "PRIVATE_" not in state["final_report"]
    markdown = tmp_path / "rehabilitation_report.md"
    markdown.write_text(state["final_report"], encoding="utf-8")
    docx = tmp_path / "rehabilitation_report.docx"
    markdown_to_docx(state["final_report"], str(docx))
    with ZipFile(docx) as archive:
        xml = archive.read("word/document.xml").decode()
    assert "Synthetic demo report" in xml
    assert "PRIVATE_" not in xml
    assert len(llm.calls) == 6


def test_empty_retrieval_stops_after_two_rewrites(synthetic_patient, external_services):
    protocols, exercises = external_services
    protocols.return_value = []
    exercises.return_value = []
    llm = FakeLLM()
    state = graph.build_pipeline(llm).invoke(initial_state(synthetic_patient))
    assert state["retries"] == 2
    assert protocols.call_count == 3
    assert not state["enriched_plan"]["phases"][0]["prescribed_exercises"][0][
        "is_mapped"
    ]
    assert "GraderOutput" not in [schema for schema, _ in llm.calls]
    assert state["final_report"]
