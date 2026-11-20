"""Node-node graph klaim.

Node = fungsi biasa: terima state, kembalikan dict berisi field yang BERUBAH saja.
"""

from __future__ import annotations

import re

from app.state import KlaimState


def router(state: KlaimState) -> dict:
    """Cari nomor klaim (format KLM-123) di kalimat permintaan."""
    cocok = re.search(r"KLM-\d{3}", state["permintaan"].upper())
    claim_id = cocok.group(0) if cocok else None
    return {"claim_id": claim_id}          # pembaruan parsial: hanya claim_id