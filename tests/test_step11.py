"""Step 11: map-reduce with Send, input_schema, a reducer that collects results."""

import time

from helpers import superstep_dari, task_per_superstep
from langgraph.types import Send

from app import tools
from app.graph import build_graph
from app.nodes import fan_out_items, check_item


def test_fan_out_satu_send_per_item():
    s = {"claim_id": "CLM-003", "claim": tools.get_claim("CLM-003")}
    sends = fan_out_items(s)
    assert len(sends) == 3 and all(isinstance(x, Send) and x.node == "check_item" for x in sends)
    assert sends[0].arg == {"claim_id": "CLM-003", "item": s["claim"]["items"][0]}


def test_periksa_item_menerima_itemtask():
    item = tools.get_claim("CLM-001")["items"][1]
    out = check_item({"claim_id": "CLM-001", "item": item})
    assert out["item_results"][0]["status"] == "capped" and len(out["item_results"]) == 1


def test_semua_periksa_item_dalam_satu_superstep():
    step = task_per_superstep(build_graph(), {"request": "Proses klaim CLM-003"})
    s = superstep_dari(step, "check_item")
    assert step[s].count("check_item") == 3 and "check_employee" in step[s]


def test_reducer_mengumpulkan_hasil():
    s = build_graph().invoke({"request": "Proses klaim CLM-003"})
    assert sorted(h["item_id"] for h in s["item_results"]) == ["CLM-003-1", "CLM-003-2", "CLM-003-3"]
    assert [h["item_id"] for h in s["decision"]["breakdown"]] == ["CLM-003-1", "CLM-003-2", "CLM-003-3"]


def test_benar_benar_paralel(monkeypatch):
    original = tools.check_item

    def slow(item, policy):
        time.sleep(0.3)
        return original(item, policy)

    monkeypatch.setattr(tools, "check_item", slow)
    t0 = time.perf_counter()
    build_graph().invoke({"request": "Proses klaim CLM-003"})
    assert time.perf_counter() - t0 < 0.8, "3 items x 0.3 s must finish in ~0.3 s when parallel"
