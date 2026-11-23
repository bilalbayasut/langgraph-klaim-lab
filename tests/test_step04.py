"""Step 4: conditional edge, three paths."""

from app.graph import build_graph
from app.nodes import router, route_after_router


def test_router_menulis_rute():
    assert router({"request": "Tolong proses klaim clm-001"})["route"] == "claim"
    assert router({"request": "Berapa batas biaya makan?"})["route"] == "policy"
    assert router({"request": "halo"})["route"] == "clarify"


def test_router_memvalidasi_nomor_klaim():
    out = router({"request": "Proses CLM-999"})
    assert out["route"] == "clarify" and out["claim_id"] == "CLM-999"


def test_fungsi_rute():
    assert route_after_router({"route": "claim"}) == "load_claim"
    assert route_after_router({"route": "policy"}) == "answer_policy"
    assert route_after_router({"route": "clarify"}) == "clarify"


def test_tiga_jalan():
    g = build_graph()
    s = g.invoke({"request": "halo"})
    assert s["final_status"] == "needs_clarification" and "CLM-001" in s["answer"]
    s = g.invoke({"request": "Proses CLM-404"})
    assert "CLM-404 not found" in s["answer"] and "decision" not in s
    s = g.invoke({"request": "Berapa batas biaya hotel per malam?"})
    assert s["route"] == "policy" and s["final_status"] == "answered" and s["answer"]
    s = g.invoke({"request": "Proses klaim CLM-001"})
    assert s["route"] == "claim" and "decision" in s


def test_gambar_punya_tiga_cabang_dari_router():
    edges = {(e.source, e.target) for e in build_graph().get_graph().edges}
    assert {("router", "load_claim"), ("router", "answer_policy"), ("router", "clarify")} <= edges
