"""Step 15: RetryPolicy, pending writes, crash in the middle of a side effect, then resume."""

import json
import os
import subprocess
import sys

import pytest
from conftest import CODE_DIR, cfg
from langgraph.checkpoint.memory import InMemorySaver

from app import tools
from app.graph import HR_RETRY, build_graph


def test_retry_policy_terkonfigurasi():
    assert HR_RETRY.retry_on is tools.HRTimeoutError
    assert HR_RETRY.max_attempts >= 3


def test_api_hr_gagal_dua_kali_tetap_berhasil(monkeypatch):
    monkeypatch.setenv("HR_FAIL_TIMES", "2")
    tools.reset_hr()
    s = build_graph(InMemorySaver()).invoke({"request": "Process CLM-002"}, cfg("r1"))
    assert s["final_status"] == "paid"


def test_api_hr_terus_gagal_lalu_dilanjutkan(monkeypatch):
    monkeypatch.setenv("HR_FAIL_TIMES", "99")
    tools.reset_hr()
    g = build_graph(InMemorySaver())
    with pytest.raises(tools.HRTimeoutError):
        g.invoke({"request": "Process CLM-002"}, cfg("r2"))
    assert "check_employee" in g.get_state(cfg("r2")).next
    monkeypatch.setenv("HR_FAIL_TIMES", "0")           # "API recovered"
    assert g.invoke(None, cfg("r2"))["final_status"] == "paid"


def _app(*args, **extra_env):
    """Run `uv run app.py ...` as a separate process (like from the terminal)."""
    env = {**os.environ, **extra_env}
    return subprocess.run([sys.executable, "app.py", *args], cwd=CODE_DIR, env=env,
                          capture_output=True, text=True, timeout=120)


def test_crash_setelah_bayar_lalu_resume_tidak_bayar_ganda(tmp_path):
    r = _app("Process CLM-002", "--thread", "crash", CRASH_AFTER_PAYMENT="1")
    assert r.returncode == 1, f"the process must die in the middle of the pay node\n{r.stdout}\n{r.stderr}"
    ledger = json.loads((tmp_path / "payments.json").read_text())
    assert len(ledger) == 1, "the transfer already happened before the crash"

    r = _app("--thread", "crash", "--resume")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "duplicate=True" in r.stdout, "the pay node is retried, but the idempotency key prevents a second transfer"
    assert len(json.loads((tmp_path / "payments.json").read_text())) == 1


def test_interrupt_dan_resume_lintas_proses():
    r = _app("Process claim CLM-003", "--thread", "hitl")
    assert r.returncode == 0 and "stopped at approval" in r.stdout, r.stdout + r.stderr
    r = _app("--thread", "hitl", "--resume", "approve", "--note", "ok")
    assert r.returncode == 0 and "\"paid\"" in r.stdout, r.stdout + r.stderr
