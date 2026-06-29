# Data Model

---

## Storage Technology

SQLite via SQLAlchemy 2.0 + Alembic (see [architecture.md `## Stack`](architecture.md)). The DB path defaults to `sqlite:///./data/agent.db` when `AGENT_DATABASE_URL` is blank. Raw uploaded files and derived datasets live as files in a local store under `./data/` (not in the DB); the DB holds metadata, profiles, conversations, and audits. SQLite is the right fit: single local user, local-first, zero-config.

> The existing `RunRow` table (skeleton, migration `0001`) is retained for the boilerplate health/runs surface. The tables below are added by migration `0002_datasets` (Phase 1), with `0003` extending for Phase 3.

## Entities

### Entity: Dataset

An uploaded file (Phase 1: one CSV) with its computed profile and on-disk location. Phase 3 generalizes to multiple files / multi-sheet workbooks.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | int (PK) | yes | Primary key |
| name | str | yes | Display name (original filename) |
| file_path | str | yes | Path in the local file store to the raw upload |
| table_name | str | yes | Python-safe name the dataset is bound to in the sandbox namespace (e.g. `df`) |
| row_count | int | yes | Rows in the loaded file |
| profile_json | JSON | yes | Columns, dtypes, per-column ranges, sample; quality flags added in Phase 2 |
| source_kind | str | yes | `csv` (Phase 1); `xlsx_sheet`, `derived` added in Phase 3 |
| created_at | datetime | yes | Upload time |

### Entity: Conversation

A thread of questions against one dataset (or, Phase 3, a workspace of datasets). Enables resume-across-days.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | int (PK) | yes | Primary key |
| dataset_id | int (FK → Dataset.id) | yes | The dataset this conversation analyzes |
| title | str | no | Auto-derived from the first question; editable later |
| created_at | datetime | yes | Created time |
| updated_at | datetime | yes | Last-message time (for sidebar ordering) |

### Entity: Message

One turn in a conversation (user question or assistant answer). Provides conversational memory.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | int (PK) | yes | Primary key |
| conversation_id | int (FK → Conversation.id) | yes | Owning conversation |
| role | str | yes | `user` or `assistant` |
| content | str | yes | Question text, or the assistant prose answer |
| audit_id | int (FK → QuestionAudit.id) | no | For assistant messages, links to the audit/code/result |
| created_at | datetime | yes | Turn time |

### Entity: QuestionAudit

The full reproducible audit for one answered question: the ordered steps, the final code, the raw result, the error (if any), and token usage. This is the "show its work" record.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | int (PK) | yes | Primary key (== `run_id` in agent state) |
| conversation_id | int (FK → Conversation.id) | yes | Owning conversation |
| dataset_id | int (FK → Dataset.id) | yes | Dataset analyzed |
| question | str | yes | The user's question |
| effort | str | no | `trivial` / `hard` (from plan) |
| steps_json | JSON | yes | Ordered trace: each `{node, code, result_repr, error, rationale, tokens}` |
| final_code | str | no | The pandas that produced the answer |
| final_result_repr | str | no | The raw computed result shown to the user |
| answer | str | no | The prose answer |
| status | str | yes | `completed` / `failed` |
| error_message | str | no | Set when `status == failed` |
| step_count | int | yes | Steps taken (≤ step_budget) |
| tokens_used | int | yes | Total Gemini tokens for this question (Phase 3 surfaces session totals) |
| created_at | datetime | yes | Asked time |
| completed_at | datetime | no | Finished time |

### Relationships

- `Dataset 1—N Conversation` (a dataset can have many conversations).
- `Conversation 1—N Message` (a conversation has many turns).
- `Conversation 1—N QuestionAudit`; each assistant `Message` references one `QuestionAudit` via `audit_id`.
- `Dataset 1—N QuestionAudit`.
- Phase 3: a workspace concept links multiple `Dataset` rows to one `Conversation` (join/compare); multi-sheet xlsx produces one `Dataset` row per sheet sharing a `source_file`.

## Data Lifecycle

- **Created:** `Dataset` on upload+profile; `Conversation` on first question; `Message`+`QuestionAudit` per question/answer.
- **Updated:** `Conversation.updated_at` on each new message; `QuestionAudit` updated to `completed`/`failed` when the run ends.
- **Deleted:** nothing is auto-deleted (long-lived local workspace). Manual delete of a dataset cascades to its conversations, messages, and audits, and removes the raw file from the store (Phase 3 management UI). Original uploaded files are never mutated.
- **Archived:** none — single-user local store; the user manages disk themselves.

## Sensitive Data

The raw spreadsheet data is the user's private data and stays entirely local: file contents live in the local file store and are loaded into memory only for analysis. The DB stores profiles, small samples, generated code, and results — which may contain data-derived values — but never leaves the machine. The only network egress is the Gemini prompt, which is bounded to schema/profile + a ≤20-row sample, never full rows (see [agent.md Memory & Context](agent.md)). The `AGENT_GEMINI_API_KEY` secret lives only in `.env` (gitignored), never in the DB.
