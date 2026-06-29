"""Graph runner — entry point invoked by the API (spec/api.md ask response).

``run_agent`` builds the initial ``AgentState``, invokes the compiled graph, and
returns the ask-response dict. It then persists the ``QuestionAudit`` update
defensively — the model import and DB write are wrapped in try/except so a
persistence failure never blocks the answer from being returned. The api-routes
slice creates the ``QuestionAudit`` row BEFORE calling ``run_agent`` and passes
``audit_id``; this runner UPDATES that row. The assistant ``Message`` is written
solely by the API layer (the single authoritative writer).
"""

import logging

from graph.agent import compiled_graph
from graph.state import AgentState
from db.session import create_db_session

logger = logging.getLogger("agent.runner")


def run_agent(
    *,
    dataset_id: int,
    question: str,
    conversation_id: int,
    profile: dict,
    dataset_paths: dict[str, str],
    history: list[dict],
    audit_id: int,
    step_budget: int = 5,
) -> dict:
    """Run the data-analysis agent for one question and return the ask payload."""
    initial: AgentState = {
        "run_id": audit_id,
        "dataset_id": dataset_id,
        "conversation_id": conversation_id,
        "question": question,
        "profile": profile or {},
        "dataset_paths": dataset_paths or {},
        "history": history or [],
        "effort": None,
        "approach": None,
        "code": None,
        "last_result": None,
        "last_result_repr": None,
        "last_error": None,
        "steps": [],
        "step_count": 0,
        "step_budget": step_budget,
        "tokens_used": 0,
        "answer": None,
        "final_code": None,
        "final_result_repr": None,
        "error": None,
        "checkpoint": None,
    }

    final = compiled_graph.invoke(initial)

    fatal = final.get("error")
    status = "failed" if fatal else "completed"
    answer = final.get("answer")
    if answer is None and fatal:
        answer = "The agent could not complete this question."

    result = {
        "conversation_id": conversation_id,
        "audit_id": audit_id,
        "answer": answer,
        "code": final.get("final_code") or final.get("code"),
        "result_repr": final.get("final_result_repr") or final.get("last_result_repr"),
        "effort": final.get("effort"),
        "step_count": final.get("step_count") or 0,
        "status": status,
        "tokens_used": final.get("tokens_used") or 0,
        "chart_spec": final.get("chart_spec"),
        "table": final.get("table"),
        "follow_ups": final.get("follow_ups"),
        "error": fatal,
    }

    _persist(final, result)
    return result


def _persist(final: AgentState, result: dict) -> None:
    """Defensively update the existing QuestionAudit row.

    The model is imported here (not at module top) so the graph package never
    couples to the db-schema slice's import timing. Any failure is logged, never
    raised.
    """
    try:
        from db.models import QuestionAudit  # noqa: PLC0415
    except Exception as exc:  # noqa: BLE001
        logger.warning("persistence skipped — models unavailable: %s", exc)
        return

    try:
        with create_db_session() as session:
            audit = session.get(QuestionAudit, result["audit_id"])
            if audit is not None:
                _set_if_has(audit, "status", result["status"])
                _set_if_has(audit, "step_count", result["step_count"])
                _set_if_has(audit, "tokens_used", result["tokens_used"])
                _set_if_has(audit, "final_code", result["code"])
                _set_if_has(audit, "final_result_repr", result["result_repr"])
                _set_if_has(audit, "effort", result["effort"])
                _set_if_has(audit, "error_message", result["error"])
                _set_if_has(audit, "steps_json", final.get("steps") or [])
    except Exception as exc:  # noqa: BLE001 — never crash the answer on persist
        logger.warning("persistence failed audit_id=%s: %s", result.get("audit_id"), exc)


def _set_if_has(obj, attr: str, value) -> None:
    """Set an attribute only if the model defines that column (defensive against
    the exact column set the db-schema slice ships)."""
    if hasattr(obj, attr):
        setattr(obj, attr, value)
