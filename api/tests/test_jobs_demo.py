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
    assert "Synthetic demo patient" not in report.text
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
