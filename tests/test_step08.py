"""Step 8: RAG with ChromaDB."""

import pytest

from app import rag
from app.graph import build_graph


def test_potong_dokumen():
    p = rag.split_documents()
    assert len(p) == 10, "3 documents: 3 + 3 + 4 '## ' sections"
    assert len({x["id"] for x in p}) == 10, "ids must be unique"
    assert {x["source"] for x in p} == {"POL-01", "POL-02", "POL-03"}
    assert all(x["text"] and not x["text"].startswith("#") for x in p)


def test_embed_deterministik_dan_ternormalisasi():
    a, b = rag.embed(["hotel limit per night", "hotel limit per night"])
    assert a == b and len(a) == rag.DIMENSIONS
    assert abs(sum(x * x for x in a) - 1) < 1e-6


def test_koleksi_chromadb_dipakai_ulang():
    k1 = rag.collection()
    assert k1.count() == 10
    k2 = rag.collection()
    assert k2.metadata["fingerprint"] == k1.metadata["fingerprint"]


def test_cari_menemukan_sumber_yang_tepat():
    expected = {
        "What is the hotel expense limit per night?": ("POL-01", "Limit per item"),
        "Can a streaming subscription be claimed?": ("POL-01", "Categories that cannot be claimed"),
        "Is a hotel without a receipt rejected?": ("POL-02", "Categories that require a receipt"),
        "When does a claim need manager approval?": ("POL-03", "Manager approval"),
        "What happens if the total exceeds the remaining budget?": ("POL-03", "Remaining annual budget"),
    }
    for q, (sources, section) in expected.items():
        top = rag.search_policy(q, k=2)[0]
        assert (top["source"], top["section"]) == (sources, section), q
        assert 0 < top["score"] <= 1


def test_pertanyaan_di_luar_topik():
    assert rag.search_policy("What is the rule for cake recipes?") == []


def test_graph_menjawab_dengan_sumber():
    s = build_graph().invoke({"request": "What is the hotel expense limit per night?"})
    assert s["final_status"] == "answered" and "POL-01" in s["sources"] and "Rp750.000" in s["answer"]
    s = build_graph().invoke({"request": "What is the rule for cake recipes?"})
    assert s["sources"] == [] and "Not found" in s["answer"]


# ---- embedding: hash / onnx choice (without downloading a model)
def test_id_embedding(monkeypatch):
    assert rag.embedding_id() == f"hash-{rag.DIMENSIONS}"
    monkeypatch.setenv("EMBEDDING", "onnx")
    assert rag.embedding_id().startswith("onnx")
    monkeypatch.setenv("EMBEDDING", "bogus")
    with pytest.raises(ValueError):
        rag.embedding_id()


def test_fungsi_onnx_tersedia():
    from chromadb.utils.embedding_functions import DefaultEmbeddingFunction  # noqa: F401


def test_hash_tetap_default():
    assert len(rag.embed(["hotel limit"])[0]) == rag.DIMENSIONS


# ---- retrieval as a tool for the assistant agent
def test_cari_kebijakan_jadi_tool_asisten():
    from app.assistant import assistant_tools, search_policy

    assert "search_policy" in {t.name for t in assistant_tools()}
    assert "[POL-02]" in search_policy.invoke({"question": "hotel without receipt"})


def test_asisten_menggabungkan_mcp_dan_rag():
    s = build_graph().invoke({"request": "What is Sari's remaining budget, and can a hotel be claimed without a receipt?"})
    called = sorted(tc["name"] for m in s["messages"] for tc in getattr(m, "tool_calls", []))
    assert called == ["employee_profile", "search_policy"]
    assert "Rp3.000.000" in s["answer"] and "POL-02" in s["answer"]


def test_app_py_potongan_dan_rag():
    from conftest import app_py

    assert "POL-01::Limit per item" in app_py("--chunks").stdout
    assert "POL-02 / Categories that require a receipt" in app_py("--rag", "Is a hotel without a receipt rejected?").stdout
