"""Tahap 11: siap untuk LangGraph Studio (langgraph dev)."""

import importlib
import json

from conftest import KODE


def test_langgraph_json():
    cfg = json.loads((KODE / "langgraph.json").read_text())
    assert cfg["graphs"]["klaim"] == "./app/graph.py:graph"
    assert "env" in cfg


def test_graph_untuk_studio_tanpa_checkpointer():
    mod = importlib.import_module("app.graph")
    assert mod.graph.checkpointer is None, "server Studio menyediakan persistence; jangan pasang checkpointer di sini"
    nodes = set(mod.graph.get_graph().nodes)
    assert {"router", "periksa_item", "persetujuan", "bayar"} <= nodes
