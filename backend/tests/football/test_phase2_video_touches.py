from __future__ import annotations

import uuid
from pathlib import Path

from app.football.pipeline.ball_tracker import track_ball_in_video
from app.football.pipeline.touch_events import detect_video_touch_events
from app.football.tasks import celery_app, process_session
from tests.football.synthetic import (
    SyntheticJugglingSpec,
    generate_synthetic_juggling_clip,
)


def test_ball_tracker_interpolates_gaps_up_to_5_frames_and_normalizes_height(
    tmp_path: Path,
) -> None:
    spec = SyntheticJugglingSpec(
        duration_s=5.0,
        fps=30,
        ball_radius_px=24,
        touch_times_ms=[1000, 1800, 2600, 3400, 4200],
        missing_frame_ranges=[(40, 44)],  # 5-frame occlusion gap
    )
    clip = generate_synthetic_juggling_clip(
        output_dir=tmp_path,
        spec=spec,
        clip_name="gap_5_frames",
        include_audio=False,
    )

    track = track_ball_in_video(clip.video_path)
    assert len(track.points) == clip.total_frames
    assert 20.0 <= track.median_radius_px <= 28.0

    interpolated_frames = [pt.frame_idx for pt in track.points if pt.interpolated]
    assert set(range(40, 45)).issubset(set(interpolated_frames))

    max_height_diameters = max(pt.height_diameters for pt in track.points)
    assert max_height_diameters >= 1.5


def test_exact_touch_count_on_synthetic_videos(tmp_path: Path) -> None:
    """
    Phase 2 'Hecho cuando' (Part 1):
    En los videos sintéticos el conteo es exacto.
    """
    for expected_touches in (4, 6, 8, 10):
        touch_times = [900 + idx * 750 for idx in range(expected_touches)]
        spec = SyntheticJugglingSpec(
            duration_s=(touch_times[-1] + 1000) / 1000.0,
            touch_times_ms=touch_times,
            peak_height_diameters=2.1,
            background_noise_std=2.5,
            missing_frame_ranges=[(32, 34)],
            seed=200 + expected_touches,
        )
        clip = generate_synthetic_juggling_clip(
            output_dir=tmp_path,
            spec=spec,
            clip_name=f"exact_{expected_touches}_touches",
            include_audio=True,
        )
        assert clip.audio_path is not None and clip.audio_path.exists()

        track = track_ball_in_video(clip.video_path)
        candidates = detect_video_touch_events(track)

        assert len(candidates) == expected_touches
        for detected, gt_ms in zip(candidates, touch_times, strict=True):
            assert abs(detected.t_ms - gt_ms) <= 70


def test_ground_bounce_is_not_counted_as_touch_and_cuts_streak(tmp_path: Path) -> None:
    """
    A ball that falls past foot level down to the real floor (ground_y_px) is a
    dropped touch, not a valid touch. It must not inflate total_touches and it
    must be flagged so the juggling streak resets there instead of merging into
    one continuous run.
    """
    touch_times = [900, 1700, 2500, 4200, 5000, 5800]  # gap at 2500 -> 4200 is the drop
    spec = SyntheticJugglingSpec(
        duration_s=(touch_times[-1] + 1200) / 1000.0,
        touch_times_ms=touch_times,
        peak_height_diameters=2.1,
        background_noise_std=1.5,
        ground_drop_times_ms=[3350],
        seed=321,
    )
    clip = generate_synthetic_juggling_clip(
        output_dir=tmp_path,
        spec=spec,
        clip_name="ground_bounce",
        include_audio=False,
    )

    track = track_ball_in_video(clip.video_path)
    candidates = detect_video_touch_events(track)

    bounce_candidates = [c for c in candidates if c.is_ground_bounce]
    valid_candidates = [c for c in candidates if not c.is_ground_bounce]

    assert len(bounce_candidates) == 1
    assert abs(bounce_candidates[0].t_ms - 3350) <= 150
    assert len(valid_candidates) == len(touch_times)


def test_celery_process_session_runs_phase2_pipeline(tmp_path: Path) -> None:
    celery_app.conf.task_always_eager = True
    spec = SyntheticJugglingSpec(
        duration_s=5.0,
        touch_times_ms=[900, 1700, 2500, 3300, 4100],
    )
    clip = generate_synthetic_juggling_clip(
        output_dir=tmp_path,
        spec=spec,
        clip_name="celery_phase2",
        include_audio=False,
    )

    session_id = str(uuid.uuid4())
    res = process_session.delay(session_id, str(clip.video_path)).get(timeout=10)
    assert res["session_id"] == session_id
    assert res["status"] == "processed_phase2"
    assert res["video_touch_count"] == 5
    assert len(res["video_touches"]) == 5


def test_20_clip_evaluation_benchmark_mae_le_2(tmp_path: Path) -> None:
    """
    Phase 2 'Hecho cuando' (Part 2):
    Script de evaluación contra conteo manual en 20 clips con error medio <= 2 toques.
    """
    errors: list[int] = []
    for i in range(20):
        num_touches = 4 + (i % 9)
        interval_ms = 650 + (i % 4) * 100
        touch_times = [900 + k * interval_ms for k in range(num_touches)]
        spec = SyntheticJugglingSpec(
            duration_s=(touch_times[-1] + 1000) / 1000.0,
            touch_times_ms=touch_times,
            peak_height_diameters=1.8 + (i % 3) * 0.4,
            background_noise_std=1.5 + (i % 4) * 1.0,
            missing_frame_ranges=[(35, 37)] if (i % 3 == 0) else [],
            seed=1000 + i,
        )
        clip = generate_synthetic_juggling_clip(
            output_dir=tmp_path,
            spec=spec,
            clip_name=f"bench_{i:02d}",
            include_audio=False,
        )
        track = track_ball_in_video(clip.video_path)
        detected = detect_video_touch_events(track)
        errors.append(abs(len(detected) - num_touches))

    mean_abs_error = sum(errors) / float(len(errors))
    assert mean_abs_error <= 2.0
    assert max(errors) == 0
