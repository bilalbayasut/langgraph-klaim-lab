"""Test configuration.

Tests import `app` from the folder pytest is run from:

    uv run pytest tests/test_step05.py                       -> tests YOUR code in ./app
    cd _solutions/step-05 && uv run pytest ../../tests/test_step05.py   -> tests the step 5 solution
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

CODE_DIR = Path.cwd()                      # folder containing app/ (and app.py, langgraph.json)
sys.path.insert(0, str(CODE_DIR))


@pytest.fixture(autouse=True)
def lab_env(monkeypatch, tmp_path):
    """Every test: mock mode, runtime (SQLite, ChromaDB, ledger) in a temporary folder, no failure simulation."""
    monkeypatch.setenv("LLM_MODE", "mock")
    monkeypatch.setenv("EMBEDDING", "hash")
    monkeypatch.setenv("MCP_HR_FINANCE_URL", "")             # stdio, unless a test sets a URL
    monkeypatch.setenv("RUNTIME_DIR", str(tmp_path))
    monkeypatch.setenv("HR_FAIL_TIMES", "0")
    monkeypatch.setenv("CRASH_AFTER_PAYMENT", "0")
    monkeypatch.setenv("MOCK_FIRST_DRAFT_INCOMPLETE", "1")
    monkeypatch.setenv("MAX_REVISIONS", "2")
    try:
        from app import tools

        tools.reset_hr()
    except (ImportError, AttributeError):
        pass
    yield


@pytest.fixture
def code_dir() -> Path:
    return CODE_DIR


def cfg(thread: str) -> dict:
    return {"configurable": {"thread_id": thread}}


def app_py(*args: str, graph_input: str | None = None) -> subprocess.CompletedProcess:
    """`uv run app.py ARGS` from the code folder, with the test env (mock, temporary runtime). `graph_input` = stdin."""
    r = subprocess.run([sys.executable, "app.py", *args], cwd=CODE_DIR, env=dict(os.environ), input=graph_input,
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stdout + r.stderr
    return r
