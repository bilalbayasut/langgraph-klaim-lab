"""Langkah 18: tracing dengan callback (tracer lokal) dan konfigurasi LangSmith."""

import json

from app.graph import build_graph
from app.jejak import PencatatJejak, path_jejak, tampilkan


def _jejak(permintaan, thread):
    build_graph().invoke({"permintaan": permintaan}, {"callbacks": [PencatatJejak(path_jejak(thread))]})
    return [json.loads(b) for b in path_jejak(thread).read_text().splitlines()]


def test_satu_trace_berisi_node_dan_tool():
    baris = _jejak("Berapa sisa anggaran Sari, dan bolehkah klaim hotel tanpa struk?", "j1")
    graph = [b for b in baris if b["jenis"] == "graph"]
    assert len(graph) == 1 and graph[0]["parent"] is None
    node = [b["nama"] for b in baris if b["jenis"] == "node"]
    assert node == ["router", "asisten", "alat", "asisten"] or sorted(node) == sorted(["router", "asisten", "alat", "asisten"])
    tool = {b["nama"] for b in baris if b["jenis"] == "tool"}
    assert tool == {"profil_karyawan", "cari_kebijakan"}
    assert all(b["durasi_ms"] >= 0 for b in baris)


def test_span_node_mencatat_superstep_dan_keluaran():
    baris = _jejak("Proses klaim KLM-002", "j2")
    putuskan = next(b for b in baris if b["nama"] == "putuskan")
    assert putuskan["superstep"] == 4 and "setujui_penuh" in putuskan["keluaran"]
    paralel = [b for b in baris if b["jenis"] == "node" and b["superstep"] == 3]
    assert len(paralel) == 3


def test_tampilkan_pohon(capsys):
    _jejak("Berapa sisa anggaran Sari?", "j3")
    tampilkan("j3")
    keluar = capsys.readouterr().out
    assert keluar.startswith("graph") and "tool  profil_karyawan" in keluar


def test_env_langsmith_terdokumentasi(kode):
    from pathlib import Path

    contoh = (Path(__file__).resolve().parents[1] / ".env.example").read_text()
    assert "LANGSMITH_TRACING=false" in contoh and "LANGSMITH_API_KEY=" in contoh
