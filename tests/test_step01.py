"""Step 1: first graph (state, node, edge, compile, invoke)."""

import json

from app.graph import build_graph
from app.nodes import router


def test_router_mengambil_nomor_klaim():
    assert router({"request": "Please process claim clm-002 ya"})["claim_id"] == "CLM-002"


def test_router_tanpa_nomor_klaim():
    assert router({"request": "halo"})["claim_id"] is None


def test_router_mengembalikan_pembaruan_parsial():
    out = router({"request": "Process CLM-002"})
    assert "request" not in out, "a node only needs to return the changed fields, not the whole state"


def test_graph_mulai_dari_router():
    g = build_graph().get_graph()
    assert "router" in g.nodes
    assert any(e.source == "__start__" and e.target == "router" for e in g.edges)


def test_invoke():
    s = build_graph().invoke({"request": "Process claim CLM-002"})
    assert s["request"] == "Process claim CLM-002"
    assert s["claim_id"] == "CLM-002"


def test_langgraph_json(code_dir):
    cfg = json.loads((code_dir / "langgraph.json").read_text())
    assert cfg["graphs"]["claim"] == "./app/graph.py:graph"


def test_app_py_menjalankan_graph(code_dir):
    """`uv run app.py "..."` runs your graph and prints every superstep."""
    import os
    import subprocess
    import sys

    r = subprocess.run([sys.executable, "app.py", "Process claim CLM-002"], cwd=code_dir,
                       env=dict(os.environ), capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "superstep 1: router" in r.stdout and '"CLM-002"' in r.stdout, r.stdout


def test_app_py_chat():
    """`uv run app.py --chat`: each line = one request, empty line = quit."""
    import re

    from conftest import app_py

    out = app_py("--chat", graph_input="Process claim CLM-002\nPlease check clm-005\n\n").stdout
    assert len(re.findall(r"superstep \d+: router", out)) == 2 and '"CLM-005"' in out, out
