from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Header,
    Query,
    Request,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from jose import JWTError
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.exceptions import SkillMatchException
from app.core.security import decode_jwt_payload
from app.db.session import AsyncSessionLocal, get_db
from app.football.schemas import (
    CalibrationRequest,
    CalibrationResponse,
    ChallengeSegmentRead,
    ChunkUploadResponse,
    CreateValidationSessionRequest,
    CreateValidationSessionResponse,
    EnvCheckRequest,
    EnvCheckResponse,
    FinalizeSessionRequest,
    FinalizeSessionResponse,
    LivenessRequest,
    LivenessResponse,
    ValidationSessionStatusResponse,
    WSClientMessage,
)
from app.football.services.session_service import (
    create_validation_session,
    evaluate_env_check,
    extract_confirmed_chunk_indices,
    finalize_validation_session,
    get_Owned_validation_session,
    record_calibration_touch,
    record_client_event_incident,
    record_liveness_check,
    upload_session_chunk,
)
from app.models.user import User
from app.schemas.response import APIResponse

logger = logging.getLogger("skillmatch.football.api")

router = APIRouter(tags=["Football Validation"])

CurrentUserDep = Annotated[User, Depends(get_current_user)]
DbSessionDep = Annotated[AsyncSession, Depends(get_db)]


async def _authenticate_ws_user(
    websocket: WebSocket,
    token: str | None,
    db: AsyncSession,
) -> User | None:
    raw_token = token
    if not raw_token:
        auth_header = websocket.headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            raw_token = auth_header.split(" ", 1)[1]

    if not raw_token:
        return None

    try:
        payload = decode_jwt_payload(raw_token)
        sub = payload.get("sub")
        token_type = payload.get("type")
        if not sub or token_type != "access":
            return None
        user_id = UUID(str(sub))
    except (JWTError, ValueError):
        return None

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active or user.is_locked:
        return None
    return user


