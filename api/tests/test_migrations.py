"""Alembic migrations on a real Postgres 16. CI starts one and sets TEST_DATABASE_URL."""

import asyncio
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from api.db import create_engine
from api.settings import database_url

pytestmark = [
    pytest.mark.allow_hosts(["127.0.0.1", "::1"]),
    pytest.mark.skipif(
        not os.getenv("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL is not set"
    ),
]

ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"

VALID_JOB = {
    "job_id": "00000000-0000-4000-8000-000000000001",
    "created_by": "user_synthetic",
    "status": "pending",
    "created_at": datetime(2026, 10, 22, tzinfo=timezone.utc),
    "warnings": "[]",
    "module2_status": "idle",
    "module2_step_index": 0,
    "module2_total_steps": 9,
}


@pytest.fixture
def alembic_config(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", os.environ["TEST_DATABASE_URL"])
    config = Config(str(ALEMBIC_INI))
    config.attributes["configure_logger"] = False
    command.downgrade(config, "base")
    yield config
    command.downgrade(config, "base")


async def _insert(job):
    engine = create_engine(database_url())
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "INSERT INTO cdss.jobs (job_id, created_by, status, created_at, warnings,"
                    " module2_status, module2_step_index, module2_total_steps)"
                    " VALUES (:job_id, :created_by, :status, :created_at,"
                    " CAST(:warnings AS jsonb), :module2_status, :module2_step_index,"
                    " :module2_total_steps)"
                ),
                job,
            )
    finally:
        await engine.dispose()


async def _tables():
    engine = create_engine(database_url())
    try:
        async with engine.connect() as connection:
            rows = await connection.execute(
                text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'cdss'")
            )
            return {row[0] for row in rows}
    finally:
        await engine.dispose()


def test_migrations_run_on_an_empty_database_and_reverse(alembic_config):
    command.upgrade(alembic_config, "head")
    assert asyncio.run(_tables()) == {"alembic_version", "jobs"}
    command.downgrade(alembic_config, "base")
    assert asyncio.run(_tables()) == {"alembic_version"}
    command.upgrade(alembic_config, "head")
    assert "jobs" in asyncio.run(_tables())


def test_valid_job_is_accepted(alembic_config):
    command.upgrade(alembic_config, "head")
    asyncio.run(_insert(VALID_JOB))


@pytest.mark.parametrize(
    "change",
    [
        pytest.param({"status": "unknown"}, id="status"),
        pytest.param({"module2_status": "unknown"}, id="module2-status"),
        pytest.param({"module2_step_index": -1}, id="negative-step"),
        pytest.param({"module2_step_index": 10}, id="step-after-last"),
        pytest.param({"created_by": None}, id="no-owner"),
    ],
)
def test_constraints_reject_invalid_jobs(alembic_config, change):
    command.upgrade(alembic_config, "head")
    with pytest.raises(IntegrityError):
        asyncio.run(_insert({**VALID_JOB, **change}))


def test_job_id_is_unique(alembic_config):
    command.upgrade(alembic_config, "head")
    asyncio.run(_insert(VALID_JOB))
    with pytest.raises(IntegrityError):
        asyncio.run(_insert(VALID_JOB))
