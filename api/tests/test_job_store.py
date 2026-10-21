import asyncio
from datetime import datetime, timezone

import pytest

from api.db import create_engine
from api.models.jobs import JobStatus, Module2Status
from api.services.job_store import JobStore


def run(coro):
    return asyncio.run(coro)


async def _with_store(url, action):
    store = JobStore(create_engine(url))
    try:
        return await action(store)
    finally:
        await store._engine.dispose()


def test_job_is_saved_and_updated(database_url):
    async def scenario(store):
        job = await store.create(created_by="user_synthetic")
        await store.update(
            job.job_id,
            status=JobStatus.COMPLETED,
            completed_at=datetime.now(timezone.utc),
            warnings=["synthetic warning"],
            module2_status=Module2Status.RUNNING,
            module2_step_index=3,
        )
        return job, await store.get(job.job_id)

    created, saved = run(_with_store(database_url, scenario))
    assert saved.job_id == created.job_id
    assert saved.status is JobStatus.COMPLETED
    assert saved.module2_status is Module2Status.RUNNING
    assert saved.module2_step_index == 3
    assert saved.warnings == ["synthetic warning"]
    assert saved.created_at.tzinfo is not None
    assert saved.completed_at.tzinfo is not None


def test_jobs_survive_a_restart(database_url):
    job = run(_with_store(database_url, lambda store: store.create(created_by="user_a")))
    # A new store with a new engine, as after a redeploy
    saved = run(_with_store(database_url, lambda store: store.get(job.job_id)))
    assert saved is not None and saved.job_id == job.job_id


def test_list_is_newest_first_and_delete_removes(database_url):
    async def scenario(store):
        first = await store.create(created_by="user_a")
        second = await store.create(created_by="user_a")
        listed = [j.job_id for j in await store.list_all()]
        await store.delete(first.job_id)
        return first, second, listed, await store.get(first.job_id)

    first, second, listed, deleted = run(_with_store(database_url, scenario))
    assert listed == [second.job_id, first.job_id]
    assert deleted is None


def test_unknown_job_is_none(database_url):
    assert run(_with_store(database_url, lambda store: store.get("missing"))) is None


@pytest.mark.parametrize(
    "values,expected",
    [
        ({"status": JobStatus.PENDING}, (JobStatus.FAILED, Module2Status.IDLE)),
        ({"status": JobStatus.RUNNING}, (JobStatus.FAILED, Module2Status.IDLE)),
        (
            {"status": JobStatus.COMPLETED, "module2_status": Module2Status.RUNNING},
            (JobStatus.COMPLETED, Module2Status.FAILED),
        ),
        (
            {"status": JobStatus.COMPLETED, "module2_status": Module2Status.COMPLETED},
            (JobStatus.COMPLETED, Module2Status.COMPLETED),
        ),
    ],
)
def test_unfinished_jobs_fail_after_restart(database_url, values, expected):
    async def scenario(store):
        job = await store.create(created_by="user_a")
        await store.update(job.job_id, **values)
        await store.fail_unfinished()
        return await store.get(job.job_id)

    job = run(_with_store(database_url, scenario))
    assert (job.status, job.module2_status) == expected
    if expected[0] is JobStatus.FAILED:
        assert "restart" in job.error and job.completed_at is not None
    if values.get("module2_status") is Module2Status.RUNNING:
        assert "restart" in job.module2_error
