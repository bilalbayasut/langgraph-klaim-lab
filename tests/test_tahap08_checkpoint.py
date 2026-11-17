"""Tahap 8: checkpointer SQLite, riwayat, dan resume dari PROSES LAIN (CLI)."""

import os
import subprocess
import sys

from langgraph.types import Command

from app.graph import build_graph, buka_sqlite


def test_state_bertahan_lintas_instance(tmp_path):
    db = str(tmp_path / "cp.db")
    cfg = {"configurable": {"thread_id": "x"}}
    build_graph(buka_sqlite(db)).invoke({"permintaan": "Proses KLM-001"}, cfg)
    g2 = build_graph(buka_sqlite(db))           # "proses baru": objek graph & koneksi baru
    assert g2.get_state(cfg).next == ("persetujuan",)
    s = g2.invoke(Command(resume="setujui"), cfg)
    assert s["status_akhir"] == "dibayar"
    riwayat = list(g2.get_state_history(cfg))
    assert len(riwayat) > 10 and riwayat[0].next == ()


def _cli(kode_dir, tmp_path, *args):
    env = {**os.environ, "PYTHONPATH": str(kode_dir), "RUNTIME_DIR": str(tmp_path), "LLM_MODE": "mock"}
    return subprocess.run([sys.executable, "-m", "app.cli", *args], env=env, capture_output=True, text=True, timeout=60)


def test_cli_jalankan_lalu_lanjut_dari_proses_baru(kode_dir, tmp_path):
    r = _cli(kode_dir, tmp_path, "jalankan", "Proses klaim KLM-003", "--thread", "cli-1")
    assert r.returncode == 0, r.stderr
    assert "persetujuan" in r.stdout and "INTERRUPT" in r.stdout
    r = _cli(kode_dir, tmp_path, "status", "--thread", "cli-1")
    assert "('persetujuan',)" in r.stdout
    r = _cli(kode_dir, tmp_path, "lanjut", "--thread", "cli-1", "--aksi", "setujui", "--catatan", "ok")
    assert r.returncode == 0, r.stderr
    assert "dibayar" in r.stdout
    r = _cli(kode_dir, tmp_path, "riwayat", "--thread", "cli-1")
    assert r.returncode == 0 and "step=" in r.stdout
