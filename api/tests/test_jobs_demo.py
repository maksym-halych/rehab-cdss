import json
import time
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from fakes import EXERCISE_HIT, PROTOCOL_HIT, FakeLLM

# Windows asyncio needs a loopback socket pair. External hosts stay blocked.
pytestmark = pytest.mark.allow_hosts(["127.0.0.1", "::1"])


@pytest.fixture
def client(monkeypatch, tmp_path, database_url):
    import langchain_openai
    from api import dependencies
    from api.app import create_app
    from api.routers import jobs
    from api.services import job_store, module2_service
    from module_2_reasoning import graph

    monkeypatch.setenv("CLERK_ISSUER", "https://clerk.example.test")
    monkeypatch.setenv("DIPLOMA_API_KEY", "synthetic-test-key")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "gemini")
    monkeypatch.setattr(langchain_openai, "ChatOpenAI", FakeLLM)
    monkeypatch.setattr(graph, "search_protocols", Mock(return_value=[PROTOCOL_HIT]))
    monkeypatch.setattr(graph, "search_exercises", Mock(return_value=[EXERCISE_HIT]))
    monkeypatch.setattr(
        graph,
        "fetch_full_protocol",
        Mock(side_effect=AssertionError("Unexpected lookup")),
    )
    for module in (jobs, module2_service):
        monkeypatch.setattr(module, "REPORTS_ROOT", tmp_path / "reports")
    with ThreadPoolExecutor(max_workers=2) as executor:
        for module in (job_store, module2_service):
            monkeypatch.setattr(module, "_EXECUTOR", executor)
        app = create_app()
        app.dependency_overrides[dependencies.get_current_user] = lambda: (
            dependencies.CurrentUser(user_id="user_test", role="doctor")
        )
        with TestClient(app) as http:
            yield http


def wait_for_report(client, status_url):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        response = client.get(status_url)
        assert response.status_code == 200
        state = response.json()
        assert state["status"] != "failed", state
        assert state["module2_status"] != "failed", state
        if state["module2_status"] == "completed":
            return state
        time.sleep(0.01)
    pytest.fail("Synthetic report did not complete within 10 seconds")


def test_json_input_reaches_report_and_preserves_form_overrides(
    client, synthetic_patient
):
    synthetic_patient["patient_info"]["name"] = "PRIVATE_NAME_SENTINEL"
    response = client.post(
        "/api/v1/jobs/from-json",
        files={
            "file": ("demo.json", json.dumps(synthetic_patient), "application/json")
        },
        data={"age": "25", "activity_level": "low"},
    )
    assert response.status_code == 202, response.text
    state = wait_for_report(client, response.json()["status_url"])
    result = state["result"]
    export = client.get(result["report_json_url"]).json()
    assert export["synthetic"]
    assert export["patient_info"]["age"] == 25
    assert export["patient_info"]["activity_level"] == "low"
    report = client.get(result["rehab_report_md_url"])
    assert report.status_code == 200
    assert "Synthetic demo report" in report.text
    assert "PRIVATE_NAME_SENTINEL" not in report.text
    assert "DEMO-0001" not in report.text
    docx = client.get(result["rehab_report_docx_url"])
    assert docx.status_code == 200 and docx.content.startswith(b"PK")


@pytest.mark.parametrize(
    "raw,code",
    [
        (b"bad json", "INVALID_JSON"),
        (b"\xff", "INVALID_JSON"),
        (b"[]", "INVALID_MODULE1_JSON"),
        (b"{}", "INVALID_MODULE1_JSON"),
        (b'{"test_results": {}}', "INVALID_MODULE1_JSON"),
    ],
)
def test_invalid_json_does_not_create_a_job_or_leak_values(client, raw, code):
    response = client.post("/api/v1/jobs/from-json", files={"file": ("demo.json", raw)})
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == code
    assert "PRIVATE_SENTINEL" not in response.text
    assert client.get("/api/v1/jobs").json()["total"] == 0


def test_json_size_limit(client, monkeypatch):
    from api.routers import jobs

    monkeypatch.setattr(jobs, "MAX_JSON_SIZE_BYTES", 10)
    response = client.post(
        "/api/v1/jobs/from-json", files={"file": ("demo.json", b"x" * 11)}
    )
    assert response.status_code == 413
    assert client.get("/api/v1/jobs").json()["total"] == 0


