import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import fields
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from ..db import JobRow
from ..models.jobs import Job, JobStatus, Module2Status

_THREAD_WORKERS = int(os.getenv("CDSS_THREAD_WORKERS", "4"))
_EXECUTOR = ThreadPoolExecutor(max_workers=_THREAD_WORKERS, thread_name_prefix="cdss-pipeline")

_JOB_FIELDS = tuple(f.name for f in fields(Job))
_RESTART_ERROR = "Interrupted by an API restart. Start the analysis again."


def _to_db(value):
    return value.value if isinstance(value, Enum) else value


def _utc(value: datetime | None) -> datetime | None:
    # SQLite (tests) returns naive datetimes; Postgres returns them with UTC
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _to_job(row: JobRow) -> Job:
    job = Job(**{name: getattr(row, name) for name in _JOB_FIELDS})
    job.status = JobStatus(row.status)
    job.module2_status = Module2Status(row.module2_status)
    job.created_at = _utc(row.created_at)
    job.completed_at = _utc(row.completed_at)
    job.warnings = list(row.warnings or [])
    return job


class JobStore:
    """Keeps jobs in the database, so they survive API restarts and redeploys."""

    def __init__(self, engine: AsyncEngine):
        self._engine = engine
        self._session = async_sessionmaker(engine, expire_on_commit=False)

    async def create(self, created_by: str) -> Job:
        job = Job(job_id=str(uuid.uuid4()))
        values = {name: _to_db(getattr(job, name)) for name in _JOB_FIELDS}
        async with self._session.begin() as session:
            session.add(JobRow(**values, created_by=created_by))
        return job

    async def get(self, job_id: str) -> Job | None:
        async with self._session() as session:
            row = await session.get(JobRow, job_id)
            return _to_job(row) if row else None

    async def update(self, job_id: str, **kwargs) -> None:
        values = {k: _to_db(v) for k, v in kwargs.items()}
        async with self._session.begin() as session:
            await session.execute(update(JobRow).where(JobRow.job_id == job_id).values(values))

    async def delete(self, job_id: str) -> None:
        async with self._session.begin() as session:
            await session.execute(delete(JobRow).where(JobRow.job_id == job_id))

    async def list_all(self) -> list[Job]:
        async with self._session() as session:
            rows = await session.scalars(select(JobRow).order_by(JobRow.created_at.desc()))
            return [_to_job(row) for row in rows]

    async def fail_unfinished(self) -> None:
        """Mark jobs that were running when the API stopped as failed.

        Pipelines run in this process, so after a restart nothing finishes them.
        Call it once at startup, before the API takes requests (one worker only).
        """
        now = datetime.now(timezone.utc)
        unfinished = (JobStatus.PENDING.value, JobStatus.RUNNING.value)
        async with self._session.begin() as session:
            await session.execute(
                update(JobRow)
                .where(JobRow.status.in_(unfinished))
                .values(status=JobStatus.FAILED.value, completed_at=now, error=_RESTART_ERROR)
            )
            await session.execute(
                update(JobRow)
                .where(JobRow.module2_status == Module2Status.RUNNING.value)
                .values(module2_status=Module2Status.FAILED.value, module2_error=_RESTART_ERROR)
            )

    async def shutdown(self) -> None:
        _EXECUTOR.shutdown(wait=False)
        await self._engine.dispose()
