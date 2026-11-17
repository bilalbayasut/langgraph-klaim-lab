"""Tahap 2: State (TypedDict + reducer) dan skema Pydantic."""

import operator
import typing

import pytest
from pydantic import ValidationError

from app.state import ItemTask, JawabanKebijakan, KlaimState, PenilaianMemo, RuteDecision


def _reducer(field):
    hint = typing.get_type_hints(KlaimState, include_extras=True)[field]
    meta = getattr(hint, "__metadata__", ())
    return meta[0] if meta else None


def test_field_wajib_ada():
    wajib = {"permintaan", "rute", "claim_id", "klaim", "profil", "hasil_item", "keputusan", "draf_memo",
             "jumlah_draf", "penilaian", "persetujuan", "pembayaran", "status_akhir", "jawaban", "sumber",
             "log", "peringatan"}
    assert wajib <= set(KlaimState.__annotations__)


def test_reducer_append_only():
    for f in ("hasil_item", "log", "peringatan"):
        assert _reducer(f) is operator.add, f"{f} harus Annotated[list[...], operator.add]"


def test_field_biasa_tanpa_reducer():
    for f in ("keputusan", "draf_memo", "jumlah_draf", "status_akhir"):
        assert _reducer(f) is None, f"{f} sebaiknya ditimpa (tanpa reducer)"


def test_item_task():
    assert set(ItemTask.__annotations__) == {"claim_id", "item"}


def test_skema_pydantic():
    assert RuteDecision(rute="klaim", claim_id="KLM-001", alasan="x").rute == "klaim"
    with pytest.raises(ValidationError):
        RuteDecision(rute="lainnya", alasan="x")
    with pytest.raises(ValidationError):
        PenilaianMemo(skor=11)
    assert PenilaianMemo(skor=8).masalah == []
    assert JawabanKebijakan(jawaban="a").sumber == []
