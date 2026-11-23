"""Step 14: interrupt + Command(resume), side effects after approval."""

import pytest
from conftest import cfg
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from app import tools
from app.graph import build_graph


def _g():
    return build_graph(InMemorySaver())


def test_bayar_idempoten():
    a = tools.pay("CLM-X", 1000)
    b = tools.pay("CLM-X", 1000)
    assert (a["duplicate"], b["duplicate"]) == (False, True) and a["ref"] == b["ref"]
    assert len(tools.read_ledger()) == 1


def test_auto_approve_tanpa_manusia():
    g = _g()
    s = g.invoke({"request": "Process claim CLM-002"}, cfg("a"))
    assert s["final_status"] == "paid" and s["payment"]["amount"] == 180000
    assert g.get_state(cfg("a")).next == ()


def test_interrupt_lalu_setujui():
    g = _g()
    s = g.invoke({"request": "Process claim CLM-001"}, cfg("b"))
    assert "__interrupt__" in s
    payload = s["__interrupt__"][0].value
    assert payload["claim_id"] == "CLM-001" and payload["total_approved"] == "Rp1.020.000"
    assert g.get_state(cfg("b")).next == ("approval",)
    assert tools.read_ledger() == {}, "no money may go out before approval"

    s = g.invoke(Command(resume={"action": "approve", "note": "ok"}), cfg("b"))
    assert s["final_status"] == "paid" and s["approval"]["action"] == "approve"
    assert len(tools.read_ledger()) == 1


def test_resume_string_tolak():
    g = _g()
    g.invoke({"request": "Process CLM-003"}, cfg("c"))
    s = g.invoke(Command(resume="reject"), cfg("c"))
    assert s["final_status"] == "rejected_by_manager" and tools.read_ledger() == {}


def test_revisi_kembali_ke_penulis_lalu_berhenti_lagi():
    g = _g()
    g.invoke({"request": "Process CLM-001"}, cfg("d"))
    s = g.invoke(Command(resume={"action": "revise", "note": "mention the hotel name"}), cfg("d"))
    assert "__interrupt__" in s, "after a revision, the new memo must be approved again"
    assert s["approval"]["note"] == "mention the hotel name"
    assert sum(b.startswith("write_memo") for b in s["log"]) >= 3


def test_injeksi_tidak_mengubah_keputusan():
    s = _g().invoke({"request": "Process CLM-004"}, cfg("e"))
    p = s["__interrupt__"][0].value
    assert p["decision"] == "partially approved" and p["total_approved"] == "Rp1.030.000"
    assert "APPROVED" not in p["memo"]


def test_tolak_otomatis_tanpa_atasan():
    s = _g().invoke({"request": "Process CLM-005"}, cfg("f"))
    assert s["final_status"] == "auto_rejected" and "__interrupt__" not in s


def test_resume_tanpa_checkpointer_gagal():
    g = build_graph()
    assert "__interrupt__" in g.invoke({"request": "Process CLM-001"}, cfg("g"))
    with pytest.raises(RuntimeError, match="checkpointer"):
        g.invoke(Command(resume="approve"), cfg("g"))


def test_app_py_berhenti_lalu_dilanjutkan_dari_proses_baru():
    """`uv run app.py` stops at the interrupt; `--resume approve` from another process resumes it."""
    import os
    import subprocess
    import sys

    from conftest import CODE_DIR

    def app(*args):
        return subprocess.run([sys.executable, "app.py", *args], cwd=CODE_DIR, env=dict(os.environ),
                              capture_output=True, text=True, timeout=120)

    r = app("Process claim CLM-001", "--thread", "hitl-12")
    assert r.returncode == 0 and "stopped at approval" in r.stdout, r.stdout + r.stderr
    r = app("--thread", "hitl-12", "--resume", "approve")
    assert r.returncode == 0 and "\"paid\"" in r.stdout, r.stdout + r.stderr


def test_app_py_chat_menjawab_interrupt():
    """In chat mode the interrupt is asked right away; the answer 'approve' resumes the graph."""
    from conftest import app_py

    out = app_py("--chat", "--thread", "chat-14", graph_input="Process claim CLM-001\napprove\n").stdout
    assert "answer (approve / revise / reject)>" in out and "\"paid\"" in out, out
