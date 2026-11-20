"""Langkah 1: graph pertama (state, node, edge, compile, invoke)."""

import json

from app.graph import build_graph
from app.nodes import router


def test_router_mengambil_nomor_klaim():
    assert router({"permintaan": "Tolong proses klaim klm-002 ya"})["claim_id"] == "KLM-002"


def test_router_tanpa_nomor_klaim():
    assert router({"permintaan": "halo"})["claim_id"] is None


def test_router_mengembalikan_pembaruan_parsial():
    out = router({"permintaan": "Proses KLM-002"})
    assert "permintaan" not in out, "node cukup mengembalikan field yang berubah, bukan state utuh"


def test_graph_mulai_dari_router():
    g = build_graph().get_graph()
    assert "router" in g.nodes
    assert any(e.source == "__start__" and e.target == "router" for e in g.edges)


def test_invoke():
    s = build_graph().invoke({"permintaan": "Proses klaim KLM-002"})
    assert s["permintaan"] == "Proses klaim KLM-002"
    assert s["claim_id"] == "KLM-002"


def test_langgraph_json(kode):
    cfg = json.loads((kode / "langgraph.json").read_text())
    assert cfg["graphs"]["klaim"] == "./app/graph.py:graph"


def test_chat_terminal_bisa_menjalankan_graph():
    """`uv run chat` (lab/chat.py) memakai graph-mu. Di sini input diberikan lewat pipe."""
    import os
    import subprocess
    import sys

    from lab.kode import ROOT

    r = subprocess.run([sys.executable, "-m", "lab.chat"], input="Proses klaim KLM-002\n/keluar\n", cwd=ROOT,
                       env=dict(os.environ), capture_output=True, text=True, timeout=120)
    assert r.returncode == 0 and "superstep 1: router" in r.stdout and "🤖" in r.stdout, r.stdout + r.stderr