@router.post(
    "/sessions",
    response_model=APIResponse[CreateValidationSessionResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Crear una sesión de validación de fútbol",
)
async def create_session_endpoint(
    request: Request,
    current_user: CurrentUserDep,
    db: DbSessionDep,
    payload: CreateValidationSessionRequest | None = None,
) -> APIResponse[CreateValidationSessionResponse]:
    skill_id = payload.skill_id if payload else None
    prefix = "/api/v1/football" if "/api/v1/" in request.url.path else "/api/football"
    session_obj, remaining_attempts, ws_url = await create_validation_session(
        db=db,
        user_id=current_user.id,
        skill_id=skill_id,
        route_prefix=prefix,
    )
    data = CreateValidationSessionResponse(
        session_id=session_obj.id,
        ws_url=ws_url,
        semilla=session_obj.semilla,
        intentos_restantes=remaining_attempts,
        estado=session_obj.estado,
        version_modelo=session_obj.version_modelo,
        version_config=session_obj.version_config,
    )
    return APIResponse(
        statuscode=status.HTTP_201_CREATED,
        message="Sesión de validación de fútbol creada exitosamente.",
        data=data,
    )


@router.get(
    "/sessions/{session_id}",
    response_model=APIResponse[ValidationSessionStatusResponse],
    status_code=status.HTTP_200_OK,
    summary="Obtener el estado actual de una sesión de validación de fútbol",
)
async def get_session_status_endpoint(
    session_id: UUID,
    current_user: CurrentUserDep,
    db: DbSessionDep,
) -> APIResponse[ValidationSessionStatusResponse]:
    session_obj = await get_Owned_validation_session(
        db=db,
        session_id=session_id,
        user_id=current_user.id,
    )
    segments = [
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
    confirmed_chunks = extract_confirmed_chunk_indices(session_obj)
    data = ValidationSessionStatusResponse(
        id=session_obj.id,
        user_id=session_obj.user_id,
        skill_id=session_obj.skill_id,
        estado=session_obj.estado,
        semilla=session_obj.semilla,
        creada_en=session_obj.creada_en,
        finalizada_en=session_obj.finalizada_en,
        version_modelo=session_obj.version_modelo,
        version_config=session_obj.version_config,
        segments=segments,
        confirmed_chunks=confirmed_chunks,
    )
    return APIResponse(
        statuscode=status.HTTP_200_OK,
        message="Estado de la sesión obtenido exitosamente.",
        data=data,
    )


@router.post(
    "/sessions/{session_id}/env-check",
    response_model=APIResponse[EnvCheckResponse],
    status_code=status.HTTP_200_OK,
    summary="Registrar y validar chequeo de ambiente (luz, ruido, rostro, balón, conexión)",
)
async def env_check_endpoint(
    session_id: UUID,
    payload: EnvCheckRequest,
    current_user: CurrentUserDep,
    db: DbSessionDep,
) -> APIResponse[EnvCheckResponse]:
    session_obj = await get_Owned_validation_session(
        db=db,
        session_id=session_id,
        user_id=current_user.id,
    )
    passed, failures = await evaluate_env_check(
        db=db,
        session_obj=session_obj,
        payload=payload,
    )
    msg = (
        "Verificación de ambiente superada exitosamente."
        if passed
        else "El ambiente no cumple todas las condiciones requeridas."
    )
    return APIResponse(
        statuscode=status.HTTP_200_OK,
        message=msg,
        data=EnvCheckResponse(
            session_id=session_obj.id,
            passed=passed,
            estado=session_obj.estado,
            failures=failures,
        ),
    )


@router.post(
    "/sessions/{session_id}/liveness",
    response_model=APIResponse[LivenessResponse],
    status_code=status.HTTP_200_OK,
    summary="Registrar resultado de prueba de vida",
)
async def liveness_endpoint(
    session_id: UUID,
    payload: LivenessRequest,
    current_user: CurrentUserDep,
    db: DbSessionDep,
) -> APIResponse[LivenessResponse]:
    session_obj = await get_Owned_validation_session(
        db=db,
        session_id=session_id,
        user_id=current_user.id,
    )
    await record_liveness_check(
        db=db,
        session_obj=session_obj,
        payload=payload,
    )
    return APIResponse(
        statuscode=status.HTTP_200_OK,
        message="Prueba de vida validada exitosamente.",
        data=LivenessResponse(
            session_id=session_obj.id,
            passed=True,
            estado=session_obj.estado,
        ),
    )


@router.post(
    "/sessions/{session_id}/calibration",
    response_model=APIResponse[CalibrationResponse],
    status_code=status.HTTP_200_OK,
    summary="Registrar marca de tiempo del toque de calibración",
)
async def calibration_endpoint(
    session_id: UUID,
    payload: CalibrationRequest,
    current_user: CurrentUserDep,
    db: DbSessionDep,
) -> APIResponse[CalibrationResponse]:
    session_obj = await get_Owned_validation_session(
        db=db,
        session_id=session_id,
        user_id=current_user.id,
    )
    await record_calibration_touch(
        db=db,
        session_obj=session_obj,
        payload=payload,
    )
    return APIResponse(
        statuscode=status.HTTP_200_OK,
        message="Toque de calibración registrado exitosamente.",
        data=CalibrationResponse(
            session_id=session_obj.id,
            client_touch_timestamp_ms=payload.client_touch_timestamp_ms,
            estado=session_obj.estado,
        ),
    )


@router.put(
    "/sessions/{session_id}/chunks/{chunk_index}",
    response_model=APIResponse[ChunkUploadResponse],
    status_code=status.HTTP_200_OK,
    summary="Subir fragmento n del video (idempotente)",
)
async def upload_chunk_endpoint(
    session_id: UUID,
    chunk_index: int,
    request: Request,
    current_user: CurrentUserDep,
    db: DbSessionDep,
    file: Annotated[UploadFile | None, File()] = None,
    x_chunk_sha256: Annotated[str | None, Header()] = None,
) -> APIResponse[ChunkUploadResponse]:
    session_obj = await get_Owned_validation_session(
        db=db,
        session_id=session_id,
        user_id=current_user.id,
    )

    if file is not None:
        payload_bytes = await file.read()
        content_type = file.content_type or "video/mp4"
    else:
        payload_bytes = await request.body()
        content_type = request.headers.get("content-type", "video/mp4")

    evidence, is_replay = await upload_session_chunk(
        db=db,
        session_obj=session_obj,
        chunk_index=chunk_index,
        payload_bytes=payload_bytes,
        content_type=content_type,
        expected_sha256=x_chunk_sha256,
    )
    return APIResponse(
        statuscode=status.HTTP_200_OK,
        message=(
            f"Fragmento {chunk_index} ya estaba confirmado (idempotente)."
            if is_replay
            else f"Fragmento {chunk_index} almacenado exitosamente."
        ),
        data=ChunkUploadResponse(
            session_id=session_obj.id,
            chunk_index=chunk_index,
            sha256=evidence.sha256,
            size_bytes=len(payload_bytes),
            storage_uri=evidence.ruta_minio,
            idempotent_replay=is_replay,
            estado=session_obj.estado,
        ),
    )


@router.post(
    "/sessions/{session_id}/finalize",
    response_model=APIResponse[FinalizeSessionResponse],
    status_code=status.HTTP_202_ACCEPTED,
    summary="Cerrar grabación, ensamblar fragmentos en Garage S3 y encolar procesamiento",
)
async def finalize_session_endpoint(
    session_id: UUID,
    current_user: CurrentUserDep,
    db: DbSessionDep,
    payload: FinalizeSessionRequest | None = None,
) -> APIResponse[FinalizeSessionResponse]:
    session_obj = await get_Owned_validation_session(
        db=db,
        session_id=session_id,
        user_id=current_user.id,
    )
    confirmed_chunks = extract_confirmed_chunk_indices(session_obj)
    video_evidence, assembled_size, task_id = await finalize_validation_session(
        db=db,
        session_obj=session_obj,
        payload=payload,
    )
    return APIResponse(
        statuscode=status.HTTP_202_ACCEPTED,
        message="Grabación ensamblada exitosamente y encolada para procesamiento.",
        data=FinalizeSessionResponse(
            session_id=session_obj.id,
            estado=session_obj.estado,
            assembled_uri=video_evidence.ruta_minio,
            assembled_sha256=video_evidence.sha256,
            assembled_size_bytes=assembled_size,
            total_chunks=len(confirmed_chunks),
            task_id=task_id,
        ),
    )


@asynccontextmanager
async def _open_ws_db(websocket: WebSocket) -> AsyncGenerator[AsyncSession, None]:
    override_fn = websocket.app.dependency_overrides.get(get_db)
    if override_fn is not None:
        gen = override_fn()
        db = await anext(gen)
        try:
            yield db
        finally:
            try:
                await anext(gen)
            except StopAsyncIteration:
                pass
    else:
        async with AsyncSessionLocal() as db:
            yield db


@router.websocket("/sessions/{session_id}/ws")
async def session_websocket_endpoint(
    websocket: WebSocket,
    session_id: UUID,
    token: Annotated[str | None, Query()] = None,
) -> None:
    async with _open_ws_db(websocket) as db:
        user = await _authenticate_ws_user(websocket, token, db)
        if user is None:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        try:
            session_obj = await get_Owned_validation_session(
                db=db,
                session_id=session_id,
                user_id=user.id,
            )
        except SkillMatchException:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        await websocket.accept()
        await websocket.send_json(
            {
                "type": "status",
                "session_id": str(session_obj.id),
                "data": {
                    "estado": session_obj.estado,
                    "semilla": session_obj.semilla,
                    "segments_count": len(session_obj.segments),
                },
            }
        )
        if session_obj.segments:
            first_seg = session_obj.segments[0]
            await websocket.send_json(
                {
                    "type": "command",
                    "session_id": str(session_obj.id),
                    "data": {
                        "indice": first_seg.indice,
                        "tipo": first_seg.tipo,
                        "inicio_servidor_ms": first_seg.inicio_servidor_ms,
                        "duracion_ms": first_seg.duracion_ms,
                    },
                }
            )

        try:
            while True:
                raw_msg = await websocket.receive_json()
                try:
                    msg = WSClientMessage.model_validate(raw_msg)
                except ValidationError:
                    await websocket.send_json(
                        {
                            "type": "status",
                            "session_id": str(session_obj.id),
                            "data": {"error": "invalid_message_format"},
                        }
                    )
                    continue

                if msg.type == "ping":
                    await websocket.send_json(
                        {
                            "type": "pong",
                            "session_id": str(session_obj.id),
                            "data": {"timestamp_ms": msg.timestamp_ms or 0},
                        }
                    )
                elif msg.type == "next_command":
                    target_idx = msg.segment_index or 0
                    matching_seg = next(
                        (s for s in session_obj.segments if s.indice == target_idx),
                        None,
                    )
                    if matching_seg is not None:
                        if msg.timestamp_ms is not None and msg.timestamp_ms >= 0:
                            matching_seg.inicio_servidor_ms = msg.timestamp_ms
                            await db.commit()
                        await websocket.send_json(
                            {
                                "type": "command",
                                "session_id": str(session_obj.id),
                                "data": {
                                    "indice": matching_seg.indice,
                                    "tipo": matching_seg.tipo,
                                    "inicio_servidor_ms": matching_seg.inicio_servidor_ms,
                                    "duracion_ms": matching_seg.duracion_ms,
                                },
                            }
                        )
                elif msg.type == "client_event" and msg.event is not None:
                    incident = await record_client_event_incident(
                        db=db,
                        session_id=session_obj.id,
                        event_type=msg.event,
                        timestamp_ms=msg.timestamp_ms or 0,
                    )
                    await websocket.send_json(
                        {
                            "type": "status",
                            "session_id": str(session_obj.id),
                            "data": {
                                "recorded_event": incident.tipo,
                                "t_ms": incident.t_ms,
                            },
                        }
                    )
        except WebSocketDisconnect:
            logger.info("WebSocket disconnected for session_id=%s", session_id)
