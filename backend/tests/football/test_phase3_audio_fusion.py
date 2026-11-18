from __future__ import annotations

import uuid
from pathlib import Path

from app.football.config import load_football_config
from app.football.pipeline.audio_events import detect_audio_impact_events
from app.football.pipeline.ball_tracker import track_ball_in_video
from app.football.pipeline.fusion import fuse_audio_video_events
from app.football.pipeline.touch_events import detect_video_touch_events
from app.football.tasks import celery_app, process_session
from tests.football.synthetic import (
    SyntheticJugglingSpec,
    generate_synthetic_juggling_clip,
)


def test_audio_events_detects_48khz_impacts_and_calibration_offset(
    tmp_path: Path,
) -> None:
    touch_times = [1000, 1800, 2600, 3400, 4200, 5000]
    spec = SyntheticJugglingSpec(
        duration_s=6.0,
        touch_times_ms=touch_times,
        audio_offset_ms=45,  # 45 ms hardware audio latency
        seed=301,
    )
    clip = generate_synthetic_juggling_clip(
        output_dir=tmp_path,
        spec=spec,
        clip_name="audio_cal_offset",
        include_audio=True,
    )
    assert clip.audio_path is not None

    audio_events = detect_audio_impact_events(clip.audio_path)
    assert len(audio_events) == len(touch_times)
    for ev, gt_ms in zip(audio_events, touch_times, strict=True):
        assert abs(ev.t_ms - (gt_ms + 45)) <= 20

    track = track_ball_in_video(clip.video_path)
    video_events = detect_video_touch_events(track)

    fused = fuse_audio_video_events(
        video_events=video_events,
        audio_events=audio_events,
        calibration_touch_ms=1000,
    )
    assert fused.confirmed_count == len(touch_times)
    assert fused.coherence == 1.0
    assert abs(fused.estimated_calibration_offset_ms - 45) <= 35
    assert abs(fused.drift_ms_per_min) <= 40.0


def test_fusion_improves_touch_counting_accuracy_over_video_only(
    tmp_path: Path,
) -> None:
    """
    Phase 3 'Hecho cuando' (Part 1):
    Fusión mejora la precisión del conteo frente a solo video, medida en el mismo conjunto.
    We evaluate a set of clips where visual occlusions (> 5 frames around one touch)
    cause video-only tracking to miss a touch, while synchronized audio+video fusion
    recovers the exact count.
    """
    video_only_errors: list[int] = []
    fused_errors: list[int] = []

    for idx in range(6):
        touch_times = [1000, 1800, 2600, 3400, 4200, 5000, 5800, 6600]
        # Occlude 9 frames around the 4th touch (3400 ms -> frame ~102 at 30 fps)
        # exceeding max_gap_frames=5 so video-only misses that touch
        occluded_touch_frame = round((touch_times[3] * 30) / 1000.0)
        spec = SyntheticJugglingSpec(
            duration_s=7.6,
            touch_times_ms=touch_times,
            missing_frame_ranges=[(occluded_touch_frame - 4, occluded_touch_frame + 4)],
            audio_offset_ms=20,
            seed=400 + idx,
        )
        clip = generate_synthetic_juggling_clip(
            output_dir=tmp_path,
            spec=spec,
            clip_name=f"occluded_set_{idx}",
            include_audio=True,
        )
        assert clip.audio_path is not None

        track = track_ball_in_video(clip.video_path)
        video_events = detect_video_touch_events(track)
        audio_events = detect_audio_impact_events(clip.audio_path)

        fused = fuse_audio_video_events(
            video_events=video_events,
            audio_events=audio_events,
            calibration_touch_ms=1000,
        )

        gt_count = len(touch_times)
        video_only_errors.append(abs(len(video_events) - gt_count))
        fused_errors.append(abs(fused.effective_touch_count - gt_count))

    mean_video_err = sum(video_only_errors) / float(len(video_only_errors))
    mean_fused_err = sum(fused_errors) / float(len(fused_errors))

    assert mean_video_err >= 1.0
    assert mean_fused_err < mean_video_err
    assert mean_fused_err == 0.0


def test_desynced_or_edited_audio_produces_low_coherence_and_high_drift(
    tmp_path: Path,
) -> None:
    """
    Phase 3 'Hecho cuando' (Part 2):
    Un video con audio desfasado o editado produce coherencia baja (y/o deriva alta).
    """
    cfg = load_football_config()
    touch_times = [1000, 1800, 2600, 3400, 4200, 5000, 5800, 6600]

    # Case A: Edited/dubbed audio track with completely mismatched impact times
    edited_spec = SyntheticJugglingSpec(
        duration_s=7.6,
        touch_times_ms=touch_times,
        custom_audio_touch_times_ms=[1350, 2190, 3010, 4650, 6220],
        seed=501,
    )
    edited_clip = generate_synthetic_juggling_clip(
        output_dir=tmp_path,
        spec=edited_spec,
        clip_name="edited_dubbed_audio",
        include_audio=True,
    )
    assert edited_clip.audio_path is not None

    v_events = detect_video_touch_events(track_ball_in_video(edited_clip.video_path))
    a_events = detect_audio_impact_events(edited_clip.audio_path)
    edited_fusion = fuse_audio_video_events(
        video_events=v_events,
        audio_events=a_events,
        calibration_touch_ms=1000,
    )
    assert edited_fusion.coherence < cfg.fusion.min_coherence
    assert edited_fusion.coherence <= 0.25

    # Case B: Progressive clock drift (e.g. +900 ms/min -> +90 ms over 6 seconds)
    drifting_spec = SyntheticJugglingSpec(
        duration_s=7.6,
        touch_times_ms=touch_times,
        audio_drift_ms_per_min=900.0,
        seed=502,
    )
    drift_clip = generate_synthetic_juggling_clip(
        output_dir=tmp_path,
        spec=drifting_spec,
        clip_name="drifting_audio",
        include_audio=True,
    )
    assert drift_clip.audio_path is not None

    v_drift = detect_video_touch_events(track_ball_in_video(drift_clip.video_path))
    a_drift = detect_audio_impact_events(drift_clip.audio_path)
    drift_fusion = fuse_audio_video_events(
        video_events=v_drift,
        audio_events=a_drift,
        calibration_touch_ms=1000,
    )
    # Either coherence drops below threshold as late touches exceed ±70 ms or drift slope exceeds max_drift_ms_per_min
    assert (
        drift_fusion.coherence < cfg.fusion.min_coherence
        or abs(drift_fusion.drift_ms_per_min) > cfg.fusion.max_drift_ms_per_min
    )


def test_celery_process_session_runs_phase3_audio_fusion(tmp_path: Path) -> None:
    celery_app.conf.task_always_eager = True
    spec = SyntheticJugglingSpec(
        duration_s=5.0,
        touch_times_ms=[1000, 1800, 2600, 3400, 4200],
        audio_offset_ms=15,
    )
    clip = generate_synthetic_juggling_clip(
        output_dir=tmp_path,
        spec=spec,
        clip_name="celery_phase3",
        include_audio=True,
    )
    assert clip.audio_path is not None

    session_id = str(uuid.uuid4())
    res = process_session.delay(
        session_id,
        str(clip.video_path),
        str(clip.audio_path),
        1000,
    ).get(timeout=10)

    assert res["status"] == "processed_phase3"
    assert res["video_touch_count"] == 5
    assert res["audio_impact_count"] == 5
    assert res["fusion"]["confirmed_count"] == 5
    assert res["fusion"]["coherence"] == 1.0
