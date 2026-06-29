# Roadmap

---

## What This Agent Does

A personal, local-first data-analysis agent for a single power user who explores CSV and Excel spreadsheets ad-hoc. The user uploads a file, the agent auto-profiles it, and the user asks questions in plain English. The agent answers with prose plus key numbers, interactive charts (the agent chooses the chart type), and aggregated result tables — and always exposes the exact pandas code it ran. Its defining promise is **trust through transparency**: every result shows its work, keeps an audit trail, and is reproducible. It runs entirely on the user's machine, raw data never leaves the device, and it minimizes LLM token spend with an adaptive effort loop.

## Who Uses It

A single technical "power user" — a data analyst, scientist, or engineer comfortable reading code who wants fast, trustworthy answers about their own spreadsheets without writing pandas by hand. They value seeing and trusting the underlying computation over a black-box answer, and they return to the same datasets across days.

## Core Problem Being Solved

Exploring a spreadsheet ad-hoc today means either writing throwaway pandas/Excel formulas by hand (slow, error-prone) or pasting data into a cloud LLM that returns an unverifiable black-box number and may exfiltrate private data. This agent replaces that with a local loop that writes and runs verifiable pandas code over the real data, shows the code and the raw result, and keeps a reproducible audit trail — so the user gets the speed of natural language with the trust of real computation.

## Success Criteria

- [ ] A user can upload a CSV and within one screen see an auto-generated profile (columns, dtypes, row count, basic ranges) computed from the real file.
- [ ] A plain-English question returns a prose answer whose key numbers are produced by pandas code that actually ran over the uploaded data — not hallucinated.
- [ ] Every answer exposes the exact pandas code that produced it, in a collapsible panel, alongside the raw computed result.
- [ ] When generated code raises an error, the agent inspects the error and retries with refined code, up to a documented step budget, rather than returning a broken answer.
- [ ] All raw data stays on the local machine; the only network egress is the LLM call, and that call never contains full raw rows (only schema/profile and small samples).

## What This Agent Does NOT Do (Out of Scope)

- No cloud/multi-user deployment, auth, or sharing — single local user only.
- No write-back to source files; uploads and derived datasets are stored separately, originals are never mutated.
- No arbitrary code execution beyond the sandboxed pandas analysis path (no shell, no network from generated code, no filesystem writes outside the dataset/derived store).
- No streaming/real-time data sources, databases, or APIs as inputs — file uploads (CSV/Excel) only.
- No fine-tuning or training; the agent uses the LLM as-is.
- No support for files too large to hold in memory in Phase 1–N (very large out-of-core datasets are explicitly out of scope; small/medium in-memory files only).

## Key Constraints

- **Local-first / privacy:** raw data must remain on the machine. LLM prompts may include schema, profile stats, and small bounded samples — never full datasets.
- **Token budget:** adaptive effort — trivial questions take a cheap single-shot path; only hard questions escalate to plan-then-execute with retries. Token usage is tracked per question and per session.
- **Latency:** small/medium files are held in memory with pandas for fast repeated queries.
- **Sandbox safety:** all LLM-generated pandas code runs in a restricted subprocess sandbox with dataset access only — no network, no filesystem writes outside the derived-dataset store, restricted builtins. Code is always captured and shown.
- **Step budget:** the adaptive loop has a hard maximum step count (default 5) to bound cost and guarantee termination.
- **Stack is fixed** (see [architecture.md `## Stack`](architecture.md)): Python, FastAPI on port 8001, SQLite via SQLAlchemy 2.0 + Alembic, Google Gemini via `google-genai`, LangGraph, Next.js static export served at `/app`.

## Phases of Development

> **Phase 1 is the smallest first-time-right user-testable win.** Its backend is minimal but REAL on the one core path. Its frontend is visually complete: real UI for the working path PLUS clearly-labelled NON-FUNCTIONAL stubs for everything coming later. Each later phase wires those stubs into real functionality.

Capabilities map to phases as follows (see [capabilities/index.md](capabilities/index.md)):

