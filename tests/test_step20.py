"""Step 20: ready for LangGraph Studio (langgraph dev) and breakpoints from code."""

import importlib
import json

from conftest import cfg
from langgraph.checkpoint.memory import InMemorySaver

from app.graph import build_graph


def test_langgraph_json(code_dir):
    c = json.loads((code_dir / "langgraph.json").read_text())
    assert c["graphs"]["claim"] == "./app/graph.py:graph" and "env" in c


def test_graph_untuk_studio_tanpa_checkpointer():
    mod = importlib.import_module("app.graph")
    assert mod.graph.checkpointer is None, "the Studio server provides persistence; do not attach a checkpointer here"
    assert {"router", "check_item", "approval", "pay"} <= set(mod.graph.get_graph().nodes)


def test_breakpoint_dan_edit_state():
    g = build_graph(InMemorySaver())
    g.invoke({"request": "Proses klaim CLM-002"}, cfg("bp"), interrupt_before=["decide"])
    assert g.get_state(cfg("bp")).next == ("decide",)
    profile = g.get_state(cfg("bp")).values["profile"]
    g.update_state(cfg("bp"), {"profile": {**profile, "remaining_budget": 100000}})
    assert g.invoke(None, cfg("bp"))["decision"]["action"] == "reject"
