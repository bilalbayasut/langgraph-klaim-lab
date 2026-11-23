"""Step 13: checkpointer, thread, history, replay, fork."""

from conftest import cfg
from langgraph.checkpoint.memory import InMemorySaver

from app.graph import build_graph, open_sqlite


def test_get_state_dan_riwayat():
    g = build_graph(InMemorySaver())
    g.invoke({"request": "Proses klaim CLM-002"}, cfg("a"))
    snap = g.get_state(cfg("a"))
    assert snap.next == () and snap.values["claim_id"] == "CLM-002"
    history = list(g.get_state_history(cfg("a")))
    assert len(history) >= 9 and history[0].next == () and history[-1].metadata["source"] == "input"
    assert [s.metadata["step"] for s in history] == sorted((s.metadata["step"] for s in history), reverse=True)


def test_thread_terpisah():
    g = build_graph(InMemorySaver())
    g.invoke({"request": "Proses klaim CLM-002"}, cfg("one"))
    g.invoke({"request": "Proses klaim CLM-003"}, cfg("two"))
    assert g.get_state(cfg("one")).values["claim_id"] == "CLM-002"
    assert g.get_state(cfg("two")).values["claim_id"] == "CLM-003"
    assert g.get_state(cfg("three")).values == {}


def test_sqlite_bertahan_lintas_instance(tmp_path):
    db = str(tmp_path / "cp.db")
    build_graph(open_sqlite(db)).invoke({"request": "Proses klaim CLM-002"}, cfg("x"))
    g2 = build_graph(open_sqlite(db))            # "new process": new graph object and new connection
    v = g2.get_state(cfg("x")).values
    assert v["decision"]["action"] == "approve_full" and v["review"]["passed"] is True


def test_fork_dari_checkpoint_lama():
    g = build_graph(InMemorySaver())
    g.invoke({"request": "Proses klaim CLM-002"}, cfg("f"))
    n_before = len(list(g.get_state_history(cfg("f"))))
    old = next(s for s in g.get_state_history(cfg("f")) if s.next == ("load_claim",))
    new_cfg = g.update_state(old.config, {"claim_id": "CLM-003"})
    result = g.invoke(None, new_cfg)
    assert result["decision"]["total_approved"] == 2100000
    assert len(list(g.get_state_history(cfg("f")))) > n_before, "fork adds a checkpoint, the old history is still there"


def test_app_py_chat_thread_per_permintaan():
    """Chat mode: every request gets its own thread, so two different claims do not get mixed up."""
    from conftest import app_py

    out = app_py("--chat", "--thread", "c13", graph_input="Proses klaim CLM-002\nProses klaim CLM-005\n").stdout
    assert "thread: c13-1" in out and "thread: c13-2" in out, out
    assert "graph stopped" not in out, out
    assert "CLM-005" in app_py("--thread", "c13-2", "--status").stdout
