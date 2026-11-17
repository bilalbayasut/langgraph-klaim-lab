"""Tiga pola orkestrasi tambahan, di domain klaim yang sama (tanpa LLM supaya strukturnya yang terlihat).

Graph utama (graph.py) sudah memakai: routing, parallelization, orchestrator-workers (Send), evaluator-optimizer.
File ini melengkapi:
1. supervisor        : satu pengendali memilih worker berikutnya; worker SELALU kembali ke supervisor.
2. handoff           : agent menyerahkan kendali ke agent lain dengan Command(goto=...), tanpa pengendali pusat.
3. planner-executor  : planner menyusun rencana di awal, executor menjalankan satu langkah per putaran.
Di sistem nyata, keputusan "siapa/apa berikutnya" biasanya dibuat LLM.
"""

from __future__ import annotations

import operator
from typing import Annotated, Literal, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from app import tools


def gabung_dict(a: dict, b: dict) -> dict:
    return {**a, **b}


# ====================================================================== 1. supervisor
class SupervisorState(TypedDict, total=False):
    claim_id: str
    temuan: Annotated[dict, gabung_dict]
    log: Annotated[list[str], operator.add]


WORKER = ["cek_struk", "cek_anggaran", "tulis_ringkasan"]


def supervisor(state: SupervisorState) -> Command[Literal["cek_struk", "cek_anggaran", "tulis_ringkasan", "__end__"]]:
    sisa = [w for w in WORKER if w not in state.get("temuan", {})]
    tujuan = sisa[0] if sisa else END
    return Command(goto=tujuan, update={"log": [f"supervisor -> {tujuan}"]})


def cek_struk(state: SupervisorState) -> dict:
    klaim = tools.ambil_klaim(state["claim_id"])
    tanpa = [it["item_id"] for it in klaim["item"] if not it["ada_struk"]]
    return {"temuan": {"cek_struk": f"{len(tanpa)} item tanpa struk {tanpa}"}}


def cek_anggaran(state: SupervisorState) -> dict:
    klaim = tools.ambil_klaim(state["claim_id"])
    profil = tools.ambil_profil_karyawan(klaim["karyawan_id"])
    total = sum(it["jumlah"] for it in klaim["item"])
    return {"temuan": {"cek_anggaran": f"diajukan {tools.format_rupiah(total)}, sisa {tools.format_rupiah(profil['sisa_anggaran'])}"}}


def tulis_ringkasan(state: SupervisorState) -> dict:
    t = state["temuan"]
    return {"temuan": {"tulis_ringkasan": f"{state['claim_id']}: {t['cek_struk']}; {t['cek_anggaran']}"}}


def build_supervisor():
    g = StateGraph(SupervisorState)
    g.add_node("supervisor", supervisor)
    for nama, fn in [("cek_struk", cek_struk), ("cek_anggaran", cek_anggaran), ("tulis_ringkasan", tulis_ringkasan)]:
        g.add_node(nama, fn)
        g.add_edge(nama, "supervisor")          # worker selalu kembali ke supervisor
    g.add_edge(START, "supervisor")
    return g.compile()


# ====================================================================== 2. handoff
class HandoffState(TypedDict, total=False):
    pesan: str
    jawaban: str
    log: Annotated[list[str], operator.add]


def resepsionis(state: HandoffState) -> Command[Literal["agen_keuangan", "agen_hr"]]:
    tujuan = "agen_hr" if any(k in state["pesan"].lower() for k in ("cuti", "gaji", "anggaran")) else "agen_keuangan"
    return Command(goto=tujuan, update={"log": [f"resepsionis -> {tujuan}"]})


def agen_keuangan(state: HandoffState) -> Command[Literal["agen_hr", "__end__"]]:
    if "anggaran" in state["pesan"].lower():           # bukan wewenang keuangan: serahkan ke HR
        return Command(goto="agen_hr", update={"log": ["agen_keuangan -> agen_hr"]})
    return Command(goto=END, update={"jawaban": "Keuangan: klaim diproses maksimal 3 hari kerja.", "log": ["agen_keuangan selesai"]})


def agen_hr(state: HandoffState) -> dict:
    return {"jawaban": "HR: sisa anggaran dan cuti bisa dicek di portal karyawan.", "log": ["agen_hr selesai"]}


def build_handoff():
    g = StateGraph(HandoffState)
    g.add_node("resepsionis", resepsionis)
    g.add_node("agen_keuangan", agen_keuangan)
    g.add_node("agen_hr", agen_hr)
    g.add_edge(START, "resepsionis")
    g.add_edge("agen_hr", END)
    return g.compile()


# ====================================================================== 3. planner-executor
class PlanState(TypedDict, total=False):
    claim_id: str
    rencana: list[str]
    data: Annotated[dict, gabung_dict]
    log: Annotated[list[str], operator.add]


def planner(state: PlanState) -> dict:
    rencana = ["ambil_klaim", "periksa_semua_item", "hitung_total"]
    return {"rencana": rencana, "log": [f"planner: {rencana}"]}


def _langkah(nama: str, state: PlanState) -> dict:
    if nama == "ambil_klaim":
        return {"klaim": tools.ambil_klaim(state["claim_id"])}
    if nama == "periksa_semua_item":
        kb = tools.ambil_kebijakan()
        return {"hasil": [tools.periksa_item(it, kb) for it in state["data"]["klaim"]["item"]]}
    if nama == "hitung_total":
        return {"total_disetujui": sum(h["disetujui"] for h in state["data"]["hasil"])}
    raise ValueError(nama)


def executor(state: PlanState) -> dict:
    langkah, *sisa = state["rencana"]
    return {"data": _langkah(langkah, state), "rencana": sisa, "log": [f"executor: {langkah}"]}


def build_planner():
    g = StateGraph(PlanState)
    g.add_node("planner", planner)
    g.add_node("executor", executor)
    g.add_edge(START, "planner")
    g.add_edge("planner", "executor")
    g.add_conditional_edges("executor", lambda s: "executor" if s["rencana"] else END, ["executor", END])
    return g.compile()


supervisor_graph = build_supervisor()
handoff_graph = build_handoff()
planner_graph = build_planner()
