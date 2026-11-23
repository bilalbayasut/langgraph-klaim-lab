"""Step 18: tracing with a callback (local tracer) and LangSmith configuration."""

import json

from app.graph import build_graph
from app.tracing import TraceRecorder, trace_path, show_trace


def _trace(request, thread):
    build_graph().invoke({"request": request}, {"callbacks": [TraceRecorder(trace_path(thread))]})
    return [json.loads(b) for b in trace_path(thread).read_text().splitlines()]


def test_satu_trace_berisi_node_dan_tool():
    lines = _trace("What is Sari's remaining budget, and can a hotel be claimed without a receipt?", "j1")
    graph = [b for b in lines if b["kind"] == "graph"]
    assert len(graph) == 1 and graph[0]["parent"] is None
    node = [b["name"] for b in lines if b["kind"] == "node"]
    assert node[:2] == ["router", "assistant"] and node[-1] == "assistant" and "run_tools" in node     # (+ "tool_approval" from Step 24 onward)
    tool = {b["name"] for b in lines if b["kind"] == "tool"}
    assert tool == {"employee_profile", "search_policy"}
    assert all(b["duration_ms"] >= 0 for b in lines)


def test_span_node_mencatat_superstep_dan_keluaran():
    lines = _trace("Process claim CLM-002", "j2")
    decide = next(b for b in lines if b["name"] == "decide")
    assert decide["superstep"] == 4 and "approve_full" in decide["output"]
    parallel = [b for b in lines if b["kind"] == "node" and b["superstep"] == 3]
    assert len(parallel) == 3


def test_tampilkan_pohon(capsys):
    _trace("What is Sari's remaining budget?", "j3")
    show_trace("j3")
    done = capsys.readouterr().out
    assert done.startswith("graph") and "tool  employee_profile" in done


def test_env_langsmith_terdokumentasi(code_dir):
    from pathlib import Path

    example = (Path(__file__).resolve().parents[1] / ".env.example").read_text()
    assert "LANGSMITH_TRACING=false" in example and "LANGSMITH_API_KEY=" in example


def test_app_py_jejak():
    from conftest import app_py

    run = app_py("Process claim CLM-002", "--thread", "j18").stdout
    assert "uv run app.py --trace j18" in run
    out = app_py("--trace", "j18").stdout
    assert "node  router" in out
