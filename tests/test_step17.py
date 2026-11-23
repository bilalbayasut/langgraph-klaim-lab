"""Step 17: stream_mode updates, values, custom, combined."""

from conftest import cfg
from langgraph.checkpoint.memory import InMemorySaver

from app.graph import build_graph
from app.monitor import monitor


def test_stream_updates_urutan_node():
    g = build_graph(InMemorySaver())
    order = [n for chunk in g.stream({"request": "Process CLM-002"}, cfg("s1"), stream_mode="updates") for n in chunk]
    assert order[:2] == ["router", "load_claim"]
    assert order.count("check_item") == 2
    assert order[-2:] == ["pay", "finish"]
    assert order.count("write_memo") == 2, "the first mock draft is rejected by the evaluator"


def test_stream_custom_dari_node_bayar():
    g = build_graph(InMemorySaver())
    progress = [c["progress"] for c in g.stream({"request": "Process CLM-002"}, cfg("s2"), stream_mode="custom")]
    assert len(progress) >= 2 and "transferring Rp180.000" in progress[0]


def test_stream_values_berisi_state_lengkap():
    g = build_graph(InMemorySaver())
    show_all = list(g.stream({"request": "Process CLM-002"}, cfg("s3"), stream_mode="values"))
    assert show_all[0]["request"] == "Process CLM-002" and show_all[-1]["final_status"] == "paid"


def test_stream_gabungan_dan_interrupt():
    g = build_graph(InMemorySaver())
    modes_seen, has_interrupt = set(), False
    for mode, chunk in g.stream({"request": "Process CLM-001"}, cfg("s4"), stream_mode=["updates", "values"]):
        modes_seen.add(mode)
        has_interrupt |= mode == "updates" and "__interrupt__" in chunk
    assert modes_seen == {"updates", "values"} and has_interrupt


def test_pantau(capsys):
    lines = monitor("Process claim CLM-002")
    assert any(b.startswith("✔ router") for b in lines)
    assert any("transferring" in b for b in lines)
    assert "finish" in capsys.readouterr().out


def test_app_py_pantau():
    from conftest import app_py

    out = app_py("Process claim CLM-002", "--monitor").stdout
    assert "✔ router" in out and "superstep" not in out
