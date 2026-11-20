"""Langkah 4: conditional edge, tiga jalan."""

from app.graph import build_graph
from app.nodes import router, rute_setelah_router


def test_router_menulis_rute():
    assert router({"permintaan": "Tolong proses klaim klm-001"})["rute"] == "klaim"
    assert router({"permintaan": "Berapa batas biaya makan?"})["rute"] == "kebijakan"
    assert router({"permintaan": "halo"})["rute"] == "klarifikasi"


def test_router_memvalidasi_nomor_klaim():
    out = router({"permintaan": "Proses KLM-999"})
    assert out["rute"] == "klarifikasi" and out["claim_id"] == "KLM-999"


def test_fungsi_rute():
    assert rute_setelah_router({"rute": "klaim"}) == "muat_klaim"
    assert rute_setelah_router({"rute": "kebijakan"}) == "jawab_kebijakan"
    assert rute_setelah_router({"rute": "klarifikasi"}) == "klarifikasi"


def test_tiga_jalan():
    g = build_graph()
    s = g.invoke({"permintaan": "halo"})
    assert s["status_akhir"] == "butuh_klarifikasi" and "KLM-001" in s["jawaban"]
    s = g.invoke({"permintaan": "Proses KLM-404"})
    assert "KLM-404 tidak ditemukan" in s["jawaban"] and "keputusan" not in s
    s = g.invoke({"permintaan": "Berapa batas biaya hotel per malam?"})
    assert s["rute"] == "kebijakan" and s["status_akhir"] == "dijawab" and s["jawaban"]
    s = g.invoke({"permintaan": "Proses klaim KLM-001"})
    assert s["rute"] == "klaim" and "keputusan" in s


def test_gambar_punya_tiga_cabang_dari_router():
    edges = {(e.source, e.target) for e in build_graph().get_graph().edges}
    assert {("router", "muat_klaim"), ("router", "jawab_kebijakan"), ("router", "klarifikasi")} <= edges
