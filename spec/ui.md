# UI

---

## UI Type

A single-page web workspace (chat-style data analysis), built as a Next.js 15 static export served at `/app` from the same FastAPI origin. One screen does everything; later-phase surfaces are present as clearly-labelled non-functional stubs in Phase 1 so the user sees the full vision and never mistakes a stub for a bug.

## Views / Screens

### Screen: Analysis Workspace (the only screen)

**Purpose:** Upload a file, read its profile, ask questions, and read answers with their exact code.

**Layout:** A left sidebar (Saved sessions — STUB in Phase 1), a top dataset/profile area, a central chat transcript, and a bottom question input.

**Key elements — REAL in Phase 1 (the working path):**
- **Upload control** — drag-and-drop / file picker for one CSV. POSTs to `POST /api/datasets`.
- **Profile panel** — renders the real computed profile: column names, dtypes, row count, per-column min/max/null-count.
- **Chat transcript** — user questions and assistant answers in order (conversational memory: follow-ups continue the same `conversation_id`).
- **Question input** — text box + submit; POSTs to `POST /api/datasets/{id}/ask`.
- **Answer block** — prose answer with key numbers, plus a **collapsible "Show code" panel** revealing the exact pandas and the raw `result_repr`. A small step counter shows `step_count`.

**Key elements — LABELLED STUBS in Phase 1 (each visibly tagged "Coming soon" / "Coming in a later phase", styled but inert):**
- **Charts tab** — placeholder where the agent-chosen interactive chart will render (Phase 2).
- **Result Table tab** — placeholder for the aggregated result table (Phase 2).
- **Suggested follow-ups strip** — placeholder chips (Phase 2).
- **Data-quality badges** — placeholder badges on the profile for nulls/outliers/anomalies (Phase 2).
- **"+ Add file / sheet" control** — multi-file / multi-sheet Excel (Phase 3).
- **Saved-sessions sidebar** — resume across days (Phase 3).
- **Token / cost meter** — per-question + running-session totals (Phase 3).
- **Full step-trace drawer** — step-by-step "why this approach" trace (Phase 3).

**Actions available (Phase 1):** upload a CSV; type and submit a question; expand/collapse the code panel; ask a follow-up in the same conversation.

## Error States

- **Loading:** upload shows a profiling spinner; ask shows a "thinking…" indicator with the live step counter.
- **Upload error** (bad/non-CSV/too large): inline message from the `invalid_file` / `storage_error` envelope, file not added.
- **Ask error** (`llm_unavailable` / `internal_error`): the assistant turn shows a clear error card ("The model was unavailable, please retry") — never a silent failure; the code/error captured so far is still shown.
- **Budget-exhausted answer:** rendered as a best-effort answer card explaining what was attempted, with the last code and error visible — not an error toast.

## Tech Stack

Next.js 15 + React 19 + Tailwind, static export (`output: export`), served at `/app`. Charts use Recharts (Phase 2). API access via a thin `frontend/src/lib/api.ts` client. E2E smoke via Playwright (`tests/e2e/`). See [architecture.md `## Stack`](architecture.md).
