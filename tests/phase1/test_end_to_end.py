"""Phase 1 primary end-to-end test — real Gemini, real DB write, real sandbox.

Exercises the one core path the user tests by hand:

    upload CSV -> profile -> ask a grouping question -> coded answer

and proves *trust through transparency*: the agent's number must come from
pandas code that actually ran (reproducible by re-running that exact code
directly over the same CSV), not from an LLM hallucination.

Bare imports work because pytest sets ``pythonpath = ["src"]``. The autouse
fixtures in conftest isolate the DB and skip when no Gemini key is present.
"""
import re
from pathlib import Path

import pandas as pd

# A real multi-call Gemini run (plan + write_code + finalize, plus a possible
# sandbox-retry loop) is allowed to take a while; the gate runs this test on
# its own so no enforced per-test timeout marker is applied (that would need an
# extra plugin). The HTTP client below has no read timeout, so the real model
# call is given as long as it needs.

FIXTURE_CSV = Path(__file__).parent / "fixtures" / "sales.csv"


def _client():
    from fastapi.testclient import TestClient
    from api import app

    return TestClient(app)


def _run_code_for_result(code: str, df: pd.DataFrame):
    """Re-run the agent's exact pandas directly, mirroring the sandbox contract.

    The sandbox binds the dataset as ``df`` and reads back the ``result``
    variable the generated code assigns. We replicate that here so we can
    compare the directly-computed value against the agent's reported one.
    Returns the ``result`` object, or None if the code didn't assign one.
    """
    namespace: dict = {"pd": pd, "df": df.copy()}
    exec(code, namespace)  # noqa: S102 - executing the agent's own captured code, by design
    return namespace.get("result")


def test_upload_profile_ask_coded_answer(sales_csv_path):
    # The fixture CSV the *test* uploads is the deterministic 5000-row file.
    csv_path = Path(sales_csv_path)
    local_df = pd.read_csv(csv_path)
    expected_rows = len(local_df)
    expected_cols = list(local_df.columns)
    assert expected_rows >= 5000, "fixture must have 5000+ rows"

    client = _client()

    # --- 1. Upload + profile -------------------------------------------------
    with csv_path.open("rb") as fh:
        upload = client.post(
            "/api/datasets",
            files={"file": ("sales.csv", fh, "text/csv")},
        )
    assert upload.status_code == 200, upload.text
    up_data = upload.json()["data"]

    dataset_id = up_data["id"]
    assert isinstance(dataset_id, int)

    # Real column count and row count, computed from the real file.
    profile = up_data["profile"]
    assert len(profile["columns"]) == len(expected_cols), (
        f"profile column count {len(profile['columns'])} != fixture {len(expected_cols)}"
    )
    profile_col_names = {c["name"] for c in profile["columns"]}
    assert profile_col_names == set(expected_cols)
    assert up_data["row_count"] == expected_rows
    assert profile["row_count"] == expected_rows

    # --- 2. Ask a grouping question -----------------------------------------
    ask = client.post(
        f"/api/datasets/{dataset_id}/ask",
        json={"question": "What is the total revenue grouped by region?"},
    )
    assert ask.status_code == 200, ask.text
    answer = ask.json()["data"]

    assert answer["status"] == "completed", f"agent did not complete: {answer}"
    assert answer["answer"] and answer["answer"].strip(), "answer prose is empty"

    # --- 3. The exact pandas code is exposed and references a real column ----
    code = answer["code"]
    assert code and code.strip(), "code field is empty — transparency broken"
    assert re.search(r"\b(region|revenue)\b", code), (
        f"code does not reference a real fixture column: {code!r}"
    )

    # --- 4. Reproducibility: the number came from code that ran -------------
    # Re-run the agent's exact code directly over the same CSV and confirm the
    # agent's reported result is consistent with the directly-computed result.
    direct_result = _run_code_for_result(code, local_df)
    assert direct_result is not None, (
        "agent code did not assign `result` — cannot verify reproducibility"
    )

    direct_repr = repr(direct_result)
    agent_repr = answer["result_repr"]
    assert agent_repr and agent_repr.strip(), "result_repr is empty"

    if direct_repr.strip() == agent_repr.strip():
        # Exact repr match — strongest possible reproducibility signal.
        reproduced = True
    else:
        # Reprs can differ by formatting/ordering; fall back to comparing the
        # grouped revenue totals computed independently. At least one of these
        # canonical totals must surface in the agent's reported result, proving
        # the number is real, not hallucinated.
        canonical = local_df.groupby("region")["revenue"].sum()
        haystack = (agent_repr + " " + (answer["answer"] or "")).lower()
        hits = 0
        for total in canonical.values:
            # Match the rounded integer part of each group total — robust to
            # how many decimals the agent chose to print.
            if str(int(round(total))) in haystack.replace(",", ""):
                hits += 1
        reproduced = hits >= 1

    assert reproduced, (
        "agent's result is not consistent with directly-computed pandas — "
        f"agent_repr={agent_repr!r} direct_repr={direct_repr!r}"
    )
