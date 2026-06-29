# Agent

---

## Agent Architecture Pattern

| Pattern | Use when |
|---------|----------|
| **Single-agent loop** | One LLM drives a deterministic tool-call loop. No branches, no handoffs. |
| **Graph (LangGraph)** | Multi-step pipeline with conditional edges, checkpointing, or parallel nodes. |
| **Multi-agent** | Specialised sub-agents with distinct roles; orchestrator routes between them. |
| **Supervisor** | One supervisor LLM dispatches to worker agents based on task type. |
| **Human-in-the-loop** | Execution pauses at defined checkpoints for user review or approval. |

**Chosen:** Graph (LangGraph). The flow is an adaptive plan → write-code → run-in-sandbox → inspect → retry loop with a conditional retry edge bounded by a step budget — exactly what conditional edges + a loop-back express cleanly, and what single-shot tool-calling cannot bound.

---

## LLM Provider & Model

| Agent / Node | Provider | Model ID | Rationale |
|-------------|----------|----------|-----------|
| `plan` | Google Gemini | `gemini-2.5-flash` (env `AGENT_LLM_MODEL_FAST`) | Classifies effort (trivial vs hard) and sketches an approach; a short, cheap call — flash minimizes token spend |
| `write_code` | Google Gemini | `gemini-3.1-pro` (env `AGENT_LLM_MODEL`) | Generates pandas; needs strong code quality to be first-time-right and reduce retries |
| `finalize` | Google Gemini | `gemini-3.1-pro` | Composes the prose answer from the raw result; quality-sensitive |

> **Assumed:** the cheap `plan` path uses `gemini-2.5-flash` and the code/finalize path uses `gemini-3.1-pro` (both env-configurable). This matches the cost-minimizing intent in [architecture.md `## Stack`](architecture.md). A trivial-question single-shot path that answers directly on flash is a possible later optimization, not a Phase-1 requirement.

**Fallback behaviour:** `LLMClient` retries transient Gemini failures (timeout / 429 / 5xx) with exponential backoff (3 attempts). On persistent failure a node sets `state["error"]`, routing to `handle_error`, and the API returns `api_error("llm_unavailable", ...)`. There is no offline/stub path — tests call the real Gemini API with `AGENT_GEMINI_API_KEY` from `.env`.

**Prompt strategy:** System/user split. `plan` and `write_code` request **structured JSON** (effort label, approach, and a fenced pandas code block / a JSON object with a `code` field). The prompt carries only the schema, profile stats, and a small bounded sample (default ≤ 20 rows) — never the full dataset. Prompts live in `src/prompts/{plan.md,write_code.md,finalize.md}`.

---

## Tools & Tool Calling

The agent does not use LLM-native tool-calling; it uses generated-code-as-tool. The single "tool" is the sandbox executor, invoked deterministically by the `run_code` node (not chosen by the LLM).

| Tool name | Description | Inputs | Output | Side-effects |
|-----------|-------------|--------|--------|--------------|
| `sandbox_exec` | Runs LLM-generated pandas in a restricted subprocess over the loaded dataset(s) | `code: str`, `dataset_paths: dict[str,str]`, `timeout_s: int` | `{ok, result_repr, result_value, stdout, error, traceback}` | None outside the sandbox: no network, no FS writes outside the derived store, restricted builtins |

**Tool selection strategy:** Rule-based / forced. After `write_code`, the graph always routes to `run_code` (the sandbox). The LLM never picks tools.

**Tool failure handling:** A sandbox error (exception, timeout, or non-serializable result) is captured into `state["last_error"]` and routed by the `inspect` node back to `write_code` for a refined attempt, until `step_count` reaches `step_budget` (default 5), after which `inspect` routes to `finalize` with a best-effort / failure answer.

---

## Agent State

