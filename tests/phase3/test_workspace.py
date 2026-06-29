"""Phase 3 persistent-workspace end-to-end tests — real Gemini, real DB, real sandbox.

These tests exercise the Phase 3 promise on top of the Phase 1/2 coded-answer
core:

1. Sessions / resume — after two questions in ONE conversation, the session is
   listable via ``GET /api/conversations`` and reloadable (with its ordered
   messages + per-answer audit trace) via ``GET /api/conversations/{id}``.
2. Multi-sheet xlsx — a 2-sheet workbook uploaded to ``POST /api/datasets``
   creates one named table per sheet bound to one workspace/conversation, and a
   JOIN question across the two sheets completes with a sensible answer.
3. Derived datasets / recipes — ``POST /api/datasets/{id}/derived`` saves a
   result as BOTH a reusable file (on disk) AND the reproducible recipe (code).
4. Token-cost tracking — the running per-session token total accumulates across
   questions (strictly greater than the first question's tokens after two).

Assertions are kept robust to LLM phrasing: we assert structure, types, counts,
and DB/file state rather than exact prose. Real multi-call Gemini runs are
allowed to take a while — the TestClient has no read timeout, so the model gets
as long as it needs.

Bare imports work because pytest sets ``pythonpath = ["src"]``. The autouse
fixtures in conftest isolate the DB and skip cleanly when no Gemini key is set.
"""
from pathlib import Path


def _client():
    from fastapi.testclient import TestClient
    from api import app

    return TestClient(app)


def _upload_csv(client, csv_path: str, name: str = "sales.csv"):
    path = Path(csv_path)
    with path.open("rb") as fh:
        resp = client.post(
            "/api/datasets",
            files={"file": (name, fh, "text/csv")},
        )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]


def _ask(client, dataset_id: int, question: str, conversation_id=None):
    body = {"question": question}
    if conversation_id is not None:
        body["conversation_id"] = conversation_id
    resp = client.post(f"/api/datasets/{dataset_id}/ask", json=body)
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload.get("error") is None, payload
    return payload["data"]


def _as_list(value):
    """A list-shaped payload may arrive as a bare list or wrapped in a dict."""
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        for key in ("conversations", "sessions", "items", "data", "results"):
            inner = value.get(key)
            if isinstance(inner, list):
                return inner
    raise AssertionError(f"expected a list-shaped payload, got: {value!r}")


