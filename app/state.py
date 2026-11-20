from __future__ import annotations

from typing import TypedDict

class KlaimState(TypedDict):
    """State of the Klaim application."""
    permintaan: str
    claim_id: str