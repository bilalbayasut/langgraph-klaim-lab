"""Tahap 12: pola orkestrasi supervisor, handoff, planner-executor."""

from app.pola import handoff_graph, planner_graph, supervisor_graph


def test_supervisor_memanggil_semua_worker_lalu_selesai():
    s = supervisor_graph.invoke({"claim_id": "KLM-003"})
    assert set(s["temuan"]) == {"cek_struk", "cek_anggaran", "tulis_ringkasan"}
    assert s["log"].count("supervisor -> __end__") == 1
    assert sum(l.startswith("supervisor") for l in s["log"]) == 4, "supervisor dipanggil sebelum tiap worker + sekali lagi untuk selesai"
    assert "1 item tanpa struk" in s["temuan"]["cek_struk"]


def test_handoff():
    s = handoff_graph.invoke({"pesan": "kapan klaim saya dibayar?"})
    assert s["log"] == ["resepsionis -> agen_keuangan", "agen_keuangan selesai"]
    s = handoff_graph.invoke({"pesan": "klaim saya kena batas anggaran?"})
    assert s["log"][0] == "resepsionis -> agen_hr" and s["jawaban"].startswith("HR")


def test_planner_executor():
    s = planner_graph.invoke({"claim_id": "KLM-001"})
    assert s["rencana"] == [] and s["data"]["total_disetujui"] == 1020000
    assert [l for l in s["log"] if l.startswith("executor")] == [
        "executor: ambil_klaim", "executor: periksa_semua_item", "executor: hitung_total"]
