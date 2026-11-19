from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from enum import Enum
from zoneinfo import ZoneInfo


class FreeQuotaDecision(str, Enum):
    FREE_AVAILABLE = "FREE_AVAILABLE"
    PAYMENT_REQUIRED_UNAVAILABLE = "PAYMENT_REQUIRED_UNAVAILABLE"


@dataclass(frozen=True)
class CancellationDecision:
    cancelled_at: datetime
    is_timely: bool
    restore_quota: bool
    blocks_booking: bool
    booking_blocked_until: datetime | None


def local_week_bounds(instant: datetime, timezone_name: str) -> tuple[datetime, datetime]:
    zone = ZoneInfo(timezone_name)
    local = instant.astimezone(zone)
    monday = local.date() - timedelta(days=local.weekday())
    start = datetime.combine(monday, time.min, zone).astimezone(UTC)
    end = datetime.combine(monday + timedelta(days=7), time.min, zone).astimezone(UTC)
    return start, end


def local_month_bounds(instant: datetime, timezone_name: str) -> tuple[datetime, datetime]:
    zone = ZoneInfo(timezone_name)
    local = instant.astimezone(zone)
    start_local = datetime(local.year, local.month, 1, tzinfo=zone)
    if local.month == 12:
        end_local = datetime(local.year + 1, 1, 1, tzinfo=zone)
    else:
        end_local = datetime(local.year, local.month + 1, 1, tzinfo=zone)
    return start_local.astimezone(UTC), end_local.astimezone(UTC)


def decide_quota(
    *,
    free_sessions_used: int,
    payment_gateway_available: bool,
) -> FreeQuotaDecision:
    if free_sessions_used < 2:
        return FreeQuotaDecision.FREE_AVAILABLE
    return FreeQuotaDecision.PAYMENT_REQUIRED_UNAVAILABLE


def classify_cancellation(
    *,
    starts_at: datetime,
    cancelled_at: datetime,
    actor_monthly_cancellations: int,
) -> CancellationDecision:
    timely = starts_at - cancelled_at >= timedelta(hours=24)
    blocks = not timely or actor_monthly_cancellations >= 3
    return CancellationDecision(
        cancelled_at=cancelled_at,
        is_timely=timely,
        restore_quota=timely,
        blocks_booking=blocks,
        booking_blocked_until=cancelled_at + timedelta(days=7) if blocks else None,
    )
