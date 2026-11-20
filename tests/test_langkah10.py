"""Langkah 10: loop evaluator-optimizer dengan batas iterasi."""

from app import tools
from app.graph import build_graph
from app.nodes import cek_memo_aturan, nilai_memo, rute_setelah_nilai, tulis_memo


def _state_dasar(cid="KLM-001"):
    k = tools.ambil_klaim(cid)
    rincian = [tools.periksa_item(it, tools.ambil_kebijakan()) for it in k["item"]]
    keputusan = {"aksi": "setujui_sebagian", "alasan": "sebagian item dipotong", "total_diajukan": 1050000,
                 "total_disetujui": 1020000, "perlu_persetujuan": True, "rincian": rincian}
    return {"claim_id": cid, "klaim": k, "profil": tools.ambil_profil_karyawan(k["karyawan_id"]), "keputusan": keputusan}


def test_cek_memo_aturan():
    k = _state_dasar()["keputusan"]
    baik = "Klaim KLM-001 disetujui sebagian. Total disetujui: Rp1.020.000."
    assert cek_memo_aturan(baik, "KLM-001", k) == []
    assert len(cek_memo_aturan("Klaim disetujui.", "KLM-001", k)) == 3
    assert any("APPROVED" in m for m in cek_memo_aturan(baik + " APPROVED", "KLM-001", k))


def test_draf_pertama_mock_ditolak_draf_kedua_lolos():
    s = _state_dasar()
    d1 = tulis_memo(s)
    assert d1["jumlah_draf"] == 1 and "Rp1.020.000" not in d1["draf_memo"]
    p = nilai_memo({**s, **d1})["penilaian"]
    assert p["lolos"] is False and any("total" in m for m in p["masalah"])
    d2 = tulis_memo({**s, **d1, "penilaian": p})
    assert d2["jumlah_draf"] == 2 and "Rp1.020.000" in d2["draf_memo"]
    assert nilai_memo({**s, **d2})["penilaian"]["lolos"] is True


def test_rute_setelah_nilai():
    k = _state_dasar()["keputusan"]
    gagal, lolos = {"lolos": False, "masalah": ["x"]}, {"lolos": True, "masalah": []}
    assert rute_setelah_nilai({"penilaian": gagal, "jumlah_draf": 1, "keputusan": k}) == "tulis_memo"
    assert rute_setelah_nilai({"penilaian": gagal, "jumlah_draf": 3, "keputusan": k}) != "tulis_memo", "jatah habis"
    assert rute_setelah_nilai({"penilaian": lolos, "jumlah_draf": 1, "keputusan": k}) != "tulis_memo"


def test_loop_di_graph():
    s = build_graph().invoke({"permintaan": "Proses klaim KLM-002"})
    assert s["jumlah_draf"] == 2 and s["penilaian"]["lolos"] is True
    assert sum(b.startswith("tulis_memo") for b in s["log"]) == 2


def test_tanpa_jatah_revisi(monkeypatch):
    monkeypatch.setenv("MAX_REVISI", "0")
    s = build_graph().invoke({"permintaan": "Proses klaim KLM-002"})
    assert s["jumlah_draf"] == 1 and s["penilaian"]["lolos"] is False


def test_loop_berhenti_di_batas(monkeypatch):
    import app.nodes as n

    monkeypatch.setattr(n, "cek_memo_aturan", lambda *a: ["selalu gagal"])
    s = build_graph().invoke({"permintaan": "Proses klaim KLM-002"})
    assert s["jumlah_draf"] == 3, "1 draf + MAX_REVISI(2) revisi, lalu berhenti"
