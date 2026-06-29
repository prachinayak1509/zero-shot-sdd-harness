"""Phase 2 rich-answer end-to-end tests — real Gemini, real DB, real sandbox.

These tests exercise the Phase 2 promise on top of the Phase 1 coded-answer
core: a grouping question now returns, alongside the prose+code, a structured
``table`` (the actual aggregated rows), an agent-chosen ``chart_spec``, and a
list of suggested ``follow_ups``; the profile carries deterministic
data-quality flags (``null_pct`` / ``outlier_count`` / ``flags`` per column and
a dataset-level ``quality.total_flags``).

Assertions are kept robust to LLM phrasing: we assert structure, types, and
counts (a non-null table with >= 2 real rows, a valid chart type, >= 2
follow-ups) rather than exact prose. A real multi-call Gemini run is allowed to
take a while — the TestClient has no read timeout, so the model gets as long as
it needs.

Bare imports work because pytest sets ``pythonpath = ["src"]``. The autouse
fixtures in conftest isolate the DB and skip cleanly when no Gemini key is set.
"""
from pathlib import Path

VALID_CHART_TYPES = {"bar", "line", "scatter", "pie"}


def _client():
    from fastapi.testclient import TestClient
    from api import app

    return TestClient(app)


def _upload(client, csv_path: str, name: str):
    path = Path(csv_path)
    with path.open("rb") as fh:
        resp = client.post(
            "/api/datasets",
            files={"file": (name, fh, "text/csv")},
        )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]


def _table_rows(table) -> list:
    """Normalize a ``table`` payload to a list of rows.

    The contract is ``{columns: [...], rows: [...]}``. ``rows`` may be a list of
    lists or a list of dicts; either way each entry is one aggregated row.
    """
    assert table is not None, "table is null for a grouping question"
    assert isinstance(table, dict), f"table is not an object: {table!r}"
    assert "columns" in table, f"table has no columns: {table!r}"
    assert "rows" in table, f"table has no rows: {table!r}"
    columns = table["columns"]
    rows = table["rows"]
    assert isinstance(columns, list) and len(columns) >= 1, (
        f"table.columns must be a non-empty list: {columns!r}"
    )
    assert isinstance(rows, list), f"table.rows must be a list: {rows!r}"
    return rows


def test_grouping_question_returns_chart_table_followups(sales_csv_path):
    """A grouping question yields a real table, a valid chart_spec, follow-ups."""
    client = _client()
    up = _upload(client, sales_csv_path, "sales.csv")
    dataset_id = up["id"]
    assert isinstance(dataset_id, int)

    ask = client.post(
        f"/api/datasets/{dataset_id}/ask",
        json={"question": "What is the total revenue grouped by region?"},
    )
    assert ask.status_code == 200, ask.text
    data = ask.json()["data"]

    assert data["status"] == "completed", f"agent did not complete: {data}"

    # --- Result table: the actual aggregated rows the code produced ----------
    rows = _table_rows(data["table"])
    assert len(rows) >= 2, (
        f"grouping question should yield >= 2 aggregated rows, got {len(rows)}: "
        f"{data['table']!r}"
    )

    # --- Chart spec: agent-chosen, valid type --------------------------------
    chart = data["chart_spec"]
    assert chart is not None, "chart_spec is null for a clearly chartable grouping"
    assert isinstance(chart, dict), f"chart_spec is not an object: {chart!r}"
    assert chart.get("type") in VALID_CHART_TYPES, (
        f"chart_spec.type {chart.get('type')!r} not in {VALID_CHART_TYPES}"
    )

    # --- Follow-ups: a list with >= 2 suggested questions --------------------
    follow_ups = data["follow_ups"]
    assert isinstance(follow_ups, list), f"follow_ups is not a list: {follow_ups!r}"
    assert len(follow_ups) >= 2, (
        f"expected >= 2 follow_ups, got {len(follow_ups)}: {follow_ups!r}"
    )
    assert all(isinstance(f, str) and f.strip() for f in follow_ups), (
        f"every follow_up must be a non-empty string: {follow_ups!r}"
    )


