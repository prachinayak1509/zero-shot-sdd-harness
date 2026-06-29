"""Conditional-edge routing functions (spec/agent.md "Conditional edges")."""

from graph.state import AgentState


def after_plan(state: AgentState) -> str:
    """plan → handle_error on fatal error, else write_code."""
    return "handle_error" if state.get("error") else "write_code"


def after_write_code(state: AgentState) -> str:
    """write_code → handle_error on fatal error, else run_code."""
    return "handle_error" if state.get("error") else "run_code"


def after_inspect(state: AgentState) -> str:
    """inspect → write_code (retry) while there is a loop-local error and budget
    remains; otherwise → finalize (valid result or budget exhausted)."""
    if state.get("last_error") and (state.get("step_count") or 0) < (state.get("step_budget") or 5):
        return "write_code"
    return "finalize"
