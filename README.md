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
