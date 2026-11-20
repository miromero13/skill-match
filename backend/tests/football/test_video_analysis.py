"""Admin juggling video analysis (odd/tasks/football-video-analysis.md, T1, S1-S5).

Everything goes through `POST /api/football/training/analyze-video` and the `APIResponse`
envelope, except the classical-fallback unit test and the official-scoring regression pin.
The EfficientDet model is forced absent in endpoint tests so they are deterministic and
independent of the locally provisioned weights.
"""
from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import settings
from app.core.security import create_access_token
from app.db.session import get_db
from app.football.pipeline import efficientdet_ball_detector
from app.football.pipeline.scoring import LEVELS, score_session_features
from app.football.services import session_service, video_analysis_service
from app.main import create_application
from app.models.user import User, UserRole
from tests.football.synthetic import (
    SyntheticJugglingSpec,
    generate_synthetic_juggling_clip,
)

ENDPOINT = "/api/football/training/analyze-video"
SUCCESS_MESSAGE = "Análisis de video completado."
DATA_KEYS = {
    "analysis_complete",
    "ball_detected",
    "detector",
    "frames_analyzed",
    "ball_frames",
    "duration_seconds",
    "total_touches",
    "max_streak",
    "streaks",
    "ground_contacts",
    "score_1_100",
    "level",
    "level_probabilities",
    "confidence",
    "model_version",
    "notes",
    "feedback",
}


