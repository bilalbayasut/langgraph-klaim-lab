"""Assembles the nodes into a graph."""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from app.nodes import router
from app.state import ClaimState


def build_graph(checkpointer=None):
    """Assemble and compile the graph.

    We only cover the checkpointer in Step 13 (app.py and the tests will attach it),
    so the parameter is prepared from now on.
    """
    g = StateGraph(ClaimState)          # 1. a graph with the ClaimState state shape
    g.add_node("router", router)         # 2. a node named "router" runs the router function
    g.add_edge(START, "router")          # 3. start at router
    g.add_edge("router", END)            #    after router, finish
    return g.compile(checkpointer=checkpointer)


# This is the variable LangGraph Studio reads (see langgraph.json).
graph = build_graph()
