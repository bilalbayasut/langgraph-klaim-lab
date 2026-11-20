"""Langkah 24: approval sebelum tool berisiko, secret management."""

import json
from pathlib import Path

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from app.asisten import ALAT_BERISIKO, IZIN_ASISTEN
from app.config import get_settings
from app.graph import build_graph


def _cfg(t):
    return {"configurable": {"thread_id": t}}


def test_tool_tulis_terdaftar_dan_berisiko():
    assert "batalkan_klaim" in ALAT_BERISIKO <= IZIN_ASISTEN | ALAT_BERISIKO
    assert "batalkan_klaim" in IZIN_ASISTEN


def test_tool_berisiko_berhenti_menunggu_manusia():
    g = build_graph(InMemorySaver())
    s = g.invoke({"permintaan": "Tolong batalkan klaim KLM-003"}, _cfg("b1"))
    p = s["__interrupt__"][0].value
    assert p["jenis"] == "izin_tool" and p["tool"][0]["nama"] == "batalkan_klaim"
    assert not (get_settings().runtime_dir / "pembatalan.json").exists(), "belum boleh ada aksi sebelum disetujui"


def test_ditolak_aksi_tidak_dijalankan():
    g = build_graph(InMemorySaver())
    g.invoke({"permintaan": "Tolong batalkan klaim KLM-003"}, _cfg("b2"))
    s = g.invoke(Command(resume={"aksi": "tolak", "catatan": "klaim valid"}), _cfg("b2"))
    assert "DITOLAK" in s["jawaban"] and "__interrupt__" not in s
    assert not (get_settings().runtime_dir / "pembatalan.json").exists()


def test_disetujui_aksi_dijalankan():
    g = build_graph(InMemorySaver())
    g.invoke({"permintaan": "Tolong batalkan klaim KLM-003"}, _cfg("b3"))
    s = g.invoke(Command(resume={"aksi": "setujui"}), _cfg("b3"))
    assert "DIBATALKAN" in s["jawaban"]
    assert "KLM-003" in json.loads((get_settings().runtime_dir / "pembatalan.json").read_text())


def test_tool_aman_tidak_perlu_izin():
    s = build_graph().invoke({"permintaan": "Berapa sisa anggaran Sari?"})
    assert "__interrupt__" not in s and "Rp3.000.000" in s["jawaban"]


def test_secret_tidak_tercetak(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "sk-rahasia-sekali")
    s = get_settings()
    assert "sk-rahasia" not in repr(s) and "sk-rahasia" not in str(s.llm_api_key)
    assert s.llm_api_key.get_secret_value() == "sk-rahasia-sekali"


def test_secret_tidak_masuk_git_dan_image(kode):
    root = Path(__file__).resolve().parents[1]
    assert ".env" in (root / ".gitignore").read_text().split()
    assert ".env" in (kode / ".dockerignore").read_text().split()
    assert "API_KEY" not in (kode / "Dockerfile").read_text()


def test_router_kode_mencegah_batal_masuk_jalur_bayar(monkeypatch):
    from app import llm
    from app.nodes import router
    from app.state import RuteDecision

    monkeypatch.setattr(llm, "structured", lambda *a, **k: RuteDecision(rute="klaim", claim_id="KLM-003", alasan="LLM"))
    assert router({"permintaan": "Tolong batalkan klaim KLM-003"})["rute"] == "asisten"
    assert router({"permintaan": "Proses klaim KLM-003"})["rute"] == "klaim"
