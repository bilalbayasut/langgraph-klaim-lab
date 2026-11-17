"""State graph (TypedDict + reducer) dan skema output LLM (Pydantic)."""

from __future__ import annotations

import operator
from typing import Annotated, Literal, TypedDict

from pydantic import BaseModel, Field

Rute = Literal["klaim", "kebijakan", "klarifikasi"]


class KlaimState(TypedDict, total=False):
    # input
    permintaan: str
    # routing
    rute: Rute
    claim_id: str | None
    # data
    klaim: dict
    profil: dict
    # map-reduce: banyak periksa_item menulis bersamaan -> WAJIB reducer
    hasil_item: Annotated[list[dict], operator.add]
    # keputusan (aturan kode, bukan LLM)
    keputusan: dict
    # loop evaluator-optimizer
    draf_memo: str
    jumlah_draf: int
    penilaian: dict
    # human-in-the-loop
    persetujuan: dict
    # hasil akhir
    pembayaran: dict
    status_akhir: str
    jawaban: str
    sumber: list[str]
    # jejak (append-only dari semua node)
    log: Annotated[list[str], operator.add]
    peringatan: Annotated[list[str], operator.add]


class ItemTask(TypedDict):
    """Input untuk periksa_item yang dikirim lewat Send (satu per item)."""

    claim_id: str
    item: dict


class RuteDecision(BaseModel):
    rute: Rute = Field(description="klaim (proses klaim), kebijakan (tanya aturan), atau klarifikasi")
    claim_id: str | None = Field(default=None, description="Nomor klaim format KLM-XXX bila disebut")
    alasan: str = Field(description="Alasan singkat")


class PenilaianMemo(BaseModel):
    skor: int = Field(ge=1, le=10, description="Kualitas memo 1-10")
    masalah: list[str] = Field(default_factory=list, description="Hal spesifik yang harus diperbaiki")


class JawabanKebijakan(BaseModel):
    jawaban: str
    sumber: list[str] = Field(default_factory=list, description="Kode dokumen yang dikutip, misal KEB-01")
