"""Tahap 1: tool Python biasa (belum ada LangGraph)."""

import pytest

from app import tools


def test_ambil_klaim():
    k = tools.ambil_klaim("KLM-001")
    assert k["claim_id"] == "KLM-001"
    assert k["karyawan_id"] == "EMP-01"
    assert len(k["item"]) == 3
    assert tools.ambil_klaim("KLM-999") is None


def test_format_rupiah():
    assert tools.format_rupiah(1050000) == "Rp1.050.000"
    assert tools.format_rupiah(0) == "Rp0"


@pytest.mark.parametrize("item_id,status,disetujui", [
    ("KLM-001-1", "ok", 650000),          # hotel di bawah batas, ada struk
    ("KLM-001-2", "dipotong", 150000),    # makan 180rb > batas 150rb
    ("KLM-001-3", "ok", 220000),          # transport tanpa struk boleh
    ("KLM-003-2", "ditolak", 0),          # peralatan wajib struk
    ("KLM-003-3", "ditolak", 0),          # hiburan tidak bisa diklaim
])
def test_periksa_item(item_id, status, disetujui):
    claim_id = item_id.rsplit("-", 1)[0]
    item = next(i for i in tools.ambil_klaim(claim_id)["item"] if i["item_id"] == item_id)
    h = tools.periksa_item(item, tools.ambil_kebijakan())
    assert h["item_id"] == item_id
    assert h["status"] == status
    assert h["disetujui"] == disetujui
    assert h["diajukan"] == item["jumlah"]
    assert h["alasan"]


def test_profil_karyawan_dan_api_tidak_stabil(monkeypatch):
    assert tools.ambil_profil_karyawan("EMP-05")["sisa_anggaran"] == 400000
    monkeypatch.setenv("HR_GAGAL_N_KALI", "2")
    tools.reset_hr()
    for _ in range(2):
        with pytest.raises(tools.HRTimeoutError):
            tools.ambil_profil_karyawan("EMP-01")
    assert tools.ambil_profil_karyawan("EMP-01")["nama"] == "Andi Pratama"


def test_bayar_idempoten():
    a = tools.bayar("KLM-002", 180000)
    b = tools.bayar("KLM-002", 180000)
    assert a["duplikat"] is False and b["duplikat"] is True
    assert a["ref"] == b["ref"]
    assert len(tools.baca_ledger()) == 1


def test_cari_kebijakan():
    hasil = tools.cari_kebijakan("apakah langganan streaming hiburan bisa diklaim?")
    assert hasil and hasil[0]["sumber"] == "KEB-01_batas_biaya"
    assert {"sumber", "teks", "skor"} <= set(hasil[0])
