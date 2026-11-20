"""uv run lihat: jalankan graph di app/graph.py dan tampilkan apa yang terjadi di TIAP SUPERSTEP.

Alat bantu lab (kamu tidak perlu menulis file ini, tapi silakan dibaca di Langkah 14).

  uv run lihat "Proses klaim KLM-002"                 jalankan dengan thread baru
  uv run lihat "Proses klaim KLM-001" --thread t1     pakai thread tertentu
  uv run lihat --thread t1 --lanjut setujui           jawab interrupt (setujui / revisi / tolak)
  uv run lihat --thread t1 --lanjut                   lanjut tanpa jawaban (misal setelah crash)
  uv run lihat --thread t1 --status                   state terakhir thread
  uv run lihat --thread t1 --riwayat                  semua checkpoint thread (time travel)
  uv run lihat --thread t1 --dari <checkpoint_id>     jalankan ulang dari checkpoint lama (fork)
  uv run lihat "..." --lengkap                        tampilkan state lengkap di setiap superstep
  uv run lihat "..." --ringkas                        satu baris per superstep
  uv run lihat "..." --mode updates                   cetak stream mentah (updates/values/custom/debug/messages)
  uv run lihat --gambar                               gambar graph (ASCII + Mermaid)

KUNCI=5 uv run lihat ...   -> menjalankan kunci jawaban langkah 5 (bukan app/ milikmu)

State disimpan di runtime/lihat.db (SQLite), jadi --lanjut/--status/--riwayat bisa dari proses baru.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import traceback
import uuid
from pathlib import Path

from dotenv import load_dotenv

from lab.kode import ROOT, label_kode, pasang_sys_path

GARIS = "━" * 64


def _json(v) -> str:
    return json.dumps(v, ensure_ascii=False, default=str)


def _ringkas(v, n: int = 96) -> str:
    s = _json(v)
    return s if len(s) <= n else s[: n - 1] + "…"


def _runtime_dir() -> Path:
    d = Path(os.getenv("RUNTIME_DIR", "./runtime"))
    d = d if d.is_absolute() else ROOT / d
    d.mkdir(parents=True, exist_ok=True)
    return d


def _muat_graph(dengan_checkpointer: bool = True):
    pasang_sys_path()
    try:
        import app.graph as modul
    except ModuleNotFoundError as e:
        if e.name in ("app", "app.graph"):
            raise SystemExit("❌ app/graph.py belum ada. Kerjakan Langkah 1 di LAB.md dulu.")
        raise
    if not hasattr(modul, "build_graph"):
        raise SystemExit("❌ app/graph.py belum punya fungsi build_graph(checkpointer=None). Lihat Langkah 1.")
    if not dengan_checkpointer:
        return modul.build_graph()
    from langgraph.checkpoint.sqlite import SqliteSaver

    conn = sqlite3.connect(str(_runtime_dir() / "lihat.db"), check_same_thread=False)
    saver = SqliteSaver(conn)
    saver.setup()
    return modul.build_graph(checkpointer=saver)


def _field_reducer(graph) -> set[str]:
    """Field state yang punya reducer (misal operator.add): pembaruannya DIGABUNG, bukan ditimpa."""
    return {n for n, ch in graph.channels.items() if type(ch).__name__ == "BinaryOperatorAggregate"}


def _cetak_tulisan(update, reducer: set[str], lengkap: bool, indent: str = "       ") -> None:
    if not update:
        print(f"{indent}(tidak menulis apa pun ke state)")
        return
    if not isinstance(update, dict):
        print(f"{indent}{_ringkas(update)}")
        return
    lebar = max(len(k) for k in update)
    for k, v in update.items():
        op = "+=" if k in reducer else "= "
        nilai = json.dumps(v, ensure_ascii=False, default=str, indent=2) if lengkap else _ringkas(v)
        nilai = nilai.replace("\n", "\n" + indent + " " * (lebar + 4))
        print(f"{indent}{k:<{lebar}} {op} {nilai}")


def _cetak_values(values: dict, indent: str = "   ") -> None:
    if not values:
        print(f"{indent}(state kosong)")
        return
    lebar = max(len(k) for k in values)
    for k, v in values.items():
        print(f"{indent}{k:<{lebar}} : {_ringkas(v, 100)}")


def _jalankan(graph, masukan, config: dict, lengkap: bool, ringkas: bool = False) -> None:
    """Stream mode 'debug' memberi 3 jenis event per superstep: task (mulai), task_result (selesai), checkpoint."""
    if ringkas:
        return _jalankan_ringkas(graph, masukan, config)
    reducer = _field_reducer(graph)
    langkah_tercetak: set[int] = set()
    tasks_per_step: dict[int, list[dict]] = {}
    ada_hasil: set[str] = set()
    step_terakhir = None
    try:
        for mode, ev in graph.stream(masukan, config, stream_mode=["debug", "custom"]):
            if mode == "custom":
                print(f"   📣 custom: {_ringkas(ev)}")
                continue
            jenis, step, p = ev["type"], ev["step"], ev["payload"]
            step_terakhir = step

            if jenis == "task":
                tasks_per_step.setdefault(step, []).append(p)
                if step not in langkah_tercetak:
                    langkah_tercetak.add(step)
                    print(f"\n{GARIS}\n superstep {step}")
                kirim = "__pregel_push" in p.get("triggers", ())
                sumber = f"  (via Send, input: {_ringkas(p['input'], 70)})" if kirim else ""
                print(f"   ▶ mulai   {p['name']}{sumber}")

            elif jenis == "task_result":
                ada_hasil.add(p["id"])
                if p.get("error"):
                    print(f"   ✖ ERROR   {p['name']}: {p['error']}")
                elif p.get("interrupts"):
                    print(f"   ⏸ BERHENTI {p['name']} (memanggil interrupt)")
                else:
                    print(f"   ✔ selesai {p['name']}, menulis ke state:")
                    _cetak_tulisan(p.get("result"), reducer, lengkap)

            elif jenis == "checkpoint":
                if step < 0:
                    continue
                nxt = list(p.get("next") or [])
                if step not in langkah_tercetak:
                    langkah_tercetak.add(step)
                    judul = " (input masuk ke state)" if step == 0 else " (checkpoint dimuat, lanjut dari sini)"
                    print(f"\n{GARIS}\n superstep {step}{judul}")
                    _cetak_values(p.get("values", {}))
                for t in tasks_per_step.get(step, []):
                    if t["id"] not in ada_hasil:
                        print(f"   ↺ {t['name']}: TIDAK dijalankan ulang, hasilnya sudah tersimpan dari percobaan sebelumnya")
                paralel = [t["name"] for t in tasks_per_step.get(step, [])]
                if len(paralel) > 1:
                    print(f"   ⇉ {len(paralel)} task jalan BERSAMAAN di superstep ini: {', '.join(paralel)}")
                if lengkap and step > 0:
                    print("   📦 state setelah superstep ini:")
                    _cetak_values(p.get("values", {}), indent="       ")
                print(f"   ⏭  berikutnya: {', '.join(nxt) if nxt else '(tidak ada, graph selesai)'}")
    except Exception as e:  # noqa: BLE001
        print(f"\n✖ ERROR di superstep {step_terakhir}: {type(e).__name__}: {e}")
        if os.getenv("LIHAT_TRACEBACK") == "1":
            traceback.print_exc()
        else:
            print("   (traceback lengkap: tambahkan LIHAT_TRACEBACK=1 di depan perintah)")
        t = config["configurable"]["thread_id"]
        print(f"   Checkpoint terakhir tetap tersimpan. Setelah kode diperbaiki: uv run lihat --thread {t} --lanjut")
        raise SystemExit(1)
    _ringkasan_akhir(graph, config)


def _jalankan_ringkas(graph, masukan, config: dict) -> None:
    """Satu baris per superstep: node apa saja yang jalan dan ke mana berikutnya."""
    tasks: dict[int, list[dict]] = {}
    ada_hasil: set[str] = set()
    step = None
    try:
        for mode, ev in graph.stream(masukan, config, stream_mode=["debug", "custom"]):
            if mode == "custom":
                print(f"   📣 {_ringkas(ev)}")
                continue
            step, p = ev["step"], ev["payload"]
            if ev["type"] == "task":
                tasks.setdefault(step, []).append(p)
            elif ev["type"] == "task_result":
                ada_hasil.add(p["id"])
            if ev["type"] == "task_result" and p.get("error"):
                print(f"   ✖ ERROR di {p['name']}: {p['error']}")
            elif ev["type"] == "task_result" and p.get("interrupts"):
                print(f"   ⏸ {p['name']} memanggil interrupt")
            elif ev["type"] == "checkpoint" and step >= 0:
                nama = [t["name"] + ("" if t["id"] in ada_hasil else " (tersimpan)") for t in tasks.get(step, [])]
                isi = ", ".join(n if nama.count(n) == 1 else f"{n} x{nama.count(n)}" for n in dict.fromkeys(nama))
                if not isi:
                    isi = "(input)" if step == 0 else "(checkpoint dimuat)"
                nxt = ", ".join(p.get("next") or []) or "END"
                print(f" superstep {step:>2}: {isi:<44} -> {nxt}")
    except Exception as e:  # noqa: BLE001
        print(f"\n✖ ERROR di superstep {step}: {type(e).__name__}: {e}")
        t = config["configurable"]["thread_id"]
        print(f"   Checkpoint terakhir tetap tersimpan. Setelah kode diperbaiki: uv run lihat --thread {t} --lanjut")
        raise SystemExit(1)
    snap = graph.get_state(config)
    t = config["configurable"]["thread_id"]
    if snap.interrupts:
        print(f" ⏸  berhenti di {', '.join(snap.next)} menunggu jawaban (uv run lihat --thread {t} --lanjut setujui)")
    else:
        status = snap.values.get("status_akhir")
        print(" ✅ graph selesai" + (f", status_akhir={status}" if status else ""))


def _ringkasan_akhir(graph, config: dict) -> None:
    snap = graph.get_state(config)
    t = config["configurable"]["thread_id"]
    print(f"\n{'═' * 64}")
    if snap.interrupts:
        print(f" ⏸  graph BERHENTI menunggu jawaban manusia di node: {', '.join(snap.next)}")
        print(" Isi interrupt (yang ditunjukkan ke manusia):")
        for intr in snap.interrupts:
            print(json.dumps(intr.value, ensure_ascii=False, indent=2, default=str))
        print(f"\n Lanjutkan:  uv run lihat --thread {t} --lanjut setujui")
        print(f"             uv run lihat --thread {t} --lanjut revisi --catatan \"...\"")
        print(f"             uv run lihat --thread {t} --lanjut tolak")
        return
    if snap.next:
        print(f" ⏸  graph berhenti sebelum: {', '.join(snap.next)}  (lanjut: uv run lihat --thread {t} --lanjut)")
    else:
        print(f" ✅ graph selesai di superstep {snap.metadata.get('step', '?')}. State akhir:")
    _cetak_values(snap.values)
    print(f"\n thread: {t}   (riwayat: uv run lihat --thread {t} --riwayat)")


def _status(graph, config: dict) -> None:
    snap = graph.get_state(config)
    if not snap.values and not snap.next:
        raise SystemExit(f"Thread {config['configurable']['thread_id']} belum punya checkpoint.")
    print(f"thread  : {config['configurable']['thread_id']}")
    print(f"step    : {snap.metadata.get('step')}")
    print(f"next    : {snap.next}")
    print("values  :")
    _cetak_values(snap.values)
    for intr in snap.interrupts:
        print("interrupt:")
        print(json.dumps(intr.value, ensure_ascii=False, indent=2, default=str))


def _riwayat(graph, config: dict) -> None:
    snaps = list(graph.get_state_history(config))
    if not snaps:
        raise SystemExit("Thread ini belum punya checkpoint.")
    print(f"{len(snaps)} checkpoint, terbaru di atas. Jalankan ulang dari salah satunya: --dari <checkpoint_id>\n")
    print(f"{'step':>4}  {'sumber':<7} {'next':<30} checkpoint_id")
    for s in snaps:
        nxt = ", ".join(s.next) if s.next else "-"
        print(f"{s.metadata.get('step'):>4}  {s.metadata.get('source', ''):<7} {nxt[:30]:<30} "
              f"{s.config['configurable']['checkpoint_id']}")


def _stream_mentah(graph, masukan, config: dict, mode: str) -> None:
    modes = [m.strip() for m in mode.split(",") if m.strip()]
    arg = modes if len(modes) > 1 else modes[0]
    print(f"for chunk in graph.stream(input, config, stream_mode={arg!r}):\n")
    for item in graph.stream(masukan, config, stream_mode=arg):
        m, chunk = item if len(modes) > 1 else (modes[0], item)
        if m == "messages":
            pesan, _meta = chunk
            if pesan.content:
                print(pesan.content, end="", flush=True)
            continue
        print(_ringkas(item, 300))
    print()


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="lihat", description="Jalankan graph app/ dan lihat tiap superstep.")
    p.add_argument("permintaan", nargs="?", help='misal: "Proses klaim KLM-002"')
    p.add_argument("--thread", help="thread_id (default: thread baru)")
    p.add_argument("--lanjut", nargs="?", const="", metavar="AKSI", help="lanjutkan thread; AKSI menjawab interrupt")
    p.add_argument("--catatan", default="", help="catatan untuk --lanjut")
    p.add_argument("--status", action="store_true", help="state terakhir thread")
    p.add_argument("--riwayat", action="store_true", help="semua checkpoint thread")
    p.add_argument("--dari", metavar="CHECKPOINT_ID", help="jalankan ulang dari checkpoint lama")
    p.add_argument("--ubah", metavar="JSON", help="bersama --dari: ubah state dulu, misal '{\"claim_id\": \"KLM-003\"}'")
    p.add_argument("--lengkap", action="store_true", help="tampilkan isi lengkap")
    p.add_argument("--ringkas", action="store_true", help="satu baris per superstep")
    p.add_argument("--mode", help="cetak stream mentah dengan stream_mode ini (pisahkan dengan koma)")
    p.add_argument("--gambar", action="store_true", help="gambar graph (ASCII + Mermaid)")
    a = p.parse_args(sys.argv[1:] if argv is None else argv)

    load_dotenv(ROOT / ".env")
    print(f"📂 kode: {label_kode()}   LLM_MODE={os.getenv('LLM_MODE', 'mock')}")

    if a.gambar:
        g = _muat_graph(dengan_checkpointer=False).get_graph()
        print(g.draw_ascii())
        print("\nMermaid (tempel di https://mermaid.live untuk gambar yang lebih rapi):\n")
        print(g.draw_mermaid())
        return

    graph = _muat_graph()
    if (a.status or a.riwayat or a.dari or a.lanjut is not None) and not a.thread:
        raise SystemExit("Perintah ini butuh --thread <id>.")
    thread = a.thread or f"t-{uuid.uuid4().hex[:6]}"
    config = {"configurable": {"thread_id": thread}, "recursion_limit": 50}

    if a.status:
        return _status(graph, config)
    if a.riwayat:
        return _riwayat(graph, config)

    if a.dari:
        cfg = {"configurable": {"thread_id": thread, "checkpoint_id": a.dari}}
        if a.ubah:
            cfg = graph.update_state(cfg, json.loads(a.ubah))
            print(f"✎ state diubah lewat update_state, checkpoint baru: {cfg['configurable']['checkpoint_id']}")
        print(f"↩ menjalankan ulang thread {thread} dari checkpoint itu (membuat cabang baru di riwayat)")
        return _jalankan(graph, None, {**cfg, "recursion_limit": 50}, a.lengkap, a.ringkas)

    if a.lanjut is not None:
        from langgraph.types import Command

        masukan = Command(resume={"aksi": a.lanjut, "catatan": a.catatan}) if a.lanjut else None
        print(f"▶ melanjutkan thread {thread}" + (f" dengan jawaban {a.lanjut!r}" if a.lanjut else " (tanpa jawaban baru)"))
    else:
        if not a.permintaan:
            p.print_help()
            raise SystemExit(2)
        if graph.get_state(config).values:
            print(f"⚠ thread {thread} sudah punya state. Input baru dijalankan DI ATAS state lama "
                  "(field ber-reducer seperti log akan menumpuk).")
        masukan = {"permintaan": a.permintaan}
        print(f"▶ thread {thread}, input: {_json(masukan)}")

    if a.mode:
        return _stream_mentah(graph, masukan, config, a.mode)
    _jalankan(graph, masukan, config, a.lengkap, a.ringkas)


if __name__ == "__main__":
    main()
