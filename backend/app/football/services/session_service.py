from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from fastapi import status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import SkillMatchException
from app.football.config import load_football_config
from app.football.models import (
    ChallengeSegment,
    DetectedEvent,
    EvidenceFile,
    FraudIncident,
    ModelVersion,
    SessionFeature,
    ValidationResult,
    ValidationSession,
    ValidationSessionState,
)
from app.football.pipeline.audio_events import detect_audio_impact_events
from app.football.pipeline.ball_tracker import BallTrack, track_ball_in_video
from app.football.pipeline.challenge_engine import (
    ChallengeEvaluationSummary,
    evaluate_challenge_plan,
    generate_plan,
)
from app.football.pipeline.features import extract_session_features
from app.football.pipeline.fraud import evaluate_fraud_signals, inspect_video_integrity
from app.football.pipeline.fusion import FusionSummary, fuse_audio_video_events
from app.football.pipeline.scoring import (
    LevelClassifierProtocol,
    TrainedArtifactLevelClassifier,
    score_session_features,
)
from app.football.pipeline.touch_events import detect_video_touch_events
from app.football.schemas import (
    CalibrationRequest,
    ChallengeSegmentRead,
    EnvCheckRequest,
    FinalizeSessionRequest,
    FraudIncidentRead,
    LivenessRequest,
    ValidationMetricsRead,
    ValidationResultResponse,
)
from app.football.services.storage import GarageS3StorageService, garage_s3_storage
from app.football.tasks import process_session


async def count_recent_attempts(
    db: AsyncSession,
    user_id: UUID,
    skill_id: UUID | None,
    window_minutes: int,
) -> int:
    cutoff = datetime.now(UTC) - timedelta(minutes=window_minutes)
    stmt = select(func.count(ValidationSession.id)).where(
        ValidationSession.user_id == user_id,
        ValidationSession.creada_en >= cutoff,
    )
    if skill_id is not None:
        stmt = stmt.where(ValidationSession.skill_id == skill_id)
    result = await db.execute(stmt)
    return int(result.scalar_one() or 0)


async def create_validation_session(
    db: AsyncSession,
    user_id: UUID,
    skill_id: UUID | None = None,
    route_prefix: str = "/api/football",
) -> tuple[ValidationSession, int, str]:
    """
    Create a new Football ValidationSession enforcing attempt limits and cooldown window.
    Returns `(session, remaining_attempts, ws_url)`.
    """
    cfg = load_football_config()
    max_attempts = cfg.session.max_attempts_per_window
    cooldown_minutes = cfg.session.cooldown_minutes

    recent_count = await count_recent_attempts(
        db=db,
        user_id=user_id,
        skill_id=skill_id,
        window_minutes=cooldown_minutes,
    )
    if recent_count >= max_attempts:
        raise SkillMatchException(
            statuscode=status.HTTP_429_TOO_MANY_REQUESTS,
            message=(
                f"Has alcanzado el límite de {max_attempts} intentos. "
                f"Por favor espera {cooldown_minutes} minutos antes de volver a intentarlo."
            ),
        )

    seed = secrets.randbelow(2_000_000_000) + 1
    segments_plan, signed_plan = generate_plan(seed)
    now = datetime.now(UTC)

    session_obj = ValidationSession(
        user_id=user_id,
        skill_id=skill_id,
        estado=ValidationSessionState.CREATED.value,
        semilla=seed,
        plan_firmado=signed_plan,
        creada_en=now,
        version_modelo="rules-v1",
        version_config=f"{cfg.version}:{cfg.config_hash[:12]}",
    )
    db.add(session_obj)
    await db.flush()

    for seg in segments_plan:
        db.add(
            ChallengeSegment(
                session_id=session_obj.id,
                indice=int(seg["indice"]),
                tipo=str(seg["tipo"]),
                inicio_servidor_ms=int(seg["inicio_servidor_ms"]),
                duracion_ms=int(seg["duracion_ms"]),
            )
        )

    await db.commit()
    await db.refresh(session_obj)

    remaining = max(0, max_attempts - (recent_count + 1))
    ws_url = f"{route_prefix}/sessions/{session_obj.id}/ws"
    return session_obj, remaining, ws_url


