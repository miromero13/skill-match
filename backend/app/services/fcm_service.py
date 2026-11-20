"""Firebase Cloud Messaging (FCM) dispatch service for native push notifications."""

import asyncio
import json
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

import firebase_admin
from firebase_admin import credentials, messaging
from firebase_admin import exceptions as firebase_exceptions
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import BASE_DIR, settings
from app.models.device_push_token import DevicePushToken
from app.schemas.device_push_token import DevicePushTokenRegister, DevicePushTokenResponse

logger = logging.getLogger("skillmatch.fcm")

ANDROID_CHANNEL_ID = "skillmatch_notifications"
FIREBASE_NOT_INITIALIZED = "FIREBASE_NOT_INITIALIZED"


@dataclass
class FirebaseState:
    """Observable init state. `error` is a short message and never contains key material."""

    initialized: bool = False
    source: str | None = None  # "json" | "path" | None
    error: str | None = None


_firebase_state = FirebaseState()


def get_firebase_status() -> dict[str, Any]:
    state = _firebase_state
    return {"initialized": state.initialized, "source": state.source, "error": state.error}


def _fail(message: str) -> bool:
    _firebase_state.error = message
    logger.error("Firebase Admin SDK no inicializado: %s", message)
    return False


def _resolve_credentials_path(raw: str) -> Path | None:
    path = Path(raw)
    if path.is_absolute():
        return path if path.exists() else None
    # BASE_DIR is backend/; also accept running from the repo root (cwd/backend/...).
    for candidate in (BASE_DIR / path, Path.cwd() / path, Path.cwd() / "backend" / path):
        if candidate.exists():
            return candidate
    return None


def _init_firebase() -> bool:
    """Initialize once; a failed attempt is retried on the next send, keeping the error visible."""
    state = _firebase_state
    if state.initialized:
        return True

    try:
        firebase_admin.get_app()
        state.initialized, state.error = True, None
        return True
    except ValueError:
        pass

    raw_json = settings.FIREBASE_CREDENTIALS_JSON.get_secret_value().strip() if settings.FIREBASE_CREDENTIALS_JSON else ""
    if raw_json:
        source = "json"
        try:
            info = json.loads(raw_json)
        except ValueError:
            return _fail("FIREBASE_CREDENTIALS_JSON no contiene un JSON válido")
        if not isinstance(info, dict):
            return _fail("FIREBASE_CREDENTIALS_JSON debe ser un objeto JSON de cuenta de servicio")
        cert_input: Any = info
    elif settings.FIREBASE_CREDENTIALS_PATH:
        source = "path"
        path = _resolve_credentials_path(settings.FIREBASE_CREDENTIALS_PATH)
        if path is None:
            return _fail("Archivo de credenciales de Firebase no encontrado (FIREBASE_CREDENTIALS_PATH)")
        if not path.is_file():
            return _fail("FIREBASE_CREDENTIALS_PATH apunta a un directorio, no a un archivo JSON")
        cert_input = str(path)
    else:
        return _fail("Firebase no configurado: defina FIREBASE_CREDENTIALS_JSON o FIREBASE_CREDENTIALS_PATH")

    try:
        firebase_admin.initialize_app(credentials.Certificate(cert_input))
    except Exception as exc:  # noqa: BLE001 — never crash the app; never echo key material
        return _fail(f"Credenciales de Firebase inválidas ({type(exc).__name__}, origen: {source})")

    state.initialized, state.source, state.error = True, source, None
    logger.info("Firebase Admin SDK inicializado exitosamente (origen: %s).", source)
    return True


def ensure_firebase_initialized() -> bool:
    """Public init attempt (admin diagnostics); never raises, state stays observable."""
    return _init_firebase()


def _is_dead_token_error(exc: Exception) -> bool:
    if isinstance(exc, (messaging.UnregisteredError, messaging.SenderIdMismatchError)):
        return True
    return isinstance(exc, firebase_exceptions.InvalidArgumentError) and "token" in str(exc).lower()


