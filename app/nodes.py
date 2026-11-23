"""Nodes of the claim graph.

Node = plain function: takes the state, returns a dict with ONLY the fields that CHANGED.
"""

from __future__ import annotations

import re

from app.state import ClaimState


def router(state: ClaimState) -> dict:
    """Find the claim number (format CLM-123) in the request sentence."""
    match = re.search(r"CLM-\d{3}", state["request"].upper())
    claim_id = match.group(0) if match else None
    return {"claim_id": claim_id}          # partial update: only claim_id
