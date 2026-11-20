"""Bangun ulang _kunci/ dari blok kode di LAB.md (alat pengelola lab, bukan bagian latihan).

LAB.md adalah satu-satunya sumber kode. Setiap blok kode yang didahului komentar
    <!-- kode: app/nodes.py | tambah -->   (tambah fungsi baru / ganti fungsi bernama sama)
    <!-- kode: app/graph.py | penuh -->    (isi file lengkap)
    <!-- hapus: app/nodes.py | nama_fungsi -->
diterapkan berurutan. Hasil setiap langkah disimpan di _kunci/langkah-NN/.

  uv run python -m lab.kunci              bangun _kunci/
  uv run python -m lab.kunci --uji        + uji: kunci langkah N harus lolos test langkah 1..N
  uv run python -m lab.kunci --output     + isi blok <!-- output: N | perintah --> di LAB.md
"""

from __future__ import annotations

import ast
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAB = ROOT / "LAB.md"
KUNCI = ROOT / "_kunci"

RE_LANGKAH = re.compile(r"^## Langkah (\d+)\b")
RE_KODE = re.compile(r"^<!-- kode: (\S+) \| (penuh|tambah) -->\s*$")
RE_HAPUS = re.compile(r"^<!-- hapus: (\S+) \| (.+?) -->\s*$")
RE_OUTPUT = re.compile(r"^<!-- output: (\d+) \| (.+?)(?: \| (\d+))? -->\s*$")


# ----------------------------------------------------------------------------- baca LAB.md
def baca_operasi(teks: str) -> list[tuple[int, str, str, str]]:
    ops, langkah = [], 0
    baris = teks.splitlines()
    i = 0
    while i < len(baris):
        b = baris[i]
        if m := RE_LANGKAH.match(b):
            langkah = int(m.group(1))
        elif m := RE_HAPUS.match(b.strip()):
            ops.append((langkah, "hapus", m.group(1), m.group(2)))
        elif m := RE_KODE.match(b.strip()):
            j = i + 1
            while not baris[j].strip():
                j += 1
            pagar = baris[j]
            if not pagar.lstrip().startswith("```"):
                raise SystemExit(f"LAB.md baris {i + 1}: komentar kode harus diikuti blok ```")
            indent = len(pagar) - len(pagar.lstrip())
            isi, j = [], j + 1
            while baris[j].strip() != "```":
                isi.append(baris[j][indent:])
                j += 1
            ops.append((langkah, m.group(2), m.group(1), "\n".join(isi) + "\n"))
            i = j
        i += 1
    return ops


# ----------------------------------------------------------------------------- operasi kode
def _nama(node: ast.stmt) -> str | None:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return node.name
    if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
        return node.targets[0].id
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        return node.target.id
    if isinstance(node, ast.If) and "__main__" in ast.unparse(node.test):
        return "__main__"
    return None


def _span(node: ast.stmt, lines: list[str]) -> tuple[int, int]:
    """(awal, akhir) indeks baris, termasuk decorator dan komentar yang menempel tepat di atasnya."""
    awal = node.lineno - 1
    if getattr(node, "decorator_list", None):
        awal = min(d.lineno for d in node.decorator_list) - 1
    while awal > 0 and lines[awal - 1].lstrip().startswith("#"):
        awal -= 1
    return awal, node.end_lineno


def _is_import(n: ast.stmt) -> bool:
    return isinstance(n, (ast.Import, ast.ImportFrom))


def _is_docstring(n: ast.stmt) -> bool:
    return isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant) and isinstance(n.value.value, str)


def _render_import(kunci: tuple, nama: list[str]) -> str:
    if kunci[0] == "import":
        return f"import {kunci[1]}" + (f" as {kunci[2]}" if kunci[2] else "")
    modul = "." * kunci[2] + (kunci[1] or "")
    baris = f"from {modul} import {', '.join(nama)}"
    if len(baris) <= 110:
        return baris
    isi, cur = [], "   "
    for n in nama:
        if len(cur) + len(n) + 2 > 100:
            isi.append(cur.rstrip())
            cur = "   "
        cur += f" {n},"
    isi.append(cur.rstrip())
    return f"from {modul} import (\n" + "\n".join(isi) + "\n)"


def _grup(kunci: tuple) -> int:
    mod = kunci[1] or ""
    if mod == "__future__":
        return 0
    if kunci[0] == "from" and kunci[2] > 0 or mod.split(".")[0] == "app":
        return 3
    return 1 if mod.split(".")[0] in sys.stdlib_module_names else 2


