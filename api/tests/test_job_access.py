import json

import pytest
from fastapi.testclient import TestClient

# Windows asyncio needs a loopback socket pair. External hosts stay blocked.
pytestmark = pytest.mark.allow_hosts(["127.0.0.1", "::1"])

DOCTOR_A = ("user_doctor_a", "doctor")
DOCTOR_B = ("user_doctor_b", "doctor")
ADMIN = ("user_admin", "admin")


@pytest.fixture
def api(monkeypatch, tmp_path, database_url):
    """Client and a function that switches the signed-in user."""
    from api import dependencies
    from api.app import create_app
    from api.routers import jobs
    from api.services import module2_service

    monkeypatch.setenv("CLERK_ISSUER", "https://clerk.example.test")
    # No DIPLOMA_API_KEY: Module 2 fails at once, without LLM calls
    for module in (jobs, module2_service):
        monkeypatch.setattr(module, "REPORTS_ROOT", tmp_path / "reports")
    app = create_app()
    current = {"user": DOCTOR_A}
    app.dependency_overrides[dependencies.get_current_user] = lambda: (
        dependencies.CurrentUser(*current["user"])
    )

    def sign_in(user):
        current["user"] = user

    with TestClient(app) as http:
        yield http, sign_in


def start_job(http, patient):
    response = http.post(
        "/api/v1/jobs/from-json",
        files={"file": ("demo.json", json.dumps(patient), "application/json")},
    )
    assert response.status_code == 202, response.text
    return response.json()["job_id"]


def test_list_has_own_jobs_with_patient_context(api, synthetic_patient):
    http, _ = api
    job_id = start_job(http, synthetic_patient)
    body = http.get("/api/v1/jobs").json()
    assert body["total"] == 1
    item = body["jobs"][0]
    assert item["job_id"] == job_id
    assert (item["age"], item["gender"], item["activity_level"]) == (
        30,
        "Чоловік",
        "recreational",
    )
    assert item["module2_status"] in {"idle", "running", "failed"}
    # The list has no identity fields from the JSON
    assert "Synthetic demo patient" not in json.dumps(body)
    assert "DEMO-0001" not in json.dumps(body)


def test_other_doctor_cannot_see_the_job(api, synthetic_patient):
    http, sign_in = api
    job_id = start_job(http, synthetic_patient)
    sign_in(DOCTOR_B)
    assert http.get("/api/v1/jobs").json() == {"jobs": [], "total": 0}
    for url in (
        f"/api/v1/jobs/{job_id}",
        f"/api/v1/reports/{job_id}/json",
        f"/api/v1/reports/{job_id}/docx",
        f"/api/v1/reports/{job_id}/rehab-report",
        f"/api/v1/reports/{job_id}/rehab-report/docx",
    ):
        response = http.get(url)
        assert response.status_code == 404, url
        assert response.json()["detail"]["code"] == "JOB_NOT_FOUND"
    assert http.delete(f"/api/v1/jobs/{job_id}").status_code == 404
    sign_in(DOCTOR_A)
    assert http.get(f"/api/v1/jobs/{job_id}").status_code == 200


def test_admin_sees_jobs_of_all_users(api, synthetic_patient):
    http, sign_in = api
    job_a = start_job(http, synthetic_patient)
    sign_in(DOCTOR_B)
    job_b = start_job(http, synthetic_patient)
    sign_in(ADMIN)
    body = http.get("/api/v1/jobs").json()
    assert {j["job_id"] for j in body["jobs"]} == {job_a, job_b}
    assert http.get(f"/api/v1/jobs/{job_a}").status_code == 200


def test_invalid_patient_values_from_json_are_not_listed(api, synthetic_patient):
    http, _ = api
    synthetic_patient["patient_info"].update(age=500, activity_level="unknown")
    start_job(http, synthetic_patient)
    item = http.get("/api/v1/jobs").json()["jobs"][0]
    assert item["age"] is None and item["activity_level"] is None


@pytest.mark.parametrize("query", ["limit=0", "limit=101", "offset=-1"])
def test_list_paging_limits(api, query):
    http, _ = api
    assert http.get(f"/api/v1/jobs?{query}").status_code == 422
