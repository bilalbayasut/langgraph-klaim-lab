"""Step 12: memo by the LLM, evaluator-optimizer loop with an iteration limit."""

from app import tools
from app.graph import build_graph
from app.nodes import check_memo_rules, review_memo, route_after_review, write_memo


def _base_state(cid="CLM-001"):
    k = tools.get_claim(cid)
    breakdown = [tools.check_item(it, tools.get_policy()) for it in k["items"]]
    decision = {"action": "approve_partial", "reason": "some items were capped", "total_submitted": 1050000,
                 "total_approved": 1020000, "needs_approval": True, "breakdown": breakdown}
    return {"claim_id": cid, "claim": k, "profile": tools.get_employee_profile(k["employee_id"]), "decision": decision}


def test_cek_memo_aturan():
    k = _base_state()["decision"]
    good = "Claim CLM-001 partially approved. Total approved: Rp1.020.000."
    assert check_memo_rules(good, "CLM-001", k) == []
    assert len(check_memo_rules("Claim approved.", "CLM-001", k)) == 3


def test_draf_pertama_mock_ditolak_draf_kedua_lolos():
    s = _base_state()
    d1 = write_memo(s)
    assert d1["draft_count"] == 1 and "Rp1.020.000" not in d1["memo_draft"]
    p = review_memo({**s, **d1})["review"]
    assert p["passed"] is False and any("total" in m for m in p["issues"])
    d2 = write_memo({**s, **d1, "review": p})
    assert d2["draft_count"] == 2 and "Rp1.020.000" in d2["memo_draft"]
    assert review_memo({**s, **d2})["review"]["passed"] is True


def test_rute_setelah_nilai():
    k = _base_state()["decision"]
    failures, lolos = {"passed": False, "issues": ["x"]}, {"passed": True, "issues": []}
    assert route_after_review({"review": failures, "draft_count": 1, "decision": k}) == "write_memo"
    assert route_after_review({"review": failures, "draft_count": 3, "decision": k}) != "write_memo", "quota used up"
    assert route_after_review({"review": lolos, "draft_count": 1, "decision": k}) != "write_memo"


def test_loop_di_graph():
    s = build_graph().invoke({"request": "Process claim CLM-002"})
    assert s["draft_count"] == 2 and s["review"]["passed"] is True
    assert sum(b.startswith("write_memo") for b in s["log"]) == 2


def test_tanpa_jatah_revisi(monkeypatch):
    monkeypatch.setenv("MAX_REVISIONS", "0")
    s = build_graph().invoke({"request": "Process claim CLM-002"})
    assert s["draft_count"] == 1 and s["review"]["passed"] is False


def test_loop_berhenti_di_batas(monkeypatch):
    import app.nodes as n

    monkeypatch.setattr(n, "check_memo_rules", lambda *a: ["always fails"])
    s = build_graph().invoke({"request": "Process claim CLM-002"})
    assert s["draft_count"] == 3, "1 draft + MAX_REVISIONS(2) revisions, then stop"
