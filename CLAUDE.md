# CLAUDE.md

Rehab CDSS is a clinical decision support system for physical rehabilitation.
The doctor uploads test results. The system makes a summary report and a rehabilitation plan.
The doctor makes the final decision.
Team 3 develops version 2.0 (Lviv Polytechnic course project, 2026).

## Product

- Module 1 parses device files (PDF, CSV) into a JSON export. Module 1 belongs to the clinic. It is NOT in this repository and NOT installed.
- Module 2 (`src/module_2_reasoning/`) is a LangGraph pipeline. It reads the Module 1 JSON and makes a bilingual report (Markdown, DOCX).
- Module 2 uses RAG: ChromaDB with 229 protocols and 1923 exercises. Gemini is the chat model.
- Without Module 1, use JSON mode: `scripts/demo/generate_module1_json.py` makes synthetic exports, and `POST /api/v1/jobs/from-json` runs Module 2.

## Layout

| Path                                       | Content                                                            |
| ------------------------------------------ | ------------------------------------------------------------------ |
| `src/api/`                                 | FastAPI app. Routers, services, in-memory `JobStore`               |
| `src/module_2_reasoning/`                  | LangGraph nodes, filter, retrieval, embeddings, report export      |
| `src/ui/`                                  | Old Gradio UI. Do not change it. Task E1.2 removes it              |
| `frontend/`                                | React 19 + TypeScript + Vite + Zustand                             |
| `scripts/ingest/`                          | Steps 1–4 that build the knowledge base in `data/`                 |
| `data/`                                    | Git-ignored. ChromaDB, knowledge base, reports, JSON exports       |
| Root `api/`, `module_2_reasoning/`, `*.py` | Old duplicates. Do not edit or import them. Task E1.1 removes them |

## Commands

```bash
uv sync                                                          # Python 3.12 only
uv run python scripts/demo/generate_module1_json.py --scenario acl_left
uv run --env-file .env rehab-api                                 # API on :8000, docs on /api/docs
cd frontend && npm install && npm run dev                        # UI on :5173
cd frontend && npm run build && npm run lint
uv run ruff check src
```

- Start the API only with `rehab-api`. `uvicorn` from the root loads the old duplicates.
- There are no automated tests and no CI checks yet. Tasks E6.1 and E6.2 add them.

## Configuration

- Copy `.env.example` to `.env`. Do not commit `.env`.
- `DIPLOMA_API_KEY` is the Gemini key. `CDSS_API_KEYS` empty means the API accepts all requests.
- The embedding provider and model must be the same as the ones that built `data/chromadb/`. If you change them, delete `data/chromadb/` and run the ingest again.
- The free Gemini tier gives 20 requests per day per model. Do not run full pipelines without need.

## Deployment

- A push to `dev` deploys the dev environment. A push to `main` deploys prod.
- API: GitHub Actions → VPS → `docker compose up --build`. Frontend: GitHub Actions → Vercel.
- `docker-compose.yaml` is the server setup. Do not change its ports or project names for local use.
- The API runs with one worker, because `JobStore` keeps jobs in memory.

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
- v2.0 adds PostgreSQL + SQLAlchemy + Alembic, OAuth2/JWT with roles, an audit log, de-identification before the LLM, and a Module 1 adapter with real and mock modes.
- Open question: OAuth2/JWT (presentation) or Clerk. Get agreement before you start E2.