async def get_Owned_validation_session(
    db: AsyncSession,
    session_id: UUID,
    user_id: UUID,
) -> ValidationSession:
    """Fetch a ValidationSession with segments and evidence_files and verify ownership."""
    stmt = (
        select(ValidationSession)
        .options(
            selectinload(ValidationSession.segments),
            selectinload(ValidationSession.evidence_files),
            selectinload(ValidationSession.features),
            selectinload(ValidationSession.result),
            selectinload(ValidationSession.fraud_incidents),
            selectinload(ValidationSession.detected_events),
        )
        .where(ValidationSession.id == session_id)
    )
    result = await db.execute(stmt)
    session_obj = result.scalar_one_or_none()
    if session_obj is None or session_obj.user_id != user_id:
        raise SkillMatchException(
            statuscode=status.HTTP_404_NOT_FOUND,
            message="Sesión de validación no encontrada.",
        )
    return session_obj


def extract_confirmed_chunk_indices(session_obj: ValidationSession) -> list[int]:
    indices: set[int] = set()
    for ev in session_obj.evidence_files:
        if ev.tipo.startswith("chunk:"):
            part = ev.tipo.split(":", 1)[1]
            if part.isdigit():
                indices.add(int(part))
    return sorted(indices)


async def _upsert_session_metadata(
    db: AsyncSession,
    session_obj: ValidationSession,
    updates: dict[str, Any],
) -> None:
    if session_obj.features is None:
        feature_row = SessionFeature(
            session_id=session_obj.id,
            features_json=dict(updates),
        )
        db.add(feature_row)
    else:
        merged = dict(session_obj.features.features_json or {})
        merged.update(updates)
        session_obj.features.features_json = merged


async def evaluate_env_check(
    db: AsyncSession,
    session_obj: ValidationSession,
    payload: EnvCheckRequest,
) -> tuple[bool, list[str]]:
    cfg = load_football_config()
    failures: list[str] = []

    if payload.brightness < cfg.env_check.min_brightness:
        failures.append("Iluminación insuficiente: mejora la luz del entorno.")
    elif payload.brightness > cfg.env_check.max_brightness:
        failures.append("Exceso de brillo o contraluz detectado.")

    if payload.noise_db > cfg.env_check.max_noise_db:
        failures.append("Nivel de ruido ambiental demasiado alto.")

    if cfg.env_check.require_face_detected and not payload.face_detected:
        failures.append("No se detecta el rostro del participante en el encuadre.")

    if cfg.env_check.require_ball_detected and not payload.ball_detected:
        failures.append("No se detecta el balón visible dentro del cuadro.")

    if payload.latency_ms > cfg.env_check.max_latency_ms:
        failures.append("Conexión inestable: latencia superior al umbral permitido.")

    passed = len(failures) == 0
    if passed:
        session_obj.estado = ValidationSessionState.ENV_CHECK.value

    await _upsert_session_metadata(
        db=db,
        session_obj=session_obj,
        updates={
            "env_check": {
                "passed": passed,
                "brightness": payload.brightness,
                "noise_db": payload.noise_db,
                "face_detected": payload.face_detected,
                "ball_detected": payload.ball_detected,
                "latency_ms": payload.latency_ms,
                "failures": failures,
            }
        },
    )
    await db.commit()
    await db.refresh(session_obj)
    return passed, failures


async def record_liveness_check(
    db: AsyncSession,
    session_obj: ValidationSession,
    payload: LivenessRequest,
) -> bool:
    if not payload.challenge_passed:
        raise SkillMatchException(
            statuscode=status.HTTP_400_BAD_REQUEST,
            message="La prueba de vida no fue superada. Inténtalo de nuevo siguiendo el gesto indicado.",
        )

    session_obj.estado = ValidationSessionState.LIVENESS.value
    await _upsert_session_metadata(
        db=db,
        session_obj=session_obj,
        updates={
            "liveness": {
                "passed": True,
                "gesture_code": payload.gesture_code,
                "confidence": payload.confidence,
            }
        },
    )
    await db.commit()
    await db.refresh(session_obj)
    return True


