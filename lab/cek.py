"""uv run cek N: jalankan test langkah 1 sampai N (default: semua yang ada).

  uv run cek 3            test langkah 1, 2, 3  (memastikan langkah lama tidak rusak)
  uv run cek 3 --hanya    hanya test langkah 3
  uv run cek 3 -x -v      argumen tambahan diteruskan ke pytest
  KUNCI=3 uv run cek 3    menguji kunci jawaban langkah 3
"""

from __future__ import annotations

import sys

import pytest

from lab.kode import ROOT, label_kode


def main() -> None:
    args = sys.argv[1:]
    hanya = "--hanya" in args
    args = [a for a in args if a != "--hanya"]
    angka = [a for a in args if a.isdigit()]
    sisa = [a for a in args if not a.isdigit()]

    semua = sorted((ROOT / "tests").glob("test_langkah*.py"))
    nomor = lambda f: int(f.stem.removeprefix("test_langkah")[:2])  # noqa: E731
    if angka:
        n = int(angka[0])
        pilih = [f for f in semua if (nomor(f) == n if hanya else nomor(f) <= n)]
        judul = f"langkah {n}" if hanya else f"langkah 1 sampai {n}"
    else:
        pilih, judul = semua, "semua langkah"
    if not pilih:
        raise SystemExit("Tidak ada file test yang cocok.")

    print(f"🧪 menguji {judul} | kode: {label_kode()}\n")
    raise SystemExit(pytest.main(["-q", *sisa, *map(str, pilih)]))


if __name__ == "__main__":
    main()
