# Capability: Persistent Workspace

> Phase 3. Builds on [adaptive_analysis_loop](adaptive_analysis_loop.md) and [ingest_and_profile](ingest_and_profile.md).

## What It Does
Makes the workspace long-lived: resume saved sessions across days, load multiple files and multi-sheet Excel workbooks to join/compare, save cleaned/derived datasets as both a reusable file and a reproducible recipe, track per-question and running-session token/cost totals, and open a full step-by-step trace ("why this approach") for any answer.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| files | CSV/XLSX upload(s) | `POST /api/datasets` (multi) | yes (for multi-file) |
| conversation_id | int | `GET /api/conversations/{id}` | yes (for resume) |
| derived save request | code + name | `POST /api/datasets/{id}/derived` | yes (for derived) |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| session list | array | sidebar |
| reloaded history | messages + audits | chat transcript |
| named tables | one per sheet/file in sandbox namespace | agent |
| derived dataset | file + recipe code | local store + Dataset row |
| token totals | per-question + per-session ints | cost meter |
| full trace | ordered steps (node, rationale, code, tokens) | step-trace drawer |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| openpyxl | read multi-sheet xlsx | bad sheet → `invalid_file`, skip/report |
| Gemini | token usage from each response | missing usage → count 0, log |
| SQLite | persist/list conversations, audits, derived | fatal → `internal_error` |
| Local file store | write derived dataset | fatal → `storage_error` |

## Business Rules
- Each Excel sheet and each uploaded file becomes a named table in the sandbox namespace, queryable together (join/compare).
- Messy files are auto-cleaned with a transparency report of the assumptions made; originals are never mutated.
- A derived dataset is saved as BOTH a reusable file AND the code recipe that produced it.
- Session token totals accumulate across questions and are shown live.
- Every answer's full ordered trace (each node, its rationale, its code, its tokens) is reconstructable from `QuestionAudit.steps_json`.

## Success Criteria
- [ ] After two questions then a page reload, the conversation appears in the sidebar and reopens with its prior messages.
- [ ] A 2-sheet `.xlsx` exposes both tables to a join question and returns a correct joined result.
- [ ] Saving a derived result yields both a downloadable file and a code recipe.
- [ ] The per-session token total after two questions is greater than a single question's tokens.
- [ ] The step-trace drawer shows each step with its "why this approach" rationale and its code.
