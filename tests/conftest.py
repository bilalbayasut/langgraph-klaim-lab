"""Konfigurasi test.

Default: test menguji kode KAMU di ./app
KUNCI=5 uv run cek 5      -> menguji kunci jawaban langkah 5 (_kunci/langkah-05/app)
KUNCI=akhir uv run cek    -> menguji kunci jawaban terakhir
"""

import pytest

from lab.kode import kode_dir, pasang_sys_path

KODE = pasang_sys_path()


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
def kode() -> object:
    return kode_dir()


def cfg(thread: str) -> dict:
    return {"configurable": {"thread_id": thread}}
