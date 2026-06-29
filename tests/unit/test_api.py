"""API contract tests — no LLM key required, graph is not invoked.

The old boilerplate ``/runs`` route was removed when the data-analysis agent
superseded the ``transform_text`` pipeline. Only ``/health`` remains here as a
retained-boilerplate smoke check; the datasets/ask coverage lives in
``tests/phase1``.
"""


def test_health(api_client):
    r = api_client.get("/health")
    assert r.status_code == 200
    assert r.json()["data"]["status"] == "ok"


def test_runs_route_removed(api_client):
    """The superseded boilerplate route must no longer be registered."""
    r = api_client.post("/runs", json={"input_text": "test"})
    assert r.status_code == 404
