"""Jalankan graph klaim dari terminal dan lihat apa yang terjadi di setiap superstep.

    uv run app.py "Proses klaim KLM-002"     # satu permintaan
    uv run app.py --chat                     # mode interaktif: ketik permintaan berkali-kali
    uv run app.py --gambar
"""

from __future__ import annotations

import argparse
import json
import sys

from app.graph import build_graph


def ringkas(nilai, maks: int = 100) -> str:
    """Nilai apa pun -> teks JSON satu baris, dipotong kalau terlalu panjang."""
    teks = json.dumps(nilai, ensure_ascii=False, default=str)
    return teks if len(teks) <= maks else teks[: maks - 1] + "…"


def jalankan(graph, masukan, config=None) -> None:
    """Jalankan graph dan cetak apa yang ditulis setiap node, per superstep.

    stream_mode="debug" mengirim event setiap kali node mulai ("task") dan selesai ("task_result").
    Setiap event membawa nomor superstep di event["step"].
    """
    for event in graph.stream(masukan, config, stream_mode="debug"):
        if event["type"] != "task_result":           # hanya tampilkan node yang SELESAI
            continue
        node = event["payload"]                       # {"name": ..., "result": {...}, ...}
        print(f"superstep {event['step']}: {node['name']}")
        for field, nilai in (node["result"] or {}).items():
            print(f"    {field} = {ringkas(nilai)}")


def tanya(prompt: str) -> str:
    """input(), tapi Ctrl+D / Ctrl+C dianggap selesai (string kosong)."""
    try:
        teks = input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        return ""
    if not sys.stdin.isatty():         # input dari pipe/file: cetak ulang supaya keluarannya mudah dibaca
        print(teks)
    return teks


def chat(graph) -> None:
    """Mode interaktif: ketik permintaan, Enter, lihat superstep-nya, ulangi. Enter kosong = keluar."""
    print("Mode chat. Ketik permintaan lalu Enter. Enter kosong atau Ctrl+D untuk keluar.")
    while teks := tanya("\nkamu> "):
        jalankan(graph, {"permintaan": teks})


def main() -> None:
    parser = argparse.ArgumentParser(description="Jalankan graph klaim.")
    parser.add_argument("permintaan", nargs="?", help='misal: "Proses klaim KLM-002"')
    parser.add_argument("--gambar", action="store_true", help="gambar graph, lalu keluar")
    parser.add_argument("--chat", action="store_true", help="mode interaktif: ketik permintaan berkali-kali")
    args = parser.parse_args()

    graph = build_graph()
    if args.gambar:
        print(graph.get_graph().draw_ascii())
        return
    if args.chat:
        chat(graph)
        return
    if not args.permintaan:
        parser.error('isi permintaan, misal: uv run app.py "Proses klaim KLM-002"')
    jalankan(graph, {"permintaan": args.permintaan})


if __name__ == "__main__":
    main()
