# Architecture

---

## System Overview

A single-process, local-first web application run by one power user on their own machine. A FastAPI backend (port 8001) serves both a JSON API and a statically-exported Next.js UI from the same origin under `/app`. The user uploads CSV/Excel files, which are profiled and stored locally; they then ask plain-English questions. Each question drives a LangGraph agent that asks Google Gemini to plan and write pandas code, runs that code in an isolated subprocess sandbox over the in-memory dataset, inspects the result or error, retries up to a step budget, and returns a prose answer with the exact code and raw result. All raw data stays on the local disk in SQLite + a local file store; the only network egress is the Gemini call, which carries schema/profile and small samples only — never full datasets.

## Component Map

```
[Browser: Next.js static UI @ /app]
        │  JSON over HTTP (same origin :8001)
        ▼
[FastAPI app  (src/api)]
   │            │
   ▼            ▼
[Profiling   [Graph runner (src/graph/runner.py)]
 service]            │
   │                 ▼
   │          [LangGraph agent (plan→write_code→run_code→inspect→retry→finalize)]
   │                 │  generated pandas
   │                 ▼
   │          [Sandbox executor (subprocess, no network, dataset-only)] ←→ [Gemini API]
   ▼                 ▼
[SQLite via SQLAlchemy 2.0 + Alembic]   [Local file store (uploads / derived)]
```

## Layers

| Layer | Responsibility |
|-------|----------------|
| UI (Next.js static export, `/app`) | Upload, profile display, chat, answer + collapsible code panel; labelled stubs for later-phase surfaces |
| API (FastAPI, `src/api`) | Upload/profile/ask endpoints; `ok()`/`api_error()` envelope; Pydantic request/response models |
| Services (`src/services`) | Dataset profiling, (later) cleaning, derived-dataset/recipe save |
| Agent (`src/graph`) | LangGraph adaptive loop: plan, write pandas, run in sandbox, inspect, retry under a step budget, finalize |
| Sandbox (`src/sandbox`) | Execute LLM-generated pandas in a restricted subprocess — dataset-only namespace, no network, restricted builtins, bounded time |
| LLM (`src/llm`) | `LLMClient.call_model(prompt, system=...)` → GeminiProvider (`google-genai`) |
| Storage (`src/db` + local files) | SQLite (datasets, conversations, messages, audits) via SQLAlchemy 2.0 + Alembic; raw/derived files on local disk |

## Data Flow

1. **Trigger:** user uploads a CSV (Phase 1) via `POST /api/datasets`.
2. The API stores the raw file in the local file store, loads it with pandas, and the profiling service computes columns, dtypes, row count, and per-column ranges; a `Dataset` row is persisted with the profile.
3. The user submits a question via `POST /api/datasets/{id}/ask`. A `Conversation`/`Message` is recorded; the graph runner loads the dataset into memory and invokes the LangGraph agent.
4. The agent **plans** (Gemini), **writes pandas** (Gemini), **runs it in the sandbox**, **inspects** the result/error, and **retries** with refined code up to the step budget. Every step (code, result, error, tokens) is captured in a `QuestionAudit`.
5. **Output:** a prose answer plus the exact pandas code and the raw computed result, returned in the `ok()` envelope and persisted as the assistant `Message`.

## External Dependencies

| Dependency | Purpose | Failure Mode |
|------------|---------|--------------|
| Google Gemini (`google-genai`) | Plan + generate pandas + compose prose | Retry with backoff; on persistent failure the answer is returned as an error via `api_error()` — no offline stub |
| SQLite (local file) | Persist datasets, conversations, messages, audits | Fatal at startup if the DB path is unwritable; surfaced as a 500 |
| Local file store (`./data/`) | Raw uploads + derived datasets | Fatal per-request if unwritable; surfaced as `api_error()` |

## Stack

> This project's concrete technology choices. Generic every-project rules (model-naming, DB driver, dev port, real-key test rule) live in `harness/patterns/tech-stack.md`.

- **Language:** Python 3.12+ (backend), TypeScript (frontend)
- **Agent framework:** LangGraph (adaptive plan→write-code→run-in-sandbox→inspect→retry loop)
- **LLM provider + model:** Google Gemini via `google-genai`; default model `gemini-3.1-pro` (env-configurable via `AGENT_LLM_MODEL`), with `gemini-2.5-flash` used for the cheap single-shot / planning path to minimize token spend. Anthropic is wired but OFF the active path.
- **Backend:** FastAPI on port 8001 (`uv run python -m src` → uvicorn `0.0.0.0:8001`, `api:app`)
- **Database + ORM:** SQLite via SQLAlchemy 2.0 + Alembic. `AGENT_DATABASE_URL` defaults to `sqlite:///./data/agent.db` when blank (`.env.example` documents it; user may leave blank).
- **Frontend:** Next.js 15 static export (`output: export`) + React 19 + Tailwind, served at `/app` from `frontend/out/` (build: `cd frontend && pnpm build`)
- **Dependency management:** uv + `pyproject.toml` (Python, `pythonpath=["src"]`, flat package `["src"]`); pnpm (frontend)

| Key library | Version | Purpose |
|-------------|---------|---------|
| langgraph | latest | Agent graph orchestration |
| google-genai | latest | Gemini LLM client |
| pandas | latest | In-memory dataframe analysis (sandbox + profiling) |
| openpyxl | latest | Excel/multi-sheet reading (Phase 3) |
| python-multipart | latest | File upload parsing in FastAPI |
| sqlalchemy | 2.0.x | ORM |
| alembic | latest | DB migrations |
| fastapi / uvicorn | latest | API server |
| Recharts | latest | Interactive charts in the UI (Phase 2) |
| @playwright/test | latest | Headless E2E smoke tests |

**Avoid:** Anthropic on the active path (Gemini only); SQLite-as-substitute for any stated DB (SQLite IS the chosen DB here); any sandbox approach that grants the generated code network or arbitrary filesystem access; loading datasets too large for memory (explicitly out of scope). No new agent framework — extend the LangGraph skeleton in place.

## Deployment Model

A long-running local single-process service started with `uv run python -m src`. No container, no cloud, no auth — one local user. The frontend is pre-built to static files and served by the same FastAPI process at `/app`, so there is a single origin and no CORS surface.