- **Phase 1:** `ingest_and_profile`, `adaptive_analysis_loop` (the coded-answer core, including the sandbox).
- **Phase 2:** `rich_answer_presentation` (charts + result tables + follow-up suggestions + data-quality flags).
- **Phase 3:** `persistent_workspace` (sessions/resume + multi-file/multi-sheet + derived datasets/recipes + token-cost tracking + full step trace).

---

### Phase 1 — Upload → Profile → Ask → Coded Answer

- **Goal:** A user uploads one CSV in the browser, sees a real auto-generated profile, types one plain-English question, and gets a prose answer whose numbers came from pandas code that actually ran in the sandbox — with a collapsible panel showing the exact code and the raw result. The full adaptive LangGraph loop (plan → write-code → run-in-sandbox → inspect → retry, with a step budget) is wired, even where routing is simple.
- **Independent slices (parallel build units):**
  - `db-schema` (backend) — new SQLAlchemy models (`Dataset`, `Conversation`, `Message`, `QuestionAudit`) + Alembic migration `0002`. Deps: none.
  - `sandbox-and-graph` (backend) — the sandbox executor module, the LangGraph nodes (`plan`, `write_code`, `run_code`, `inspect`, `finalize`, `handle_error`), state shape, routing/step-budget, runner, profiling service. Deps: none (uses models by name via the DB session; imports are stable from `db-schema`'s declared model names, so it can be built in parallel against the agreed model interface in [data.md](data.md)).
  - `api-routes` (backend) — FastAPI routers for `POST /api/datasets` (upload+profile), `POST /api/datasets/{id}/ask`, `GET /api/datasets/{id}` (profile). Pydantic request/response models. Deps: none (calls the graph runner + profiling service by their declared signatures in [agent.md](agent.md) / [api.md](api.md)).
  - `frontend` (frontend) — the single-page workspace: real upload + profile panel + chat + answer + collapsible code panel for the working path, PLUS labelled non-functional stubs for charts, tables, multi-file/multi-sheet, persistence/resume, follow-up suggestions, data-quality flags, token/cost tracking, and the full step trace. Deps: none (calls the API contract in [api.md](api.md)).
  - `e2e-tests` (backend/test) — `tests/e2e/` Playwright smoke + `tests/phase1/` pytest end-to-end. Deps: none at authoring time; runs against the assembled app at gate time.
- **Key surfaces / files:**
  - `db-schema`: `src/db/models.py` (extend), `alembic/versions/0002_datasets.py`.
  - `sandbox-and-graph`: `src/sandbox/executor.py`, `src/sandbox/runner_proc.py`, `src/services/profiling.py`, `src/graph/state.py` (extend), `src/graph/nodes.py` (replace `transform_text` slot), `src/graph/edges.py` (extend), `src/graph/agent.py` (rebuild graph), `src/graph/runner.py` (replace), `src/prompts/plan.md`, `src/prompts/write_code.md` (replace `transform.md`).
  - `api-routes`: `src/api/datasets.py`, `src/api/__init__.py` (register router), `src/domain/dataset.py` (Pydantic models).
  - `frontend`: `frontend/src/app/page.tsx` (replace), `frontend/src/components/*`, `frontend/src/lib/api.ts`.
  - `e2e-tests`: `tests/phase1/test_end_to_end.py`, `tests/e2e/primary_journey.spec.ts`, `frontend/playwright.config.ts`.
- **Gate command (all must pass, in order):**
  ```
  uv run alembic upgrade head && \
  uv run pytest tests/phase1 -q && \
  cd frontend && pnpm build && cd .. && \
  uv run python -c "import socket,subprocess,sys,time; p=subprocess.Popen([sys.executable,'-m','src']); time.sleep(6); s=socket.socket(); s.connect(('127.0.0.1',8001)); s.close(); p.terminate(); print('boot-ok')" && \
  (uv run python -m src & echo $! > /tmp/agent.pid; sleep 6; cd frontend && npx playwright test tests/e2e/ --reporter=line; cd ..; kill $(cat /tmp/agent.pid))
  ```
  > On Windows PowerShell the boot+Playwright steps are run via the equivalent `Start-Process`/`Stop-Process` wrapper documented in the README; the pytest + alembic + pnpm build steps are identical. `tests/phase1/test_end_to_end.py` calls the real Gemini API using `AGENT_GEMINI_API_KEY` from `.env` against the default SQLite DB, exercising upload → profile → ask → coded-answer and asserting (a) the profile has the real column count of the fixture, (b) the answer's `code` field is non-empty pandas that references a fixture column, (c) the `result` field equals the value computed by running that pandas directly. The fixture CSV has 5000+ rows so a sampled answer differs observably from a full-data answer.
- **How the user tests it (handoff seed):**
  1. Fill `.env` with `AGENT_GEMINI_API_KEY` (already present). Leave `AGENT_DATABASE_URL` blank to use the default `sqlite:///./data/agent.db`.
  2. Run `uv run alembic upgrade head`, then `cd frontend && pnpm build && cd ..`, then `uv run python -m src`.
  3. Open `http://localhost:8001/app/`.
  4. **Real path:** Drag-and-drop or select a CSV. A profile panel appears showing column names, types, row count, and per-column ranges (these are computed from your real file). Type a question like "What is the average of <numeric column> grouped by <category column>?" and submit. A prose answer with the key numbers appears; click "Show code" to expand the exact pandas code and the raw computed result.
  5. **Labelled stubs (NOT bugs — each visibly tagged "Coming soon"):** the Charts tab, the Result Table tab, the "+ Add file / sheet" control, the "Saved sessions" sidebar, the "Suggested follow-ups" strip, the data-quality badges, the token/cost meter, and the full step-trace drawer are present and styled but show a "Coming in a later phase" placeholder.

### Phase 2 — Rich Answers: Charts, Tables, Follow-ups, Quality Flags

- **Goal:** The same ask flow now returns, alongside the prose+code, an interactive chart (agent-chosen type) when appropriate, an aggregated result table, 2–3 suggested follow-up questions, and data-quality flags surfaced on the profile (nulls, outliers, anomalies). The user can click a suggested follow-up to ask it.
- **Capabilities delivered:** `rich_answer_presentation` expands into charts, tables, follow-up suggestions, and data-quality flags (4 capability facets — meets the ≥3 rule).
- **Independent slices (parallel build units):**
  - `answer-enrichment` (backend) — extend the graph's `finalize`/output contract so the agent emits a structured `chart_spec` (type + encodings), a `table` (columns + rows), `follow_ups` (list), and `quality_flags`; new prompt sections + an `inspect`-stage chart-type decision. Deps: none.
  - `quality-profiler` (backend) — extend `src/services/profiling.py` to compute null counts, outlier flags (IQR), and basic anomaly notes during profiling, persisted on the `Dataset` profile. Deps: none.
  - `frontend-rich` (frontend) — wire the Charts tab (render `chart_spec` with a charting lib), the Result Table tab (render `table`), the Suggested-follow-ups strip (clickable), and the data-quality badges on the profile. Deps: none (consumes the extended API contract in [api.md](api.md)).
  - `phase2-tests` (backend/test + e2e) — pytest asserting a grouping question yields a non-empty `table` and a valid `chart_spec`; Playwright asserting the chart canvas and table render and a follow-up click re-asks. Deps: none at authoring; runs against assembled app.
- **Key surfaces / files:** `src/graph/nodes.py`, `src/graph/state.py`, `src/services/profiling.py`, `src/prompts/write_code.md`, `src/domain/dataset.py` (extend response), `frontend/src/components/Charts.tsx`, `frontend/src/components/ResultTable.tsx`, `frontend/src/components/FollowUps.tsx`, `frontend/src/components/QualityBadges.tsx`, `tests/phase2/`, `tests/e2e/rich_answers.spec.ts`.
- **Gate command:**
  ```
  uv run pytest tests/phase2 -q && cd frontend && pnpm build && cd .. && (start app; npx playwright test tests/e2e/rich_answers.spec.ts --reporter=line; stop app)
  ```
  Tests call real Gemini via `.env` against SQLite; assert a grouping question returns a `chart_spec` with a valid `type`, a `table` with ≥2 rows from the 5000-row fixture, and ≥2 `follow_ups`.
- **How the user tests it (handoff seed):** Open `http://localhost:8001/app/`, upload the CSV, ask a grouping question. Now the Charts tab renders a real interactive chart, the Result Table tab shows the aggregated rows, a "Suggested follow-ups" strip shows 2–3 clickable questions (clicking asks one), and the profile shows real data-quality badges (null %, outlier flags). Still labelled stubs: saved sessions / resume, multi-file, derived datasets, token/cost meter, full step trace.

### Phase 3 — Persistent Workspace: Sessions, Multi-file, Recipes, Cost & Trace

- **Goal:** The workspace becomes long-lived. The user returns across days to a saved session, loads multiple files (and multi-sheet Excel workbooks) to join/compare, saves a derived/cleaned dataset as both a reusable file and a reproducible recipe (the code), sees per-question and running-session token/cost totals, and opens a full step-by-step trace with "why this approach" for any answer.
- **Capabilities delivered:** `persistent_workspace` expands into sessions/resume, multi-file/multi-sheet, derived datasets/recipes, token-cost tracking, and the full step trace (5 capability facets — meets the ≥3 rule).
- **Independent slices (parallel build units):**
  - `persistence-api` (backend) — list/resume conversations, persist every message and `QuestionAudit` (steps, code, tokens), endpoints to list sessions and reload a dataset+history. Deps: none.
  - `multifile-ingest` (backend) — accept multiple files and multi-sheet Excel (`openpyxl`); each sheet becomes a named table in the sandbox namespace; cleaning + transparency report; save-derived-dataset (file + recipe) endpoint. Deps: none.
  - `cost-and-trace` (backend) — capture token usage per LLM call from the Gemini response, persist per-question and aggregate per-session; expose the full ordered step trace (each node, its rationale, its code, its tokens). Deps: none.
  - `frontend-workspace` (frontend) — wire the Saved-sessions sidebar (resume), the multi-file / multi-sheet add control, the derived-dataset save UI, the token/cost meter, and the full step-trace drawer. Deps: none (consumes the API contracts above).
  - `phase3-tests` (backend/test + e2e) — pytest: resume a session and assert history returns; upload a 2-sheet xlsx and assert both tables are queryable; assert token totals accumulate. Playwright: reload page, reopen saved session, see prior answer; open the trace drawer. Deps: none at authoring.
- **Key surfaces / files:** `src/api/datasets.py`, `src/api/sessions.py`, `src/services/profiling.py`, `src/services/cleaning.py`, `src/services/derived.py`, `src/graph/nodes.py` (multi-table namespace, token capture), `src/db/models.py` (extend if needed) + migration `0003`, `frontend/src/components/SessionsSidebar.tsx`, `FileManager.tsx`, `DerivedSave.tsx`, `CostMeter.tsx`, `StepTrace.tsx`, `tests/phase3/`, `tests/e2e/workspace.spec.ts`.
- **Gate command:**
  ```
  uv run alembic upgrade head && uv run pytest tests/phase3 -q && cd frontend && pnpm build && cd .. && (start app; npx playwright test tests/e2e/workspace.spec.ts --reporter=line; stop app)
  ```
  Tests call real Gemini via `.env` against SQLite; assert: a resumed conversation returns its prior messages; a 2-sheet `.xlsx` exposes both tables to a join question; per-session token total is > a single question's tokens after two questions.
- **How the user tests it (handoff seed):** Open the app, ask a question, reload the page — the session appears in the Saved-sessions sidebar and reopens with its history. Use "+ Add file / sheet" to add a second CSV or an Excel workbook and ask a question that joins them. Save a cleaned/derived result; it appears as both a downloadable file and a code recipe. The token/cost meter shows per-question and running-session totals. Open the step-trace drawer on any answer to see each step and "why this approach". No labelled stubs remain — every capability is real.
