"""Langkah 5: fan-out, beberapa node dalam satu superstep, join."""

from helpers import superstep_dari, task_per_superstep

from app.graph import build_graph
from app.nodes import cek_karyawan


def test_cek_karyawan():
    out = cek_karyawan({"klaim": {"karyawan_id": "EMP-05"}})
    assert out["profil"]["sisa_anggaran"] == 400000 and out["profil"]["nama"] == "Eko Saputra"


def test_cek_karyawan_paralel_dengan_pemeriksaan_item():
    langkah = task_per_superstep(build_graph(), {"permintaan": "Proses klaim KLM-001"})
    s = superstep_dari(langkah, "cek_karyawan")
    assert any(n.startswith("periksa") for n in langkah[s]), f"harus satu superstep: {langkah}"
    assert sum(n == "putuskan" for nama in langkah.values() for n in nama) == 1, "join: putuskan jalan sekali"
    assert superstep_dari(langkah, "putuskan") == s + 1


def test_tolak_karena_anggaran():
    s = build_graph().invoke({"permintaan": "Proses klaim KLM-005"})
    k = s["keputusan"]
    assert (k["aksi"], k["total_disetujui"], k["perlu_persetujuan"]) == ("tolak", 0, False)
    assert "anggaran" in k["alasan"] and s["profil"]["karyawan_id"] == "EMP-05"


def test_keputusan_semua_klaim():
    harapan = {
        "KLM-001": ("setujui_sebagian", 1020000, True),
        "KLM-002": ("setujui_penuh", 180000, False),
        "KLM-003": ("setujui_sebagian", 2100000, True),
        "KLM-004": ("setujui_sebagian", 1030000, True),
        "KLM-005": ("tolak", 0, False),
    }
    g = build_graph()
    for cid, (aksi, total, perlu) in harapan.items():
        k = g.invoke({"permintaan": f"Proses {cid}"})["keputusan"]
        assert (k["aksi"], k["total_disetujui"], k["perlu_persetujuan"]) == (aksi, total, perlu), cid
