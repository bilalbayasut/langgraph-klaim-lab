"""Langkah 8: RAG dengan ChromaDB."""

import pytest

from app import rag
from app.graph import build_graph


def test_potong_dokumen():
    p = rag.potong_dokumen()
    assert len(p) == 10, "3 dokumen: 3 + 3 + 4 bagian '## '"
    assert len({x["id"] for x in p}) == 10, "id harus unik"
    assert {x["sumber"] for x in p} == {"KEB-01", "KEB-02", "KEB-03"}
    assert all(x["teks"] and not x["teks"].startswith("#") for x in p)


def test_embed_deterministik_dan_ternormalisasi():
    a, b = rag.embed(["batas hotel per malam", "batas hotel per malam"])
    assert a == b and len(a) == rag.DIMENSI
    assert abs(sum(x * x for x in a) - 1) < 1e-6


def test_koleksi_chromadb_dipakai_ulang():
    k1 = rag.koleksi()
    assert k1.count() == 10
    k2 = rag.koleksi()
    assert k2.metadata["sidik"] == k1.metadata["sidik"]


def test_cari_menemukan_sumber_yang_tepat():
    harapan = {
        "Berapa batas biaya hotel per malam?": ("KEB-01", "Batas per item"),
        "Apakah langganan streaming bisa diklaim?": ("KEB-01", "Kategori yang tidak dapat diklaim"),
        "Hotel tanpa struk apakah ditolak?": ("KEB-02", "Kategori yang wajib struk"),
        "Kapan klaim perlu persetujuan atasan?": ("KEB-03", "Persetujuan atasan"),
        "Apa yang terjadi kalau total melebihi sisa anggaran?": ("KEB-03", "Sisa anggaran tahunan"),
    }
    for q, (sumber, bagian) in harapan.items():
        teratas = rag.cari_kebijakan(q, k=2)[0]
        assert (teratas["sumber"], teratas["bagian"]) == (sumber, bagian), q
        assert 0 < teratas["skor"] <= 1


def test_pertanyaan_di_luar_topik():
    assert rag.cari_kebijakan("Bagaimana aturan resep kue?") == []


def test_graph_menjawab_dengan_sumber():
    s = build_graph().invoke({"permintaan": "Berapa batas biaya hotel per malam?"})
    assert s["status_akhir"] == "dijawab" and "KEB-01" in s["sumber"] and "Rp750.000" in s["jawaban"]
    s = build_graph().invoke({"permintaan": "Bagaimana aturan resep kue?"})
    assert s["sumber"] == [] and "Tidak ditemukan" in s["jawaban"]


# ---- embedding: pilihan hash / onnx (tanpa mengunduh model)
def test_id_embedding(monkeypatch):
    assert rag.id_embedding() == f"hash-{rag.DIMENSI}"
    monkeypatch.setenv("EMBEDDING", "onnx")
    assert rag.id_embedding().startswith("onnx")
    monkeypatch.setenv("EMBEDDING", "ngawur")
    with pytest.raises(ValueError):
        rag.id_embedding()


def test_fungsi_onnx_tersedia():
    from chromadb.utils.embedding_functions import DefaultEmbeddingFunction  # noqa: F401


def test_hash_tetap_default():
    assert len(rag.embed(["batas hotel"])[0]) == rag.DIMENSI


# ---- retrieval sebagai tool untuk agent asisten
def test_cari_kebijakan_jadi_tool_asisten():
    from app.asisten import alat, cari_kebijakan

    assert "cari_kebijakan" in {t.name for t in alat()}
    assert "[KEB-02]" in cari_kebijakan.invoke({"pertanyaan": "hotel tanpa struk"})


def test_asisten_menggabungkan_mcp_dan_rag():
    s = build_graph().invoke({"permintaan": "Berapa sisa anggaran Sari, dan bolehkah klaim hotel tanpa struk?"})
    dipanggil = sorted(tc["name"] for m in s["messages"] for tc in getattr(m, "tool_calls", []))
    assert dipanggil == ["cari_kebijakan", "profil_karyawan"]
    assert "Rp3.000.000" in s["jawaban"] and "KEB-02" in s["jawaban"]
