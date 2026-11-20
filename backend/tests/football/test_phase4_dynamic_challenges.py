from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from app.football.pipeline.audio_events import detect_audio_impact_events
from app.football.pipeline.ball_tracker import track_ball_in_video
from app.football.pipeline.challenge_engine import (
    evaluate_challenge_plan,
    generate_plan,
    verify_signed_plan,
)
from app.football.pipeline.fusion import fuse_audio_video_events
from app.football.pipeline.touch_events import detect_video_touch_events
from app.football.tasks import celery_app, process_session
from tests.football.synthetic import (
    build_synthetic_spec_for_plan,
    generate_synthetic_juggling_clip,
)


def test_fixed_plan_produces_high_compliance_on_matching_synthetic_clip(
    tmp_path: Path,
) -> None:
    """
    Phase 4 'Hecho cuando' (Part 1):
    Un plan fijo produce cumplimiento correcto en sintéticos.
    """
    fixed_plan: list[dict[str, Any]] = [
        {"indice": 0, "tipo": "LOW", "inicio_servidor_ms": 0, "duracion_ms": 4000},
        {"indice": 1, "tipo": "HIGH", "inicio_servidor_ms": 4000, "duracion_ms": 4500},
        {"indice": 2, "tipo": "SLOW", "inicio_servidor_ms": 8500, "duracion_ms": 5000},
        {"indice": 3, "tipo": "FAST", "inicio_servidor_ms": 13500, "duracion_ms": 4000},
    ]

    spec = build_synthetic_spec_for_plan(fixed_plan, seed=901)
    clip = generate_synthetic_juggling_clip(
        output_dir=tmp_path,
        spec=spec,
        clip_name="compliant_plan_clip",
        include_audio=True,
    )
    assert clip.audio_path is not None

    track = track_ball_in_video(clip.video_path)
    video_events = detect_video_touch_events(track)
    audio_events = detect_audio_impact_events(clip.audio_path)
    fused = fuse_audio_video_events(video_events, audio_events)

    eval_summary = evaluate_challenge_plan(
        segments_plan=fixed_plan,
        fused_events=fused.events,
        track=track,
    )

    assert eval_summary.plan_coherent is True
    assert eval_summary.mean_compliance >= 0.85
    assert eval_summary.incoherent_segments_count == 0
    for seg_res in eval_summary.segments:
        assert seg_res.cumplimiento >= 0.75
        assert seg_res.latencia_reaccion_ms is not None
        assert seg_res.latencia_reaccion_ms >= 150


def test_video_recorded_with_different_plan_is_marked_incoherent(
    tmp_path: Path,
) -> None:
    """
    Phase 4 'Hecho cuando' (Part 2):
    Un video grabado con otro plan queda marcado como incoherente.
    """
    # Server issued Plan A: HIGH -> SLOW -> HIGH -> SLOW
    issued_plan_a: list[dict[str, Any]] = [
        {"indice": 0, "tipo": "HIGH", "inicio_servidor_ms": 0, "duracion_ms": 4500},
        {"indice": 1, "tipo": "SLOW", "inicio_servidor_ms": 4500, "duracion_ms": 5000},
        {"indice": 2, "tipo": "HIGH", "inicio_servidor_ms": 9500, "duracion_ms": 4500},
        {"indice": 3, "tipo": "SLOW", "inicio_servidor_ms": 14000, "duracion_ms": 5000},
    ]

    # Attacker uploaded a pre-recorded video that followed Plan B: LOW -> FAST -> LOW -> FAST
    recorded_plan_b: list[dict[str, Any]] = [
        {"indice": 0, "tipo": "LOW", "inicio_servidor_ms": 0, "duracion_ms": 4500},
        {"indice": 1, "tipo": "FAST", "inicio_servidor_ms": 4500, "duracion_ms": 5000},
        {"indice": 2, "tipo": "LOW", "inicio_servidor_ms": 9500, "duracion_ms": 4500},
        {"indice": 3, "tipo": "FAST", "inicio_servidor_ms": 14000, "duracion_ms": 5000},
    ]

    spec_b = build_synthetic_spec_for_plan(recorded_plan_b, seed=902)
    clip_b = generate_synthetic_juggling_clip(
        output_dir=tmp_path,
        spec=spec_b,
        clip_name="mismatched_plan_clip",
        include_audio=True,
    )
    assert clip_b.audio_path is not None

    track = track_ball_in_video(clip_b.video_path)
    video_events = detect_video_touch_events(track)
    audio_events = detect_audio_impact_events(clip_b.audio_path)
    fused = fuse_audio_video_events(video_events, audio_events)

    eval_summary = evaluate_challenge_plan(
        segments_plan=issued_plan_a,
        fused_events=fused.events,
        track=track,
    )

    assert eval_summary.plan_coherent is False
    assert eval_summary.mean_compliance <= 0.25
    assert eval_summary.incoherent_segments_count >= 3


def test_celery_process_session_runs_phase4_challenge_evaluation(
    tmp_path: Path,
) -> None:
    celery_app.conf.task_always_eager = True
    plan, signed_str = generate_plan(seed=101010)
    assert verify_signed_plan(signed_str) is True

    # Shorten segment durations to 3.5s each for fast test execution
    compact_plan: list[dict[str, Any]] = []
    offset = 0
    for seg in plan[:4]:
        compact_plan.append(
            {
                "indice": seg["indice"],
                "tipo": seg["tipo"],
                "inicio_servidor_ms": offset,
                "duracion_ms": 3500,
            }
        )
        offset += 3500

    spec = build_synthetic_spec_for_plan(compact_plan, seed=903)
    clip = generate_synthetic_juggling_clip(
        output_dir=tmp_path,
        spec=spec,
        clip_name="celery_phase4",
        include_audio=True,
    )
    assert clip.audio_path is not None

    session_id = str(uuid.uuid4())
    res = process_session.delay(
        session_id,
        str(clip.video_path),
        str(clip.audio_path),
        None,
        None,
        compact_plan,
    ).get(timeout=20)

    assert res["status"] == "processed_phase4"
    assert res["challenges"] is not None
    assert res["challenges"]["plan_coherent"] is True
    assert res["challenges"]["mean_compliance"] >= 0.75
