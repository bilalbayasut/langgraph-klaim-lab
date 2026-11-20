"""Langkah 22: data confidential (minimasi, redaksi, audit)."""

import json

from langgraph.checkpoint.memory import InMemorySaver

from app.graph import build_graph
from app.jejak import PencatatJejak, _singkat, path_jejak
from app.nodes import cek_karyawan
from app.privasi import samarkan, samarkan_data, tanpa_rahasia
from app import tools


def test_data_sumber_memang_berisi_rahasia():
    p = tools.ambil_profil_karyawan("EMP-02")
    assert {"nik", "no_rekening", "email"} <= set(p)


def test_minimasi_di_cek_karyawan():
    out = cek_karyawan({"klaim": tools.ambil_klaim("KLM-002")})
    assert out["profil"]["sisa_anggaran"] == 3000000
    assert not {"nik", "no_rekening", "email"} & set(out["profil"])
    assert tanpa_rahasia({"nama": "x", "nik": "1"}) == {"nama": "x"}


def test_redaksi():
    teks = samarkan("rek 0123456782, NIK 3174024506920002, sari@contoh.co.id, total Rp1.020.000")
    assert teks == "rek [REKENING], NIK [NIK], [EMAIL], total Rp1.020.000"
    assert samarkan_data({"nik": "123", "x": ["0123456782"]}) == {"nik": "***", "x": ["[REKENING]"]}
    assert "3174024506920002" not in _singkat({"profil": {"nik": "3174024506920002"}})


def test_state_dan_jejak_bersih():
    g = build_graph(InMemorySaver())
    cfg = {"configurable": {"thread_id": "p22"}, "callbacks": [PencatatJejak(path_jejak("p22"))]}
    g.invoke({"permintaan": "Proses klaim KLM-002"}, cfg)
    state = json.dumps(g.get_state(cfg).values, default=str)
    assert "3174024506920002" not in state and "0123456782" not in state
    assert "3174024506920002" not in path_jejak("p22").read_text()


def test_audit_thread_bersih(capsys):
    import subprocess, sys, os
    from conftest import KODE

    env = dict(os.environ)
    subprocess.run([sys.executable, "app.py", "Proses klaim KLM-002", "--thread", "aud"], cwd=KODE, env=env,
                   capture_output=True, check=True)
    from app.privasi import audit
    assert audit("aud") == []
