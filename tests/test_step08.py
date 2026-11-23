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
    a, b = rag.embed(["batas hotel per malam", "batas hotel per malam"])
    assert a == b and len(a) == rag.DIMENSIONS
    assert abs(sum(x * x for x in a) - 1) < 1e-6


def test_koleksi_chromadb_dipakai_ulang():
    k1 = rag.collection()
    assert k1.count() == 10
    k2 = rag.collection()
    assert k2.metadata["fingerprint"] == k1.metadata["fingerprint"]


def test_cari_menemukan_sumber_yang_tepat():
    expected = {
        "Berapa batas biaya hotel per malam?": ("POL-01", "Batas per item"),
        "Apakah langganan streaming bisa diklaim?": ("POL-01", "Kategori yang tidak dapat diklaim"),
        "Hotel tanpa struk apakah ditolak?": ("POL-02", "Kategori yang wajib struk"),
        "Kapan klaim perlu persetujuan atasan?": ("POL-03", "Persetujuan atasan"),
        "Apa yang terjadi kalau total melebihi sisa anggaran?": ("POL-03", "Sisa anggaran tahunan"),
    }
    for q, (sources, section) in expected.items():
        top = rag.search_policy(q, k=2)[0]
        assert (top["source"], top["section"]) == (sources, section), q
        assert 0 < top["score"] <= 1


def test_pertanyaan_di_luar_topik():
    assert rag.search_policy("Bagaimana aturan resep kue?") == []


def test_graph_menjawab_dengan_sumber():
    s = build_graph().invoke({"request": "Berapa batas biaya hotel per malam?"})
    assert s["final_status"] == "answered" and "POL-01" in s["sources"] and "Rp750.000" in s["answer"]
    s = build_graph().invoke({"request": "Bagaimana aturan resep kue?"})
    assert s["sources"] == [] and "Not found" in s["answer"]


# ---- embedding: hash / semantic choice (without downloading a model)
def test_id_embedding(monkeypatch):
    assert rag.embedding_id() == f"hash-{rag.DIMENSIONS}"
    monkeypatch.setenv("EMBEDDING", "semantic")
    assert rag.embedding_id() == "semantic-paraphrase-multilingual-MiniLM-L12-v2"
    monkeypatch.setenv("EMBEDDING_MODEL", "sentence-transformers/paraphrase-multilingual-mpnet-base-v2")
    assert rag.embedding_id() == "semantic-paraphrase-multilingual-mpnet-base-v2"   # one collection per model
    monkeypatch.setenv("EMBEDDING", "bogus")
    with pytest.raises(ValueError):
        rag.embedding_id()


def test_model_default_tersedia():
    """fastembed is installed and knows the default EMBEDDING_MODEL (checks the catalogue only, nothing is downloaded)."""
    from fastembed import TextEmbedding

    from app.config import get_settings

    model = {m["model"]: m for m in TextEmbedding.list_supported_models()}[get_settings().embedding_model]
    assert model["dim"] == 384


def test_hash_tetap_default():
    assert len(rag.embed(["batas hotel"])[0]) == rag.DIMENSIONS


# ---- retrieval as a tool for the assistant agent
def test_cari_kebijakan_jadi_tool_asisten():
    from app.assistant import assistant_tools, search_policy

    assert "search_policy" in {t.name for t in assistant_tools()}
    assert "[POL-02]" in search_policy.invoke({"question": "hotel tanpa struk"})


def test_asisten_menggabungkan_mcp_dan_rag():
    s = build_graph().invoke({"request": "Berapa sisa anggaran Sari, dan bolehkah klaim hotel tanpa struk?"})
    called = sorted(tc["name"] for m in s["messages"] for tc in getattr(m, "tool_calls", []))
    assert called == ["employee_profile", "search_policy"]
    assert "Rp3.000.000" in s["answer"] and "POL-02" in s["answer"]


def test_app_py_potongan_dan_rag():
    from conftest import app_py

    assert "POL-01::Batas per item" in app_py("--chunks").stdout
    assert "POL-02 / Kategori yang wajib struk" in app_py("--rag", "Hotel tanpa struk apakah ditolak?").stdout
