from copy import deepcopy
import importlib.util
import json
from pathlib import Path

import pytest

from fakes import IDENTITY, FakeLLM
from module_2_reasoning import graph
from module_2_reasoning.privacy import PrivacyError, active_guard
from module_2_reasoning.schemas import GraderOutput
from test_privacy import assert_no_identity


class EchoIdentityLLM(FakeLLM):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.graded = False

    def respond(self, schema, prompt):
        assert active_guard()
        result = super().respond(schema, prompt)
        if hasattr(result, "thought_process"):
            result.thought_process = IDENTITY["name"]
        if hasattr(result, "patient_context"):
            result.patient_context += " " + IDENTITY["patient_code"]
        if hasattr(result, "queries"):
            for query in result.queries:
                query.keywords += " " + IDENTITY["name"]
        if schema is GraderOutput and not self.graded:
            self.graded = True
            result.evaluations[0].is_relevant = False
            result.evaluations[0].reason_for_rejection = IDENTITY["name"]
        return result


def test_every_graph_stage_rewrite_translation_and_search_is_deidentified(
    identified_patient,
    external_services,
    capsys,
    caplog,
    monkeypatch,
):
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    original = deepcopy(identified_patient)
    llm = EchoIdentityLLM()
    state = graph.build_pipeline(llm).invoke(
        {
            "module1_data": identified_patient,
            "patient_info": identified_patient["patient_info"],
            "untrusted_metadata": IDENTITY["name"],
        },
        config={"metadata": IDENTITY, "run_name": IDENTITY["name"]},
    )
    assert state["retries"] == 1
    assert {schema for schema, _ in llm.calls} == {
        "ClinicalSummary",
        "ProtocolQueryList",
        "GraderOutput",
        "RewrittenQueries",
        "DraftTreatmentPlan",
        "EnglishRehabilitationReport",
        "RehabilitationReport",
    }
    assert_no_identity(llm.calls)
    assert_no_identity(state)
    assert_no_identity(capsys.readouterr().out + caplog.text)
    for service in external_services:
        assert_no_identity(service.call_args_list)
    assert identified_patient == original
    with pytest.raises(PrivacyError):
        active_guard()


def test_direct_graph_errors_are_safe_and_context_is_reset(
    synthetic_patient, external_services
):
    llm = FakeLLM()
    synthetic_patient["test_results"][0]["results"] = "PRIVATE_SENTINEL"
    with pytest.raises(PrivacyError) as error:
        graph.build_pipeline(llm).invoke({"module1_data": synthetic_patient})
    assert "PRIVATE_SENTINEL" not in str(error.value)
    assert llm.calls == []
    with pytest.raises(PrivacyError):
        active_guard()


def test_cli_does_not_dump_patient_input_paths_or_graph_state(
    tmp_path,
    monkeypatch,
    identified_patient,
    external_services,
    capsys,
):
    import dotenv

    monkeypatch.setattr(dotenv, "load_dotenv", lambda *args, **kwargs: None)
    monkeypatch.setenv("DIPLOMA_API_KEY", "synthetic-key")
    path = (
        Path(__file__).resolve().parents[2] / "scripts" / "module2" / "run_pipeline.py"
    )
    spec = importlib.util.spec_from_file_location("privacy_cli", path)
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    input_path = tmp_path / (IDENTITY["patient_code"] + ".json")
    input_path.write_text(json.dumps(identified_patient), encoding="utf-8")
    monkeypatch.setattr(cli, "ChatOpenAI", EchoIdentityLLM)
    monkeypatch.setattr(cli, "OUTPUT_DIR", tmp_path / "output")
    monkeypatch.setattr(cli, "_PROJECT_ROOT", tmp_path)
    monkeypatch.setattr("sys.argv", ["module2", "--file", str(input_path)])
    cli.main()
    assert_no_identity(capsys.readouterr().out)
    assert len(list(cli.OUTPUT_DIR.glob("*.json"))) == 3
    for output in cli.OUTPUT_DIR.glob("*.json"):
        assert_no_identity(output.read_text(encoding="utf-8"))