# ---------------------------------------------------------------------------
# 1 + 4. Resume a session and assert token totals accumulate across questions.
# ---------------------------------------------------------------------------
def test_resume_session_returns_history(sales_csv_path):
    """Two questions in ONE conversation are listable and fully reloadable.

    Asserts:
    - the session appears in ``GET /api/conversations`` (id, title, updated_at);
    - ``GET /api/conversations/{id}`` returns the ordered messages including
      BOTH Q&A pairs;
    - each assistant turn carries an ``audit`` with a non-empty ``steps`` trace;
    - the per-session ``session_tokens`` total is > 0 and >= a single audit's
      ``tokens_used`` (i.e. it accumulates across the two questions).
    """
    client = _client()
    up = _upload_csv(client, sales_csv_path)
    dataset_id = up["id"]
    assert isinstance(dataset_id, int)

    q1 = "What is the total amount grouped by region?"
    first = _ask(client, dataset_id, q1)
    conversation_id = first["conversation_id"]
    assert isinstance(conversation_id, int)
    assert first["status"] == "completed", first
    first_tokens = first["tokens_used"]
    assert isinstance(first_tokens, int) and first_tokens > 0, first

    q2 = "Which region has the highest total amount?"
    second = _ask(client, dataset_id, q2, conversation_id=conversation_id)
    assert second["conversation_id"] == conversation_id, (
        "second question started a new conversation instead of resuming"
    )
    assert second["status"] == "completed", second
    second_tokens = second["tokens_used"]
    assert isinstance(second_tokens, int) and second_tokens > 0, second

    # --- The session is listed in the sidebar feed -------------------------
    listing = client.get("/api/conversations")
    assert listing.status_code == 200, listing.text
    sessions = _as_list(listing.json()["data"])
    assert sessions, "no conversations were listed"
    match = next((s for s in sessions if s.get("id") == conversation_id), None)
    assert match is not None, (
        f"conversation {conversation_id} not in session list: {sessions!r}"
    )
    assert match.get("title"), f"listed session has no title: {match!r}"
    assert match.get("updated_at"), f"listed session has no updated_at: {match!r}"

    # --- Reload the full conversation history ------------------------------
    detail = client.get(f"/api/conversations/{conversation_id}")
    assert detail.status_code == 200, detail.text
    convo = detail.json()["data"]
    assert convo.get("id") == conversation_id, convo

    messages = convo.get("messages")
    assert isinstance(messages, list), f"messages is not a list: {convo!r}"

    roles = [m.get("role") for m in messages]
    contents = [m.get("content") or "" for m in messages]
    user_turns = [c for r, c in zip(roles, contents) if r == "user"]
    assistant_msgs = [m for m in messages if m.get("role") == "assistant"]

    # Both Q&A pairs are present and in order.
    assert len(user_turns) >= 2, f"expected >= 2 user turns, got roles={roles!r}"
    assert len(assistant_msgs) >= 2, (
        f"expected >= 2 assistant turns, got roles={roles!r}"
    )
    assert q1 in user_turns, f"first question not recorded: {user_turns!r}"
    assert q2 in user_turns, f"second question not recorded: {user_turns!r}"

    # Each assistant turn carries an audit with a non-empty step trace, and the
    # per-audit token counts are positive.
    audit_token_values = []
    for msg in assistant_msgs:
        audit = msg.get("audit")
        assert audit is not None, f"assistant message has no audit: {msg!r}"
        steps = audit.get("steps")
        assert isinstance(steps, list) and len(steps) >= 1, (
            f"assistant audit has an empty/invalid step trace: {audit!r}"
        )
        # Every step in the trace describes a node of the agent's run.
        for step in steps:
            assert isinstance(step, dict), f"a trace step is not an object: {step!r}"
        tok = audit.get("tokens_used")
        assert isinstance(tok, int) and tok >= 0, f"audit tokens invalid: {audit!r}"
        audit_token_values.append(tok)

    # --- Per-session token total accumulates across both questions ---------
    session_tokens = convo.get("session_tokens")
    assert isinstance(session_tokens, int), (
        f"session_tokens is not an int: {convo!r}"
    )
    assert session_tokens > 0, f"session_tokens should be > 0: {session_tokens}"
    assert session_tokens >= max(audit_token_values), (
        "session_tokens should be >= any single audit's tokens_used "
        f"(got session={session_tokens}, audits={audit_token_values})"
    )


def test_session_token_total_accumulates(sales_csv_path):
    """After two questions, the running session total exceeds the first question.

    A dedicated, narrow assertion of the cost-tracking promise: ``session_tokens``
    is strictly greater than the FIRST question's ``tokens_used`` once a second
    question has been asked in the same conversation.
    """
    client = _client()
    up = _upload_csv(client, sales_csv_path)
    dataset_id = up["id"]

    first = _ask(client, dataset_id, "What is the total amount grouped by region?")
    conversation_id = first["conversation_id"]
    first_tokens = first["tokens_used"]
    assert isinstance(first_tokens, int) and first_tokens > 0, first

    second = _ask(
        client,
        dataset_id,
        "What is the average amount per region?",
        conversation_id=conversation_id,
    )
    assert second["status"] == "completed", second

    detail = client.get(f"/api/conversations/{conversation_id}")
    assert detail.status_code == 200, detail.text
    convo = detail.json()["data"]

    session_tokens = convo.get("session_tokens")
    assert isinstance(session_tokens, int), f"session_tokens not int: {convo!r}"
    assert session_tokens > first_tokens, (
        "running session token total must strictly exceed the first question's "
        f"tokens after a second question (session={session_tokens}, "
        f"first={first_tokens})"
    )