@pytest.fixture
async def analysis_api(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> AsyncGenerator[dict[str, Any], None]:
    # Deterministic: no EfficientDet weights and no trained classifier from the shared DB.
    monkeypatch.setattr(
        efficientdet_ball_detector,
        "efficientdet_model_path",
        lambda: tmp_path / "absent-efficientdet.tflite",
    )

    async def no_active_classifier(db: AsyncSession) -> None:
        return None

    monkeypatch.setattr(
        session_service, "_load_active_level_classifier", no_active_classifier
    )

    engine = create_async_engine(settings.async_database_url, pool_pre_ping=True)
    app = create_application()
    async with engine.connect() as connection:
        transaction = await connection.begin()
        try:
            async with AsyncSession(
                bind=connection,
                expire_on_commit=False,
                join_transaction_mode="create_savepoint",
            ) as db:
                suffix = uuid.uuid4().hex[:8]
                admin_user = User(
                    id=uuid.uuid4(),
                    email=f"admin-video-{suffix}@skillmatch.io",
                    full_name="Admin Video Analysis",
                    role=UserRole.ADMIN,
                    is_active=True,
                    is_locked=False,
                    hashed_password="hashed_pw_test",
                )
                member_user = User(
                    id=uuid.uuid4(),
                    email=f"member-video-{suffix}@skillmatch.io",
                    full_name="Member Video",
                    role=UserRole.MEMBER,
                    is_active=True,
                    is_locked=False,
                    hashed_password=None,
                )
                db.add_all([admin_user, member_user])
                await db.commit()

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

                app.dependency_overrides[get_db] = transaction_db
                admin_token = create_access_token(subject=str(admin_user.id), role="ADMIN")
                member_token = create_access_token(subject=str(member_user.id), role="MEMBER")
                transport = ASGITransport(app=app, raise_app_exceptions=False)
                async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                    yield {
                        "client": client,
                        "admin_headers": {"Authorization": f"Bearer {admin_token}"},
                        "member_headers": {"Authorization": f"Bearer {member_token}"},
                    }
        finally:
            await transaction.rollback()
    await engine.dispose()


async def _post_video(
    api: dict[str, Any], payload: bytes, filename: str = "clip.mp4"
) -> dict[str, Any]:
    res = await api["client"].post(
        ENDPOINT,
        headers=api["admin_headers"],
        files={"file": (filename, payload, "video/mp4")},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["statuscode"] == 200
    assert body["message"] == SUCCESS_MESSAGE
    assert set(body["data"].keys()) == DATA_KEYS
    return body["data"]


def _assert_zero_touch_result(data: dict[str, Any]) -> None:
    assert data["total_touches"] == 0
    assert data["max_streak"] == 0
    assert data["streaks"] == []
    assert data["ground_contacts"] == 0
    assert data["level"] == "Principiante"
    assert data["score_1_100"] == 1.0
    assert data["level_probabilities"] == {
        "Principiante": 1.0,
        "Intermedio": 0.0,
        "Avanzado": 0.0,
        "Experto": 0.0,
    }
    assert data["notes"], "a zero-touch result must explain why in notes"


def _juggling_clip_with_ground_bounce(tmp_path: Path) -> Path:
    # 3 touches, ball drops to the floor at 3350 ms, then 5 touches.
    touch_times = [900, 1700, 2500, 4200, 5000, 5800, 6600, 7400]
    spec = SyntheticJugglingSpec(
        duration_s=(touch_times[-1] + 1200) / 1000.0,
        touch_times_ms=touch_times,
        peak_height_diameters=2.1,
        background_noise_std=1.5,
        ground_drop_times_ms=[3350],
        seed=321,
    )
    clip = generate_synthetic_juggling_clip(
        output_dir=tmp_path, spec=spec, clip_name="bounce", include_audio=False
    )
    return clip.video_path


def _no_ball_clip(tmp_path: Path) -> Path:
    path = tmp_path / "no_ball.mp4"
    writer = cv2.VideoWriter(
        str(path), cv2.VideoWriter_fourcc(*"mp4v"), 30.0, (640, 360)  # type: ignore[attr-defined]
    )
    rng = np.random.default_rng(7)
    base = np.full((360, 640, 3), (36, 52, 38), dtype=np.uint8)
    for _ in range(90):
        noise = rng.normal(0.0, 2.0, size=base.shape).astype(np.int16)
        writer.write(np.clip(base.astype(np.int16) + noise, 0, 255).astype(np.uint8))
    writer.release()
    return path


@pytest.mark.asyncio
async def test_juggling_with_ground_bounce_resets_streak_and_keeps_best(
    analysis_api: dict[str, Any], tmp_path: Path
) -> None:
    data = await _post_video(analysis_api, _juggling_clip_with_ground_bounce(tmp_path).read_bytes())

    assert data["analysis_complete"] is True
    assert data["ball_detected"] is True
    assert data["detector"] == "classical"
    assert data["total_touches"] == 8
    assert data["streaks"] == [3, 5]
    assert data["max_streak"] == 5
    assert data["ground_contacts"] == 1
    assert data["frames_analyzed"] == 258
    assert 0 < data["ball_frames"] <= data["frames_analyzed"]
    assert data["duration_seconds"] == pytest.approx(258 / 30.0, abs=0.01)
    assert data["level"] in LEVELS
    assert 1.0 <= data["score_1_100"] <= 100.0
    assert data["model_version"] == "rules-v1"
    assert data["feedback"]["fortalezas"] or data["feedback"]["mejoras"]
    # Uploads carry no dynamic challenge plan: feedback must not grade challenge compliance.
    feedback_text = " ".join(data["feedback"]["fortalezas"] + data["feedback"]["mejoras"])
    assert "dinámic" not in feedback_text


@pytest.mark.asyncio
async def test_video_without_ball_scores_principiante_with_note(
    analysis_api: dict[str, Any], tmp_path: Path
) -> None:
    data = await _post_video(analysis_api, _no_ball_clip(tmp_path).read_bytes())

    assert data["analysis_complete"] is True
    assert data["ball_detected"] is False
    assert data["frames_analyzed"] == 90
    _assert_zero_touch_result(data)
    assert "No se detectó balón en el video." in data["notes"]


@pytest.mark.asyncio
async def test_corrupt_bytes_return_complete_zero_result(
    analysis_api: dict[str, Any],
) -> None:
    data = await _post_video(analysis_api, b"definitely not a video container" * 64)

    assert data["analysis_complete"] is False
    assert data["ball_detected"] is False
    assert data["frames_analyzed"] == 0
    _assert_zero_touch_result(data)
    assert (
        "No se pudo leer el video (formato no soportado o archivo dañado)." in data["notes"]
    )


@pytest.mark.asyncio
async def test_oversize_upload_returns_zero_result_with_note(
    analysis_api: dict[str, Any], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(video_analysis_service, "MAX_UPLOAD_BYTES", 1024)
    data = await _post_video(analysis_api, _no_ball_clip(tmp_path).read_bytes())

    assert data["analysis_complete"] is False
    _assert_zero_touch_result(data)
    assert "El video supera el tamaño máximo de 200 MB; no se analizó." in data["notes"]


@pytest.mark.asyncio
async def test_detector_crash_never_becomes_an_http_error(
    analysis_api: dict[str, Any], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def exploding_tracker(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("detector exploded")

    monkeypatch.setattr(video_analysis_service, "track_ball_in_video", exploding_tracker)
    data = await _post_video(analysis_api, _no_ball_clip(tmp_path).read_bytes())

    assert data["analysis_complete"] is False
    _assert_zero_touch_result(data)
    assert "Ocurrió un fallo interno al analizar el video; se informa sin toques." in data["notes"]


@pytest.mark.asyncio
async def test_missing_file_field_returns_zero_result(
    analysis_api: dict[str, Any],
) -> None:
    res = await analysis_api["client"].post(
        ENDPOINT, headers=analysis_api["admin_headers"], data={"other": "x"}
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["message"] == SUCCESS_MESSAGE
    assert body["data"]["analysis_complete"] is False
    _assert_zero_touch_result(body["data"])
    assert "No se recibió ningún archivo de video." in body["data"]["notes"]


@pytest.mark.asyncio
async def test_trained_classifier_failure_falls_back_to_rules(
    analysis_api: dict[str, Any], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    async def broken_loader(db: AsyncSession) -> None:
        raise RuntimeError("storage offline")

    monkeypatch.setattr(session_service, "_load_active_level_classifier", broken_loader)
    data = await _post_video(analysis_api, _juggling_clip_with_ground_bounce(tmp_path).read_bytes())

    assert data["analysis_complete"] is True
    assert data["model_version"] == "rules-v1"
    assert data["max_streak"] == 5
    assert (
        "No se pudo cargar el clasificador entrenado; se usó el clasificador por reglas."
        in data["notes"]
    )


@pytest.mark.asyncio
async def test_non_admin_and_anonymous_get_404(
    analysis_api: dict[str, Any], tmp_path: Path
) -> None:
    files = {"file": ("clip.mp4", _no_ball_clip(tmp_path).read_bytes(), "video/mp4")}
    res_anon = await analysis_api["client"].post(ENDPOINT, files=files)
    res_member = await analysis_api["client"].post(
        ENDPOINT, headers=analysis_api["member_headers"], files=files
    )
    for res in (res_anon, res_member):
        assert res.status_code == 404
        body = res.json()
        assert body["statuscode"] == 404
        assert body["message"] == "Recurso no encontrado"
        assert body["data"] is None


def test_missing_model_file_falls_back_to_classical_with_note(tmp_path: Path) -> None:
    video = _juggling_clip_with_ground_bounce(tmp_path)
    data = video_analysis_service.analyze_video_file(
        video, classifier=None, model_path=tmp_path / "missing.tflite"
    )

    assert data["detector"] == "classical"
    assert (
        "Modelo EfficientDet-Lite0 no instalado; se usó solo el detector clásico."
        in data["notes"]
    )
    assert data["max_streak"] == 5


@pytest.mark.skipif(
    not efficientdet_ball_detector.efficientdet_model_path().is_file(),
    reason="efficientdet_lite0.tflite not installed (run scripts/install_vision_models.py)",
)
def test_installed_model_runs_fused_detector(tmp_path: Path) -> None:
    video = _juggling_clip_with_ground_bounce(tmp_path)
    data = video_analysis_service.analyze_video_file(video, classifier=None)

    assert data["analysis_complete"] is True
    assert data["detector"] == "mediapipe-efficientdet-lite0+classical"
    assert data["streaks"] == [3, 5]


def test_official_scoring_zero_touches_is_still_no_calificado() -> None:
    out = score_session_features({"total_touches": 0})
    assert out.nivel == "No calificado"
    assert out.puntaje_1_100 == 1.0
    assert out.confianza == 0.0
    assert out.requiere_revision is True