async def record_calibration_touch(
    db: AsyncSession,
    session_obj: ValidationSession,
    payload: CalibrationRequest,
) -> ValidationSession:
    session_obj.estado = ValidationSessionState.RECORDING.value
    await _upsert_session_metadata(
        db=db,
        session_obj=session_obj,
        updates={
            "calibration": {
                "client_touch_timestamp_ms": payload.client_touch_timestamp_ms,
                "estimated_ball_radius_px": payload.estimated_ball_radius_px,
            }
        },
    )
    await db.commit()
    await db.refresh(session_obj)
    return session_obj


async def upload_session_chunk(
    db: AsyncSession,
    session_obj: ValidationSession,
    chunk_index: int,
    payload_bytes: bytes,
    content_type: str = "video/mp4",
    expected_sha256: str | None = None,
    storage: GarageS3StorageService | None = None,
) -> tuple[EvidenceFile, bool]:
    """
    Idempotently store chunk `chunk_index` for `session_obj` in Garage S3 and `evidence_files`.
    Returns `(evidence_file, idempotent_replay)`.
    """
    if chunk_index < 0:
        raise SkillMatchException(
            statuscode=status.HTTP_400_BAD_REQUEST,
            message="El índice del fragmento debe ser mayor o igual a 0.",
        )
    if not payload_bytes:
        raise SkillMatchException(
            statuscode=status.HTTP_400_BAD_REQUEST,
            message="El fragmento enviado está vacío.",
        )

    cfg = load_football_config()
    max_bytes = cfg.session.max_chunk_size_mb * 1024 * 1024
    if len(payload_bytes) > max_bytes:
        raise SkillMatchException(
            statuscode=status.HTTP_400_BAD_REQUEST,
            message=f"El fragmento supera el límite permitido de {cfg.session.max_chunk_size_mb} MB.",
        )

    storage_svc = storage or garage_s3_storage
    computed_sha256 = storage_svc.compute_sha256(payload_bytes)
    if expected_sha256 and expected_sha256.strip().lower() != computed_sha256:
        raise SkillMatchException(
            statuscode=status.HTTP_400_BAD_REQUEST,
            message="El hash SHA-256 del fragmento no coincide con los bytes recibidos.",
        )

    chunk_type = f"chunk:{chunk_index}"
    existing = next(
        (ev for ev in session_obj.evidence_files if ev.tipo == chunk_type),
        None,
    )
    if existing is not None and existing.sha256 == computed_sha256:
        return existing, True

    ext = "webm" if "webm" in content_type.lower() else "mp4"
    object_key = f"sessions/{session_obj.id}/chunks/{chunk_index}.{ext}"
    storage_uri, _ = storage_svc.put_object_bytes(
        object_key=object_key,
        payload=payload_bytes,
        content_type=content_type,
    )

    expires_at = datetime.now(UTC) + timedelta(days=cfg.session.retention_days)
    if existing is not None:
        existing.ruta_minio = storage_uri
        existing.sha256 = computed_sha256
        existing.duracion_s = float(cfg.session.chunk_duration_seconds)
        existing.expira_en = expires_at
        evidence = existing
    else:
        evidence = EvidenceFile(
            session_id=session_obj.id,
            tipo=chunk_type,
            ruta_minio=storage_uri,
            duracion_s=float(cfg.session.chunk_duration_seconds),
            fps=30.0,
            sha256=computed_sha256,
            expira_en=expires_at,
        )
        db.add(evidence)

    if session_obj.estado in {
        ValidationSessionState.CREATED.value,
        ValidationSessionState.ENV_CHECK.value,
        ValidationSessionState.LIVENESS.value,
        ValidationSessionState.CALIBRATION.value,
        ValidationSessionState.RECORDING.value,
    }:
        session_obj.estado = ValidationSessionState.UPLOADING.value

    await db.commit()
    await db.refresh(evidence)
    await db.refresh(session_obj)
    return evidence, False


