# API

---

## API Style

REST (JSON) over HTTP, served by FastAPI on port 8001, same origin as the UI (`/app`). Every successful response uses the `ok(data)` envelope `{"data": ..., "error": null}`; every error is raised via `api_error(code, message, status_code)` producing `{"detail": {"code": ..., "message": ...}}` (see `src/api/_common.py`). All endpoints below are added in Phase 1 unless marked otherwise.

## Endpoints / Commands

### `POST /api/datasets`

**Purpose:** Upload one CSV, store it locally, profile it, and create a `Dataset`. (Phase 3: accept multiple files / multi-sheet xlsx.)

**Request:** `multipart/form-data` with a `file` field (the CSV).

**Response:**
```json
{
  "data": {
    "id": "int — Dataset id",
    "name": "str — original filename",
    "row_count": "int",
    "profile": {
      "columns": [{"name": "str", "dtype": "str", "min": "any|null", "max": "any|null", "null_count": "int"}],
      "row_count": "int",
      "sample": [{"col": "value"}]
    }
  },
  "error": null
}
```

**Error cases:**
| Status | Condition |
|--------|-----------|
| 400 | Missing file, non-CSV, unparseable CSV, or file too large to load in memory (`invalid_file`) |
| 500 | File store unwritable or DB error (`storage_error`) |

### `GET /api/datasets/{id}`

**Purpose:** Fetch a dataset's stored profile (to render the profile panel on reload).

**Response:** same `profile` shape as the upload response, plus `id`, `name`, `row_count`.

**Error cases:**
| Status | Condition |
|--------|-----------|
| 404 | No dataset with that id (`not_found`) |

### `POST /api/datasets/{id}/ask`

**Purpose:** Ask one plain-English question; runs the LangGraph agent and returns a coded answer. Creates/uses a `Conversation` and records `Message` + `QuestionAudit`.

**Request:**
```json
{
  "question": "str — the plain-English question",
  "conversation_id": "int|null — omit/null to start a new conversation; provided to continue (gives conversational memory)"
}
```

**Response:**
```json
{
  "data": {
    "conversation_id": "int",
    "audit_id": "int",
    "answer": "str — prose answer with key numbers",
    "code": "str — exact pandas that produced the result",
    "result_repr": "str — raw computed result shown in the collapsible panel",
    "effort": "str — trivial|hard",
    "step_count": "int — steps taken (<= step_budget)",
    "status": "str — completed|failed",
    "tokens_used": "int — Gemini tokens for this question",
    "chart_spec": "object|null — Phase 2",
    "table": "object|null — Phase 2 (columns + rows)",
    "follow_ups": "string[]|null — Phase 2",
    "steps": "array|null — Phase 3 full trace (node, code, rationale, tokens)"
  },
  "error": null
}
```
> `chart_spec`, `table`, `follow_ups`, and `steps` are `null` in Phase 1 (their UI is a labelled stub) and populated in Phase 2/3.

**Error cases:**
| Status | Condition |
|--------|-----------|
| 400 | Empty question (`invalid_question`) |
| 404 | No dataset with that id (`not_found`) |
| 502 | Gemini unavailable after retries (`llm_unavailable`) |
| 500 | Internal/graph error (`internal_error`) |

### `GET /api/conversations` and `GET /api/conversations/{id}` — Phase 3

**Purpose:** List saved sessions (sidebar) and reload a conversation with its full message history + audits (resume across days). Response: list of `{id, title, dataset_id, updated_at}`, and per-conversation the ordered `messages` with their linked audits.

### `POST /api/datasets/{id}/derived` — Phase 3

**Purpose:** Save a cleaned/derived result as both a reusable file and a reproducible recipe (the code). Response: the new derived `Dataset` `id`, its `file_path`, and the `recipe` code.

## Authentication

None. Single local user, bound to localhost (`0.0.0.0:8001` for local access only); same-origin UI means no CORS surface and no token. This is an explicit consequence of the local-first, single-user scope (see [roadmap.md Out of Scope](roadmap.md)).
