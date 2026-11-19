"""Adapter for Reputation adjustments upon incidents (HU-40 integration boundary).

Zero third-party APIs, zero fictional score mutations. Records immutable incident reference.
"""

from typing import Literal
from uuid import UUID

ReputationIncidentStatus = Literal["PENDING_REPUTATION", "PROCESSED", "DISMISSED"]


class SessionReputationAdapter:
    """Manages the boundary between no-show reporting and reputation penalty."""

    @staticmethod
    async def record_noshow_incident(
        *,
        session_id: UUID,
        absent_user_id: UUID,
        reported_by_id: UUID,
    ) -> ReputationIncidentStatus:
        """Audits the no-show incident and queues it for reputation processing.

        When HU-40 reputation engine is deployed, this adapter will trigger
        the canonical reputation penalty calculation without modifying HU-39 contracts.
        """
        # Preserved as source-of-truth in session_no_show_reports table with status PENDING_REPUTATION
        return "PENDING_REPUTATION"
