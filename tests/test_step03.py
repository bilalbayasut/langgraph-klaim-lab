"""Step 3: business rules in code, operator.add reducer for the log."""

from app import tools
from app.graph import build_graph


def _item(category, amount, struk=True):
    return {"item_id": "X-1", "category": category, "amount": amount, "has_receipt": struk, "description": ""}


def test_periksa_item_semua_status():
    kb = tools.get_policy()
    assert tools.check_item(_item("meals", 100000), kb)["status"] == "ok"
    h = tools.check_item(_item("meals", 180000), kb)
    assert (h["status"], h["approved"]) == ("capped", 150000)
    assert tools.check_item(_item("hotel", 500000, struk=False), kb)["status"] == "rejected"
    assert tools.check_item(_item("transport", 100000, struk=False), kb)["status"] == "ok"
    assert tools.check_item(_item("entertainment", 50000), kb)["status"] == "rejected"


def test_keputusan_klm_001():
    s = build_graph().invoke({"request": "Process claim CLM-001"})
    assert len(s["item_results"]) == 3
    k = s["decision"]
    assert (k["action"], k["total_submitted"], k["total_approved"], k["needs_approval"]) == (
        "approve_partial", 1050000, 1020000, True)
    assert [h["item_id"] for h in k["breakdown"]] == ["CLM-001-1", "CLM-001-2", "CLM-001-3"]


def test_keputusan_klaim_lain():
    g = build_graph()
    k = g.invoke({"request": "Process CLM-002"})["decision"]
    assert (k["action"], k["total_approved"], k["needs_approval"]) == ("approve_full", 180000, False)
    k = g.invoke({"request": "Process CLM-003"})["decision"]
    assert (k["action"], k["total_approved"]) == ("approve_partial", 2100000)


def test_log_bertambah_dengan_reducer():
    log = build_graph().invoke({"request": "Process claim CLM-001"})["log"]
    for prefix in ("router", "load_claim", "decide"):
        assert any(lines.startswith(prefix) for lines in log), f"log must contain a line from {prefix}: {log}"
