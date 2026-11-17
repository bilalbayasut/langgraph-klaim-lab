"""Konfigurasi test.

Default: test menguji kode KAMU di ./app
KUNCI=1 uv run pytest  -> menguji kunci jawaban di ./_kunci/app (untuk membandingkan)
"""

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
KODE = ROOT / "_kunci" if os.getenv("KUNCI") == "1" else ROOT
sys.path.insert(0, str(KODE))


@pytest.fixture(autouse=True)
def env_latihan(monkeypatch, tmp_path):
    """Setiap test: mode mock, runtime di folder sementara, tanpa simulasi gangguan."""
    monkeypatch.setenv("LLM_MODE", "mock")
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
def kode_dir() -> Path:
    """Folder yang berisi package app yang sedang dites (untuk test subprocess)."""
    return KODE