def gabung_import(src: str, impor_baru: list[ast.stmt]) -> str:
    tree, lines = ast.parse(src), src.splitlines()
    body, i = tree.body, 0
    if body and _is_docstring(body[0]):
        i = 1
    lama = []
    while i < len(body) and _is_import(body[i]):
        lama.append(body[i])
        i += 1
    entri: dict[tuple, list[str]] = {}
    for n in lama + impor_baru:
        if isinstance(n, ast.Import):
            for a in n.names:
                entri.setdefault(("import", a.name, a.asname), [])
        else:
            daftar = entri.setdefault(("from", n.module, n.level), [])
            for a in n.names:
                s = a.name + (f" as {a.asname}" if a.asname else "")
                if s not in daftar:
                    daftar.append(s)
    grup: dict[int, list[tuple]] = {}
    for k, nama in entri.items():
        grup.setdefault(_grup(k), []).append(k)
    for g in grup:
        grup[g] = [_render_import(k, sorted(entri[k])) for k in sorted(grup[g], key=lambda k: (k[0] == "from", k[1] or ""))]
    header = "\n\n".join("\n".join(grup[g]) for g in sorted(grup))
    if lama:
        awal, akhir = lama[0].lineno - 1, lama[-1].end_lineno
    else:
        awal = akhir = body[0].end_lineno if body and _is_docstring(body[0]) else 0
        header = ("\n" if awal else "") + header + "\n"
    return "\n".join(lines[:awal] + header.splitlines() + lines[akhir:]) + "\n"


def tambah(lama: str, baru: str) -> str:
    """Upsert: definisi bernama sama diganti, yang baru ditambahkan di akhir, import digabung."""
    tb, lb = ast.parse(baru), baru.splitlines()
    lines = lama.splitlines()
    tl = ast.parse(lama) if lama.strip() else ast.Module(body=[], type_ignores=[])
    posisi_lama = {_nama(n): _span(n, lines) for n in tl.body if _nama(n)}

    ganti, tambahan, akhir_sebelum = [], [], 0
    for n in tb.body:
        if _is_import(n) or _is_docstring(n):
            akhir_sebelum = n.end_lineno
            continue
        nama = _nama(n)
        if nama and nama in posisi_lama:
            a, b = _span(n, lb)
            ganti.append((posisi_lama[nama], lb[a:b]))
        else:
            seg = lb[akhir_sebelum:n.end_lineno]
            while seg and not seg[0].strip():
                seg.pop(0)
            tambahan.append(seg)
        akhir_sebelum = n.end_lineno

    for (a, b), isi in sorted(ganti, key=lambda x: -x[0][0]):
        lines[a:b] = isi
    teks = "\n".join(lines).rstrip()
    for seg in tambahan:
        teks += ("\n\n\n" if teks else "") + "\n".join(seg)
    teks += "\n"
    impor = [n for n in tb.body if _is_import(n)]
    if impor:
        teks = gabung_import(teks, impor)
    return rapikan(teks)


def hapus(lama: str, nama_nama: list[str]) -> str:
    lines = lama.splitlines()
    spans = [_span(n, lines) for n in ast.parse(lama).body if _nama(n) in nama_nama]
    if len(spans) != len(nama_nama):
        raise SystemExit(f"hapus: tidak semua nama ditemukan: {nama_nama}")
    for a, b in sorted(spans, reverse=True):
        del lines[a:b]
    return rapikan("\n".join(lines) + "\n")


def rapikan(teks: str) -> str:
    return re.sub(r"\n{4,}", "\n\n\n", teks).strip("\n") + "\n"


# ----------------------------------------------------------------------------- bangun _kunci
def bangun() -> list[int]:
    teks = LAB.read_text(encoding="utf-8")
    ops = baca_operasi(teks)
    langkah_ada = sorted({int(m.group(1)) for b in teks.splitlines() if (m := RE_LANGKAH.match(b))} - {0})
    files: dict[str, str] = {"app/__init__.py": ""}
    if KUNCI.exists():
        shutil.rmtree(KUNCI)
    for n in langkah_ada:
        for (_, op, path, isi) in (o for o in ops if o[0] == n):
            if op == "penuh":
                files[path] = isi
            elif op == "tambah":
                files[path] = tambah(files.get(path, ""), isi)
            else:
                files[path] = hapus(files[path], [x.strip() for x in isi.split(",")])
            if path.endswith(".py"):
                try:
                    ast.parse(files[path])
                except SyntaxError as e:
                    raise SystemExit(f"Langkah {n}, {path}: SyntaxError {e}")
        tujuan = KUNCI / f"langkah-{n:02d}"
        for path, isi in files.items():
            f = tujuan / path
            f.parent.mkdir(parents=True, exist_ok=True)
            if path == "langgraph.json":
                isi = isi.replace('"env": ".env"', '"env": "../../.env"')
            f.write_text(isi, encoding="utf-8")
    (KUNCI / "README.md").write_text(
        "# Kunci jawaban per langkah\n\n"
        "Folder ini DIBANGKITKAN dari blok kode di LAB.md (`uv run python -m lab.kunci`). Jangan diedit manual.\n\n"
        "- `langkah-NN/app/` = isi app/ setelah Langkah NN selesai.\n"
        "- Jalankan kunci: `KUNCI=5 uv run lihat \"Proses klaim KLM-001\"`, `KUNCI=5 uv run cek 5`.\n"
        "- Bandingkan dengan kodemu: `diff -ru _kunci/langkah-05/app app`.\n",
        encoding="utf-8",
    )
    print(f"_kunci/ dibangun: langkah {langkah_ada}")
    return langkah_ada