# ---------------------------------------------------------------------------
# 2. Multi-sheet xlsx → one named table per sheet, queryable together (join).
# ---------------------------------------------------------------------------
def test_multisheet_xlsx_join(multisheet_xlsx_bytes):
    """A 2-sheet xlsx exposes both sheets as named tables to a join question.

    Uploads a workbook whose ``orders`` sheet (region, amount) and ``regions``
    sheet (region, manager) join on ``region``. Asserts TWO datasets are created
    (one per sheet) bound to a single workspace/conversation, then asks a JOIN
    question ("total amount by manager") that cannot be answered from one sheet
    alone and asserts a completed, non-empty result.
    """
    client = _client()

    resp = client.post(
        "/api/datasets",
        files={
            "file": (
                "workbook.xlsx",
                multisheet_xlsx_bytes,
                "application/vnd.openpyxlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]

    # The upload of a multi-sheet workbook yields TWO datasets (one per sheet).
    created = _as_list(data) if isinstance(data, list) else data.get("datasets", data)
    if isinstance(created, dict):
        # A single-object response that itself carries the sibling datasets.
        created = created.get("datasets") or [created]
    assert isinstance(created, list), f"expected a list of datasets: {data!r}"
    assert len(created) >= 2, (
        f"a 2-sheet workbook should create >= 2 datasets, got {len(created)}: {data!r}"
    )

    # Each created dataset has an id; collect them.
    dataset_ids = [d.get("id") for d in created]
    assert all(isinstance(i, int) for i in dataset_ids), (
        f"every created dataset needs an int id: {created!r}"
    )

    # They are bound to a single workspace/conversation.
    conversation_ids = {
        d.get("conversation_id") for d in created if d.get("conversation_id") is not None
    }
    assert len(conversation_ids) <= 1, (
        f"sheets of one workbook must share one conversation/workspace: {created!r}"
    )

    # Identify the primary dataset to ask against (any of the sheets is fine;
    # the agent's sandbox namespace holds BOTH sheet tables).
    ask_dataset_id = dataset_ids[0]
    conversation_id = next(iter(conversation_ids), None)

    answer = _ask(
        client,
        ask_dataset_id,
        "What is the total amount by manager? Join the orders sheet to the "
        "regions sheet on region to find each region's manager.",
        conversation_id=conversation_id,
    )

    assert answer["status"] == "completed", (
        f"the cross-sheet join question did not complete: {answer!r}"
    )
    # A sensible, non-empty answer that actually computed something.
    assert (answer.get("answer") or "").strip(), f"empty join answer: {answer!r}"
    assert (answer.get("code") or "").strip(), (
        f"join answer exposed no code: {answer!r}"
    )
    assert (answer.get("result_repr") or "").strip(), (
        f"join answer produced no raw result: {answer!r}"
    )


# ---------------------------------------------------------------------------
# 3. Derived dataset saved as BOTH a reusable file AND a reproducible recipe.
# ---------------------------------------------------------------------------
def test_derived_save_file_and_recipe(sales_csv_path):
    """Saving a derived result yields a new dataset, a real file, and the recipe.

    POSTs a derived-save request with a name + the pandas code that produces it;
    asserts the response carries a NEW dataset id, a ``file_path`` that exists on
    disk, and a ``recipe`` equal to the submitted code.
    """
    client = _client()
    up = _upload_csv(client, sales_csv_path)
    dataset_id = up["id"]

    code = "result = df.head(5)"
    resp = client.post(
        f"/api/datasets/{dataset_id}/derived",
        json={"name": "first_five", "code": code},
    )
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload.get("error") is None, payload
    data = payload["data"]

    # A NEW, distinct dataset id.
    new_id = data.get("id")
    assert isinstance(new_id, int), f"derived response has no int id: {data!r}"
    assert new_id != dataset_id, (
        f"derived dataset reused the source id {dataset_id}: {data!r}"
    )

    # A reusable file that actually exists on disk.
    file_path = data.get("file_path")
    assert file_path, f"derived response has no file_path: {data!r}"
    assert Path(file_path).exists(), (
        f"derived file_path does not exist on disk: {file_path!r}"
    )

    # The reproducible recipe equals the submitted code.
    recipe = data.get("recipe")
    assert recipe == code, (
        f"derived recipe must equal the submitted code "
        f"(submitted={code!r}, got={recipe!r})"
    )
