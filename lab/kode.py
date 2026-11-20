"""Menentukan folder kode yang sedang dipakai: app/ milikmu, atau kunci jawaban.

    (tanpa KUNCI)   -> ./app            (kode yang kamu tulis)
    KUNCI=5         -> ./_kunci/langkah-05/app
    KUNCI=akhir     -> kunci langkah terakhir (proyek lengkap)

Dipakai oleh `uv run lihat`, `uv run cek`, dan tests/conftest.py.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KUNCI_DIR = ROOT / "_kunci"


def daftar_langkah_kunci() -> list[int]:
    if not KUNCI_DIR.exists():
        return []
    return sorted(int(p.name.split("-")[1]) for p in KUNCI_DIR.glob("langkah-*") if p.is_dir())


def kode_dir() -> Path:
    """Folder yang berisi package `app` yang akan diimpor."""
    k = os.getenv("KUNCI", "").strip().lower()
    if not k or k == "0":
        return ROOT
    if k == "akhir":
        ada = daftar_langkah_kunci()
        if not ada:
            raise SystemExit("Folder _kunci/ kosong.")
        n = ada[-1]
    elif k.isdigit():
        n = int(k)
    else:
        raise SystemExit(f"KUNCI={k!r} tidak dikenal. Pakai nomor langkah (KUNCI=5) atau KUNCI=akhir.")
    d = KUNCI_DIR / f"langkah-{n:02d}"
    if not d.exists():
        raise SystemExit(f"Kunci untuk langkah {n} tidak ada ({d}).")
    return d


def label_kode() -> str:
    d = kode_dir()
    return "app/ (kode kamu)" if d == ROOT else f"{d.relative_to(ROOT)}/app (kunci jawaban)"


def pasang_sys_path() -> Path:
    """Taruh folder kode paling depan di sys.path, supaya `import app` mengambil yang benar."""
    d = kode_dir()
    sys.path[:] = [p for p in sys.path if Path(p or ".").resolve() != d]
    sys.path.insert(0, str(d))
    return d