def _test_untuk(n: int) -> list[str]:
    return [str(f) for f in sorted((ROOT / "tests").glob("test_langkah*.py"))
            if int(f.stem.removeprefix("test_langkah")[:2]) <= n]


def uji(langkah: list[int]) -> bool:
    def satu(n: int):
        tests = _test_untuk(n)
        if not tests:
            return n, True, "(tidak ada test)"
        env = {**os.environ, "KUNCI": str(n)}
        env.pop("LLM_API_KEY", None)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-x", *tests], cwd=ROOT, env=env,
                           capture_output=True, text=True, timeout=600)
        return n, r.returncode == 0, (r.stdout.strip().splitlines() or ["?"])[-1] if r.returncode == 0 else r.stdout[-3000:]

    ok = True
    with ThreadPoolExecutor(max_workers=4) as ex:
        for n, lulus, info in ex.map(satu, langkah):
            print(f"langkah {n:2d}: {'LULUS' if lulus else 'GAGAL'}  {info if lulus else ''}")
            if not lulus:
                ok = False
                print(info)
    return ok


# ----------------------------------------------------------------------------- isi contoh output
def _jalankan_perintah(n: int, perintah: str, runtime: str) -> str:
    keluaran = []
    for cmd in perintah.split(" && "):
        stdin = None
        if cmd.startswith("printf ") and " | " in cmd:
            kiri, kanan = cmd.split(" | ", 1)
            stdin = shlex.split(kiri)[1].encode().decode("unicode_escape").encode("latin-1").decode("utf-8")
            token = shlex.split(kanan)
        else:
            token = shlex.split(cmd)
        env = {**os.environ, "KUNCI": str(n), "RUNTIME_DIR": runtime, "LLM_MODE": "mock", "PYTHONIOENCODING": "utf-8",
               "PYTHONDONTWRITEBYTECODE": "1", "EMBEDDING": "hash", "MAX_REVISI": "2", "MOCK_DRAF_PERTAMA_KURANG": "1",
               "HR_GAGAL_N_KALI": "0", "CRASH_SETELAH_BAYAR": "0", "COLUMNS": "120"}
        env.pop("LLM_API_KEY", None)
        while token and re.match(r"^[A-Z_]+=", token[0]):
            k, v = token.pop(0).split("=", 1)
            env[k] = v
        if token[:3] == ["uv", "run", "lihat"]:
            argv = [sys.executable, "-m", "lab.lihat", *token[3:]]
        elif token[:3] == ["uv", "run", "chat"]:
            argv = [sys.executable, "-m", "lab.chat", *token[3:]]
        elif token[:3] == ["uv", "run", "cek"]:
            argv = [sys.executable, "-m", "lab.cek", *token[3:]]
        elif token[:3] == ["uv", "run", "python"]:
            argv = [sys.executable, *token[3:]]
            env["PYTHONPATH"] = str(KUNCI / f"langkah-{n:02d}")
        else:
            raise SystemExit(f"perintah output tidak dikenal: {cmd}")
        cwd = KUNCI / f"langkah-{n:02d}" if argv[1:2] != ["-m"] or argv[2] not in ("lab.lihat", "lab.cek", "lab.chat") else ROOT
        r = subprocess.run(argv, cwd=cwd, env=env, input=stdin, capture_output=True, text=True, timeout=300)
        teks = (r.stdout + r.stderr).rstrip()
        keluaran.append(f"$ {cmd}\n{teks}")
    hasil = "\n\n".join(keluaran)
    if "KUNCI=" not in perintah:
        hasil = re.sub(r"_kunci/langkah-\d+/app \(kunci jawaban\)", "app/ (kode kamu)", hasil)
    hasil = re.sub(r"\bt-[0-9a-f]{6}\b", "t-a1b2c3", hasil)
    hasil = hasil.replace(str(ROOT) + "/", "").replace(runtime, "runtime")
    return hasil


def isi_output() -> None:
    teks = LAB.read_text(encoding="utf-8")
    baris = teks.splitlines()
    out, i = [], 0
    while i < len(baris):
        m = RE_OUTPUT.match(baris[i].strip())
        out.append(baris[i])
        if not m:
            i += 1
            continue
        j = i + 1
        while baris[j].strip() != "<!-- /output -->":
            j += 1
        n, perintah, maks = int(m.group(1)), m.group(2), m.group(3)
        with tempfile.TemporaryDirectory() as rt:
            hasil = _jalankan_perintah(n, perintah, rt)
        b = hasil.splitlines()
        if maks and len(b) > int(maks):
            b = b[: int(maks)] + [f"… ({len(b) - int(maks)} baris berikutnya dipotong)"]
        out += ["```text", *b, "```", "<!-- /output -->"]
        print(f"output langkah {n}: {perintah[:60]} ({len(b)} baris)")
        i = j + 1
    LAB.write_text("\n".join(out) + "\n", encoding="utf-8")


def main() -> None:
    langkah = bangun()
    if "--uji" in sys.argv and not uji(langkah):
        raise SystemExit(1)
    if "--output" in sys.argv:
        isi_output()


if __name__ == "__main__":
    main()
