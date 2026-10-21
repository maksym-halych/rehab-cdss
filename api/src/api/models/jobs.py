from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class Module2Status(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


MODULE2_STEPS = [
    ("filter", "Фільтрація даних"),
    ("summarize", "Клінічне резюме"),
    ("query_generator", "Генерація запитів"),
    ("protocol_retriever", "Пошук протоколів"),
    ("grader", "Оцінка релевантності"),
    ("query_rewriter", "Перезапис запитів"),
    ("reasoner", "Планування лікування"),
    ("exercise_mapper", "Зіставлення вправ"),
    ("report_formatter", "Формування звіту"),
]


@dataclass
class Job:
    job_id: str
    # Clerk user ID of the doctor who started the job
    created_by: str | None = None
    # Patient context for the job list; no names or IDs (NFR-01)
    age: int | None = None
    gender: str | None = None
    activity_level: str | None = None
    status: JobStatus = JobStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None
    error: str | None = None
    docx_path: str | None = None
    json_export_path: str | None = None
    warnings: list[str] = field(default_factory=list)
    # Module 2 fields
    module2_status: Module2Status = Module2Status.IDLE
    module2_step: str | None = None
    module2_step_index: int = 0
    module2_total_steps: int = 9
    module2_step_label: str | None = None
    module2_error: str | None = None
    module2_report_md_path: str | None = None
    module2_report_docx_path: str | None = None
