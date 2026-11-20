"""Langkah 3: aturan bisnis di kode, reducer operator.add untuk log."""

from app import tools
from app.graph import build_graph


def _item(kategori, jumlah, struk=True):
    return {"item_id": "X-1", "kategori": kategori, "jumlah": jumlah, "ada_struk": struk, "keterangan": ""}


def test_periksa_item_semua_status():
    kb = tools.ambil_kebijakan()
    assert tools.periksa_item(_item("makan", 100000), kb)["status"] == "ok"
    h = tools.periksa_item(_item("makan", 180000), kb)
    assert (h["status"], h["disetujui"]) == ("dipotong", 150000)
    assert tools.periksa_item(_item("hotel", 500000, struk=False), kb)["status"] == "ditolak"
    assert tools.periksa_item(_item("transport", 100000, struk=False), kb)["status"] == "ok"
    assert tools.periksa_item(_item("hiburan", 50000), kb)["status"] == "ditolak"


def test_keputusan_klm_001():
    s = build_graph().invoke({"permintaan": "Proses klaim KLM-001"})
    assert len(s["hasil_item"]) == 3
    k = s["keputusan"]
    assert (k["aksi"], k["total_diajukan"], k["total_disetujui"], k["perlu_persetujuan"]) == (
        "setujui_sebagian", 1050000, 1020000, True)
    assert [h["item_id"] for h in k["rincian"]] == ["KLM-001-1", "KLM-001-2", "KLM-001-3"]


def test_keputusan_klaim_lain():
    g = build_graph()
    k = g.invoke({"permintaan": "Proses KLM-002"})["keputusan"]
    assert (k["aksi"], k["total_disetujui"], k["perlu_persetujuan"]) == ("setujui_penuh", 180000, False)
    k = g.invoke({"permintaan": "Proses KLM-003"})["keputusan"]
    assert (k["aksi"], k["total_disetujui"]) == ("setujui_sebagian", 2100000)


def test_log_bertambah_dengan_reducer():
    log = build_graph().invoke({"permintaan": "Proses klaim KLM-001"})["log"]
    for awalan in ("router", "muat_klaim", "putuskan"):
        assert any(baris.startswith(awalan) for baris in log), f"log harus berisi baris dari {awalan}: {log}"
