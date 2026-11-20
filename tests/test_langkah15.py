"""Langkah 15: RetryPolicy, pending writes, crash di tengah efek samping lalu resume."""

import json
import os
import subprocess
import sys

import pytest
from conftest import KODE, cfg
from langgraph.checkpoint.memory import InMemorySaver

from app import tools
from app.graph import HR_RETRY, build_graph


def test_retry_policy_terkonfigurasi():
    assert HR_RETRY.retry_on is tools.HRTimeoutError
    assert HR_RETRY.max_attempts >= 3


def test_api_hr_gagal_dua_kali_tetap_berhasil(monkeypatch):
    monkeypatch.setenv("HR_GAGAL_N_KALI", "2")
    tools.reset_hr()
    s = build_graph(InMemorySaver()).invoke({"permintaan": "Proses KLM-002"}, cfg("r1"))
    assert s["status_akhir"] == "dibayar"


def test_api_hr_terus_gagal_lalu_dilanjutkan(monkeypatch):
    monkeypatch.setenv("HR_GAGAL_N_KALI", "99")
    tools.reset_hr()
    g = build_graph(InMemorySaver())
    with pytest.raises(tools.HRTimeoutError):
        g.invoke({"permintaan": "Proses KLM-002"}, cfg("r2"))
    assert "cek_karyawan" in g.get_state(cfg("r2")).next
    monkeypatch.setenv("HR_GAGAL_N_KALI", "0")           # "API pulih"
    assert g.invoke(None, cfg("r2"))["status_akhir"] == "dibayar"


def _app(*args, **env_tambahan):
    """Jalankan `uv run app.py ...` sebagai proses terpisah (seperti dari terminal)."""
    env = {**os.environ, **env_tambahan}
    return subprocess.run([sys.executable, "app.py", *args], cwd=KODE, env=env,
                          capture_output=True, text=True, timeout=120)


def test_crash_setelah_bayar_lalu_resume_tidak_bayar_ganda(tmp_path):
    r = _app("Proses KLM-002", "--thread", "crash", CRASH_SETELAH_BAYAR="1")
    assert r.returncode == 1, f"proses harus mati di tengah node bayar\n{r.stdout}\n{r.stderr}"
    ledger = json.loads((tmp_path / "pembayaran.json").read_text())
    assert len(ledger) == 1, "transfer sudah terjadi sebelum crash"

    r = _app("--thread", "crash", "--lanjut")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "duplikat=True" in r.stdout, "node bayar diulang, tapi kunci idempotensi mencegah transfer kedua"
    assert len(json.loads((tmp_path / "pembayaran.json").read_text())) == 1


def test_interrupt_dan_resume_lintas_proses():
    r = _app("Proses klaim KLM-003", "--thread", "hitl")
    assert r.returncode == 0 and "berhenti di persetujuan" in r.stdout, r.stdout + r.stderr
    r = _app("--thread", "hitl", "--lanjut", "setujui", "--catatan", "ok")
    assert r.returncode == 0 and '"dibayar"' in r.stdout, r.stdout + r.stderr
