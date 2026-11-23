"""Step 19: FastAPI API (including human-in-the-loop and SSE) and Docker files."""

import importlib.util

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(code_dir):
    spec = importlib.util.spec_from_file_location("api_lab", code_dir / "api.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return TestClient(module.app)


def test_health(client):
    assert client.get("/health").json() == {"ok": True}


def test_klaim_otomatis_selesai(client):
    r = client.post("/claim", json={"request": "Process claim CLM-002"}).json()
    assert r["status"] == "finished" and r["final_status"] == "paid"
    assert r["decision"]["total_approved"] == 180000


def test_human_in_the_loop_lewat_http(client):
    r = client.post("/claim", json={"request": "Process claim CLM-001", "thread_id": "h1"}).json()
    assert r["status"] == "awaiting_approval" and r["waiting"]["claim_id"] == "CLM-001"
    r = client.post("/claim/h1/resume", json={"action": "approve", "note": "ok"}).json()
    assert r["status"] == "finished" and r["final_status"] == "paid"
    assert client.get("/claim/h1").json()["final_status"] == "paid"
    assert client.post("/claim/h1/resume", json={"action": "approve"}).status_code == 409


def test_thread_tidak_ada(client):
    assert client.get("/claim/missing").status_code == 404


def test_asisten_lewat_http(client):
    r = client.post("/claim", json={"request": "What is Sari's remaining budget?"}).json()
    assert r["route"] == "assistant" and "Rp3.000.000" in r["answer"]


def test_stream_sse(client):
    with client.stream("POST", "/claim/stream", json={"request": "Process claim CLM-002"}) as r:
        text = "".join(r.iter_text())
    assert r.headers["content-type"].startswith("text/event-stream")
    assert "event: node" in text and "event: progress" in text and "event: finished" in text


def test_berkas_docker(code_dir):
    docker = (code_dir / "Dockerfile").read_text()
    assert "uv sync --frozen --no-dev" in docker and "uvicorn" in docker
    assert docker.index("uv sync") < docker.index("COPY app")          # dependencies before code (cache)
    assert ".env" in (code_dir / ".dockerignore").read_text().split()
    compose = (code_dir / "docker-compose.yml").read_text()
    assert "env_file" in compose and "volumes" in compose
