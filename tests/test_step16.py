"""Step 16: orchestration patterns supervisor, handoff (Command goto), planner-executor."""

import json

from app.patterns import merge_dicts, handoff_graph, planner_graph, supervisor_graph


def test_reducer_custom():
    assert merge_dicts({"a": 1}, {"b": 2}) == {"a": 1, "b": 2}


def test_supervisor_memanggil_semua_worker_lalu_selesai():
    s = supervisor_graph.invoke({"claim_id": "CLM-003"})
    assert set(s["findings"]) == {"check_receipts", "check_budget", "write_summary"}
    assert s["log"].count("supervisor -> __end__") == 1
    assert sum(b.startswith("supervisor") for b in s["log"]) == 4
    assert "1 items without receipt" in s["findings"]["check_receipts"]


def test_supervisor_tergambar_lewat_anotasi_command():
    edges = {(e.source, e.target) for e in supervisor_graph.get_graph().edges}
    assert {("supervisor", "check_receipts"), ("supervisor", "check_budget")} <= edges


def test_handoff():
    s = handoff_graph.invoke({"message": "when will my claim be paid?"})
    assert s["log"] == ["receptionist -> finance_agent", "finance_agent done"]
    s = handoff_graph.invoke({"message": "did my claim hit the budget limit?"})
    assert s["log"][0] == "receptionist -> hr_agent" and s["answer"].startswith("HR")


def test_planner_executor():
    s = planner_graph.invoke({"claim_id": "CLM-001"})
    assert s["plan"] == [] and s["data"]["total_approved"] == 1020000
    assert [b for b in s["log"] if b.startswith("executor")] == [
        "executor: get_claim", "executor: check_all_items", "executor: compute_total"]


def test_langgraph_json_berisi_semua_graph(code_dir):
    graphs = json.loads((code_dir / "langgraph.json").read_text())["graphs"]
    assert set(graphs) == {"claim", "pattern_supervisor", "pattern_handoff", "pattern_planner"}
