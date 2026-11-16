from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import settings
from app.core.security import create_access_token
from app.db.session import get_db
from app.football.pipeline.ball_tracker import BallFramePoint, BallTrack
from app.football.pipeline.challenge_engine import (
    ChallengeEvaluationSummary,
    SegmentComplianceResult,
)
from app.football.pipeline.features import extract_session_features
from app.football.pipeline.fraud import evaluate_fraud_signals
from app.football.pipeline.fusion import FusedTouchEvent, FusionSummary
from app.football.pipeline.scoring import score_session_features
from app.football.services.session_service import (
    evaluate_and_persist_session_result,
    get_Owned_validation_session,
)
from app.football.tasks import celery_app
from app.main import create_application
from app.models.user import User, UserRole
from tests.football.synthetic import (
    SyntheticJugglingSpec,
    generate_synthetic_juggling_clip,
)


@pytest.fixture
async def football_p5_api() -> AsyncGenerator[dict[str, Any], None]:
    celery_app.conf.task_always_eager = True
    engine = create_async_engine(settings.async_database_url, pool_pre_ping=True)
    app = create_application()
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            try:
                async with AsyncSession(
                    bind=connection,
                    expire_on_commit=False,
                    join_transaction_mode="create_savepoint",
                ) as db:
                    suffix = uuid.uuid4().hex[:8]
                    member_user = User(
                        id=uuid.uuid4(),
                        email=f"football-p5-{suffix}@skillmatch.io",
                        full_name="Jugador Prueba Fase 5",
                        role=UserRole.MEMBER,
                        is_active=True,
                        is_locked=False,
                        hashed_password=None,
                    )
                    db.add(member_user)
                    await db.flush()

                    async def transaction_db() -> AsyncGenerator[AsyncSession, None]:
                        async with AsyncSession(
                            bind=connection,
                            expire_on_commit=False,
                            join_transaction_mode="create_savepoint",
                        ) as request_db:
                            try:
                                yield request_db
                                await request_db.commit()
                            except Exception:
                                await request_db.rollback()
                                raise

                    await db.commit()
                    app.dependency_overrides[get_db] = transaction_db

                    member_token = create_access_token(
                        subject=str(member_user.id),
                        role="MEMBER",
                    )

                    transport = ASGITransport(app=app, raise_app_exceptions=False)
                    async with AsyncClient(
                        transport=transport, base_url="http://testserver"
                    ) as client:
                        yield {
                            "app": app,
                            "client": client,
                            "member_token": member_token,
                            "member_user": member_user,
                            "db": db,
                        }
                    app.dependency_overrides.clear()
            finally:
                await transaction.rollback()
    finally:
        await engine.dispose()


def _make_clean_fusion(num_touches: int = 16, interval_ms: int = 650) -> FusionSummary:
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
        drift_ms_per_min=5.0,
        estimated_calibration_offset_ms=0,
    )


def _make_clean_challenge_eval() -> ChallengeEvaluationSummary:
    return ChallengeEvaluationSummary(
        segments=[
            SegmentComplianceResult(
                indice=0,
                tipo="LOW",
                inicio_servidor_ms=0,
                duracion_ms=8000,
                cumplimiento=0.92,
                latencia_reaccion_ms=280,
                median_height_diameters=1.1,
                median_interval_s=0.65,
                touch_count=8,
            ),
            SegmentComplianceResult(
                indice=1,
                tipo="HIGH",
                inicio_servidor_ms=8000,
                duracion_ms=8000,
                cumplimiento=0.90,
                latencia_reaccion_ms=310,
                median_height_diameters=3.3,
                median_interval_s=0.75,
                touch_count=8,
            ),
        ],
        mean_compliance=0.91,
        mean_reaction_latency_ms=295.0,
        plan_coherent=True,
        incoherent_segments_count=0,
    )