def test_follow_up_reask_same_conversation(sales_csv_path):
    """Clicking a suggested follow-up re-asks in the SAME conversation.

    We take a real follow_up string from the first answer and POST it back to
    /ask with the same conversation_id, then assert the conversation now holds
    the expected appended message sequence (user + assistant turns for both
    questions) — proving conversational continuity, not a new conversation.
    """
    client = _client()
    up = _upload(client, sales_csv_path, "sales.csv")
    dataset_id = up["id"]

    first = client.post(
        f"/api/datasets/{dataset_id}/ask",
        json={"question": "What is the total revenue grouped by region?"},
    )
    assert first.status_code == 200, first.text
    first_data = first.json()["data"]
    assert first_data["status"] == "completed", first_data

    conversation_id = first_data["conversation_id"]
    assert isinstance(conversation_id, int)

    follow_ups = first_data["follow_ups"]
    assert isinstance(follow_ups, list) and len(follow_ups) >= 1, (
        f"need a follow-up to re-ask: {follow_ups!r}"
    )
    follow_up_question = follow_ups[0]
    assert isinstance(follow_up_question, str) and follow_up_question.strip()

    # Re-ask the follow-up in the SAME conversation.
    second = client.post(
        f"/api/datasets/{dataset_id}/ask",
        json={"question": follow_up_question, "conversation_id": conversation_id},
    )
    assert second.status_code == 200, second.text
    second_data = second.json()["data"]
    # No error envelope on a successful re-ask.
    assert second.json().get("error") is None, second.json()
    assert second_data["status"] == "completed", second_data

    # Continuity: the second turn stayed in the same conversation.
    assert second_data["conversation_id"] == conversation_id, (
        "follow-up started a new conversation instead of continuing the existing one"
    )

    # The conversation now has the expected appended message sequence: two user
    # turns (the original question + the follow-up) and two assistant turns.
    from db.session import create_db_session
    from db.models import Message

    with create_db_session() as session:
        messages = (
            session.query(Message)
            .filter(Message.conversation_id == conversation_id)
            .order_by(Message.created_at, Message.id)
            .all()
        )
        roles = [m.role for m in messages]
        contents = [m.content for m in messages]

    user_turns = [c for r, c in zip(roles, contents) if r == "user"]
    assistant_turns = [r for r in roles if r == "assistant"]
    assert len(user_turns) >= 2, (
        f"expected >= 2 user turns in the conversation, got roles={roles!r}"
    )
    assert len(assistant_turns) >= 2, (
        f"expected >= 2 assistant turns in the conversation, got roles={roles!r}"
    )
    # The follow-up question text is one of the recorded user turns.
    assert follow_up_question in user_turns, (
        f"follow-up question not recorded as a user turn: {user_turns!r}"
    )


def test_profile_quality_flags(quality_csv_path):
    """The profile surfaces deterministic null_pct + outlier_count + flags.

    Uploads a CSV crafted with a sparse (many-null) column and an obvious
    numeric outlier, then GETs the dataset and asserts the per-column and
    dataset-level quality fields are populated and non-trivial.
    """
    client = _client()
    up = _upload(client, quality_csv_path, "quality.csv")
    dataset_id = up["id"]

    got = client.get(f"/api/datasets/{dataset_id}")
    assert got.status_code == 200, got.text
    data = got.json()["data"]
    profile = data["profile"]

    columns = profile["columns"]
    assert isinstance(columns, list) and columns, "profile has no columns"

    # Every column carries the Phase 2 quality fields.
    for col in columns:
        assert "null_pct" in col, f"column missing null_pct: {col!r}"
        assert "outlier_count" in col, f"column missing outlier_count: {col!r}"
        assert "flags" in col, f"column missing flags: {col!r}"
        assert isinstance(col["flags"], list), f"flags not a list: {col!r}"

    by_name = {c["name"]: c for c in columns}

    # The sparse column has a real null percentage > 0.
    assert "notes" in by_name, f"expected a 'notes' column: {list(by_name)!r}"
    assert by_name["notes"]["null_pct"] > 0, (
        f"sparse column null_pct should be > 0: {by_name['notes']!r}"
    )

    # The amount column has the injected outlier counted.
    assert "amount" in by_name, f"expected an 'amount' column: {list(by_name)!r}"
    assert by_name["amount"]["outlier_count"] >= 1, (
        f"outlier column outlier_count should be >= 1: {by_name['amount']!r}"
    )

    # At least one column surfaces a non-empty flags list.
    assert any(col["flags"] for col in columns), (
        f"expected at least one column with non-empty flags: {columns!r}"
    )

    # The dataset-level quality summary aggregates the flags.
    assert "quality" in profile, f"profile missing dataset-level quality: {profile!r}"
    quality = profile["quality"]
    assert isinstance(quality, dict), f"quality is not an object: {quality!r}"
    assert "total_flags" in quality, f"quality missing total_flags: {quality!r}"
    assert quality["total_flags"] >= 1, (
        f"dataset total_flags should be >= 1: {quality!r}"
    )
