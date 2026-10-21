# rehab-cdss

My bachelor's thesis project — a Clinical Decision Support System (CDSS) for physical rehabilitation. The system assists clinicians by aggregating patient assessment data and generating structured rehabilitation reports with protocol and exercise recommendations.

**Project logic.** The pipeline consists of two modules. Module 1 processes raw patient data (PDFs, CSVs) from various assessments such as baropodometry, dynamometry, goniometry, and postural analysis. It produces structured test results and exports them as JSON. Module 2 is a multi-agent system (LangGraph): specialized agents handle clinical summarization, search-query generation, protocol retrieval and grading, query rewriting on weak results, clinical reasoning, exercise matching, and report generation. It uses RAG over a vector store (ChromaDB) and produces bilingual rehabilitation reports in Markdown and DOCX.

**Repository scope.** Module 1 is not included — it belongs to the partner clinic. Module 2 and the API/UI layers are available here.

## Layout

| Path                  | Content                                                                  |
| --------------------- | ------------------------------------------------------------------------ |
| [`api/`](api/)        | Python backend: FastAPI and Module 2. See [api/README.md](api/README.md) |
| [`frontend/`](frontend/) | React frontend. See [frontend/README.md](frontend/README.md)          |
| `scripts/`            | Knowledge base ingest, demo data, CLI pipeline. Run with `uv run --project api` |
| `data/`               | Git-ignored. ChromaDB, knowledge base, reports, JSON exports             |
| `docker-compose.yaml` | Server setup. Run with `docker compose --env-file api/.env up --build`   |

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

| Setting | Where | Value |
| --- | --- | --- |
| `VITE_CLERK_PUBLISHABLE_KEY` | `frontend/.env`, Vercel env (Preview and Production) | `pk_test_…` (dev instance) or `pk_live_…` (prod instance) |
| `CLERK_ISSUER` | `api/.env` locally and on the VPS | Clerk Frontend API URL, for example `https://simple-cicada-2857.clerk.accounts.dev` |
| `CDSS_ALLOWED_ORIGINS` | `api/.env` on the VPS | The frontend URL. The API rejects tokens from other origins. |

To add a user:

1. In the Clerk Dashboard, open Users and invite the user, or use Create user.
2. Open the user and set the public metadata to `{"role": "doctor"}` or `{"role": "admin"}`.

A user without a role can sign in, but the API returns 403.

## DNS

The zone `notetaker.uk` is on Cloudflare. All records for this project use the `rehab-cdss` suffix.

| Type  | Name                 | Value                                 | Proxy    | Purpose                              | Link                                    |
| ----- | -------------------- | ------------------------------------- | -------- | ------------------------------------ | --------------------------------------- |
| A     | `api-rehab-cdss`     | `<VPS_IP>`                            | Proxied  | API, prod (`main`)                   | <https://api-rehab-cdss.notetaker.uk>     |
| A     | `api-dev-rehab-cdss` | `<VPS_IP>`                            | Proxied  | API, dev (`dev`)                     | <https://api-dev-rehab-cdss.notetaker.uk> |
| CNAME | `rehab-cdss`         | `864832b82e884f30.vercel-dns-017.com` | DNS only | Frontend, Vercel Production (`main`) | <https://rehab-cdss.notetaker.uk>         |
| CNAME | `dev-rehab-cdss`     | `864832b82e884f30.vercel-dns-017.com` | DNS only | Frontend, Vercel Preview (`dev`)     | <https://dev-rehab-cdss.notetaker.uk>     |

Frontend records must be **DNS only**, so that Vercel can issue the TLS certificate. The CNAME target is the project-specific value from *Project → Settings → Domains*; `cname.vercel-dns.com` also works as a fallback.
>

## Deploy notifications

Both deploy workflows send the result to a Telegram chat: status, branch, the user, the merged PR and a link to the run.
Repository secrets: `TELEGRAM_BOT_TOKEN` (from @BotFather) and `TELEGRAM_CHAT_ID` (the group ID is negative).
Without these secrets, the deploy runs as usual and only writes a warning.
