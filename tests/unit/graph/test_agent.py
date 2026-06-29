def test_graph_compiles():
    """Graph compiles without requiring any env vars."""
    from graph.agent import compiled_graph
    assert compiled_graph is not None
