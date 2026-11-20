"""Langkah 19: API FastAPI (termasuk human-in-the-loop dan SSE) dan berkas Docker."""

import importlib.util

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def klien(kode):
    spec = importlib.util.spec_from_file_location("api_lab", kode / "api.py")
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return TestClient(modul.app)


def test_health(klien):
    assert klien.get("/health").json() == {"ok": True}


def test_klaim_otomatis_selesai(klien):
    r = klien.post("/klaim", json={"permintaan": "Proses klaim KLM-002"}).json()
    assert r["status"] == "selesai" and r["status_akhir"] == "dibayar"
    assert r["keputusan"]["total_disetujui"] == 180000


def test_human_in_the_loop_lewat_http(klien):
    r = klien.post("/klaim", json={"permintaan": "Proses klaim KLM-001", "thread_id": "h1"}).json()
    assert r["status"] == "menunggu_persetujuan" and r["menunggu"]["claim_id"] == "KLM-001"
    r = klien.post("/klaim/h1/lanjut", json={"aksi": "setujui", "catatan": "ok"}).json()
    assert r["status"] == "selesai" and r["status_akhir"] == "dibayar"
    assert klien.get("/klaim/h1").json()["status_akhir"] == "dibayar"
    assert klien.post("/klaim/h1/lanjut", json={"aksi": "setujui"}).status_code == 409


def test_thread_tidak_ada(klien):
    assert klien.get("/klaim/tidak-ada").status_code == 404


def test_asisten_lewat_http(klien):
    r = klien.post("/klaim", json={"permintaan": "Berapa sisa anggaran Sari?"}).json()
    assert r["rute"] == "asisten" and "Rp3.000.000" in r["jawaban"]


def test_stream_sse(klien):
    with klien.stream("POST", "/klaim/stream", json={"permintaan": "Proses klaim KLM-002"}) as r:
        teks = "".join(r.iter_text())
    assert r.headers["content-type"].startswith("text/event-stream")
    assert "event: node" in teks and "event: progres" in teks and "event: selesai" in teks


def test_berkas_docker(kode):
    docker = (kode / "Dockerfile").read_text()
    assert "uv sync --frozen --no-dev" in docker and "uvicorn" in docker
    assert docker.index("uv sync") < docker.index("COPY app")          # dependency sebelum kode (cache)
    assert ".env" in (kode / ".dockerignore").read_text().split()
    compose = (kode / "docker-compose.yml").read_text()
    assert "env_file" in compose and "volumes" in compose
