"""Langkah 17: pilihan embedding (tanpa memanggil LLM / mengunduh model)."""

import pytest

from app import rag


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
