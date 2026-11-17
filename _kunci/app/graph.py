"""Perakitan graph klaim.

START -> router
router --klaim--------> muat_klaim
router --kebijakan----> jawab_kebijakan -> END
router --klarifikasi--> klarifikasi -> END
muat_klaim -> cek_karyawan                        (paralel, dengan RetryPolicy)
muat_klaim --Send per item--> periksa_item xN      (map)
[cek_karyawan + periksa_item] -> putuskan          (join / barrier, reduce lewat operator.add)
putuskan -> tulis_memo -> nilai_memo
nilai_memo --belum lolos & masih ada jatah--> tulis_memo   (loop evaluator-optimizer)
nilai_memo --tolak--> selesai
nilai_memo --perlu atasan--> persetujuan                    (interrupt)
nilai_memo --auto-approve--> bayar
persetujuan --setujui--> bayar -> selesai -> END
persetujuan --revisi---> tulis_memo
persetujuan --tolak----> selesai
"""

from __future__ import annotations

import sqlite3

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import RetryPolicy

from app.config import get_settings
from app.nodes import (
    bayar, cek_karyawan, fan_out_item, jawab_kebijakan, klarifikasi, muat_klaim, nilai_memo, periksa_item,
    persetujuan, putuskan, router, rute_setelah_nilai, rute_setelah_persetujuan, rute_setelah_router, selesai,
    tulis_memo,
)
from app.state import ItemTask, KlaimState
from app.tools import HRTimeoutError

HR_RETRY = RetryPolicy(
    max_attempts=4,          # 1 percobaan + 3 retry
    initial_interval=0.1,
    backoff_factor=2.0,      # 0.1s, 0.2s, 0.4s
    jitter=False,
    retry_on=HRTimeoutError,  # hanya error ini yang di-retry
)


def build_builder() -> StateGraph:
    g = StateGraph(KlaimState)
    g.add_node("router", router)
    g.add_node("klarifikasi", klarifikasi)
    g.add_node("jawab_kebijakan", jawab_kebijakan)
    g.add_node("muat_klaim", muat_klaim)
    g.add_node("cek_karyawan", cek_karyawan, retry_policy=HR_RETRY)
    g.add_node("periksa_item", periksa_item, input_schema=ItemTask)
    g.add_node("putuskan", putuskan)
    g.add_node("tulis_memo", tulis_memo)
    g.add_node("nilai_memo", nilai_memo)
    g.add_node("persetujuan", persetujuan)
    g.add_node("bayar", bayar)
    g.add_node("selesai", selesai)

    g.add_edge(START, "router")
    g.add_conditional_edges("router", rute_setelah_router, ["muat_klaim", "jawab_kebijakan", "klarifikasi"])
    g.add_edge("klarifikasi", END)
    g.add_edge("jawab_kebijakan", END)

    g.add_edge("muat_klaim", "cek_karyawan")
    g.add_conditional_edges("muat_klaim", fan_out_item, ["periksa_item"])
    g.add_edge(["cek_karyawan", "periksa_item"], "putuskan")      # tunggu SEMUA cabang

    g.add_edge("putuskan", "tulis_memo")
    g.add_edge("tulis_memo", "nilai_memo")
    g.add_conditional_edges("nilai_memo", rute_setelah_nilai, ["tulis_memo", "persetujuan", "bayar", "selesai"])
    g.add_conditional_edges("persetujuan", rute_setelah_persetujuan, ["bayar", "tulis_memo", "selesai"])
    g.add_edge("bayar", "selesai")
    g.add_edge("selesai", END)
    return g


def build_graph(checkpointer: BaseCheckpointSaver | None = None):
    """Untuk kode kita sendiri (CLI, test). Tanpa checkpointer, interrupt tidak bisa dipakai."""
    return build_builder().compile(checkpointer=checkpointer or InMemorySaver())


def buka_sqlite(path: str | None = None) -> SqliteSaver:
    """Checkpointer persisten: state bertahan walau proses mati."""
    conn = sqlite3.connect(path or str(get_settings().runtime_dir / "checkpoints.db"), check_same_thread=False)
    saver = SqliteSaver(conn)
    saver.setup()
    return saver


# Untuk LangGraph Studio / `langgraph dev`: TANPA checkpointer, karena server menyediakan persistence sendiri.
graph = build_builder().compile()
