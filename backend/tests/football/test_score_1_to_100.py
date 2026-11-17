from __future__ import annotations

import pytest

from app.football.pipeline.fusion import FusedTouchEvent, FusionSummary
from app.football.pipeline.features import extract_session_features
from app.football.pipeline.scoring import score_session_features


def _fusion_with_streak(num_touches: int, interval_ms: int = 600) -> FusionSummary:
    events = [
        FusedTouchEvent(
            t_ms=800 + i * interval_ms,
            estado="confirmed",
            confianza=0.95,
            video_t_ms=800 + i * interval_ms,
            audio_t_ms=800 + i * interval_ms,
            offset_ms=0,
        )
        for i in range(num_touches)
    ]
    return FusionSummary(
        events=events,
        confirmed_count=num_touches,
        video_only_count=0,
        audio_only_count=0,
        effective_touch_count=num_touches,
        coherence=1.0,
        drift_ms_per_min=0.0,
        estimated_calibration_offset_ms=0,
    )


def test_score_1_100_is_monotonic_with_streak_and_bounded() -> None:
    """
    puntaje_1_100 must increase monotonically as skill (streak) grows, and must
    always stay within the documented [1, 100] bound regardless of input.
    """
    scores: list[float] = []
    for streak in (3, 10, 20, 40, 70, 95):
        fusion = _fusion_with_streak(streak)
        feats = extract_session_features(track=None, fusion=fusion, session_duration_s=60.0)
        out = score_session_features(feats)
        assert 1.0 <= out.puntaje_1_100 <= 100.0
        scores.append(out.puntaje_1_100)

    for earlier, later in zip(scores, scores[1:]):
        assert later >= earlier


def test_score_1_100_is_minimal_when_unrated() -> None:
    feats = extract_session_features(
        track=None,
        fusion=FusionSummary(events=[], confirmed_count=0, video_only_count=0, audio_only_count=0),
        session_duration_s=10.0,
    )
    out = score_session_features(feats)
    assert out.nivel == "No calificado"
    assert out.puntaje_1_100 == pytest.approx(1.0)


def test_score_1_100_is_flagged_as_uncalibrated() -> None:
    fusion = _fusion_with_streak(15)
    feats = extract_session_features(track=None, fusion=fusion, session_duration_s=30.0)
    out = score_session_features(feats)
    assert out.puntaje_calibrado is False
