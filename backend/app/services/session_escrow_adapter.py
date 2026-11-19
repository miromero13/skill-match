"""Adapter for Escrow release (HU-42 integration boundary).

Zero third-party APIs, zero simulated points. Returns explicit status until HU-42 contract lands.
"""

from typing import Literal

EscrowReleaseStatus = Literal["NOT_APPLICABLE", "PENDING_HU42", "RELEASED"]


class SessionEscrowAdapter:
    """Manages the boundary between session completion and escrow release."""

    @staticmethod
    async def process_completion(
        *,
        session_id: str,
        is_free: bool,
        points_required: int | None,
    ) -> EscrowReleaseStatus:
        """Determines escrow release status upon session completion.

        For free community sessions, escrow is not applicable.
        For paid sessions, marks as PENDING_HU42 until HU-42 escrow contract is deployed.
        """
        if is_free or not points_required or points_required <= 0:
            return "NOT_APPLICABLE"

        # Explicit placeholder for HU-42 integration:
        # When HU-42 is merged, call: await wallet_service.release_session_escrow(...)
        return "PENDING_HU42"
