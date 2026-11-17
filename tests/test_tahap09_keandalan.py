"""Tahap 9: RetryPolicy, idempotensi, crash di tengah efek samping lalu resume."""

import json
import os
import subprocess
import sys

import pytest

from app import tools
from app.graph import HR_RETRY, build_graph


def test_retry_policy_terkonfigurasi():
    assert HR_RETRY.retry_on is tools.HRTimeoutError
    assert HR_RETRY.max_attempts >= 3


def test_api_hr_gagal_dua_kali_tetap_berhasil(monkeypatch):
    monkeypatch.setenv("HR_GAGAL_N_KALI", "2")
    tools.reset_hr()
    s = build_graph().invoke({"permintaan": "Proses KLM-002"}, {"configurable": {"thread_id": "r1"}})
    assert s["status_akhir"] == "dibayar"


def test_api_hr_terus_gagal_akhirnya_menyerah(monkeypatch):
    monkeypatch.setenv("HR_GAGAL_N_KALI", "99")
    tools.reset_hr()
    with pytest.raises(tools.HRTimeoutError):
        build_graph().invoke({"permintaan": "Proses KLM-002"}, {"configurable": {"thread_id": "r2"}})


def test_crash_setelah_bayar_lalu_resume_tidak_bayar_ganda(kode_dir, tmp_path):
    env = {**os.environ, "PYTHONPATH": str(kode_dir), "RUNTIME_DIR": str(tmp_path), "LLM_MODE": "mock"}
    jalankan = [sys.executable, "-m", "app.cli"]
    r = subprocess.run(jalankan + ["jalankan", "Proses KLM-002", "--thread", "crash"],
                       env={**env, "CRASH_SETELAH_BAYAR": "1"}, capture_output=True, text=True, timeout=60)
    assert r.returncode == 1, "proses harus mati di tengah node bayar"
    ledger = json.loads((tmp_path / "pembayaran.json").read_text())
    assert len(ledger) == 1, "transfer sudah terjadi sebelum crash"

    r = subprocess.run(jalankan + ["lanjut", "--thread", "crash"], env=env, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    assert "duplikat=True" in r.stdout, "node bayar diulang, tapi kunci idempotensi mencegah transfer kedua"
    assert len(json.loads((tmp_path / "pembayaran.json").read_text())) == 1
