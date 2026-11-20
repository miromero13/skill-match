"""Adapter for Escrow release (HU-42 integration)."""
from typing import Literal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

EscrowReleaseStatus = Literal["NOT_APPLICABLE", "PENDING_HU42", "RELEASED"]


class SessionEscrowAdapter:
    """Manages the boundary between session completion and escrow release."""

    @staticmethod
    async def process_completion(
        *,
        session_id: str,
        is_free: bool,
        points_required: int | None,
        db: AsyncSession | None = None,
    ) -> EscrowReleaseStatus:
        """Determines escrow release status upon session completion.

        For free community sessions, escrow is not applicable.
        For paid sessions with escrow locked, releases points to the tutor via wallet_service.
        """
        if is_free or not points_required or points_required <= 0:
            return "NOT_APPLICABLE"

        if db is None:
            return "PENDING_HU42"

        from app.services.wallet_service import wallet_service

        released = await wallet_service.release_session_escrow(db, UUID(session_id))
        return "RELEASED" if released else "PENDING_HU42"
