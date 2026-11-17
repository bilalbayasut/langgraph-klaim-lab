"""Guardrail sederhana untuk prompt injection di data yang ditulis pengguna (keterangan item)."""

from __future__ import annotations

import re

POLA_INJEKSI = [
    r"abaikan\s+(semua\s+)?(aturan|instruksi|perintah)",
    r"ignore\s+(all\s+)?(previous\s+)?(instructions|rules)",
    r"\bapproved\b",
    r"setujui\s+(klaim|penuh|semua)",
]


def deteksi_injeksi(teks: str) -> list[str]:
    """Daftar pola yang cocok (kosong = aman)."""
    return [p for p in POLA_INJEKSI if re.search(p, teks, re.IGNORECASE)]


def bungkus_tidak_tepercaya(teks: str) -> str:
    """Tandai teks dari pengguna sebagai DATA, bukan instruksi, sebelum masuk prompt."""
    return f"<data_tidak_tepercaya>{teks}</data_tidak_tepercaya>"
