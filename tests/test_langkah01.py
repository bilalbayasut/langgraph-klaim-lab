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


def test_app_py_menjalankan_graph(kode):
    """`uv run app.py "..."` menjalankan graph-mu dan mencetak setiap superstep."""
    import os
    import subprocess
    import sys

    r = subprocess.run([sys.executable, "app.py", "Proses klaim KLM-002"], cwd=kode,
                       env=dict(os.environ), capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "superstep 1: router" in r.stdout and '"KLM-002"' in r.stdout, r.stdout


def test_app_py_chat():
    """`uv run app.py --chat`: setiap baris = satu permintaan, baris kosong = keluar."""
    import re

    from conftest import app_py

    out = app_py("--chat", masukan="Proses klaim KLM-002\nTolong cek klm-005\n\n").stdout
    assert len(re.findall(r"superstep \d+: router", out)) == 2 and '"KLM-005"' in out, out
