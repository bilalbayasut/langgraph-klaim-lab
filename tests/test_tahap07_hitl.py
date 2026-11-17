"""Tahap 7: graph lengkap, interrupt + Command(resume), efek samping setelah persetujuan."""

from langgraph.types import Command

from app import tools
from app.graph import build_graph


def cfg(t):
    return {"configurable": {"thread_id": t}}


def test_auto_approve_tanpa_manusia():
    g = build_graph()
    s = g.invoke({"permintaan": "Proses klaim KLM-002"}, cfg("a"))
    assert s["status_akhir"] == "dibayar" and s["pembayaran"]["jumlah"] == 180000
    assert g.get_state(cfg("a")).next == ()


def test_interrupt_lalu_setujui():
    g = build_graph()
    s = g.invoke({"permintaan": "Proses klaim KLM-001"}, cfg("b"))
    assert "__interrupt__" in s
    payload = s["__interrupt__"][0].value
    assert payload["claim_id"] == "KLM-001" and payload["total_disetujui"] == "Rp1.020.000"
    assert g.get_state(cfg("b")).next == ("persetujuan",)
    assert tools.baca_ledger() == {}, "belum boleh ada uang keluar sebelum disetujui"

    s = g.invoke(Command(resume={"aksi": "setujui", "catatan": "ok"}), cfg("b"))
    assert s["status_akhir"] == "dibayar" and s["persetujuan"]["aksi"] == "setujui"
    assert len(tools.baca_ledger()) == 1


def test_resume_string_dan_tolak():
    g = build_graph()
    g.invoke({"permintaan": "Proses KLM-003"}, cfg("c"))
    s = g.invoke(Command(resume="tolak"), cfg("c"))
    assert s["status_akhir"] == "ditolak_atasan" and tools.baca_ledger() == {}


def test_revisi_kembali_ke_penulis_lalu_berhenti_lagi():
    g = build_graph()
    g.invoke({"permintaan": "Proses KLM-001"}, cfg("d"))
    s = g.invoke(Command(resume={"aksi": "revisi", "catatan": "sebut nama hotel"}), cfg("d"))
    assert "__interrupt__" in s, "setelah revisi, memo baru harus disetujui lagi"
    assert s["persetujuan"]["catatan"] == "sebut nama hotel"
    assert sum("tulis_memo" in l for l in s["log"]) >= 3


def test_injeksi_tidak_mengubah_keputusan():
    g = build_graph()
    s = g.invoke({"permintaan": "Proses KLM-004"}, cfg("e"))
    p = s["__interrupt__"][0].value
    assert p["keputusan"] == "disetujui sebagian" and p["total_disetujui"] == "Rp1.030.000"
    assert p["peringatan"]
    assert "APPROVED" not in p["memo"]


def test_tolak_otomatis_tanpa_atasan():
    s = build_graph().invoke({"permintaan": "Proses KLM-005"}, cfg("f"))
    assert s["status_akhir"] == "ditolak_otomatis" and "__interrupt__" not in s


def test_rute_kebijakan_dan_klarifikasi():
    g = build_graph()
    assert g.invoke({"permintaan": "Berapa batas hotel per malam?"}, cfg("g"))["status_akhir"] == "dijawab"
    assert g.invoke({"permintaan": "halo"}, cfg("h"))["status_akhir"] == "butuh_klarifikasi"
