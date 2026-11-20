"""Langkah 9: evaluasi perilaku agent dengan dataset kasus."""

import importlib.util

import pytest


@pytest.fixture
def evaluasi(kode):
    spec = importlib.util.spec_from_file_location("evaluasi", kode / "evaluasi.py")
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def test_dataset_lengkap(evaluasi):
    kasus = evaluasi.muat_kasus()
    assert len(kasus) >= 10 and len({k["id"] for k in kasus}) == len(kasus)
    assert {"routing", "keputusan", "tool", "rag"} <= {k["kategori"] for k in kasus}


def test_periksa_menemukan_kegagalan(evaluasi):
    kasus = {"harap": {"rute": "klaim", "aksi": "tolak", "tool": ["detail_klaim"], "jawaban_memuat": ["X"]}}
    gagal = evaluasi.periksa(kasus, {"rute": "kebijakan", "keputusan": {"aksi": "tolak"}, "jawaban": "abc"})
    assert len(gagal) == 3


def test_mode_mock_skor_penuh(evaluasi, capsys):
    assert evaluasi.main() == 0
    assert "(100%)" in capsys.readouterr().out