def test_generated_json_reaches_report(client):
    response = client.get("/api/v1/demo/module1-json")
    assert response.status_code == 200
    disposition = response.headers["content-disposition"]
    assert disposition.startswith('attachment; filename="synthetic_random_DEMO')
    created = client.post(
        "/api/v1/jobs/from-json",
        files={"file": ("demo.json", response.content, "application/json")},
    )
    assert created.status_code == 202, created.text
    state = wait_for_report(client, created.json()["status_url"])
    assert state["result"]["rehab_report_md_url"]


@pytest.mark.parametrize(
    "scenario", ["acl_left", "shoulder_right", "low_back_posture", "healthy", "random"]
)
def test_generated_json_has_module1_shape(client, scenario):
    data = client.get(f"/api/v1/demo/module1-json?scenario={scenario}").json()
    assert data["synthetic"] and data["scenario"] == scenario
    info = data["patient_info"]
    assert 0 <= info["age"] <= 120
    assert info["activity_level"] in {"elite", "recreational", "low"}
    assert data["test_results"]
    for test in data["test_results"]:
        assert test["test_name"]
        for table in test["results"]["tables"]:
            for row in table["rows"]:
                assert row["parameter"]
                assert "value" in row or {"left", "right"} <= row.keys()


def test_same_seed_gives_same_json(client):
    def generate():
        data = client.get("/api/v1/demo/module1-json?seed=7").json()
        del data["generated_at"]
        return data

    assert generate() == generate()


def test_unknown_scenario_is_rejected(client):
    assert client.get("/api/v1/demo/module1-json?scenario=unknown").status_code == 422
def test_provider_error_is_not_returned_in_job_status(
    client, synthetic_patient, monkeypatch, caplog, capsys
):
    import langchain_openai

    class FailingLLM(FakeLLM):
        def respond(self, schema, prompt):
            raise RuntimeError("PRIVATE_PATIENT_SENTINEL synthetic-provider-secret")

    monkeypatch.setattr(langchain_openai, "ChatOpenAI", FailingLLM)
    response = client.post(
        "/api/v1/jobs/from-json",
        files={
            "file": ("private.json", json.dumps(synthetic_patient), "application/json")
        },
    )
    assert response.status_code == 202
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        status = client.get(response.json()["status_url"])
        if status.json()["module2_status"] == "failed":
            break
        time.sleep(0.01)
    else:
        pytest.fail("Failed provider was not reflected in job status")
    output = status.text + caplog.text + capsys.readouterr().out
    assert "PRIVATE_PATIENT_SENTINEL" not in output
    assert "synthetic-provider-secret" not in output
    assert status.json()["module2_error"]


def test_form_identity_overrides_do_not_lose_original_redaction_tokens(
    client, synthetic_patient, monkeypatch, capsys
):
    import langchain_openai

    tokens = [
        "ORIGINAL_PRIVATE_NAME",
        "ORIGINAL_PRIVATE_CODE",
        "EDITED_PRIVATE_NAME",
        "EDITED_PRIVATE_CODE",
    ]
    synthetic_patient["patient_info"].update(name=tokens[0], patient_code=tokens[1])
    synthetic_patient["test_results"][0]["interpretation"] = (
        "Strength deficit 40%; " + "; ".join(tokens)
    )
    prompts = []

    class CapturingLLM(FakeLLM):
        def respond(self, schema, prompt):
            prompts.append(prompt)
            return super().respond(schema, prompt)

    monkeypatch.setattr(langchain_openai, "ChatOpenAI", CapturingLLM)
    response = client.post(
        "/api/v1/jobs/from-json",
        files={
            "file": ("demo.json", json.dumps(synthetic_patient), "application/json")
        },
        data={"manual_person_name": tokens[2], "patient_code": tokens[3]},
    )
    assert response.status_code == 202
    state = wait_for_report(client, response.json()["status_url"])
    export = client.get(state["result"]["report_json_url"]).json()
    assert export["patient_info"]["name"] == tokens[2]
    assert export["patient_info"]["patient_code"] == tokens[3]
    assert prompts
    output = "\n".join(prompts) + capsys.readouterr().out
    for token in tokens:
        assert token not in output
