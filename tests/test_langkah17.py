"""Langkah 17: stream_mode updates, values, custom, gabungan."""

from conftest import cfg
from langgraph.checkpoint.memory import InMemorySaver

from app.graph import build_graph
from app.pantau import pantau


def test_stream_updates_urutan_node():
    g = build_graph(InMemorySaver())
    urutan = [n for chunk in g.stream({"permintaan": "Proses KLM-002"}, cfg("s1"), stream_mode="updates") for n in chunk]
    assert urutan[:2] == ["router", "muat_klaim"]
    assert urutan.count("periksa_item") == 2
    assert urutan[-2:] == ["bayar", "selesai"]
    assert urutan.count("tulis_memo") == 2, "draf pertama mock ditolak evaluator"


def test_stream_custom_dari_node_bayar():
    g = build_graph(InMemorySaver())
    progres = [c["progres"] for c in g.stream({"permintaan": "Proses KLM-002"}, cfg("s2"), stream_mode="custom")]
    assert len(progres) >= 2 and "mentransfer Rp180.000" in progres[0]


def test_stream_values_berisi_state_lengkap():
    g = build_graph(InMemorySaver())
    semua = list(g.stream({"permintaan": "Proses KLM-002"}, cfg("s3"), stream_mode="values"))
    assert semua[0]["permintaan"] == "Proses KLM-002" and semua[-1]["status_akhir"] == "dibayar"


def test_stream_gabungan_dan_interrupt():
    g = build_graph(InMemorySaver())
    mode_terlihat, ada_interrupt = set(), False
    for mode, chunk in g.stream({"permintaan": "Proses KLM-001"}, cfg("s4"), stream_mode=["updates", "values"]):
        mode_terlihat.add(mode)
        ada_interrupt |= mode == "updates" and "__interrupt__" in chunk
    assert mode_terlihat == {"updates", "values"} and ada_interrupt


def test_pantau(capsys):
    baris = pantau("Proses klaim KLM-002")
    assert any(b.startswith("✔ router") for b in baris)
    assert any("mentransfer" in b for b in baris)
    assert "selesai" in capsys.readouterr().out


def test_app_py_pantau():
    from conftest import app_py

    out = app_py("Proses klaim KLM-002", "--pantau").stdout
    assert "✔ router" in out and "superstep" not in out
