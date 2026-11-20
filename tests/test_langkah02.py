"""Langkah 2: tool sebagai fungsi biasa, node kedua, edge berurutan."""

from app import tools
from app.graph import build_graph


def test_ambil_klaim():
    k = tools.ambil_klaim("KLM-001")
    assert k["claim_id"] == "KLM-001" and k["karyawan_id"] == "EMP-01" and len(k["item"]) == 3
    assert tools.ambil_klaim("KLM-999") is None


def test_format_rupiah():
    assert tools.format_rupiah(1020000) == "Rp1.020.000"
    assert tools.format_rupiah(0) == "Rp0"


def test_router_lalu_muat_klaim():
    g = build_graph().get_graph()
    assert any(e.source == "router" and e.target == "muat_klaim" for e in g.edges)


def test_graph_memuat_klaim():
    s = build_graph().invoke({"permintaan": "Proses klaim KLM-002"})
    assert s["klaim"]["karyawan_id"] == "EMP-02" and len(s["klaim"]["item"]) == 2
