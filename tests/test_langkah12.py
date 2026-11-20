"""Langkah 12: interrupt + Command(resume), efek samping setelah persetujuan."""

import pytest
from conftest import cfg
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from app import tools
from app.graph import build_graph


def _g():
    return build_graph(InMemorySaver())


def test_bayar_idempoten():
    a = tools.bayar("KLM-X", 1000)
    b = tools.bayar("KLM-X", 1000)
    assert (a["duplikat"], b["duplikat"]) == (False, True) and a["ref"] == b["ref"]
    assert len(tools.baca_ledger()) == 1


def test_auto_approve_tanpa_manusia():
    g = _g()
    s = g.invoke({"permintaan": "Proses klaim KLM-002"}, cfg("a"))
    assert s["status_akhir"] == "dibayar" and s["pembayaran"]["jumlah"] == 180000
    assert g.get_state(cfg("a")).next == ()


def test_interrupt_lalu_setujui():
    g = _g()
    s = g.invoke({"permintaan": "Proses klaim KLM-001"}, cfg("b"))
    assert "__interrupt__" in s
    payload = s["__interrupt__"][0].value
    assert payload["claim_id"] == "KLM-001" and payload["total_disetujui"] == "Rp1.020.000"
    assert g.get_state(cfg("b")).next == ("persetujuan",)
    assert tools.baca_ledger() == {}, "belum boleh ada uang keluar sebelum disetujui"

    s = g.invoke(Command(resume={"aksi": "setujui", "catatan": "ok"}), cfg("b"))
    assert s["status_akhir"] == "dibayar" and s["persetujuan"]["aksi"] == "setujui"
    assert len(tools.baca_ledger()) == 1


def test_resume_string_tolak():
    g = _g()
    g.invoke({"permintaan": "Proses KLM-003"}, cfg("c"))
    s = g.invoke(Command(resume="tolak"), cfg("c"))
    assert s["status_akhir"] == "ditolak_atasan" and tools.baca_ledger() == {}


def test_revisi_kembali_ke_penulis_lalu_berhenti_lagi():
    g = _g()
    g.invoke({"permintaan": "Proses KLM-001"}, cfg("d"))
    s = g.invoke(Command(resume={"aksi": "revisi", "catatan": "sebut nama hotel"}), cfg("d"))
    assert "__interrupt__" in s, "setelah revisi, memo baru harus disetujui lagi"
    assert s["persetujuan"]["catatan"] == "sebut nama hotel"
    assert sum(b.startswith("tulis_memo") for b in s["log"]) >= 3


def test_injeksi_tidak_mengubah_keputusan():
    s = _g().invoke({"permintaan": "Proses KLM-004"}, cfg("e"))
    p = s["__interrupt__"][0].value
    assert p["keputusan"] == "disetujui sebagian" and p["total_disetujui"] == "Rp1.030.000"
    assert p["peringatan"] and "APPROVED" not in p["memo"]


def test_tolak_otomatis_tanpa_atasan():
    s = _g().invoke({"permintaan": "Proses KLM-005"}, cfg("f"))
    assert s["status_akhir"] == "ditolak_otomatis" and "__interrupt__" not in s


def test_resume_tanpa_checkpointer_gagal():
    g = build_graph()
    assert "__interrupt__" in g.invoke({"permintaan": "Proses KLM-001"}, cfg("g"))
    with pytest.raises(RuntimeError, match="checkpointer"):
        g.invoke(Command(resume="setujui"), cfg("g"))


def test_app_py_berhenti_lalu_dilanjutkan_dari_proses_baru():
    """`uv run app.py` berhenti di interrupt; `--lanjut setujui` dari proses lain melanjutkannya."""
    import os
    import subprocess
    import sys

    from conftest import KODE

    def app(*args):
        return subprocess.run([sys.executable, "app.py", *args], cwd=KODE, env=dict(os.environ),
                              capture_output=True, text=True, timeout=120)

    r = app("Proses klaim KLM-001", "--thread", "hitl-12")
    assert r.returncode == 0 and "berhenti di persetujuan" in r.stdout, r.stdout + r.stderr
    r = app("--thread", "hitl-12", "--lanjut", "setujui")
    assert r.returncode == 0 and '"dibayar"' in r.stdout, r.stdout + r.stderr
