# Local Data-Analysis Agent

A personal, local-first data-analysis agent. Upload a spreadsheet, ask questions in plain English, and get a prose answer whose key numbers come from **pandas code that actually ran** over your data — with the exact code always shown. Trust through transparency: every result shows its work and is reproducible. Runs entirely on your machine; raw data never leaves the device. Powered by Google Gemini via LangGraph.

> **All commands run from the repo root** (the directory containing this README, `pyproject.toml`, and `alembic.ini`). There is no subdirectory to `cd` into for backend commands.

## Prerequisites

- Python 3.11+ and [uv](https://docs.astral.sh/uv/)
- Node 18+ and [pnpm](https://pnpm.io/) (for the web UI)
- A Google Gemini API key

## Setup

1. Copy the env template and add your key:

   ```bash
   cp .env.example .env
   ```

   Set `AGENT_GEMINI_API_KEY` in `.env`. Leave `AGENT_ANTHROPIC_API_KEY` blank (the provider auto-selects Gemini). Leave `AGENT_DATABASE_URL` blank to use the default local SQLite store at `./data/agent.db`.

2. Install Python dependencies:

   ```bash
   uv sync
   ```

3. Create the database tables:

   ```bash
   uv run alembic upgrade head
   uv run alembic current   # must print a revision hash, not blank
   ```

4. Build the web UI (static export served by the backend):

   ```bash
   cd frontend && pnpm install && pnpm build && cd ..
   ```

## Run

From the repo root:

```bash
uv run python -m src
```

Then open **http://localhost:8001/app/** in your browser.

Health check: **http://localhost:8001/health**.

## Using it (Phase 1)

1. Upload one CSV (drag-and-drop or file picker).
2. A **profile panel** appears with the real column names, dtypes, row count, and per-column min/max/null-count.
3. Type a plain-English question (e.g. "What is the average of <numeric column> grouped by <category column>?") and submit.
4. A prose **answer** with the key numbers appears. Click **"Show code"** to expand the exact pandas code and the raw computed result.

**Labelled "Coming soon" stubs (not bugs):** Charts tab, Result Table tab, suggested follow-ups, data-quality badges, "+ Add file / sheet", saved-sessions sidebar, token/cost meter, and the full step-trace drawer. These are styled placeholders for later phases.

## Tests

Run the Phase 1 gate (real Gemini via `.env`, against SQLite):

```bash
uv run alembic upgrade head
uv run pytest tests/phase1 -q
cd frontend && pnpm build && cd ..
# UI smoke (start the app on :8001, then):
cd frontend && npx playwright test ../tests/e2e/ --reporter=line && cd ..
```

The end-to-end test exercises upload → profile → ask → coded-answer against the real Gemini API and asserts the answer's numbers were computed by the shown pandas code over a 5000+ row fixture.

## Architecture

See `spec/` for the full spec: `spec/roadmap.md` (phases), `spec/architecture.md` (stack + design), `spec/agent.md` (the adaptive LangGraph plan→write-code→run-in-sandbox→inspect→retry loop), `spec/data.md`, `spec/api.md`, `spec/ui.md`.
