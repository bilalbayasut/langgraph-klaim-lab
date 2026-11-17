"""Tahap 3: node, edge, conditional edge, compile, invoke."""

from langgraph.graph import END, START, StateGraph

from app.nodes import klarifikasi, router, rute_setelah_router
from app.state import KlaimState


def _graph_mini():
    g = StateGraph(KlaimState)
    g.add_node("router", router)
    g.add_node("klarifikasi", klarifikasi)
    g.add_node("muat_klaim", lambda s: {"log": ["(placeholder muat_klaim)"]})
    g.add_node("jawab_kebijakan", lambda s: {"log": ["(placeholder jawab_kebijakan)"]})
    g.add_edge(START, "router")
    g.add_conditional_edges("router", rute_setelah_router, ["muat_klaim", "jawab_kebijakan", "klarifikasi"])
    for n in ("muat_klaim", "jawab_kebijakan", "klarifikasi"):
        g.add_edge(n, END)
    return g.compile()


def test_router_mengembalikan_pembaruan_parsial():
    out = router({"permintaan": "Tolong proses klaim klm-001"})
    assert out["rute"] == "klaim" and out["claim_id"] == "KLM-001"
    assert isinstance(out["log"], list) and len(out["log"]) == 1
    assert "permintaan" not in out, "node cukup mengembalikan field yang berubah"


def test_router_memvalidasi_nomor_klaim():
    out = router({"permintaan": "Proses KLM-999"})
    assert out["rute"] == "klarifikasi" and out["claim_id"] == "KLM-999"


def test_rute_setelah_router():
    assert rute_setelah_router({"rute": "klaim"}) == "muat_klaim"
    assert rute_setelah_router({"rute": "kebijakan"}) == "jawab_kebijakan"
    assert rute_setelah_router({"rute": "klarifikasi"}) == "klarifikasi"


def test_graph_mini_jalan():
    g = _graph_mini()
    s = g.invoke({"permintaan": "halo"})
    assert s["rute"] == "klarifikasi" and s["status_akhir"] == "butuh_klarifikasi"
    assert "KLM-001" in s["jawaban"]
    s = g.invoke({"permintaan": "Berapa batas biaya makan?"})
    assert s["rute"] == "kebijakan" and s["log"][-1] == "(placeholder jawab_kebijakan)"
    s = g.invoke({"permintaan": "Proses KLM-404"})
    assert "KLM-404 tidak ditemukan" in s["jawaban"]
