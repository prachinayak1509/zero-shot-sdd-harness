# Capability: Adaptive Analysis Loop

## What It Does
Answers a plain-English question by having the LangGraph agent plan, write pandas, run it in a sandbox, inspect the result/error, and retry up to a step budget — returning prose with the exact code and raw result.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| question | str | `POST /api/datasets/{id}/ask` | yes |
| dataset_id | int (path) | URL | yes |
| conversation_id | int\|null | request body | no (omit to start a new conversation) |
| profile + sample | JSON | stored Dataset | yes (loaded server-side) |
| history | list[turn] | prior Messages | no (loaded for conversational memory) |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| answer | str (prose) | API response → chat transcript |
| code | str (pandas) | API response → collapsible code panel |
| result_repr | str | API response → code panel |
| QuestionAudit | row (steps, code, result, tokens, status) | SQLite |
| assistant Message | row | SQLite |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| Gemini (`google-genai`) | plan / write code / finalize | retry+backoff; persistent → `llm_unavailable` (502) |
| Sandbox subprocess | run generated pandas | error captured as `last_error` → retry loop (not fatal) |
| SQLite | persist audit + message | fatal → `internal_error` (500) |

## Business Rules
- The numbers in the prose answer come from the sandbox result, never invented.
- The exact generated code is ALWAYS returned, success or failure.
- Generated code runs only in the restricted subprocess sandbox (no network, restricted builtins, dataset-only, bounded time) — see [agent.md Sandbox Safety](../agent.md).
- The retry loop is bounded by `step_budget` (default 5); on exhaustion `finalize` returns a best-effort answer explaining the attempt, never a silent break.
- Prompts carry only schema/profile/sample + recent history — never full rows.
- Follow-up questions in the same `conversation_id` get prior turns as context (conversational memory).

## Success Criteria
- [ ] A grouping/aggregation question returns a prose answer whose key number equals the value obtained by running the returned `code` directly over the fixture.
- [ ] The `code` field is non-empty pandas referencing a real fixture column.
- [ ] When the first generated code raises an error, the agent retries with refined code and still returns a valid answer within `step_budget` (verifiable via `step_count > 1` in `QuestionAudit`).
- [ ] On a 5000+ row fixture, the answer reflects full-data computation (a sampled answer would differ observably).
- [ ] A follow-up referencing the prior question ("now group that by X") resolves correctly using conversation history.
