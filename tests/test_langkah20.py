"""Langkah 20: siap untuk LangGraph Studio (langgraph dev) dan breakpoint dari kode."""

import importlib
import json

from conftest import cfg
from langgraph.checkpoint.memory import InMemorySaver

from app.graph import build_graph


def test_langgraph_json(kode):
    c = json.loads((kode / "langgraph.json").read_text())
    assert c["graphs"]["klaim"] == "./app/graph.py:graph" and "env" in c


def test_graph_untuk_studio_tanpa_checkpointer():
    mod = importlib.import_module("app.graph")
    assert mod.graph.checkpointer is None, "server Studio menyediakan persistence; jangan pasang checkpointer di sini"
    assert {"router", "periksa_item", "persetujuan", "bayar"} <= set(mod.graph.get_graph().nodes)


def test_breakpoint_dan_edit_state():
    g = build_graph(InMemorySaver())
    g.invoke({"permintaan": "Proses klaim KLM-002"}, cfg("bp"), interrupt_before=["putuskan"])
    assert g.get_state(cfg("bp")).next == ("putuskan",)
    profil = g.get_state(cfg("bp")).values["profil"]
    g.update_state(cfg("bp"), {"profil": {**profil, "sisa_anggaran": 100000}})
    assert g.invoke(None, cfg("bp"))["keputusan"]["aksi"] == "tolak"
