"""Step 2: tools as plain functions, a second node, sequential edges."""

from app import tools
from app.graph import build_graph


def test_ambil_klaim():
    k = tools.get_claim("CLM-001")
    assert k["claim_id"] == "CLM-001" and k["employee_id"] == "EMP-01" and len(k["items"]) == 3
    assert tools.get_claim("CLM-999") is None


def test_format_rupiah():
    assert tools.format_idr(1020000) == "Rp1.020.000"
    assert tools.format_idr(0) == "Rp0"


def test_router_lalu_muat_klaim():
    g = build_graph().get_graph()
    assert any(e.source == "router" and e.target == "load_claim" for e in g.edges)


def test_graph_memuat_klaim():
    s = build_graph().invoke({"request": "Proses klaim CLM-002"})
    assert s["claim"]["employee_id"] == "EMP-02" and len(s["claim"]["items"]) == 2
