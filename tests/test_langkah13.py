"""Langkah 13: checkpointer, thread, riwayat, replay, fork."""

from conftest import cfg
from langgraph.checkpoint.memory import InMemorySaver

from app.graph import build_graph, buka_sqlite


def test_get_state_dan_riwayat():
    g = build_graph(InMemorySaver())
    g.invoke({"permintaan": "Proses klaim KLM-002"}, cfg("a"))
    snap = g.get_state(cfg("a"))
    assert snap.next == () and snap.values["claim_id"] == "KLM-002"
    riwayat = list(g.get_state_history(cfg("a")))
    assert len(riwayat) >= 9 and riwayat[0].next == () and riwayat[-1].metadata["source"] == "input"
    assert [s.metadata["step"] for s in riwayat] == sorted((s.metadata["step"] for s in riwayat), reverse=True)


def test_thread_terpisah():
    g = build_graph(InMemorySaver())
    g.invoke({"permintaan": "Proses klaim KLM-002"}, cfg("satu"))
    g.invoke({"permintaan": "Proses klaim KLM-003"}, cfg("dua"))
    assert g.get_state(cfg("satu")).values["claim_id"] == "KLM-002"
    assert g.get_state(cfg("dua")).values["claim_id"] == "KLM-003"
    assert g.get_state(cfg("tiga")).values == {}


def test_sqlite_bertahan_lintas_instance(tmp_path):
    db = str(tmp_path / "cp.db")
    build_graph(buka_sqlite(db)).invoke({"permintaan": "Proses klaim KLM-002"}, cfg("x"))
    g2 = build_graph(buka_sqlite(db))            # "proses baru": objek graph dan koneksi baru
    v = g2.get_state(cfg("x")).values
    assert v["keputusan"]["aksi"] == "setujui_penuh" and v["penilaian"]["lolos"] is True


def test_fork_dari_checkpoint_lama():
    g = build_graph(InMemorySaver())
    g.invoke({"permintaan": "Proses klaim KLM-002"}, cfg("f"))
    n_awal = len(list(g.get_state_history(cfg("f"))))
    lama = next(s for s in g.get_state_history(cfg("f")) if s.next == ("muat_klaim",))
    cfg_baru = g.update_state(lama.config, {"claim_id": "KLM-003"})
    hasil = g.invoke(None, cfg_baru)
    assert hasil["keputusan"]["total_disetujui"] == 2100000
    assert len(list(g.get_state_history(cfg("f")))) > n_awal, "fork menambah checkpoint, riwayat lama tetap ada"


def test_app_py_chat_thread_per_permintaan():
    """Mode chat: setiap permintaan thread sendiri, jadi dua klaim berbeda tidak saling tercampur."""
    from conftest import app_py

    out = app_py("--chat", "--thread", "c13", masukan="Proses klaim KLM-002\nProses klaim KLM-005\n").stdout
    assert "thread: c13-1" in out and "thread: c13-2" in out, out
    assert "graph berhenti" not in out, out
    assert "KLM-005" in app_py("--thread", "c13-2", "--status").stdout
