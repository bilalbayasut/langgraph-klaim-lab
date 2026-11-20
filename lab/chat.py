"""uv run chat: antarmuka terminal interaktif untuk graph di app/graph.py.

Ketik permintaan, dapatkan jawaban. Kalau graph berhenti di interrupt (Langkah 12), kamu ditanya
langsung sebagai atasan. Kode app/ dimuat ulang otomatis bila ada file yang berubah, jadi kamu bisa
mengedit kode lalu langsung mencoba lagi tanpa keluar.

  uv run chat                 mulai (jejak superstep ringkas)
  uv run chat --detail        tampilkan apa yang ditulis setiap node
  uv run chat --diam          hanya jawaban
  KUNCI=12 uv run chat        pakai kunci jawaban langkah 12

Perintah di dalam chat: /bantuan
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid

from dotenv import load_dotenv

from lab import lihat
from lab.kode import ROOT, kode_dir, label_kode, pasang_sys_path

BANTUAN = """\
Contoh permintaan:
  Proses klaim KLM-001          (KLM-001 s.d. KLM-005)
  Berapa batas biaya hotel per malam?
  halo
Perintah:
  /ringkas  /detail  /diam      ubah jejak superstep (sekarang: {mode})
  /thread                       thread terakhir (untuk uv run lihat --thread ... --riwayat)
  /lanjut [aksi] [catatan]      lanjutkan thread terakhir (misal setelah error / dijawab 'nanti')
  /gambar                       gambar graph
  /muat                         muat ulang kode app/ sekarang
  /keluar                       keluar (atau Ctrl+D)"""


def _rupiah(n) -> str:
    return "Rp" + f"{int(n):,}".replace(",", ".")


class Sesi:
    def __init__(self, mode: str) -> None:
        self.mode = mode
        self.graph = None
        self.cap_waktu: dict[str, float] = {}
        self.thread: str | None = None
        self.interaktif = sys.stdin.isatty()

    # ------------------------------------------------------------------ muat graph (dengan hot reload)
    def _file_app(self) -> dict[str, float]:
        d = kode_dir() / "app"
        return {str(f): f.stat().st_mtime for f in d.glob("*.py")} if d.exists() else {}

    def muat(self, paksa: bool = False) -> bool:
        sekarang = self._file_app()
        if self.graph is not None and not paksa and sekarang == self.cap_waktu:
            return True
        for nama in [m for m in sys.modules if m == "app" or m.startswith("app.")]:
            del sys.modules[nama]
        try:
            g = lihat._muat_graph()
        except SystemExit as e:
            print(e)
            return False
        except Exception as e:  # noqa: BLE001  (misalnya SyntaxError saat kode sedang diedit)
            print(f"✖ gagal memuat app/: {type(e).__name__}: {e}")
            return False
        if self.graph is not None:
            print("↻ kode app/ berubah, graph dimuat ulang")
        self.graph, self.cap_waktu = g, sekarang
        return True

    # ------------------------------------------------------------------ jalankan + jejak
    def jalankan(self, masukan, config: dict) -> bool:
        reducer = lihat._field_reducer(self.graph)
        tasks: dict[int, list[dict]] = {}
        ada_hasil: set[str] = set()
        try:
            for m, ev in self.graph.stream(masukan, config, stream_mode=["debug", "custom"]):
                if m == "custom":
                    if self.mode != "diam":
                        print(f"   📣 {ev.get('progres', ev) if isinstance(ev, dict) else ev}")
                    continue
                step, p = ev["step"], ev["payload"]
                if ev["type"] == "task":
                    tasks.setdefault(step, []).append(p)
                elif ev["type"] == "task_result":
                    ada_hasil.add(p["id"])
                    if self.mode == "detail" and not p.get("error") and not p.get("interrupts"):
                        print(f"   ✔ {p['name']} (superstep {step}) menulis:")
                        lihat._cetak_tulisan(p.get("result"), reducer, False, indent="       ")
                elif ev["type"] == "checkpoint" and step >= 1 and self.mode == "ringkas":
                    nama = [t["name"] + ("" if t["id"] in ada_hasil else " (tersimpan)") for t in tasks.get(step, [])]
                    isi = ", ".join(n if nama.count(n) == 1 else f"{n} x{nama.count(n)}" for n in dict.fromkeys(nama))
                    if isi:
                        print(f"   · superstep {step}: {isi}")
        except Exception as e:  # noqa: BLE001
            print(f"✖ ERROR: {type(e).__name__}: {e}")
            print("  Checkpoint terakhir tersimpan. Perbaiki kode (otomatis dimuat ulang), lalu ketik /lanjut")
            return False
        return True

    # ------------------------------------------------------------------ tampilkan jawaban
    def tampilkan(self, values: dict, memo_sudah_tampil: bool = False) -> None:
        k = values.get("keputusan")
        # 1. jawaban utama
        if values.get("jawaban"):
            sumber = f"   [sumber: {', '.join(values['sumber'])}]" if values.get("sumber") else ""
            print(f"🤖 {values['jawaban']}{sumber}")
        elif k:
            print(f"🤖 Keputusan {values.get('claim_id')}: {k['aksi']}")
        else:   # langkah awal: belum ada jawaban, tampilkan saja isi state
            lain = {kk: v for kk, v in values.items() if kk not in ("permintaan", "log", "hasil_item", "peringatan")}
            print("🤖 (graph belum menghasilkan jawaban; isi state:)")
            lihat._cetak_values(lain, indent="   ")
        # 2. rincian
        if k:
            print(f"   keputusan: {k['aksi']}, disetujui {_rupiah(k['total_disetujui'])} dari "
                  f"{_rupiah(k['total_diajukan'])} ({k['alasan']})")
            for h in k.get("rincian", []):
                print(f"     - {h['item_id']} {h['kategori']}: {h['status']} ({h['alasan']})")
        for w in values.get("peringatan") or []:
            print(f"   ⚠ {w}")
        if values.get("draf_memo") and self.mode != "diam" and not memo_sudah_tampil:
            print("   📝 memo:\n" + "\n".join("      " + b for b in values["draf_memo"].splitlines()))
        if values.get("pembayaran"):
            t = values["pembayaran"]
            print(f"   💸 transfer {t['ref']} {_rupiah(t['jumlah'])}"
                  + (" (duplikat, tidak ditransfer ulang)" if t.get("duplikat") else ""))

    # ------------------------------------------------------------------ satu giliran
    def proses(self, masukan, thread: str) -> None:
        if not self.muat():
            return
        self.thread = thread
        config = {"configurable": {"thread_id": thread}, "recursion_limit": 50}
        pernah_interrupt = False
        while True:
            if not self.jalankan(masukan, config):
                return
            snap = self.graph.get_state(config)
            if not snap.interrupts:
                self.tampilkan(snap.values, memo_sudah_tampil=pernah_interrupt)
                return
            pernah_interrupt = True
            masukan = self.tanya_atasan(snap)
            if masukan is None:
                print(f"   ⏸ ditunda. Lanjutkan nanti: /lanjut setujui   (thread {thread})")
                return

    def tanya_atasan(self, snap):
        from langgraph.types import Command

        for intr in snap.interrupts:
            v = intr.value
            if isinstance(v, dict) and "claim_id" in v:
                print(f"\n⏸  PERSETUJUAN ATASAN ({v.get('atasan', '-')})")
                print(f"   klaim {v['claim_id']} atas nama {v.get('karyawan', '-')}: {v.get('keputusan')} {v.get('total_disetujui')}")
                for w in v.get("peringatan") or []:
                    print(f"   ⚠ {w}")
                for msl in v.get("masalah_memo") or []:
                    print(f"   ✎ masalah memo: {msl}")
                print("   📝 memo:\n" + "\n".join("      " + b for b in str(v.get("memo", "")).splitlines()))
            else:
                print(f"\n⏸  INTERRUPT: {json.dumps(v, ensure_ascii=False, default=str)}")
        jawab = self._input("atasan [setujui | revisi <catatan> | tolak | nanti] > ").strip()
        if not jawab or jawab.lower() == "nanti":
            return None
        aksi, _, catatan = jawab.partition(" ")
        return Command(resume={"aksi": aksi, "catatan": catatan.strip()})

    def _input(self, prompt: str) -> str:
        teks = input(prompt)
        if not self.interaktif:          # input dari pipe: tampilkan supaya transkrip terbaca
            print(teks)
        return teks

    # ------------------------------------------------------------------ perintah /...
    def perintah(self, baris: str) -> bool:
        nama, _, arg = baris[1:].partition(" ")
        if nama in ("keluar", "exit", "quit", "q"):
            return False
        if nama in ("ringkas", "detail", "diam"):
            self.mode = nama
            print(f"   jejak superstep: {nama}")
        elif nama == "thread":
            print(f"   thread terakhir: {self.thread or '-'}"
                  + (f"   (uv run lihat --thread {self.thread} --riwayat)" if self.thread else ""))
        elif nama == "lanjut":
            if not self.thread:
                print("   belum ada thread.")
            else:
                from langgraph.types import Command

                aksi, _, catatan = arg.strip().partition(" ")
                self.proses(Command(resume={"aksi": aksi, "catatan": catatan}) if aksi else None, self.thread)
        elif nama == "gambar":
            if self.muat():
                print(self.graph.get_graph().draw_ascii())
        elif nama == "muat":
            self.muat(paksa=True)
        else:
            print(BANTUAN.format(mode=self.mode))
        return True


def main() -> None:
    p = argparse.ArgumentParser(prog="chat", description="Chat terminal dengan graph app/.")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--detail", action="store_true", help="tampilkan tulisan setiap node")
    g.add_argument("--diam", action="store_true", help="hanya jawaban")
    a = p.parse_args()

    load_dotenv(ROOT / ".env")
    pasang_sys_path()
    try:
        import readline  # noqa: F401  (panah atas/bawah untuk riwayat input)
    except ImportError:
        pass
    sesi = Sesi("detail" if a.detail else "diam" if a.diam else "ringkas")
    print(f"💬 chat klaim | kode: {label_kode()} | LLM_MODE={os.getenv('LLM_MODE', 'mock')} | /bantuan untuk bantuan")
    if not sesi.muat():
        return
    while True:
        try:
            baris = sesi._input("\nkamu > ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not baris:
            continue
        if baris.startswith("/"):
            if not sesi.perintah(baris):
                break
            continue
        try:
            sesi.proses({"permintaan": baris}, f"chat-{uuid.uuid4().hex[:6]}")
        except KeyboardInterrupt:
            print("\n   (dibatalkan)")
    print("sampai jumpa 👋")


if __name__ == "__main__":
    main()
