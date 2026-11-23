"""Step 22: confidential data (minimization, redaction, audit)."""

import json

from langgraph.checkpoint.memory import InMemorySaver

from app.graph import build_graph
from app.tracing import TraceRecorder, _short, trace_path
from app.nodes import check_employee
from app.privacy import redact, redact_data, strip_secrets
from app import tools


def test_data_sumber_memang_berisi_rahasia():
    p = tools.get_employee_profile("EMP-02")
    assert {"national_id", "bank_account", "email"} <= set(p)


def test_minimasi_di_cek_karyawan():
    out = check_employee({"claim": tools.get_claim("CLM-002")})
    assert out["profile"]["remaining_budget"] == 3000000
    assert not {"national_id", "bank_account", "email"} & set(out["profile"])
    assert strip_secrets({"name": "x", "national_id": "1"}) == {"name": "x"}


def test_redaksi():
    text = redact("acct 0123456782, NIK 3174024506920002, sari@example.co.id, total Rp1.020.000")
    assert text == "acct [BANK_ACCOUNT], NIK [NATIONAL_ID], [EMAIL], total Rp1.020.000"
    assert redact_data({"national_id": "123", "x": ["0123456782"]}) == {"national_id": "***", "x": ["[BANK_ACCOUNT]"]}
    assert "3174024506920002" not in _short({"profile": {"national_id": "3174024506920002"}})


def test_state_dan_jejak_bersih():
    g = build_graph(InMemorySaver())
    cfg = {"configurable": {"thread_id": "p22"}, "callbacks": [TraceRecorder(trace_path("p22"))]}
    g.invoke({"request": "Proses klaim CLM-002"}, cfg)
    state = json.dumps(g.get_state(cfg).values, default=str)
    assert "3174024506920002" not in state and "0123456782" not in state
    assert "3174024506920002" not in trace_path("p22").read_text()


def test_audit_thread_bersih(capsys):
    import subprocess, sys, os
    from conftest import CODE_DIR

    env = dict(os.environ)
    subprocess.run([sys.executable, "app.py", "Proses klaim CLM-002", "--thread", "aud"], cwd=CODE_DIR, env=env,
                   capture_output=True, check=True)
    from app.privacy import audit
    assert audit("aud") == []


def test_app_py_audit():
    from conftest import app_py

    app_py("Proses klaim CLM-002", "--thread", "aud22")
    assert "no secret data" in app_py("--audit", "aud22").stdout
