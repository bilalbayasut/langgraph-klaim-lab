"""Langkah 6: function calling, ToolNode, tools_condition, rute asisten."""

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.asisten import _agen_mock, alat
from app.graph import build_graph
from app.nodes import rute_aturan, rute_setelah_router


def test_router_mengenali_pertanyaan_data():
    assert rute_aturan("Berapa sisa anggaran Sari?").rute == "asisten"
    assert rute_aturan("Apa status KLM-003?").rute == "asisten"
    assert rute_aturan("Proses klaim KLM-003").rute == "klaim"
    assert rute_aturan("Berapa batas biaya hotel per malam?").rute == "kebijakan"
    assert rute_setelah_router({"rute": "asisten"}) == "asisten"


def test_tool_punya_nama_deskripsi_dan_argumen():
    t = {t.name: t for t in alat()}
    assert {"profil_karyawan", "detail_klaim"} <= set(t)
    assert "sisa anggaran" in t["profil_karyawan"].description
    assert "nama" in t["profil_karyawan"].args


def test_mock_meminta_tool_lalu_menjawab():
    nama = {t.name for t in alat()}
    pesan = [HumanMessage(content="Berapa sisa anggaran Sari?")]
    ai = _agen_mock(pesan, nama)
    assert [tc["name"] for tc in ai.tool_calls] == ["profil_karyawan"]
    assert ai.tool_calls[0]["args"] == {"nama": "Sari"}
    pesan += [ai, ToolMessage(content="Sari sisa Rp3.000.000", tool_call_id=ai.tool_calls[0]["id"])]
    akhir = _agen_mock(pesan, nama)
    assert not akhir.tool_calls and "Rp3.000.000" in akhir.content


def test_loop_agent_di_graph():
    s = build_graph().invoke({"permintaan": "Berapa sisa anggaran Sari dan siapa atasannya?"})
    assert s["rute"] == "asisten" and s["status_akhir"] == "dijawab"
    assert "Rp3.000.000" in s["jawaban"] and "Tono" in s["jawaban"]
    jenis = [type(m).__name__ for m in s["messages"]]
    assert jenis == ["HumanMessage", "AIMessage", "ToolMessage", "AIMessage"]


def test_beberapa_tool_sekaligus():
    s = build_graph().invoke({"permintaan": "Apa detail KLM-003, dan berapa sisa anggaran Budi?"})
    dipanggil = [tc["name"] for m in s["messages"] if isinstance(m, AIMessage) for tc in m.tool_calls]
    assert sorted(dipanggil) == ["detail_klaim", "profil_karyawan"]
    assert "KLM-003" in s["jawaban"] and "Rp6.000.000" in s["jawaban"]


def test_jalur_klaim_tetap_workflow():
    s = build_graph().invoke({"permintaan": "Proses klaim KLM-002"})
    assert s["rute"] == "klaim" and not s.get("messages")      # jalur klaim tidak memakai LLM agent
