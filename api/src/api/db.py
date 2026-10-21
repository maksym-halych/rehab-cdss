from datetime import datetime

from sqlalchemy import JSON, CheckConstraint, DateTime, Index, Integer, MetaData, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Own schema, not "public": Supabase publishes "public" through its Data API
SCHEMA = "cdss"

_NAMING = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

_JOB_STATUSES = "'pending', 'running', 'completed', 'failed'"
_MODULE2_STATUSES = "'idle', 'running', 'completed', 'failed'"


class Base(DeclarativeBase):
    metadata = MetaData(schema=SCHEMA, naming_convention=_NAMING)


class JobRow(Base):
    """One analysis run. Report files stay in data/reports/; the row keeps their paths."""

    __tablename__ = "jobs"
    __table_args__ = (
        CheckConstraint(f"status IN ({_JOB_STATUSES})", name="status"),
        CheckConstraint(f"module2_status IN ({_MODULE2_STATUSES})", name="module2_status"),
        CheckConstraint(
            "module2_step_index >= 0 AND module2_step_index <= module2_total_steps",
            name="module2_step_index",
        ),
        CheckConstraint("age >= 0 AND age <= 120", name="age"),
        Index(None, "created_by", "created_at"),
    )

    job_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    # Clerk user ID (token "sub"). No users table: Clerk keeps the users (ADR-03)
    created_by: Mapped[str] = mapped_column(String(64))
    # Patient context for the job list. No names, birth dates or patient IDs (NFR-01)
    age: Mapped[int | None] = mapped_column(Integer)
    gender: Mapped[str | None] = mapped_column(String(32))
    activity_level: Mapped[str | None] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)
    docx_path: Mapped[str | None] = mapped_column(Text)
    json_export_path: Mapped[str | None] = mapped_column(Text)
    warnings: Mapped[list[str]] = mapped_column(JSON().with_variant(JSONB(), "postgresql"))
    module2_status: Mapped[str] = mapped_column(String(16))
    module2_step: Mapped[str | None] = mapped_column(String(64))
    module2_step_index: Mapped[int] = mapped_column(Integer)
    module2_total_steps: Mapped[int] = mapped_column(Integer)
    module2_step_label: Mapped[str | None] = mapped_column(String(128))
    module2_error: Mapped[str | None] = mapped_column(Text)
    module2_report_md_path: Mapped[str | None] = mapped_column(Text)
    module2_report_docx_path: Mapped[str | None] = mapped_column(Text)


def create_engine(url: str) -> AsyncEngine:
    if url.startswith("sqlite"):
        # Tests use SQLite, which has no schemas: the tables go to its main database
        return create_async_engine(url).execution_options(schema_translate_map={SCHEMA: None})
    # pre_ping: the Supabase pooler closes idle connections
    return create_async_engine(url, pool_pre_ping=True, pool_size=5, max_overflow=5)