```python
class AgentState(TypedDict):
    # Identity
    run_id: int                          # set at initialisation (== QuestionAudit.id)
    dataset_id: int                      # set at initialisation
    conversation_id: int                 # set at initialisation

    # Input
    question: str                        # the user's plain-English question
    profile: dict                        # columns, dtypes, ranges, sample (from profiling service)
    dataset_paths: dict[str, str]        # table_name -> on-disk file path (one entry in Phase 1)
    history: list[dict]                  # prior (role, content) turns for conversational context

    # Pipeline data (populated progressively by nodes)
    effort: str | None                   # "trivial" | "hard" — set by plan
    approach: str | None                 # one-line plan rationale ("why this approach") — set by plan
    code: str | None                     # latest generated pandas — set by write_code
    last_result: Any | None              # latest sandbox result value — set by run_code
    last_result_repr: str | None         # printable repr of the result — set by run_code
    last_error: str | None               # latest sandbox error/traceback (loop-local, not fatal) — set by run_code
    steps: list[dict]                    # ordered trace: {node, code, result_repr, error, tokens, rationale}
    step_count: int                      # incremented each write_code→run_code cycle
    step_budget: int                     # hard max (default 5), set at initialisation
    tokens_used: int                     # running token total for this question — accumulated by each LLM node

    # Output
    answer: str | None                   # final prose answer — set by finalize
    final_code: str | None               # the code that produced the answer — set by finalize
    final_result_repr: str | None        # the raw result shown to the user — set by finalize

    # Control
    error: str | None                    # set by any node on FATAL failure → routes to handle_error
    checkpoint: str | None               # last completed node (for resume)
```

---

## Nodes / Steps

### `node_plan`

**Reads from state:** `question`, `profile`, `history`

**Writes to state:** `effort`, `approach`, `steps` (append), `tokens_used`

**LLM call:** Yes. `src/prompts/plan.md`, Gemini, structured JSON `{effort, approach}`.

| System | Operation | On Failure |
|--------|-----------|------------|
| Gemini | classify effort + sketch approach | retry/backoff in LLMClient; persistent → set `error` (fatal) |

**Behaviour:** Classifies the question as `trivial` or `hard` and records a one-line rationale ("why this approach"). Routing is simple in Phase 1 — both paths proceed to `write_code` — but the classification and rationale are captured for the trace and to enable a cheaper single-shot path later.

### `node_write_code`

**Reads from state:** `question`, `profile`, `approach`, `last_error`, `last_result_repr`, `history`

**Writes to state:** `code`, `steps` (append), `tokens_used`

**LLM call:** Yes. `src/prompts/write_code.md`, Gemini, returns a fenced pandas code block (extracted to `code`). On a retry, the prior `code` and `last_error` are included so the model refines rather than restarts.

| System | Operation | On Failure |
|--------|-----------|------------|
| Gemini | generate/refine pandas | retry/backoff; persistent → set `error` (fatal) |

**Behaviour:** Produces pandas that computes the answer, assigning the final value to a variable named `result`. Carries only schema/profile/sample — never full rows.

### `node_run_code` (sandbox execution node)

**Reads from state:** `code`, `dataset_paths`, `step_budget`

**Writes to state:** `last_result`, `last_result_repr`, `last_error`, `step_count` (+1), `steps` (append)

**LLM call:** No.

| System | Operation | On Failure |
|--------|-----------|------------|
| Sandbox subprocess | run pandas over dataset(s) | exception/timeout captured into `last_error` (loop-local, NOT fatal) |

**Behaviour:** Invokes `sandbox_exec` (see Sandbox Safety). Loads each `dataset_paths` table into a pandas DataFrame in a restricted namespace, executes `code`, and extracts the `result` variable. Captures result, repr, stdout, and any error/traceback. Does not itself decide retries — that is `inspect`.

### `node_inspect`

**Reads from state:** `last_error`, `last_result`, `step_count`, `step_budget`

**Writes to state:** `steps` (append a rationale)

**LLM call:** No (deterministic in Phase 1).

**Behaviour:** Routing logic (see conditional edges). If `last_error` is set and `step_count < step_budget`, route back to `write_code` to refine. If the result is valid, route to `finalize`. If the budget is exhausted with no valid result, route to `finalize` for a best-effort/failure answer.

### `node_finalize`

