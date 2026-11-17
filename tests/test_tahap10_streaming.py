"""Tahap 10: stream_mode updates, values, custom."""

from app.graph import build_graph


def test_stream_updates_urutan_node():
    g = build_graph()
    urutan = [n for chunk in g.stream({"permintaan": "Proses KLM-002"}, {"configurable": {"thread_id": "s1"}},
                                      stream_mode="updates") for n in chunk]
    assert urutan[:2] == ["router", "muat_klaim"]
    assert urutan.count("periksa_item") == 2
    assert urutan[-2:] == ["bayar", "selesai"]
    assert urutan.count("tulis_memo") == 2, "draf pertama mock ditolak evaluator"


def test_stream_custom_dari_node_bayar():
    g = build_graph()
    progres = [c["progres"] for c in g.stream({"permintaan": "Proses KLM-002"}, {"configurable": {"thread_id": "s2"}},
                                              stream_mode="custom")]
    assert len(progres) == 2 and "mentransfer Rp180.000" in progres[0]


def test_stream_gabungan_dan_interrupt():
    g = build_graph()
    mode_terlihat, interrupt = set(), False
    for mode, chunk in g.stream({"permintaan": "Proses KLM-001"}, {"configurable": {"thread_id": "s3"}},
                                stream_mode=["updates", "values"]):
        mode_terlihat.add(mode)
        interrupt |= mode == "updates" and "__interrupt__" in chunk
    assert mode_terlihat == {"updates", "values"} and interrupt
