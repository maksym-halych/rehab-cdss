import json
import os
from copy import deepcopy
from pathlib import Path
from unittest.mock import Mock

import pytest

from fakes import EXERCISE_HIT, IDENTITY, PROTOCOL_HIT
from module_2_reasoning import graph


@pytest.fixture
def synthetic_patient():
    return json.loads(
        (Path(__file__).parent / "fixtures" / "patient.json").read_text(
            encoding="utf-8"
        )
    )


@pytest.fixture
def identified_patient(synthetic_patient):
    patient = deepcopy(synthetic_patient)
    patient["patient_info"].update(IDENTITY)
    patient["unknown_metadata"] = {"name": "EXTRA_PRIVATE_PERSON"}
    narrative = "Strength deficit 40%; " + "; ".join(IDENTITY.values())
    test = patient["test_results"][0]
    test["interpretation"] = narrative
    test["recommendations"] = "12.04.1990; " + narrative
    test["test_name"] += " " + IDENTITY["patient_code"]
    test["results"]["tables"][0]["rows"][0]["parameter"] += " " + IDENTITY["name"]
    return patient


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


@pytest.fixture(autouse=True)
def isolate_environment(monkeypatch):
    """Tests must never use the developer's provider keys or tracing settings."""
    for name in tuple(os.environ):
        if (
            name
            in {
                "DIPLOMA_API_KEY",
                "OPENAI_API_KEY",
                "CLERK_ISSUER",
                "CDSS_ALLOWED_ORIGINS",
                "DATABASE_URL",
            }
            or name.startswith("LANGCHAIN_")
            or name.startswith("LANGSMITH_")
        ):
            monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")
    monkeypatch.setenv("LANGSMITH_TRACING", "false")


@pytest.fixture
def database_url(monkeypatch, tmp_path):
    """An empty SQLite database with the API tables; DATABASE_URL points to it."""
    from sqlalchemy import create_engine

    from api.db import SCHEMA, Base

    path = tmp_path / "cdss.db"
    engine = create_engine(f"sqlite:///{path}")
    with engine.begin() as connection:
        connection = connection.execution_options(schema_translate_map={SCHEMA: None})
        Base.metadata.create_all(connection)
    engine.dispose()
    url = f"sqlite+aiosqlite:///{path}"
    monkeypatch.setenv("DATABASE_URL", url)
    return url