async def finalize_validation_session(
    db: AsyncSession,
    session_obj: ValidationSession,
    payload: FinalizeSessionRequest | None = None,
    storage: GarageS3StorageService | None = None,
    enqueue_celery: bool = True,
) -> tuple[EvidenceFile, int, str | None]:
    """
    Verify all chunks `0..N-1` are present, assemble the full recording in Garage S3
    with its SHA-256 hash, transition session state to `processing`, and enqueue Celery.
    """
    cfg = load_football_config()
    storage_svc = storage or garage_s3_storage

    chunk_evidences = sorted(
        [ev for ev in session_obj.evidence_files if ev.tipo.startswith("chunk:")],
        key=lambda ev: int(ev.tipo.split(":", 1)[1]),
    )
    if not chunk_evidences:
        raise SkillMatchException(
            statuscode=status.HTTP_400_BAD_REQUEST,
            message="No hay fragmentos subidos para ensamblar en esta sesión.",
        )

    db_indices = [int(ev.tipo.split(":", 1)[1]) for ev in chunk_evidences]
    expected_count = (
        payload.expected_chunks
        if payload and payload.expected_chunks is not None
        else len(db_indices)
    )
    expected_indices = list(range(expected_count))
    if db_indices != expected_indices:
        missing = sorted(set(expected_indices) - set(db_indices))
        raise SkillMatchException(
            statuscode=status.HTTP_400_BAD_REQUEST,
            message=f"Fragmentos incompletos. Faltan los fragmentos: {missing}.",
        )

    try:
        assembled_uri, assembled_sha256, assembled_size, indices = (
            storage_svc.assemble_session_chunks(
                session_id=str(session_obj.id),
                extension="mp4",
                content_type="video/mp4",
            )
        )
    except (ValueError, FileNotFoundError) as exc:
        raise SkillMatchException(
            statuscode=status.HTTP_400_BAD_REQUEST,
            message=str(exc),
        ) from exc

    total_duration_s = (
        payload.duration_seconds
        if payload and payload.duration_seconds is not None
        else float(len(indices) * cfg.session.chunk_duration_seconds)
    )
    fps = payload.fps if payload and payload.fps is not None else 30.0
    expires_at = datetime.now(UTC) + timedelta(days=cfg.session.retention_days)

    existing_video = next(
        (ev for ev in session_obj.evidence_files if ev.tipo == "video"),
        None,
    )
    if existing_video is not None:
        existing_video.ruta_minio = assembled_uri
        existing_video.duracion_s = total_duration_s
        existing_video.fps = fps
        existing_video.sha256 = assembled_sha256
        existing_video.expira_en = expires_at
        video_evidence = existing_video
    else:
        video_evidence = EvidenceFile(
            session_id=session_obj.id,
            tipo="video",
            ruta_minio=assembled_uri,
            duracion_s=total_duration_s,
            fps=fps,
            sha256=assembled_sha256,
            expira_en=expires_at,
        )
        db.add(video_evidence)

    session_obj.estado = ValidationSessionState.PROCESSING.value
    session_obj.finalizada_en = datetime.now(UTC)
    await _upsert_session_metadata(
        db=db,
        session_obj=session_obj,
        updates={
            "assembly": {
                "assembled_uri": assembled_uri,
                "assembled_sha256": assembled_sha256,
                "assembled_size_bytes": assembled_size,
                "total_chunks": len(indices),
                "duration_seconds": total_duration_s,
            }
        },
    )

    await db.commit()
    await db.refresh(video_evidence)
    await db.refresh(session_obj)

    task_id: str | None = None
    if enqueue_celery:
        try:
            async_res = process_session.delay(str(session_obj.id))
            task_id = str(async_res.id)
        except (OSError, RuntimeError):
            task_id = None

    return video_evidence, assembled_size, task_id


async def record_client_event_incident(
    db: AsyncSession,
    session_id: UUID,
    event_type: str,
    timestamp_ms: int,
) -> FraudIncident:
    """Persist a client-side anti-fraud event (`tab_hidden`, `focus_lost`, `fullscreen_exit`)."""
    incident = FraudIncident(
        session_id=session_id,
        tipo=event_type,
        severidad="medium",
        t_ms=max(0, timestamp_ms),
        detalle=f"Evento de cliente reportado por WebSocket: {event_type}",
    )
    db.add(incident)
    await db.commit()
    await db.refresh(incident)
    return incident