def _build_message(token: str, title: str, body: str, data: dict[str, str] | None) -> messaging.Message:
    return messaging.Message(
        notification=messaging.Notification(title=title, body=body),
        data={str(k): str(v) for k, v in (data or {}).items()},
        android=messaging.AndroidConfig(
            priority="high",
            notification=messaging.AndroidNotification(
                channel_id=ANDROID_CHANNEL_ID,
                sound="default",
                default_vibrate_timings=True,
                default_light_settings=True,
            ),
        ),
        token=token,
    )


async def _deactivate_tokens(tokens: list[str]) -> None:
    """Own short session: never commits (or touches) the caller's transaction."""
    from app.db.session import BackgroundSessionLocal

    try:
        async with BackgroundSessionLocal() as db:
            await db.execute(
                update(DevicePushToken).where(DevicePushToken.fcm_token.in_(tokens)).values(is_active=False)
            )
            await db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning("No se pudieron desactivar %d token(s) FCM inválidos: %s", len(tokens), type(exc).__name__)


class FCMService:
    @classmethod
    async def register_device(
        cls,
        db: AsyncSession,
        *,
        user_id: UUID,
        payload: DevicePushTokenRegister,
    ) -> DevicePushTokenResponse:
        stmt = (
            insert(DevicePushToken)
            .values(
                user_id=user_id,
                fcm_token=payload.fcm_token,
                platform=payload.platform,
                device_label=payload.device_label,
                is_active=True,
            )
            .on_conflict_do_update(
                index_elements=[DevicePushToken.fcm_token],
                set_={
                    "user_id": user_id,
                    "platform": payload.platform,
                    "device_label": payload.device_label,
                    "is_active": True,
                },
            )
            .returning(DevicePushToken)
        )
        token_record = await db.scalar(stmt)
        await db.commit()
        return DevicePushTokenResponse.model_validate(token_record)

    @classmethod
    async def deactivate_device(
        cls,
        db: AsyncSession,
        *,
        user_id: UUID,
        fcm_token: str,
    ) -> bool:
        stmt = (
            update(DevicePushToken)
            .where(
                DevicePushToken.user_id == user_id,
                DevicePushToken.fcm_token == fcm_token,
            )
            .values(is_active=False)
        )
        result = await db.execute(stmt)
        await db.commit()
        return bool(result.rowcount)

    @classmethod
    async def send_to_tokens(
        cls,
        tokens: Sequence[str],
        *,
        title: str,
        body: str,
        data: dict[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        """Send to each token off the event loop; returns `[{token_suffix, ok, error}]` in token order."""
        if not tokens:
            return []
        if not _init_firebase():
            return [{"token_suffix": t[-8:], "ok": False, "error": FIREBASE_NOT_INITIALIZED} for t in tokens]

        results: list[dict[str, Any]] = []
        dead_tokens: list[str] = []
        for token in tokens:
            error: str | None = None
            try:
                await asyncio.to_thread(messaging.send, _build_message(token, title, body, data))
            except Exception as exc:  # noqa: BLE001
                error = type(exc).__name__
                if _is_dead_token_error(exc):
                    dead_tokens.append(token)
                    logger.info("Token FCM inválido o expirado (...%s): %s", token[-8:], error)
                else:
                    logger.warning("Error al enviar push FCM al token ...%s: %s", token[-8:], error)
            results.append({"token_suffix": token[-8:], "ok": error is None, "error": error})

        if dead_tokens:
            await _deactivate_tokens(dead_tokens)
        return results

    @classmethod
    async def send_push_to_user(
        cls,
        db: AsyncSession,
        *,
        user_id: UUID,
        title: str,
        body: str,
        data: dict[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        """Push to the user's active devices. `db` is only read; it is never committed here."""
        tokens = list(
            (
                await db.scalars(
                    select(DevicePushToken.fcm_token).where(
                        DevicePushToken.user_id == user_id,
                        DevicePushToken.is_active.is_(True),
                    )
                )
            ).all()
        )
        if not tokens:
            logger.info("Usuario %s no tiene dispositivos FCM activos registrados.", user_id)
            return []
        results = await cls.send_to_tokens(tokens, title=title, body=body, data=data)
        logger.info(
            "FCM push enviado a %d/%d dispositivo(s) del usuario %s.",
            sum(r["ok"] for r in results), len(results), user_id,
        )
        return results
