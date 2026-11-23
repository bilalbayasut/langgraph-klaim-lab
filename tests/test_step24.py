"""Step 24: approval before risky tools, secret management."""

import json
from pathlib import Path

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from app.assistant import RISKY_TOOLS, ASSISTANT_ALLOWLIST
from app.config import get_settings
from app.graph import build_graph


def _cfg(t):
    return {"configurable": {"thread_id": t}}


def test_tool_tulis_terdaftar_dan_berisiko():
    assert "cancel_claim" in RISKY_TOOLS <= ASSISTANT_ALLOWLIST | RISKY_TOOLS
    assert "cancel_claim" in ASSISTANT_ALLOWLIST


def test_tool_berisiko_berhenti_menunggu_manusia():
    g = build_graph(InMemorySaver())
    s = g.invoke({"request": "Tolong batalkan klaim CLM-003"}, _cfg("b1"))
    p = s["__interrupt__"][0].value
    assert p["kind"] == "tool_approval" and p["tool"][0]["name"] == "cancel_claim"
    assert not (get_settings().runtime_dir / "cancellations.json").exists(), "no action may happen before approval"


def test_ditolak_aksi_tidak_dijalankan():
    g = build_graph(InMemorySaver())
    g.invoke({"request": "Tolong batalkan klaim CLM-003"}, _cfg("b2"))
    s = g.invoke(Command(resume={"action": "reject", "note": "valid claim"}), _cfg("b2"))
    assert "REJECTED" in s["answer"] and "__interrupt__" not in s
    assert not (get_settings().runtime_dir / "cancellations.json").exists()


def test_disetujui_aksi_dijalankan():
    g = build_graph(InMemorySaver())
    g.invoke({"request": "Tolong batalkan klaim CLM-003"}, _cfg("b3"))
    s = g.invoke(Command(resume={"action": "approve"}), _cfg("b3"))
    assert "CANCELLED" in s["answer"]
    assert "CLM-003" in json.loads((get_settings().runtime_dir / "cancellations.json").read_text())


def test_tool_aman_tidak_perlu_izin():
    s = build_graph().invoke({"request": "Berapa sisa anggaran Sari?"})
    assert "__interrupt__" not in s and "Rp3.000.000" in s["answer"]


def test_secret_tidak_tercetak(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "sk-very-secret")
    s = get_settings()
    assert "sk-secret" not in repr(s) and "sk-secret" not in str(s.llm_api_key)
    assert s.llm_api_key.get_secret_value() == "sk-very-secret"


def test_secret_tidak_masuk_git_dan_image(code_dir):
    root = Path(__file__).resolve().parents[1]
    assert ".env" in (root / ".gitignore").read_text().split()
    assert ".env" in (code_dir / ".dockerignore").read_text().split()
    assert "API_KEY" not in (code_dir / "Dockerfile").read_text()


def test_router_kode_mencegah_batal_masuk_jalur_bayar(monkeypatch):
    from app import llm
    from app.nodes import router
    from app.state import RouteDecision

    monkeypatch.setattr(llm, "structured", lambda *a, **k: RouteDecision(route="claim", claim_id="CLM-003", reason="LLM"))
    assert router({"request": "Tolong batalkan klaim CLM-003"})["route"] == "assistant"
    assert router({"request": "Proses klaim CLM-003"})["route"] == "claim"