async def _load_active_level_classifier(
    db: AsyncSession,
) -> LevelClassifierProtocol | None:
    """
    Check `model_versions` for an active `level_classifier` entry (`activa = True`).
    If present and its artifact exists on disk, load `TrainedArtifactLevelClassifier`
    without requiring any code changes.
    """
    stmt = (
        select(ModelVersion)
        .where(
            ModelVersion.nombre == "level_classifier",
            ModelVersion.activa.is_(True),
        )
        .order_by(ModelVersion.created_at.desc())
        .limit(1)
    )
    res = await db.execute(stmt)
    active_model = res.scalar_one_or_none()
    if active_model is None:
        return None

    try:
        return TrainedArtifactLevelClassifier(
            artifact_path=active_model.ruta_onnx,
            version_tag=f"{active_model.nombre}:{active_model.version}",
        )
    except (OSError, ValueError, KeyError):
        return None


async def evaluate_and_persist_session_result(
    db: AsyncSession,
    session_obj: ValidationSession,
    video_path: str | None = None,
    audio_path: str | None = None,
    detected_faces_count: int = 1,
) -> ValidationResult:
    """
    Execute the complete football validation pipeline for `session_obj`, persist
    `DetectedEvent`, `ChallengeSegment` compliance, `SessionFeature`, `FraudIncident`,
    and `ValidationResult`, and update `session_obj.estado` (`scored` or `needs_review`).
    """
    track: BallTrack | None = None
    candidates = []
    video_integrity: dict[str, Any] | None = None
    actual_duration_s: float | None = None

    if video_path:
        try:
            track = track_ball_in_video(video_path)
            if track.points and track.fps > 0:
                actual_duration_s = len(track.points) / float(track.fps)
            candidates = detect_video_touch_events(track)
            video_integrity = inspect_video_integrity(video_path)
        except ValueError:
            track = None

    audio_events = []
    if audio_path:
        try:
            audio_events = detect_audio_impact_events(audio_path)
        except Exception:  # noqa: BLE001
            audio_events = []

    cal_ms: int | None = None
    expected_duration_s: float | None = None
    if session_obj.features and isinstance(session_obj.features.features_json, dict):
        cal_dict = session_obj.features.features_json.get("calibration")
        if isinstance(cal_dict, dict) and "client_touch_timestamp_ms" in cal_dict:
            cal_ms = int(cal_dict["client_touch_timestamp_ms"])
        asm_dict = session_obj.features.features_json.get("assembly")
        if isinstance(asm_dict, dict) and "duration_seconds" in asm_dict:
            expected_duration_s = float(asm_dict["duration_seconds"])

    fused: FusionSummary = fuse_audio_video_events(
        video_events=candidates,
        audio_events=audio_events,
        calibration_touch_ms=cal_ms,
    )

    for ev in fused.events:
        db.add(
            DetectedEvent(
                session_id=session_obj.id,
                tipo="touch_fused",
                t_ms=ev.t_ms,
                estado=ev.estado,
                confianza=ev.confianza,
            )
        )

    plan_dicts = [
        {
            "indice": s.indice,
            "tipo": s.tipo,
            "inicio_servidor_ms": s.inicio_servidor_ms,
            "duracion_ms": s.duracion_ms,
        }
        for s in session_obj.segments
    ]
    challenge_eval: ChallengeEvaluationSummary | None = None
    if plan_dicts:
        challenge_eval = evaluate_challenge_plan(
            segments_plan=plan_dicts,
            fused_events=fused.events,
            track=track,
        )
        eval_by_idx = {sr.indice: sr for sr in challenge_eval.segments}
        for seg_model in session_obj.segments:
            if seg_model.indice in eval_by_idx:
                sr = eval_by_idx[seg_model.indice]
                seg_model.cumplimiento = sr.cumplimiento
                seg_model.latencia_reaccion_ms = sr.latencia_reaccion_ms

    features_dict = extract_session_features(
        track=track,
        fusion=fused,
        challenge_eval=challenge_eval,
        session_duration_s=actual_duration_s or expected_duration_s,
    )
    await _upsert_session_metadata(db=db, session_obj=session_obj, updates=features_dict)

    active_clf = await _load_active_level_classifier(db)
    scoring_out = score_session_features(
        features=features_dict,
        classifier=active_clf,
    )

    existing_client_incidents = [
        {"tipo": inc.tipo, "t_ms": inc.t_ms}
        for inc in session_obj.fraud_incidents
    ]
    fraud_out = evaluate_fraud_signals(
        fusion=fused,
        challenge_eval=challenge_eval,
        track=track,
        client_events=existing_client_incidents,
        video_integrity=video_integrity,
        expected_duration_s=expected_duration_s,
        actual_video_duration_s=actual_duration_s,
        detected_faces_count=detected_faces_count,
    )

    existing_types = {inc.tipo for inc in session_obj.fraud_incidents}
    for sig in fraud_out.incidencias:
        if sig.tipo not in existing_types:
            db.add(
                FraudIncident(
                    session_id=session_obj.id,
                    tipo=sig.tipo,
                    severidad=sig.severidad,
                    t_ms=sig.t_ms,
                    detalle=sig.detalle,
                )
            )

    requires_review = scoring_out.requiere_revision or fraud_out.requiere_revision
    session_obj.version_modelo = scoring_out.version_modelo
    session_obj.version_config = scoring_out.version_config
    session_obj.estado = (
        ValidationSessionState.NEEDS_REVIEW.value
        if requires_review
        else ValidationSessionState.SCORED.value
    )

    if session_obj.result is not None:
        result_row = session_obj.result
        result_row.nivel = scoring_out.nivel
        result_row.probabilidades = scoring_out.probabilidades
        result_row.confianza = scoring_out.confianza
        result_row.puntaje_riesgo = fraud_out.puntaje_riesgo
        result_row.requiere_revision = requires_review
        result_row.retroalimentacion = scoring_out.retroalimentacion
    else:
        result_row = ValidationResult(
            session_id=session_obj.id,
            nivel=scoring_out.nivel,
            probabilidades=scoring_out.probabilidades,
            confianza=scoring_out.confianza,
            puntaje_riesgo=fraud_out.puntaje_riesgo,
            requiere_revision=requires_review,
            retroalimentacion=scoring_out.retroalimentacion,
        )
        db.add(result_row)

    await db.commit()
    await db.refresh(result_row)
    await db.refresh(session_obj)
    return result_row


