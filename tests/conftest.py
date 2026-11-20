"""Konfigurasi test.

Test mengimpor `app` dari folder tempat pytest dijalankan:

    uv run pytest tests/test_langkah05.py                       -> menguji kode KAMU di ./app
    cd _kunci/langkah-05 && uv run pytest ../../tests/test_langkah05.py   -> menguji kunci jawaban langkah 5
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

KODE = Path.cwd()                      # folder yang berisi app/ (dan app.py, langgraph.json)
sys.path.insert(0, str(KODE))


@pytest.fixture(autouse=True)
def env_latihan(monkeypatch, tmp_path):
    """Setiap test: mode mock, runtime (SQLite, ChromaDB, ledger) di folder sementara, tanpa simulasi gangguan."""
    monkeypatch.setenv("LLM_MODE", "mock")
    monkeypatch.setenv("EMBEDDING", "hash")
    monkeypatch.setenv("RUNTIME_DIR", str(tmp_path))
    monkeypatch.setenv("HR_GAGAL_N_KALI", "0")
    monkeypatch.setenv("CRASH_SETELAH_BAYAR", "0")
    monkeypatch.setenv("MOCK_DRAF_PERTAMA_KURANG", "1")
    monkeypatch.setenv("MAX_REVISI", "2")
    try:
        from app import tools

        tools.reset_hr()
    except (ImportError, AttributeError):
        pass
    yield


@pytest.fixture
def kode() -> Path:
    return KODE


def cfg(thread: str) -> dict:
    return {"configurable": {"thread_id": thread}}


def app_py(*args: str) -> subprocess.CompletedProcess:
    """`uv run app.py ARGS` dari folder kode, dengan env test (mock, runtime sementara)."""
    r = subprocess.run([sys.executable, "app.py", *args], cwd=KODE, env=dict(os.environ),
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stdout + r.stderr
    return r
