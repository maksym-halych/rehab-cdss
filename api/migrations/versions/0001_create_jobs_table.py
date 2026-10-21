"""create jobs table

Revision ID: 0001
Revises:
Create Date: 2026-10-22
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column("job_id", sa.String(length=36), nullable=False),
        sa.Column("created_by", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("docx_path", sa.Text(), nullable=True),
        sa.Column("json_export_path", sa.Text(), nullable=True),
        sa.Column("warnings", postgresql.JSONB(), nullable=False),
        sa.Column("module2_status", sa.String(length=16), nullable=False),
        sa.Column("module2_step", sa.String(length=64), nullable=True),
        sa.Column("module2_step_index", sa.Integer(), nullable=False),
        sa.Column("module2_total_steps", sa.Integer(), nullable=False),
        sa.Column("module2_step_label", sa.String(length=128), nullable=True),
        sa.Column("module2_error", sa.Text(), nullable=True),
        sa.Column("module2_report_md_path", sa.Text(), nullable=True),
        sa.Column("module2_report_docx_path", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed')",
            name=op.f("ck_jobs_status"),
        ),
        sa.CheckConstraint(
            "module2_status IN ('idle', 'running', 'completed', 'failed')",
            name=op.f("ck_jobs_module2_status"),
        ),
        sa.CheckConstraint(
            "module2_step_index >= 0 AND module2_step_index <= module2_total_steps",
            name=op.f("ck_jobs_module2_step_index"),
        ),
        sa.PrimaryKeyConstraint("job_id", name=op.f("pk_jobs")),
        schema="cdss",
    )
    op.create_index(
        op.f("ix_jobs_created_by_created_at"),
        "jobs",
        ["created_by", "created_at"],
        schema="cdss",
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_jobs_created_by_created_at"), table_name="jobs", schema="cdss")
    op.drop_table("jobs", schema="cdss")
