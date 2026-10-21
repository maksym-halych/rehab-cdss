"""add patient context to jobs

Age, gender and activity level for the job list. No names or patient IDs (NFR-01).

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-22
"""

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("age", sa.Integer(), nullable=True), schema="cdss")
    op.add_column("jobs", sa.Column("gender", sa.String(length=32), nullable=True), schema="cdss")
    op.add_column(
        "jobs", sa.Column("activity_level", sa.String(length=16), nullable=True), schema="cdss"
    )
    op.create_check_constraint(
        op.f("ck_jobs_age"), "jobs", "age >= 0 AND age <= 120", schema="cdss"
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_jobs_age"), "jobs", type_="check", schema="cdss")
    op.drop_column("jobs", "activity_level", schema="cdss")
    op.drop_column("jobs", "gender", schema="cdss")
    op.drop_column("jobs", "age", schema="cdss")