async def get_validation_result_payload(
    db: AsyncSession,
    session_obj: ValidationSession,
) -> ValidationResultResponse:
    """
    Build `ValidationResultResponse` for `GET /sessions/{id}/result`.
    If the session has not yet been scored, evaluates on-the-fly from stored metadata.
    """
    if session_obj.result is None:
        await evaluate_and_persist_session_result(db=db, session_obj=session_obj)
        session_obj = await get_Owned_validation_session(
            db=db, session_id=session_obj.id, user_id=session_obj.user_id
        )

    assert session_obj.result is not None
    res = session_obj.result
    f_json = (
        session_obj.features.features_json
        if session_obj.features and isinstance(session_obj.features.features_json, dict)
        else {}
    )

    segments_read = [
        ChallengeSegmentRead(
            indice=s.indice,
            tipo=s.tipo,  # type: ignore[arg-type]
            inicio_servidor_ms=s.inicio_servidor_ms,
            duracion_ms=s.duracion_ms,
            cumplimiento=s.cumplimiento,
            latencia_reaccion_ms=s.latencia_reaccion_ms,
        )
        for s in session_obj.segments
    ]
    metrics = ValidationMetricsRead(
        toques=int(f_json.get("total_touches", 0)),
        racha=int(f_json.get("max_streak", 0)),
        toques_por_minuto=float(f_json.get("touches_per_minute", 0.0)),
        altura_media=float(f_json.get("mean_height_diameters", 0.0)),
        regularidad=float(f_json.get("regularity_score", 0.0)),
        cumplimiento_por_tramo=segments_read,
    )
    incidents_read = [
        FraudIncidentRead(
            tipo=inc.tipo,
            severidad=inc.severidad,
            t_ms=inc.t_ms,
            detalle=inc.detalle,
        )
        for inc in session_obj.fraud_incidents
    ]

    return ValidationResultResponse(
        session_id=session_obj.id,
        estado=session_obj.estado,
        nivel=res.nivel,
        probabilidades=res.probabilidades,
        confianza=res.confianza,
        metricas=metrics,
        coherencia_audio_video=float(f_json.get("av_coherence", 0.0)),
        puntaje_riesgo=res.puntaje_riesgo,
        incidencias=incidents_read,
        retroalimentacion=res.retroalimentacion,
        requiere_revision=res.requiere_revision,
        version_modelo=session_obj.version_modelo,
        version_config=session_obj.version_config,
    )
