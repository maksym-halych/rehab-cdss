# Backend tests and CI

This work covers E6.2 (#36) and the remaining checks in E6.1 (#35).
Module 1 integration is outside this scope.
The tests start from a fictional JSON input stored in `api/tests/fixtures/patient.json`.

## Local checks

Use Python 3.12 and the locked dependencies.
From the repository root:

```bash
uv run --project api --locked ruff check api/src api/tests scripts
make test
make docker-check
cd frontend && npm ci && npm run lint && npm run build
```

If `make` is unavailable, run the backend tests from `api/`:

```bash
uv run --locked pytest --cov --cov-fail-under=60 --cov-report=term-missing --cov-report=xml:coverage.xml --cov-report=html:htmlcov
```

Run the Docker check from the repository root:

```bash
docker build --progress=plain --tag rehab-cdss:ci ./api
```

The Docker check needs a running Docker engine with Linux containers.
It uses the existing server Dockerfile and does not start or deploy the image.
The test and build checks need no clinic package, real patient data or provider keys.

## Test coverage

- Clinical filter: inclusive absolute bounds, strict asymmetry threshold, zero threshold, missing values, text-only tests and empty input.
- Exercise matching: exact names, aliases, fuzzy/vector thresholds, missing results and source traceability.
- Retrieval: metadata exclusions, empty results and ordering of protocol sections.
- Module 2: synthetic JSON through the real LangGraph pipeline, Markdown renderer and DOCX exporter.
- JSON API: upload, form overrides, background processing, status polling, report downloads and existing input/size rejection rules.
- Job store: save, update, list by owner and status, delete, jobs after a restart, and failing jobs that a restart interrupted (SQLite).
- Job access: a doctor lists and opens only own jobs, an admin sees all, another user's job gives 404, and the list has no identity fields.
- Migrations on Postgres 16: upgrade on an empty database, downgrade and upgrade again, check constraints and the primary key.
- Patient identity fields are excluded from the report-generation prompt. Tests check that synthetic identity sentinels do not reach LLM prompts or output reports.

Deterministic substitutes replace LLM responses and knowledge-base searches.
Tests do not use a live ChromaDB or paid LLM requests.
Network sockets are blocked; API tests allow only loopback addresses for Windows asyncio.
API and job store tests use a temporary SQLite file with the same tables.
The migration tests need Postgres and run only when `TEST_DATABASE_URL` is set.
CI starts an empty Postgres 16 for them.
They drop the `cdss` tables, so never point `TEST_DATABASE_URL` at a database with data you need.
To run them locally on a separate database:

```bash
docker exec rehab-cdss-db createdb -U rehab rehab_test
cd api && TEST_DATABASE_URL=postgresql://rehab:rehab@127.0.0.1:5432/rehab_test uv run pytest tests/test_migrations.py
```

Free-text de-identification remains a separate E2.6 task.

Coverage includes all Python source under `api/src/`.
The XML and HTML reports are written to `api/coverage.xml` and `api/htmlcov/`.
They are local outputs and are not committed.
CI enforces the E6 target of at least 60%; coverage does not replace acceptance review.

For a restricted Windows environment that cannot create temporary files, add `--basetemp=.pytest_cache/run`.
Use only this dedicated directory: pytest clears it before a run.
The Windows event loop also needs permission to create a local socket pair.

## Pull request checks

The CI workflow runs on pull requests into `dev` and `main`:

1. Ruff checks backend source, tests and scripts.
2. Pytest runs the offline checks and the Postgres migration tests, and saves the `backend-coverage` artifact.
3. Docker builds the API image from `api/`.
4. ESLint, TypeScript and Vite check and build the frontend.

Each check fails the workflow when its command fails.
Coverage artifacts are uploaded even after test failures when the reports exist.
The deployment workflows are separate and run on pushes to `dev` or `main`.
