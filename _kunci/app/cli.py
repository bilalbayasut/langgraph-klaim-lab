"""CLI latihan. State disimpan di SQLite, jadi `lanjut` bisa dijalankan dari proses baru.

  uv run python -m app.cli jalankan "Proses klaim KLM-001" --thread t1
  uv run python -m app.cli status   --thread t1
  uv run python -m app.cli lanjut   --thread t1 --aksi setujui --catatan "ok"
  uv run python -m app.cli lanjut   --thread t1              # lanjut tanpa jawaban (setelah crash)
  uv run python -m app.cli riwayat  --thread t1
  uv run python -m app.cli diagram
  uv run python -m app.cli pembayaran
"""

from __future__ import annotations

import argparse
import json
import uuid

from langgraph.types import Command

from app import tools
from app.graph import build_graph, buka_sqlite


def _config(thread: str) -> dict:
    return {"configurable": {"thread_id": thread}, "recursion_limit": 40}


def _jalankan_stream(graph, masukan, config) -> None:
    """stream_mode gabungan: 'updates' (node selesai) + 'custom' (progres dari get_stream_writer)."""
    for mode, chunk in graph.stream(masukan, config, stream_mode=["updates", "custom"]):
        if mode == "custom":
            print(f"   ⏳ {chunk['progres']}")
            continue
        for node, update in chunk.items():
            if node == "__interrupt__":
                print("⏸️  INTERRUPT: menunggu persetujuan atasan")
                continue
            for baris in (update or {}).get("log", []):
                print(f"➡️  {baris}")


def _cetak_status(graph, config) -> None:
    snap = graph.get_state(config)
    v = snap.values
    print(f"\nthread     : {config['configurable']['thread_id']}")
    print(f"next       : {snap.next}")
    print(f"status     : {v.get('status_akhir', '(belum selesai)')}")
    if v.get("keputusan"):
        k = v["keputusan"]
        print(f"keputusan  : {k['aksi']} | disetujui {tools.format_rupiah(k['total_disetujui'])}")
    if v.get("peringatan"):
        print(f"peringatan : {v['peringatan']}")
    if v.get("jawaban"):
        print(f"jawaban    : {v['jawaban']}")
    for intr in snap.interrupts:
        print("\n--- menunggu persetujuan ---")
        print(json.dumps(intr.value, ensure_ascii=False, indent=2))


def main() -> None:
    p = argparse.ArgumentParser(prog="app.cli")
    sub = p.add_subparsers(dest="cmd", required=True)
    j = sub.add_parser("jalankan"); j.add_argument("permintaan"); j.add_argument("--thread")
    lj = sub.add_parser("lanjut"); lj.add_argument("--thread", required=True); lj.add_argument("--aksi"); lj.add_argument("--catatan", default="")
    for nama in ("status", "riwayat"):
        sub.add_parser(nama).add_argument("--thread", required=True)
    sub.add_parser("diagram"); sub.add_parser("pembayaran")
    a = p.parse_args()

    if a.cmd == "pembayaran":
        print(json.dumps(tools.baca_ledger(), indent=2)); return
    graph = build_graph(buka_sqlite())
    if a.cmd == "diagram":
        print(graph.get_graph().draw_mermaid()); return

    thread = getattr(a, "thread", None) or f"t-{uuid.uuid4().hex[:6]}"
    config = _config(thread)
    if a.cmd == "jalankan":
        _jalankan_stream(graph, {"permintaan": a.permintaan}, config)
    elif a.cmd == "lanjut":
        masukan = Command(resume={"aksi": a.aksi, "catatan": a.catatan}) if a.aksi else None
        _jalankan_stream(graph, masukan, config)
    elif a.cmd == "riwayat":
        for i, snap in enumerate(graph.get_state_history(config)):
            print(f"{i:2d}. step={snap.metadata.get('step'):>3}  next={snap.next}  id={snap.config['configurable']['checkpoint_id'][:13]}…")
        return
    _cetak_status(graph, config)


if __name__ == "__main__":
    main()
