"""Tahap 4: lapisan LLM (mock/live), structured output, RAG mini."""

import pytest

from app import llm
from app.nodes import jawab_kebijakan, router
from app.state import RuteDecision


def test_mock_memakai_fallback():
    assert not llm.is_live()
    r = llm.structured(RuteDecision, "sys", "user", fallback=lambda: RuteDecision(rute="klarifikasi", alasan="fb"))
    assert r.alasan == "fb"
    assert llm.teks("sys", "user", fallback=lambda: "halo") == "halo"


def test_live_tanpa_key_gagal_jelas(monkeypatch):
    monkeypatch.setenv("LLM_MODE", "live")
    monkeypatch.setenv("LLM_API_KEY", "")
    assert llm.is_live()
    with pytest.raises(RuntimeError, match="LLM_API_KEY"):
        llm.chat_model()


def test_router_lewat_lapisan_llm(monkeypatch):
    dipanggil = {}

    def palsu(schema, system, user, fallback):
        dipanggil["user"] = user
        return RuteDecision(rute="klaim", claim_id="KLM-777", alasan="LLM mengarang nomor")

    monkeypatch.setattr(llm, "structured", palsu)
    out = router({"permintaan": "proses klaim saya"})
    assert dipanggil["user"] == "proses klaim saya"
    assert out["rute"] == "klarifikasi", "nomor klaim dari LLM harus divalidasi ke data"


def test_jawab_kebijakan():
    out = jawab_kebijakan({"permintaan": "Apakah hotel wajib struk?"})
    assert out["status_akhir"] == "dijawab"
    assert "KEB-02_bukti_struk" in out["sumber"]
    assert "struk" in out["jawaban"].lower()
