# ADR-04: Jobs in Postgres (Supabase)

Status: Proposed. The TL and PO must approve it before the merge into `main`.
Tasks: E3.1 (#25). The job owner check is part of E2.4.

## Context

`JobStore` kept jobs in process memory.
Each restart or deploy lost all jobs, so the doctor could not open a report after a deploy.
E3.1 asks for PostgreSQL with Alembic migrations and a base schema for users, patients, jobs and reports.

- Users: Clerk keeps the users (ADR-03). A users table is not necessary.
- Patients: no screen uses patient data. `GET /patients` exists, but the frontend does not call it.
- Reports: each job has one report. The report paths fit on the job row.

## Decision

- Postgres 16 keeps one table: `cdss.jobs`.
- Each row is one analysis run: status, Module 2 progress, errors, warnings, report file paths and `created_by` (Clerk user ID).
- The row also keeps age, gender and activity level, so the doctor can tell the jobs apart in "Мої аналізи". It keeps no names, birth dates or patient IDs (NFR-01).
- A doctor sees and opens only own jobs. An admin sees all jobs. For another user's job the API returns 404.
- Report files stay in `data/reports/`. The database keeps only their paths.
- The tables are in the `cdss` schema, not `public`.
- The Supabase Data API is off. With the `cdss` schema, the table also stays out of a Data API that someone turns on later.
- The servers use Supabase: one project for dev and one for prod. Supabase branching needs a paid plan.
- The API connects through the Supabase Session pooler, because the direct connection needs IPv6.
- Alembic manages the schema. The container runs `alembic upgrade head` before the API starts.
- At startup the API marks `pending` and `running` jobs as failed. The pipelines run in the API process, so nothing finishes them after a restart.
- The API runs with one worker. A second worker would fail the jobs of the first worker at its startup.

## How this meets the acceptance criteria

| Criterion | How |
| --- | --- |
| PostgreSQL 16 runs locally; the connection uses environment variables | Postgres 16 runs in Docker (README, Database). The API reads `DATABASE_URL` and does not start without it. |
| The base schema has Alembic migrations | `api/migrations/versions/` (0001 creates `jobs`, 0002 adds the patient context). Only `jobs`, see Context. |
| Migrations run on an empty database; constraints are checked | `api/tests/test_migrations.py` on Postgres 16 in CI: upgrade, downgrade, upgrade, check constraints, primary key |

## Consequences

- Jobs and report links stay after a restart or a deploy.
- The frontend has a "Мої аналізи" tab. A doctor opens an earlier report from it after a reload or a deploy.
- The servers need `DATABASE_URL` in `api/.env` before the deploy. Without it the API does not start.
- Free Supabase projects pause after 7 days without activity. Restore the dev project in the dashboard.
- A local `DATABASE_URL` must not point to the dev Supabase project: at startup the local API would fail the jobs of the dev server.

## Alternatives

- Redis: a good fit for short-lived queues. Jobs here are durable records that the doctor opens later, and the v2.0 plan names PostgreSQL.
- Postgres in `docker-compose.yaml` on the VPS: more to operate (volume, backups). Supabase gives backups and a dashboard.
- The full schema from the issue (users, patients, reports): tables with no feature that uses them. Add them with the feature (patient history, E2.5 audit log).
