"""Langkah 16: pola orkestrasi supervisor, handoff (Command goto), planner-executor."""

import json

from app.pola import gabung_dict, handoff_graph, planner_graph, supervisor_graph


def test_reducer_custom():
    assert gabung_dict({"a": 1}, {"b": 2}) == {"a": 1, "b": 2}


def test_supervisor_memanggil_semua_worker_lalu_selesai():
    s = supervisor_graph.invoke({"claim_id": "KLM-003"})
    assert set(s["temuan"]) == {"cek_struk", "cek_anggaran", "tulis_ringkasan"}
    assert s["log"].count("supervisor -> __end__") == 1
    assert sum(b.startswith("supervisor") for b in s["log"]) == 4
    assert "1 item tanpa struk" in s["temuan"]["cek_struk"]


def test_supervisor_tergambar_lewat_anotasi_command():
    edges = {(e.source, e.target) for e in supervisor_graph.get_graph().edges}
    assert {("supervisor", "cek_struk"), ("supervisor", "cek_anggaran")} <= edges


def test_handoff():
    s = handoff_graph.invoke({"pesan": "kapan klaim saya dibayar?"})
    assert s["log"] == ["resepsionis -> agen_keuangan", "agen_keuangan selesai"]
    s = handoff_graph.invoke({"pesan": "klaim saya kena batas anggaran?"})
    assert s["log"][0] == "resepsionis -> agen_hr" and s["jawaban"].startswith("HR")


def test_planner_executor():
    s = planner_graph.invoke({"claim_id": "KLM-001"})
    assert s["rencana"] == [] and s["data"]["total_disetujui"] == 1020000
    assert [b for b in s["log"] if b.startswith("executor")] == [
        "executor: ambil_klaim", "executor: periksa_semua_item", "executor: hitung_total"]


def test_langgraph_json_berisi_semua_graph(kode):
    graphs = json.loads((kode / "langgraph.json").read_text())["graphs"]
    assert set(graphs) == {"klaim", "pola_supervisor", "pola_handoff", "pola_planner"}
