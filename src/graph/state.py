from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    """State for the data-analysis agent (spec/agent.md "Agent State").

    ``total=False`` so nodes can populate fields progressively.
    """

    # Identity
    run_id: int                          # == QuestionAudit.id, set at init
    dataset_id: int                      # set at init
    conversation_id: int                 # set at init

    # Input
    question: str                        # the user's plain-English question
    profile: dict                        # columns, dtypes, ranges, sample
    dataset_paths: dict[str, str]        # table_name -> on-disk file path
    history: list[dict]                  # prior (role, content) turns

    # Pipeline data (populated progressively by nodes)
    effort: str | None                   # "trivial" | "hard" — set by plan
    approach: str | None                 # one-line rationale — set by plan
    code: str | None                     # latest generated pandas — write_code
    last_result: Any | None              # latest sandbox result value — run_code
    last_result_repr: str | None         # printable repr — run_code
    last_table: dict | None              # latest sandbox {columns, rows} table — run_code
    last_error: str | None               # latest sandbox error (loop-local)
    steps: list[dict]                    # ordered trace
    step_count: int                      # incremented each run_code cycle
    step_budget: int                     # hard max (default 5)
    tokens_used: int                     # running token total

    # Output
    answer: str | None                   # final prose answer — finalize
    final_code: str | None               # code that produced the answer
    final_result_repr: str | None        # raw result shown to the user

    # Phase 2 — rich answer presentation (all optional, set by finalize)
    chart_spec: dict | None              # agent-chosen chart encodings (or None)
    table: dict | None                   # {columns, rows} aggregated result table
    follow_ups: list[str] | None         # 2–3 suggested next questions

    # Control
    error: str | None                    # FATAL failure → handle_error
    checkpoint: str | None               # last completed node (for resume)
