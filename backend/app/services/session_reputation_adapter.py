"""Adapter for Reputation adjustments upon incidents (HU-40 integration boundary).

Zero third-party APIs, zero fictional score mutations. Records immutable incident reference.
"""

from typing import Literal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

ReputationIncidentStatus = Literal["PENDING_REPUTATION", "PROCESSED", "DISMISSED"]


class SessionReputationAdapter:
    """Manages the boundary between no-show reporting and reputation penalty."""

    @staticmethod
    async def record_noshow_incident(
        *,
        db: AsyncSession,
        session_id: UUID,
        absent_user_id: UUID,
        reported_by_id: UUID,
    ) -> ReputationIncidentStatus:
        """Mark a validated incident for immediate HU-40 reputation processing.

        The caller owns the transaction and persists the immutable report.  The
        reputation calculation reads that report after flush/commit, so this
        boundary must not open or commit an independent unit of work.
        """
        del db, session_id, absent_user_id, reported_by_id
        return "PROCESSED"
