"""Graph assembly (spec/agent.md "Graph Assembly").

The graph MUST compile at import time without a DB or API key — no node runs
here, so no Gemini call happens at import. Only ``compiled_graph.invoke(...)``
executes nodes.
"""

from langgraph.graph import StateGraph, END

from graph.state import AgentState
from graph.nodes import (
    node_plan,
    node_write_code,
    node_run_code,
    node_inspect,
    node_finalize,
    node_handle_error,
)
from graph.edges import after_plan, after_write_code, after_inspect


def _build_graph():
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
        after_plan,
        {"handle_error": "handle_error", "write_code": "write_code"},
    )
    graph.add_conditional_edges(
        "write_code",
        after_write_code,
        {"handle_error": "handle_error", "run_code": "run_code"},
    )
    graph.add_edge("run_code", "inspect")
    graph.add_conditional_edges(
        "inspect",
        after_inspect,
        {"write_code": "write_code", "finalize": "finalize"},
    )
    graph.add_edge("finalize", END)
    graph.add_edge("handle_error", END)

    return graph.compile()


compiled_graph = _build_graph()

# Backwards-compatibility alias for existing imports (runner / tests).
agentic_ai = compiled_graph