**Reads from state:** `question`, `last_result_repr`, `last_error`, `code`, `effort`

**Writes to state:** `answer`, `final_code`, `final_result_repr`, `steps`, `tokens_used`, `checkpoint`

**LLM call:** Yes. `src/prompts/finalize.md`, Gemini — composes prose from the raw result (or explains the failure if the budget was exhausted). The numbers in the prose come from `last_result_repr`, not invention.

**Behaviour:** Builds the final user-facing answer, attaches the exact code and raw result, and persists the `QuestionAudit` (steps, tokens, final code/result) and the assistant `Message`.

### `node_handle_error`

**Reads from state:** `error`, `run_id`

**Behaviour:** Marks the `QuestionAudit` as failed with `error_message`, logs with `run_id` context, terminates the graph. The API surfaces `api_error()`.

---

## Graph / Flow Topology

```
START
  │
  ▼
node_plan ──(error)──► node_handle_error ──► END
  │
  ▼
node_write_code ──(error)──► node_handle_error
  │
  ▼
node_run_code
  │
  ▼
node_inspect
  │   ├──(last_error and step_count < step_budget)──► node_write_code   (retry loop)
  │   └──(result valid OR budget exhausted)─────────► node_finalize
  ▼
node_finalize ──► END
```

**Conditional edges:**

| Source node | Condition | Target |
|-------------|-----------|--------|
| `node_plan` | `state["error"] is not None` | `node_handle_error` |
| `node_plan` | else | `node_write_code` |
| `node_write_code` | `state["error"] is not None` | `node_handle_error` |
| `node_write_code` | else | `node_run_code` |
| `node_inspect` | `state["last_error"]` set AND `state["step_count"] < state["step_budget"]` | `node_write_code` |
| `node_inspect` | else (result valid OR budget exhausted) | `node_finalize` |

---

## Memory & Context

| Scope | Mechanism | What is stored |
|-------|-----------|----------------|
| **Within a run** | LangGraph state | question, profile, code, results, steps, tokens |
| **Across runs** | SQLite (`Dataset`, `Conversation`, `Message`, `QuestionAudit`) | uploaded datasets + profiles, full conversation history, per-question audit (steps/code/result/tokens) |
| **Conversation** | message history loaded into `state["history"]` | prior turns of the same conversation, so follow-up questions have context |

> **Conversation memory in Phase 1:** prior turns of the active conversation are loaded into `state["history"]` and passed to `plan`/`write_code`, so a follow-up like "now break that down by region" resolves against the previous question. This satisfies the chat-memory requirement from day one.

**Context window management:** Only schema, profile stats, and a bounded sample (≤ 20 rows) plus the last N turns (default 6) of history enter the prompt — never full datasets. If history exceeds the window it is truncated to the most recent turns.

---

## Human-in-the-Loop Checkpoints

| Checkpoint | What is shown to the user | Expected user action | Timeout / default |
|------------|--------------------------|----------------------|-------------------|
| Clarification (Phase 2+) | A clarifying question when the request is genuinely ambiguous | answer, or accept the best-guess | none — Phase 1 always best-guesses and flags assumptions in the answer |

> Phase 1 has no blocking checkpoint: the agent always proceeds with a best guess and surfaces assumptions in the prose. Genuine clarification is a Phase-2 enhancement.

---

## Error Handling & Recovery

**Node-level:** Each node catches its own exceptions. A **fatal** failure (e.g. Gemini unavailable after retries) sets `state["error"]` and routes to `handle_error`. A **loop-local** failure (sandbox raised on generated code) sets `state["last_error"]` and is handled by the retry loop — it is NOT fatal.

**Graph-level (`node_handle_error`):**
- Reads: `state.error`, `state.run_id`
- Updates DB: `QuestionAudit` status → "failed", `error_message`, `completed_at`
- Logs error with `run_id` context
- Terminates graph

**Resume / retry strategy:** Within a run, the sandbox retry loop refines code up to `step_budget`. A fully failed run is not auto-resumed; the user re-asks. Conversation history persists, so context is not lost.

