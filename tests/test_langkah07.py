"""Langkah 7: lapisan LLM (mock/live), structured output, validasi output LLM."""

import pytest

from app import llm
from app.nodes import router, rute_aturan
from app.state import RuteDecision


def test_mode_mock_memakai_fallback():
    assert llm.is_live() is False
    hasil = llm.structured(RuteDecision, "sys", "user", fallback=lambda: RuteDecision(rute="kebijakan", alasan="x"))
    assert hasil.rute == "kebijakan"
    assert llm.teks("sys", "user", fallback=lambda: "halo") == "halo"


def test_mode_live_tanpa_key_gagal_jelas(monkeypatch):
    monkeypatch.setenv("LLM_MODE", "live")
    monkeypatch.setenv("LLM_API_KEY", "")
    with pytest.raises(RuntimeError, match="LLM_API_KEY"):
        llm.teks("sys", "user", fallback=lambda: "tidak dipakai")


def test_rute_aturan_mengembalikan_pydantic():
    d = rute_aturan("Tolong cek KLM-003")
    assert isinstance(d, RuteDecision) and (d.rute, d.claim_id) == ("klaim", "KLM-003")


def test_router_memvalidasi_karangan_llm(monkeypatch):
    """LLM 'mengarang' nomor klaim yang tidak ada -> kode mengarahkannya ke klarifikasi."""
    palsu = RuteDecision(rute="klaim", claim_id="klm-777", alasan="LLM yakin sekali")
    monkeypatch.setattr(llm, "structured", lambda *a, **k: palsu)
    out = router({"permintaan": "cek klaim saya dong"})
    assert out["rute"] == "klarifikasi" and out["claim_id"] == "KLM-777"


def test_router_klaim_tanpa_nomor_dari_llm(monkeypatch):
    monkeypatch.setattr(llm, "structured", lambda *a, **k: RuteDecision(rute="klaim", alasan="?"))
    assert router({"permintaan": "proses klaim saya"})["rute"] == "klarifikasi"
