"""State of the claim graph: the 'shared whiteboard' that every node reads and writes."""

from __future__ import annotations

from typing import TypedDict


class ClaimState(TypedDict, total=False):
    # total=False: every field may be missing at first. The state grows as nodes write to it.
    request: str          # input from the user, e.g. "Process claim CLM-002"
    claim_id: str | None     # filled in by the router node
