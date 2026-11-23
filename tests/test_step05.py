"""Step 5: LLM layer (mock/live), structured output, validating LLM output."""

import pytest

from app import llm
from app.nodes import router, rule_based_route
from app.state import RouteDecision


def test_mode_mock_memakai_fallback():
    assert llm.is_live() is False
    result = llm.structured(RouteDecision, "sys", "user", fallback=lambda: RouteDecision(route="policy", reason="x"))
    assert result.route == "policy"
    assert llm.text("sys", "user", fallback=lambda: "halo") == "halo"


def test_mode_live_tanpa_key_gagal_jelas(monkeypatch):
    monkeypatch.setenv("LLM_MODE", "live")
    monkeypatch.setenv("LLM_API_KEY", "")
    with pytest.raises(RuntimeError, match="LLM_API_KEY"):
        llm.text("sys", "user", fallback=lambda: "not used")


def test_rute_aturan_mengembalikan_pydantic():
    d = rule_based_route("Tolong cek CLM-003")
    assert isinstance(d, RouteDecision) and (d.route, d.claim_id) == ("claim", "CLM-003")


def test_router_memvalidasi_karangan_llm(monkeypatch):
    """The LLM 'makes up' a claim number that does not exist -> the code sends it to clarify."""
    fake = RouteDecision(route="claim", claim_id="clm-777", reason="LLM is very sure")
    monkeypatch.setattr(llm, "structured", lambda *a, **k: fake)
    out = router({"request": "cek klaim saya dong"})
    assert out["route"] == "clarify" and out["claim_id"] == "CLM-777"


def test_router_klaim_tanpa_nomor_dari_llm(monkeypatch):
    monkeypatch.setattr(llm, "structured", lambda *a, **k: RouteDecision(route="claim", reason="?"))
    assert router({"request": "proses klaim saya"})["route"] == "clarify"
