# Rehab CDSS API

FastAPI backend and Module 2 (LangGraph reasoning pipeline) of Rehab CDSS.

Run all commands in this folder.

```bash
cp .env.example .env                                         # then fill in the keys
uv sync                                                      # Python 3.12 only
uv run --env-file .env rehab-api                             # API on :8000, docs on /api/docs
uv run ruff check src
```

| Path                       | Content                                                  |
| -------------------------- | -------------------------------------------------------- |
| `src/api/`                 | FastAPI app. Routers, services, in-memory `JobStore`     |
| `src/module_2_reasoning/`  | LangGraph nodes, filter, retrieval, embeddings, export   |
| `src/ui/`                  | Old Gradio UI. Task E1.2 removes it                      |

The data folder is `data/` in the repository root, outside `api/`.
In Docker it is `/data`. `docker-compose.yaml` mounts it there.

The scripts in the root `scripts/` folder use this environment: `uv run --project api python scripts/...`.
