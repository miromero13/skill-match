from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from ml.eval.report import generate_final_evaluation_report
from ml.export.export_onnx import export_level_classifier_to_onnx
from ml.train.train_models import train_and_evaluate_level_classifier
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import settings
from app.core.security import create_access_token
from app.db.session import get_db
from app.football.models import ModelVersion
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
async def football_p7_api() -> AsyncGenerator[dict[str, Any], None]:
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
                        email=f"football-p7-{suffix}@skillmatch.io",
                        full_name="Jugador Prueba Fase 7",
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


@pytest.mark.asyncio
async def test_phase7_trained_onnx_model_beats_rules_and_activates_via_db(
    football_p7_api: dict[str, Any],
    tmp_path: Path,
) -> None:
    """
    Phase 7 'Hecho cuando':
    Los modelos entrenados superan a las reglas en el conjunto de prueba y se
    activan sin cambiar el código (mediante la tabla `model_versions`).
    """
    trained_artifact = train_and_evaluate_level_classifier(seed=2026)
    metrics = trained_artifact["metrics"]
    assert metrics["beats_rule_baseline"] is True
    assert metrics["trained_exact_accuracy"] > metrics["rule_baseline_accuracy"]
    assert metrics["trained_exact_accuracy"] >= 0.85

    onnx_file = tmp_path / "level_classifier_v1.onnx"
    export_level_classifier_to_onnx(onnx_file, trained_artifact=trained_artifact)
    assert onnx_file.exists()

    # Register active model version in `model_versions`
    db: AsyncSession = football_p7_api["db"]
    client: AsyncClient = football_p7_api["client"]
    token: str = football_p7_api["member_token"]
    member_user: User = football_p7_api["member_user"]
    headers = {"Authorization": f"Bearer {token}"}

    model_row = ModelVersion(
        id=uuid.uuid4(),
        nombre="level_classifier",
        version="1.0.0-onnx",
        ruta_onnx=str(onnx_file),
        metricas=metrics,
        activa=True,
    )
    db.add(model_row)
    await db.commit()

    # Create and score a session -> must automatically use `level_classifier:1.0.0-onnx`
    create_resp = await client.post("/api/v1/football/sessions", headers=headers, json={})
    session_id = create_resp.json()["data"]["session_id"]

    spec = SyntheticJugglingSpec(
        duration_s=6.0,
        touch_times_ms=[800, 1500, 2200, 2900, 3600, 4300, 5000],
        seed=707,
    )
    clip = generate_synthetic_juggling_clip(
        output_dir=tmp_path,
        spec=spec,
        clip_name="onnx_active_clip",
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
    body_data = res_resp.json()["data"]
    assert body_data["version_modelo"] == "level_classifier:1.0.0-onnx"


def test_phase8_final_evaluation_report_meets_all_section_12_targets(
    tmp_path: Path,
) -> None:
    """
    Phase 8 'Hecho cuando':
    Se cumplen las metas de la sección 12 evaluadas sobre participantes nuevos (`test` split):
    - Error de conteo de toques <= 1 toque o <= 10 %
    - Precisión y exhaustividad de toques >= 90 %
    - Nivel: acierto exacto >= 75 %, a +-1 nivel >= 90 %
    - Fraude simulado detectado >= 90 % con falsos positivos <= 5 %
    - Tiempo de procesamiento <= 2 minutos en CPU
    """
    report = generate_final_evaluation_report(artifact_dir=tmp_path, seed=2026)

    assert report["all_section_12_targets_met"] is True
    assert report["touch_metrics"]["fused_mae"] <= 1.0
    assert report["touch_metrics"]["fused_MAE" if "fused_MAE" in report["touch_metrics"] else "fused_mae"] <= report["touch_metrics"]["video_only_mae"]
    assert report["touch_metrics"]["fused_precision"] >= 0.90
    assert report["touch_metrics"]["fused_recall"] >= 0.90
    assert report["level_metrics"]["exact_accuracy"] >= 0.75
    assert report["level_metrics"]["within_one_level_accuracy"] >= 0.90
    assert report["level_metrics"]["quadratic_weighted_kappa"] >= 0.80
    assert report["fraud_metrics"]["simulated_attack_detection_rate"] >= 0.90
    assert report["fraud_metrics"]["legitimate_false_positive_rate"] <= 0.05
    assert report["performance"]["under_2_minutes_target"] is True
