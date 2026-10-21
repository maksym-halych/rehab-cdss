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
