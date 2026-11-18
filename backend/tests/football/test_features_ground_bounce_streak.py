from __future__ import annotations

from app.football.pipeline.features import extract_session_features
from app.football.pipeline.fusion import FusedTouchEvent, FusionSummary


def _confirmed_event(t_ms: int, is_ground_bounce: bool = False) -> FusedTouchEvent:
    return FusedTouchEvent(
        t_ms=t_ms,
        estado="confirmed",
        confianza=0.95,
        video_t_ms=t_ms,
        audio_t_ms=t_ms,
        offset_ms=0,
        is_ground_bounce=is_ground_bounce,
    )


def test_ground_bounce_excluded_from_total_touches_and_cuts_streak() -> None:
    """
    A ground bounce between two runs of touches must not count as a touch and
    must split the juggling streak, even though the time gap around it is
    shorter than the 2.2s drop threshold.
    """
    events = [
        _confirmed_event(0),
        _confirmed_event(650),
        _confirmed_event(1300),
        _confirmed_event(1950, is_ground_bounce=True),
        _confirmed_event(2600),
        _confirmed_event(3250),
        _confirmed_event(3900),
        _confirmed_event(4550),
    ]
    fusion = FusionSummary(
        events=events,
        confirmed_count=len(events),
        video_only_count=0,
        audio_only_count=0,
        effective_touch_count=len(events),
        coherence=1.0,
        drift_ms_per_min=0.0,
        estimated_calibration_offset_ms=0,
    )

    feats = extract_session_features(track=None, fusion=fusion, session_duration_s=6.0)

    assert feats["total_touches"] == 7
    assert feats["ground_bounce_count"] == 1
    assert feats["max_streak"] == 4
    assert feats["drops_count"] == 1


def test_no_ground_bounce_keeps_single_streak() -> None:
    events = [_confirmed_event(i * 650) for i in range(6)]
    fusion = FusionSummary(
        events=events,
        confirmed_count=len(events),
        video_only_count=0,
        audio_only_count=0,
        effective_touch_count=len(events),
        coherence=1.0,
        drift_ms_per_min=0.0,
        estimated_calibration_offset_ms=0,
    )

    feats = extract_session_features(track=None, fusion=fusion, session_duration_s=5.0)

    assert feats["total_touches"] == 6
    assert feats["ground_bounce_count"] == 0
    assert feats["max_streak"] == 6
    assert feats["drops_count"] == 0