**Partial failure:** If the budget is exhausted without a clean result, `finalize` still returns a best-effort answer that explains what was attempted and shows the last code/error — never a silent break.

---

## Observability

| Signal | What | Where |
|--------|------|-------|
| **Trace** | One ordered `steps` list per question (each node, code, result/error, rationale, tokens) | persisted in `QuestionAudit.steps`; structured log to stdout |
| **LLM calls** | Model, prompt/response, token counts, latency | structured log per call; tokens accumulated in `state["tokens_used"]` and persisted |
| **Tool calls** | Sandbox code, success/error, latency | structured log + `steps` entry |
| **Run outcome** | Status, total steps, total tokens, error if any | `QuestionAudit` + structured log |

> Structured request/response logging is wired in Phase 1 (input question, generated code, result/error, latency, tokens to stdout). LangSmith tracing is OFF by default (local-first, minimize egress); it can be enabled via `LANGCHAIN_TRACING_V2`/`LANGCHAIN_API_KEY` env vars without code change. **Assumed:** LangSmith is opt-in, not default, to honor the local-first/privacy constraint — structured stdout logging is the always-on observability baseline.

---

## Concurrency Model

- **Run isolation:** one question at a time per process is the practical model for a single local user; runs are scoped by `run_id`/`dataset_id` so state never crosses. No hard 409 lock in Phase 1 (single user); the API processes requests sequentially.
- **Parallel nodes within a run:** none — the loop is strictly sequential.
- **Checkpointing:** none (LangGraph in-memory). Durable state lives in SQLite (`QuestionAudit`, `Message`), which is sufficient for resume-by-re-ask. A `SqliteSaver` checkpointer is a possible later addition, not required.

---

## Sandbox Safety

Generated pandas runs in a **separate subprocess** (`src/sandbox/runner_proc.py`), launched by `src/sandbox/executor.py`, with:

- **No network:** the subprocess monkeypatches `socket.socket` to raise, and imports of `socket`/`urllib`/`requests`/`http` are blocked, so generated code cannot make network calls.
- **Restricted builtins:** the exec namespace exposes only a safe allowlist (`pd`, the loaded DataFrames by table name, plus pure builtins like `len`, `range`, `min`, `max`, `sum`, `sorted`, `round`, `abs`); `open`, `exec`, `eval`, `__import__`, `os`, `sys`, `subprocess` are not provided.
- **No filesystem writes outside the derived store:** the working directory is constrained; writes are only permitted to the derived-dataset directory (Phase 3 feature). Phase 1 code is read-only over the dataset.
- **Bounded time:** the subprocess is killed after `timeout_s` (default 30s); a timeout becomes a `last_error` and feeds the retry loop.
- **Dataset access only:** the parent passes `dataset_paths`; the subprocess loads exactly those files into the namespace and nothing else.
- **Result contract:** generated code must assign its answer to `result`; the subprocess serializes `result` (and a printable repr) back to the parent over stdout/a pipe. Non-serializable or missing `result` is a `last_error`.

The exact captured code is ALWAYS returned to the user, regardless of success or failure.

---

## Graph Assembly (`src/graph/agent.py`)

```python
graph = StateGraph(AgentState)

graph.add_node("plan", node_plan)
graph.add_node("write_code", node_write_code)
graph.add_node("run_code", node_run_code)
graph.add_node("inspect", node_inspect)
graph.add_node("finalize", node_finalize)
graph.add_node("handle_error", node_handle_error)

graph.set_entry_point("plan")

graph.add_conditional_edges(
    "plan",
    lambda s: "handle_error" if s.get("error") else "write_code",
)
graph.add_conditional_edges(
    "write_code",
    lambda s: "handle_error" if s.get("error") else "run_code",
)
graph.add_edge("run_code", "inspect")
graph.add_conditional_edges(
    "inspect",
    lambda s: "write_code"
        if s.get("last_error") and s["step_count"] < s["step_budget"]
        else "finalize",
)
graph.add_edge("finalize", END)
graph.add_edge("handle_error", END)

compiled_graph = graph.compile()
```
