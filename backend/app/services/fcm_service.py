"""Firebase Cloud Messaging (FCM) dispatch service for native push notifications."""

import logging
from pathlib import Path
from uuid import UUID

import firebase_admin
from firebase_admin import credentials, messaging
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.device_push_token import DevicePushToken
from app.schemas.device_push_token import DevicePushTokenRegister, DevicePushTokenResponse

logger = logging.getLogger("skillmatch.fcm")

_firebase_initialized = False


def _init_firebase() -> bool:
    global _firebase_initialized
    if _firebase_initialized:
        return True

    try:
        firebase_admin.get_app()
        _firebase_initialized = True
        return True
    except ValueError:
        pass

    creds_path = settings.FIREBASE_CREDENTIALS_PATH
    if not creds_path:
        logger.warning("FIREBASE_CREDENTIALS_PATH no configurado.")
        return False

    path = Path(creds_path)
    if not path.is_absolute():
        backend_dir = Path(__file__).resolve().parent.parent.parent
        candidates = [
            backend_dir / creds_path,
            Path.cwd() / creds_path,
            Path.cwd() / "backend" / creds_path,
        ]
        found = False
        for c in candidates:
            if c.exists():
                path = c
                found = True
                break
        if not found:
            logger.warning(f"Archivo de credenciales de Firebase no encontrado en: {creds_path}")
            return False

    try:
        cred = credentials.Certificate(str(path))
        firebase_admin.initialize_app(cred)
        _firebase_initialized = True
        logger.info("Firebase Admin SDK inicializado exitosamente.")
        return True
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Error al inicializar Firebase Admin SDK: {exc}")
        return False


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
    async def send_push_to_user(
        cls,
        db: AsyncSession,
        *,
        user_id: UUID,
        title: str,
        body: str,
        data: dict[str, str] | None = None,
    ) -> int:
        """Sends native FCM push notification to all active devices registered by the user."""
        if not _init_firebase():
            return 0

        # Query all active tokens
        stmt = select(DevicePushToken).where(
            DevicePushToken.user_id == user_id,
            DevicePushToken.is_active.is_(True),
        )
        result = await db.execute(stmt)
        tokens = result.scalars().all()

        if not tokens:
            logger.info(f"Usuario {user_id} no tiene dispositivos FCM activos registrados.")
            return 0

        sent_count = 0
        dead_tokens: list[str] = []

        for t in tokens:
            try:
                msg = messaging.Message(
                    notification=messaging.Notification(
                        title=title,
                        body=body,
                    ),
                    data=data or {},
                    android=messaging.AndroidConfig(
                        priority="high",
                        notification=messaging.AndroidNotification(
                            channel_id="skillmatch_notifications",
                            sound="default",
                            default_vibrate_timings=True,
                            default_light_settings=True,
                        ),
                    ),
                    token=t.fcm_token,
                )
                messaging.send(msg)
                sent_count += 1
            except messaging.UnregisteredError:
                logger.info(f"Token FCM expirado o desinstalado: {t.fcm_token[:20]}...")
                dead_tokens.append(t.fcm_token)
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"Error al enviar push FCM al token {t.fcm_token[:20]}...: {exc}")

        if dead_tokens:
            await db.execute(
                update(DevicePushToken)
                .where(DevicePushToken.fcm_token.in_(dead_tokens))
                .values(is_active=False)
            )
            await db.commit()

        logger.info(f"FCM push enviado a {sent_count}/{len(tokens)} dispositivo(s) del usuario {user_id}.")
        return sent_count
