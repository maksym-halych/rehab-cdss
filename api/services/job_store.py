import asyncio
import uuid
from concurrent.futures import ThreadPoolExecutor

from ..models.jobs import Job

_THREAD_WORKERS = int(__import__("os").getenv("CDSS_THREAD_WORKERS", "4"))
_EXECUTOR = ThreadPoolExecutor(max_workers=_THREAD_WORKERS, thread_name_prefix="cdss-pipeline")


class JobStore:
    def __init__(self):
        self._jobs: dict[str, Job] = {}
        self._lock = asyncio.Lock()

    async def create(self) -> Job:
        job = Job(job_id=str(uuid.uuid4()))
        async with self._lock:
            self._jobs[job.job_id] = job
        return job

    async def get(self, job_id: str) -> Job | None:
        async with self._lock:
            return self._jobs.get(job_id)

    async def update(self, job_id: str, **kwargs) -> None:
        async with self._lock:
            job = self._jobs.get(job_id)
            if job:
                for k, v in kwargs.items():
                    setattr(job, k, v)

    async def delete(self, job_id: str) -> None:
        async with self._lock:
            self._jobs.pop(job_id, None)

    async def list_all(self) -> list[Job]:
        async with self._lock:
            return sorted(
                self._jobs.values(),
                key=lambda j: j.created_at,
                reverse=True,
            )

    async def shutdown(self) -> None:
        _EXECUTOR.shutdown(wait=False)