def test_rule_scoring_levels_and_template_feedback() -> None:
    """
    Phase 5 'Hecho cuando':
    Verifica niveles Principiante, Intermedio, Avanzado y Experto por reglas,
    retroalimentación por plantillas y versiones guardadas.
    """
    for target_streak, expected_level in [
        (4, "Principiante"),
        (16, "Intermedio"),
        (42, "Avanzado"),
        (75, "Experto"),
    ]:
        fusion = _make_clean_fusion(num_touches=target_streak, interval_ms=550)
        chal = _make_clean_challenge_eval()
        feats = extract_session_features(
            track=None,
            fusion=fusion,
            challenge_eval=chal,
            session_duration_s=30.0,
        )
        out = score_session_features(feats)
        assert out.nivel == expected_level
        assert sum(out.probabilidades.values()) == pytest.approx(1.0, abs=1e-2)
        assert out.version_modelo == "rules-v1"
        assert len(out.version_config) > 10
        assert len(out.retroalimentacion["fortalezas"]) >= 1
        assert len(out.retroalimentacion["mejoras"]) >= 1


@pytest.mark.asyncio
async def test_end_to_end_session_result_endpoint_persists_versions(
    football_p5_api: dict[str, Any],
    tmp_path: Path,
) -> None:
    """
    Phase 5 'Hecho cuando':
    El flujo completo funciona de extremo a extremo con el modelo de reglas y el
    resultado guarda versiones (`version_modelo` y `version_config`).
    """
    client: AsyncClient = football_p5_api["client"]
    token: str = football_p5_api["member_token"]
    member_user: User = football_p5_api["member_user"]
    db: AsyncSession = football_p5_api["db"]
    headers = {"Authorization": f"Bearer {token}"}

    create_resp = await client.post("/api/v1/football/sessions", headers=headers, json={})
    assert create_resp.status_code == 201
    session_id = create_resp.json()["data"]["session_id"]

    # Generate 12-touch synthetic clip (Intermedio level)
    touch_times = [800 + i * 600 for i in range(12)]
    spec = SyntheticJugglingSpec(
        duration_s=8.5,
        touch_times_ms=touch_times,
        peak_height_diameters=1.4,
        seed=555,
    )
    clip = generate_synthetic_juggling_clip(
        output_dir=tmp_path,
        spec=spec,
        clip_name="e2e_phase5",
        include_audio=True,
    )
    assert clip.audio_path is not None

    session_obj = await get_Owned_validation_session(
        db=db,
        session_id=uuid.UUID(session_id),
        user_id=member_user.id,
    )
    await evaluate_and_persist_session_result(
        db=db,
        session_obj=session_obj,
        video_path=str(clip.video_path),
        audio_path=str(clip.audio_path),
    )

    res_resp = await client.get(
        f"/api/v1/football/sessions/{session_id}/result",
        headers=headers,
    )
    assert res_resp.status_code == 200
    result_data = res_resp.json()["data"]
    assert result_data["session_id"] == session_id
    assert result_data["nivel"] in {"Principiante", "Intermedio", "Avanzado", "Experto"}
    assert result_data["metricas"]["toques"] == 12
    assert result_data["metricas"]["racha"] == 12
    assert result_data["version_modelo"] == "rules-v1"
    assert ":" in result_data["version_config"]
    assert len(result_data["retroalimentacion"]["fortalezas"]) >= 1


