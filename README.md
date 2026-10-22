# rehab-cdss

My bachelor's thesis project — a Clinical Decision Support System (CDSS) for physical rehabilitation. The system assists clinicians by aggregating patient assessment data and generating structured rehabilitation reports with protocol and exercise recommendations.

**Project logic.** The pipeline consists of two modules. Module 1 processes raw patient data (PDFs, CSVs) from various assessments such as baropodometry, dynamometry, goniometry, and postural analysis. It produces structured test results and exports them as JSON. Module 2 is a multi-agent system (LangGraph): specialized agents handle clinical summarization, search-query generation, protocol retrieval and grading, query rewriting on weak results, clinical reasoning, exercise matching, and report generation. It uses RAG over a vector store (ChromaDB) and produces bilingual rehabilitation reports in Markdown and DOCX.

**Repository scope.** Module 1 is not included — it belongs to the partner clinic. Module 2 and the API/UI layers are available here.

## Layout

| Path                     | Content                                                                         |
| ------------------------ | ------------------------------------------------------------------------------- |
| [`api/`](api/)           | Python backend: FastAPI and Module 2. See [api/README.md](api/README.md)        |
| [`frontend/`](frontend/) | React frontend. See [frontend/README.md](frontend/README.md)                    |
| `scripts/`               | Knowledge base ingest, CLI pipeline. Run with `uv run --project api`            |
| `data/`                  | Git-ignored. ChromaDB, knowledge base, reports, JSON exports                    |
| `docker-compose.yaml`    | Server setup. Run with `docker compose --env-file api/.env up --build`          |

## Checks

