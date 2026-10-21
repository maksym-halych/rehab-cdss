import json
import os
from pathlib import Path

import pytest


@pytest.fixture
def synthetic_patient():
    return json.loads(
        (Path(__file__).parent / "fixtures" / "patient.json").read_text(
            encoding="utf-8"
        )
    )


@pytest.fixture(autouse=True)
def isolate_environment(monkeypatch):
    """Tests must never use the developer's provider keys or tracing settings."""
    for name in tuple(os.environ):
        if (
            name in {"DIPLOMA_API_KEY", "OPENAI_API_KEY", "CLERK_ISSUER", "CDSS_ALLOWED_ORIGINS"}
            or name.startswith("LANGCHAIN_")
            or name.startswith("LANGSMITH_")
        ):
            monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