def test_simulated_fraud_attacks_trigger_incidents_and_legit_clips_have_zero_fp() -> None:
    """
    Phase 6 'Hecho cuando':
    Cada ataque simulado de la lista de pruebas dispara su incidencia;
    falsos positivos <= 5 % en clips legítimos.
    """
    base_fusion = _make_clean_fusion(num_touches=12)
    base_chal = _make_clean_challenge_eval()

    # 1. Legitimate clips benchmark (20 variations) -> FP rate must be <= 5% (0% here)
    false_positives = 0
    for i in range(20):
        legit_fusion = FusionSummary(
            events=base_fusion.events,
            confirmed_count=12,
            video_only_count=0,
            audio_only_count=0,
            effective_touch_count=12,
            coherence=0.85 + 0.005 * i,
            drift_ms_per_min=10.0 + i,
        )
        out = evaluate_fraud_signals(
            fusion=legit_fusion,
            challenge_eval=base_chal,
            expected_duration_s=16.0,
            actual_video_duration_s=16.2,
            detected_faces_count=1,
        )
        if out.requiere_revision or len(out.incidencias) > 0:
            false_positives += 1
    assert (false_positives / 20.0) <= 0.05

    # Attack 1: Superimposed / desynced audio (`low_av_coherence` & `high_av_drift`)
    dubbed_fusion = FusionSummary(
        events=base_fusion.events,
        confirmed_count=2,
        video_only_count=10,
        audio_only_count=5,
        effective_touch_count=12,
        coherence=0.12,
        drift_ms_per_min=450.0,
    )
    attack1 = evaluate_fraud_signals(fusion=dubbed_fusion, challenge_eval=base_chal)
    types1 = {inc.tipo for inc in attack1.incidencias}
    assert "low_av_coherence" in types1
    assert "high_av_drift" in types1

    # Attack 2: Video cuts or repeated frames (`frame_cut_or_repeat`)
    attack2 = evaluate_fraud_signals(
        fusion=base_fusion,
        challenge_eval=base_chal,
        video_integrity={"frame_repeat_count": 8, "frame_cut_count": 2, "camera_jitter_px": 1.0, "first_anomaly_ms": 2400},
    )
    assert any(inc.tipo == "frame_cut_or_repeat" for inc in attack2.incidencias)

    # Attack 3: Second person in frame (`multiple_faces`)
    attack3 = evaluate_fraud_signals(
        fusion=base_fusion,
        challenge_eval=base_chal,
        detected_faces_count=2,
    )
    assert any(inc.tipo == "multiple_faces" for inc in attack3.incidencias)

    # Attack 4: Pre-recorded video with wrong challenge sequence (`plan_sequence_mismatch`)
    wrong_plan_chal = ChallengeEvaluationSummary(
        segments=base_chal.segments,
        mean_compliance=0.18,
        mean_reaction_latency_ms=300.0,
        plan_coherent=False,
        incoherent_segments_count=2,
    )
    attack4 = evaluate_fraud_signals(fusion=base_fusion, challenge_eval=wrong_plan_chal)
    assert any(inc.tipo == "plan_sequence_mismatch" for inc in attack4.incidencias)

    # Attack 5: Tab switch / focus loss (`tab_hidden`)
    attack5 = evaluate_fraud_signals(
        fusion=base_fusion,
        challenge_eval=base_chal,
        client_events=[{"tipo": "tab_hidden", "t_ms": 3200}],
    )
    assert any(inc.tipo == "tab_hidden" for inc in attack5.incidencias)

    # Attack 6: Unrealistic reaction latency (< 150 ms) (`unrealistic_reaction_latency`)
    bot_chal = ChallengeEvaluationSummary(
        segments=[
            SegmentComplianceResult(
                indice=0,
                tipo="FAST",
                inicio_servidor_ms=0,
                duracion_ms=8000,
                cumplimiento=0.95,
                latencia_reaccion_ms=40,
                median_height_diameters=1.2,
                median_interval_s=0.45,
                touch_count=10,
            )
        ],
        mean_compliance=0.95,
        mean_reaction_latency_ms=40.0,
        plan_coherent=True,
        incoherent_segments_count=0,
    )
    attack6 = evaluate_fraud_signals(fusion=base_fusion, challenge_eval=bot_chal)
    assert any(inc.tipo == "unrealistic_reaction_latency" for inc in attack6.incidencias)

    # Attack 7: Out-of-frame ball/person & duration mismatch
    out_track = BallTrack(
        points=[
            BallFramePoint(frame_idx=i, t_ms=i * 33, x=2.0, y=2.0, radius=24.0, confidence=0.8)
            for i in range(30)
        ],
        frame_width=640,
        frame_height=360,
    )
    attack7 = evaluate_fraud_signals(
        fusion=base_fusion,
        challenge_eval=base_chal,
        track=out_track,
        expected_duration_s=40.0,
        actual_video_duration_s=18.0,
    )
    types7 = {inc.tipo for inc in attack7.incidencias}
    assert "out_of_frame" in types7
    assert "duration_mismatch" in types7
