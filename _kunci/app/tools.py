"""Tool: fungsi Python biasa yang dipanggil node. Tidak ada LangGraph di file ini.

Semua aturan bisnis yang bisa dihitung ditaruh di sini (deterministik, mudah dites).
LLM tidak pernah menghitung uang.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from app.config import get_settings


class HRTimeoutError(RuntimeError):
    """API HR tiruan sedang lambat. Dipakai untuk latihan RetryPolicy."""


def _baca_json(nama: str) -> dict:
    return json.loads((get_settings().data_dir / nama).read_text(encoding="utf-8"))


def ambil_klaim(claim_id: str) -> dict | None:
    """Klaim lengkap (dict) atau None bila tidak ada. Menyertakan claim_id di dalamnya."""
    klaim = _baca_json("klaim.json").get(claim_id)
    return {"claim_id": claim_id, **klaim} if klaim else None


def ambil_kebijakan() -> dict:
    return _baca_json("kebijakan.json")


def periksa_item(item: dict, kebijakan: dict) -> dict:
    """Bandingkan satu item dengan aturan kategorinya.

    status: "ok" (dibayar penuh), "dipotong" (dibayar sampai batas), "ditolak" (tidak dibayar).
    """
    aturan = kebijakan["kategori"].get(item["kategori"])
    hasil = {"item_id": item["item_id"], "kategori": item["kategori"], "diajukan": item["jumlah"]}
    if aturan is None or aturan["batas_per_item"] == 0:
        return {**hasil, "disetujui": 0, "status": "ditolak", "alasan": f"kategori {item['kategori']} tidak dapat diklaim"}
    if aturan["wajib_struk"] and not item["ada_struk"]:
        return {**hasil, "disetujui": 0, "status": "ditolak", "alasan": "wajib struk tetapi struk tidak ada"}
    if item["jumlah"] > aturan["batas_per_item"]:
        return {**hasil, "disetujui": aturan["batas_per_item"], "status": "dipotong",
                "alasan": f"melebihi batas {format_rupiah(aturan['batas_per_item'])}"}
    return {**hasil, "disetujui": item["jumlah"], "status": "ok", "alasan": "sesuai aturan"}


# ---------------------------------------------------------------- API HR tiruan (tidak stabil)
_hr_panggilan = {"n": 0}


def reset_hr() -> None:
    _hr_panggilan["n"] = 0


def ambil_profil_karyawan(karyawan_id: str) -> dict:
    """Profil + sisa anggaran. Gagal (HRTimeoutError) untuk HR_GAGAL_N_KALI panggilan pertama."""
    _hr_panggilan["n"] += 1
    if _hr_panggilan["n"] <= get_settings().hr_gagal_n_kali:
        raise HRTimeoutError(f"API HR timeout (panggilan ke-{_hr_panggilan['n']})")
    profil = _baca_json("karyawan.json").get(karyawan_id)
    if profil is None:
        raise KeyError(f"karyawan {karyawan_id} tidak ditemukan")
    return {"karyawan_id": karyawan_id, **profil}


# ---------------------------------------------------------------- pembayaran tiruan (idempoten)
def _ledger_path() -> Path:
    return get_settings().runtime_dir / "pembayaran.json"


def baca_ledger() -> dict:
    p = _ledger_path()
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def bayar(claim_id: str, jumlah: int) -> dict:
    """Transfer tiruan. Kunci idempotensi = claim_id + jumlah.

    Panggilan kedua dengan kunci sama TIDAK mentransfer lagi; hasil lama dikembalikan dengan duplikat=True.
    """
    kunci = f"{claim_id}:{jumlah}"
    ledger = baca_ledger()
    if kunci in ledger:
        return {**ledger[kunci], "duplikat": True}
    transaksi = {"kunci": kunci, "claim_id": claim_id, "jumlah": jumlah, "ref": f"TRF-{len(ledger) + 1:04d}"}
    ledger[kunci] = transaksi
    _ledger_path().write_text(json.dumps(ledger, indent=2), encoding="utf-8")
    return {**transaksi, "duplikat": False}


# ---------------------------------------------------------------- pencarian kebijakan (RAG mini)
def _kata(teks: str) -> set[str]:
    return {k for k in re.findall(r"[a-z0-9]+", teks.lower()) if len(k) > 2}


def cari_kebijakan(pertanyaan: str, k: int = 2) -> list[dict]:
    """Retrieval sederhana: skor = jumlah kata yang sama antara pertanyaan dan paragraf."""
    q = _kata(pertanyaan)
    kandidat = []
    for f in sorted((get_settings().data_dir / "kebijakan").glob("*.md")):
        for paragraf in f.read_text(encoding="utf-8").split("\n\n"):
            if paragraf.startswith("#"):
                continue
            skor = len(q & _kata(paragraf))
            if skor:
                kandidat.append({"sumber": f.stem, "teks": paragraf.strip(), "skor": skor})
    return sorted(kandidat, key=lambda x: -x["skor"])[:k]


def format_rupiah(n: int) -> str:
    return "Rp" + f"{n:,}".replace(",", ".")