CI runs ruff, offline backend tests with coverage, ESLint, the frontend build and the API Docker build on each pull request.
Run the same checks before each commit with [pre-commit](https://pre-commit.com):

```bash
uv run --project api pre-commit install
make pre-commit                                  # all hooks on all files
```

`make` lists the other shortcuts: `make api` (API on :8000), `make frontend` (UI on :3000).

Run backend tests from `api/` with `uv run --locked pytest --cov --cov-report=html --cov-report=xml`.
CI saves the reports in the `backend-coverage` artifact.
See [backend tests and CI](docs/testing.md) for local checks and the synthetic JSON scenario.

## Authentication

Users sign in with Clerk. Sign-up is invite-only. See [ADR-03](docs/adr/ADR-03-auth-clerk.md).

| Setting                      | Where                                                | Value                                                                                                                           |
| ---------------------------- | ---------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| `VITE_CLERK_PUBLISHABLE_KEY` | `frontend/.env`, Vercel env (Preview and Production) | `pk_test_…` (dev instance) or `pk_live_…` (prod instance)                                                                       |
| `CLERK_ISSUER`               | `api/.env` locally and on the VPS                    | Clerk Frontend API URL, dev: `https://simple-cicada-2857.clerk.accounts.dev`, prod: `https://clerk.rehab-cdss.notetaker.uk`     |
| `CDSS_ALLOWED_ORIGINS`       | `api/.env` on the VPS                                | dev: `https://dev-rehab-cdss.notetaker.uk`, prod: `https://rehab-cdss.notetaker.uk`. The API rejects tokens from other origins. |

To add a user:

1. In the Clerk Dashboard, open Users and invite the user, or use Create user.
2. Open the user and set the public metadata to `{"role": "doctor"}` or `{"role": "admin"}`.

A user without a role can sign in, but the API returns 403.

## Database

The API keeps jobs in Postgres 16, in the `cdss` schema. See [ADR-04](docs/adr/ADR-04-jobs-postgres.md).
Report files stay in `data/reports/`; the `jobs` table keeps their paths.

| Environment | Database                             | `DATABASE_URL`                                  |
| ----------- | ------------------------------------ | ----------------------------------------------- |
| Local       | Docker, `127.0.0.1:5432` (see below) | `postgresql://rehab:rehab@127.0.0.1:5432/rehab` |
| Dev server  | Supabase project `rehab-cdss-dev`    | Supabase → Connect → Session pooler             |
| Prod server | Supabase project `rehab-cdss-prod`   | Supabase → Connect → Session pooler             |
| CI          | Postgres 16 service container        | set by the workflow                             |

Start the local Postgres once. Later, start it again with `docker start rehab-cdss-db`:

```bash
docker run -d --name rehab-cdss-db -e POSTGRES_USER=rehab -e POSTGRES_PASSWORD=rehab -e POSTGRES_DB=rehab -p 127.0.0.1:5432:5432 -v rehab-cdss-db:/var/lib/postgresql/data postgres:16
```

The container runs `alembic upgrade head` before the API starts.
Locally, apply the migrations from `api/` before you start the API:

```bash
uv run --env-file .env alembic upgrade head
```

To add a migration, change `api/src/api/db.py`, then run from `api/`:

```bash
uv run --env-file .env alembic revision --autogenerate -m "short description"
```

At startup the API marks jobs that a restart interrupted as failed.

## DNS

The zone `notetaker.uk` is on Cloudflare. All records for this project use the `rehab-cdss` suffix.

| Type  | Name                 | Value                                 | Proxy    | Purpose                              | Link                                      |
| ----- | -------------------- | ------------------------------------- | -------- | ------------------------------------ | ----------------------------------------- |
| A     | `api-rehab-cdss`     | `<VPS_IP>`                            | Proxied  | API, prod (`main`)                   | <https://api-rehab-cdss.notetaker.uk>     |
| A     | `api-dev-rehab-cdss` | `<VPS_IP>`                            | Proxied  | API, dev (`dev`)                     | <https://api-dev-rehab-cdss.notetaker.uk> |
| CNAME | `rehab-cdss`         | `864832b82e884f30.vercel-dns-017.com` | DNS only | Frontend, Vercel Production (`main`) | <https://rehab-cdss.notetaker.uk>         |
| CNAME | `dev-rehab-cdss`     | `864832b82e884f30.vercel-dns-017.com` | DNS only | Frontend, Vercel Preview (`dev`)     | <https://dev-rehab-cdss.notetaker.uk>     |

Frontend records must be **DNS only**, so that Vercel can issue the TLS certificate. The CNAME target is the project-specific value from *Project → Settings → Domains*; `cname.vercel-dns.com` also works as a fallback.

The Clerk production instance is a secondary application on `rehab-cdss.notetaker.uk`. It needs these records:

| Type  | Name                         | Value                         | Proxy    | Purpose                             |
| ----- | ---------------------------- | ----------------------------- | -------- | ----------------------------------- |
| CNAME | `clerk.rehab-cdss`           | `frontend-api.clerk.services` | DNS only | Clerk Frontend API (`CLERK_ISSUER`) |
| CNAME | `accounts.rehab-cdss`        | `accounts.clerk.services`     | DNS only | Clerk Account Portal                |
| CNAME | `clkmail.rehab-cdss`         | `mail.<id>.clerk.services`    | DNS only | Clerk email sending                 |
| CNAME | `clk._domainkey.rehab-cdss`  | `dkim1.<id>.clerk.services`   | DNS only | Clerk email DKIM                    |
| CNAME | `clk2._domainkey.rehab-cdss` | `dkim2.<id>.clerk.services`   | DNS only | Clerk email DKIM                    |

Copy the exact values from Clerk Dashboard → Production → *Configure → Domains*. `<id>` is specific to the instance.
Clerk records must be **DNS only**. Clerk does not verify proxied records and cannot issue its certificates.
The dev Clerk instance (`*.clerk.accounts.dev`) needs no DNS records.

## Deploy notifications

Both deploy workflows send the result to a Telegram chat: status, branch, the user, the merged PR and a link to the run.
Repository secrets: `TELEGRAM_BOT_TOKEN` (from @BotFather) and `TELEGRAM_CHAT_ID` (the group ID is negative).
Without these secrets, the deploy runs as usual and only writes a warning.
