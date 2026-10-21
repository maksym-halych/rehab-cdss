# CLAUDE.md

Rehab CDSS is a clinical decision support system for physical rehabilitation.
The doctor uploads test results. The system makes a summary report and a rehabilitation plan.
The doctor makes the final decision.
Team 3 develops version 2.0 (Lviv Polytechnic course project, 2026).

## Product

- Module 1 parses device files (PDF, CSV) into a JSON export. Module 1 belongs to the clinic. It is NOT in this repository and NOT installed.
- Module 2 (`api/src/module_2_reasoning/`) is a LangGraph pipeline. It reads the Module 1 JSON and makes a bilingual report (Markdown, DOCX).
- Module 2 uses RAG: ChromaDB with 229 protocols and 1923 exercises. Gemini is the chat model.
- Without Module 1, use JSON mode: `scripts/demo/generate_module1_json.py` makes synthetic exports, and `POST /api/v1/jobs/from-json` runs Module 2.

## Layout

| Path                          | Content                                                                 |
| ----------------------------- | ----------------------------------------------------------------------- |
| `api/`                        | Python backend: `pyproject.toml`, `uv.lock`, `Dockerfile`, `.env`, Alembic `migrations/` |
| `api/src/api/`                | FastAPI app. Routers, services, `JobStore` on Postgres (`db.py`)        |
| `api/src/module_2_reasoning/` | LangGraph nodes, filter, retrieval, embeddings, report export, paths    |
| `scripts/`                    | Repo tools: `ingest/` (steps 1–4 that build `data/`), `demo/`, `module2/` |
| `frontend/`                   | React 19 + TypeScript + Vite + Zustand                                  |
| `data/`                       | Git-ignored. ChromaDB, knowledge base, reports, JSON exports            |
| Root files                    | `docker-compose.yaml`, CI workflows, docs                               |

## Commands

```bash
make                                                             # list shortcuts: pre-commit, api, frontend
docker start rehab-cdss-db                                       # local Postgres 16 on 127.0.0.1:5432 (first run: README, Database)
cd api && uv run --env-file .env alembic upgrade head            # apply migrations
cd api && uv sync                                                # Python 3.12 only
cd api && uv run --env-file .env rehab-api                       # API on :8000, docs on /api/docs
cd api && uv run ruff check src
uv run --project api python scripts/demo/generate_module1_json.py --scenario acl_left
uv run --project api ruff check scripts
cd frontend && npm install && npm run dev                        # UI on :3000
cd frontend && npm run build && npm run lint
uv run --project api pre-commit install                          # once: ruff and ESLint on each commit
uv run --project api pre-commit run --all-files
```

- Run API commands in `api/`. Run `scripts/` from the root with `uv run --project api`, so they use the `api/` environment.
- Code in `api/src/` finds `data/` through `module_2_reasoning.paths.DATA_DIR`. Do not write paths relative to the working directory.
- CI (`.github/workflows/ci.yml`) runs on each PR into `dev` and `main`: ruff, offline backend tests with coverage, ESLint (warnings fail), the frontend type check and build, and the API Docker build.
- Run tests in `api/`: `uv run --locked pytest --cov --cov-report=html --cov-report=xml`. CI saves the `backend-coverage` artifact.
- Module 1 integration is out of scope for the current work. Tests use synthetic JSON input and replace external LLM and retrieval calls. See `docs/testing.md`.

## Configuration

- Copy `api/.env.example` to `api/.env`. Do not commit `.env`.
- `DIPLOMA_API_KEY` is the Gemini key.
- `DATABASE_URL` is the Postgres URL. Locally it is the `rehab-cdss-db` Docker container. On the servers it is the Supabase Session pooler URL (dev and prod are separate Supabase projects).
- Copy `frontend/.env.example` to `frontend/.env`. It has the Clerk publishable key for the dev instance.
- The embedding provider and model must be the same as the ones that built `data/chromadb/`. If you change them, delete `data/chromadb/` and run the ingest again.
- The free Gemini tier gives 20 requests per day per model. Do not run full pipelines without need.

## Deployment

- A push to `dev` deploys the dev environment. A push to `main` deploys prod.
- API: GitHub Actions → VPS → `docker compose --env-file api/.env up --build`. The `--env-file` flag gives `HOST_PORT` to the port mapping. Frontend: GitHub Actions → Vercel.
- `docker-compose.yaml` is the server setup. Do not change its ports or project names for local use.
- The API runs with one worker. Pipelines run in the API process, and at startup the API fails the jobs that a restart interrupted.
- The container runs `alembic upgrade head` before the API starts.

## Rules for personal data (NFR-01)

- Do not send names, birth dates or patient IDs to an LLM. Send only age, gender, activity level and test values.
- Do not write personal data to logs.
- Use only synthetic data in fixtures, tests and examples.

## Work process

- Backlog: GitHub Project "Rehab CDSS v2.0 · Команда 3" (https://github.com/users/maksym-halych/projects/1).
- Each task is an issue. The title has the WBS ID, for example `[E2.3] ...`. Labels: `type:*`, `priority:*`, `sprint:S1–S4`, `sp:*`.
- Read the issue before you start. Do its acceptance criteria and its "Стан на" notes. Do not do work again that a merged PR already did.
- Status flow: Backlog → To Do → In Progress → Review → Done.
- Branch: `feat/<short-name>` from `dev`. PR target: `dev`. PR body has `Closes #<issue>`.
- Do not add or change `make` commands unless the user asks. The Makefile is the user's own shortcuts.
- Commits: Conventional Commits, for example `feat(jobs): run module 2 from json`.
- PR descriptions: ASD-STE100. One sentence or one list item per line.
- No Claude attribution in commits or PRs.
- Do not commit, push or open a PR until the user tells you to.

## Definition of Done

- Code review is complete. CI is green. New tests are added.
- QA checked the acceptance criteria.
- No personal data in logs or LLM requests.
- Documentation is updated.

## Decisions

- Architecture: modular monolith (ADR-01). Do not split it into services.
- v2.0 adds PostgreSQL + SQLAlchemy + Alembic, Clerk sign-in with roles, an audit log, and de-identification before the LLM.
- Authentication is Clerk (ADR-03, `docs/adr/ADR-03-auth-clerk.md`). Sign-up is invite-only. Clerk stores the users and passwords; there is no users table.
- The API accepts only a Clerk session token (`Authorization: Bearer`). `api.dependencies.get_current_user` checks it and returns the Clerk user ID and the role. `/api/v1/health` is public.
- The role (`doctor` or `admin`) is in the Clerk user's public metadata. A session token template copies it into the `role` claim. A user without a role gets 403.
- The API does not start without `CLERK_ISSUER`.
- Jobs are in Postgres, table `cdss.jobs` (ADR-04). Only this table for now. Add patients, reports or audit tables when a feature needs them. Use the `cdss` schema, not `public`.
- Change the schema only with an Alembic migration. Do not edit an applied migration.
