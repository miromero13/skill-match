import json
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, ExchangeModality
from app.schemas.user_profile import (
    BiometricEnrollRequest,
    IdentityVerifyRequest,
    UserProfilePatch,
    UserProfileResponse,
    UserProfileUpdate,
)
from app.services.biometric_service import BiometricService, EMBEDDING_DIMENSIONS


class UserProfileService:
    """
    Servicio de dominio para gestión del perfil personal y biometría facial.
    Opera directamente sobre la entidad User (sin tabla 1:1 redundante).
    """

    @staticmethod
    def _ensure_defaults(user: User) -> None:
        if user.languages is None:
            user.languages = ["Español"]
        if not user.timezone:
            user.timezone = "America/La_Paz"
        if user.links is None:
            user.links = {}
        if not user.exchange_modality:
            user.exchange_modality = ExchangeModality.VIRTUAL
        if user.presencial_radius_km is None:
            user.presencial_radius_km = 10
        if user.buffer_minutes is None:
            user.buffer_minutes = 15
        if user.gcal_synced is None:
            user.gcal_synced = False
        if not user.gcal_calendar_email:
            user.gcal_calendar_email = user.email

    @classmethod
    def to_response(cls, user: User) -> UserProfileResponse:
        cls._ensure_defaults(user)
        has_biometrics = bool(user.biometric_embedding and user.biometric_face_hash)
        dims: Optional[int] = None
        if has_biometrics and user.biometric_embedding:
            try:
                parsed = json.loads(user.biometric_embedding)
                if isinstance(parsed, list):
                    dims = len(parsed)
                else:
                    dims = EMBEDDING_DIMENSIONS
            except Exception:
                dims = EMBEDDING_DIMENSIONS

        return UserProfileResponse(
            id=user.id,
            user_id=user.id,
            full_name=user.full_name,
            email=user.email,
            bio=user.bio,
            avatar_url=user.avatar_url,
            languages=list(user.languages or ["Español"]),
            timezone=user.timezone or "America/La_Paz",
            links=dict(user.links or {}),
            exchange_modality=user.exchange_modality or ExchangeModality.VIRTUAL,
            presencial_radius_km=user.presencial_radius_km if user.presencial_radius_km is not None else 10,
            location_label=user.location_label,
            latitude=user.latitude,
            longitude=user.longitude,
            buffer_minutes=user.buffer_minutes if user.buffer_minutes is not None else 15,
            gcal_synced=bool(user.gcal_synced),
            gcal_calendar_email=user.gcal_calendar_email,
            has_biometric_enrollment=has_biometrics,
            biometric_enrolled_at=user.biometric_enrolled_at,
            biometric_face_hash=user.biometric_face_hash,
            embedding_dimensions=dims,
            identity_status=getattr(user, "identity_status", "NOT_VERIFIED") or "NOT_VERIFIED",
            id_document_number=getattr(user, "id_document_number", None),
            id_document_type=getattr(user, "id_document_type", "CI") or "CI",
            id_face_similarity_score=getattr(user, "id_face_similarity_score", None),
            identity_verified_at=getattr(user, "identity_verified_at", None),
            identity_rejection_reason=getattr(user, "identity_rejection_reason", None),
        )

    @classmethod
    async def get_profile(cls, db: AsyncSession, user: User) -> UserProfileResponse:
        cls._ensure_defaults(user)
        return cls.to_response(user)

    @classmethod
    async def update_profile(
        cls,
        db: AsyncSession,
        user: User,
        payload: UserProfileUpdate,
    ) -> UserProfileResponse:
        cls._ensure_defaults(user)

        if payload.full_name is not None:
            user.full_name = payload.full_name.strip()
        if payload.avatar_url is not None:
            user.avatar_url = payload.avatar_url

        user.bio = payload.bio
        user.languages = payload.languages
        user.timezone = payload.timezone
        user.links = payload.links
        user.exchange_modality = payload.exchange_modality
        user.presencial_radius_km = payload.presencial_radius_km
        user.location_label = payload.location_label
        user.latitude = payload.latitude
        user.longitude = payload.longitude
        user.buffer_minutes = payload.buffer_minutes
        user.gcal_synced = payload.gcal_synced
        user.gcal_calendar_email = payload.gcal_calendar_email

        await db.commit()
        await db.refresh(user)
        return cls.to_response(user)

    @classmethod
    async def patch_profile(
        cls,
        db: AsyncSession,
        user: User,
        payload: UserProfilePatch,
    ) -> UserProfileResponse:
        cls._ensure_defaults(user)
        fields_set = payload.model_fields_set

        if "full_name" in fields_set and payload.full_name is not None:
            user.full_name = payload.full_name.strip()
        if "avatar_url" in fields_set:
            user.avatar_url = payload.avatar_url
        if "bio" in fields_set:
            user.bio = payload.bio
        if "languages" in fields_set and payload.languages is not None:
            user.languages = payload.languages
        if "timezone" in fields_set and payload.timezone is not None:
            user.timezone = payload.timezone
        if "links" in fields_set and payload.links is not None:
            user.links = payload.links
        if "exchange_modality" in fields_set and payload.exchange_modality is not None:
            user.exchange_modality = payload.exchange_modality
        if "presencial_radius_km" in fields_set and payload.presencial_radius_km is not None:
            user.presencial_radius_km = payload.presencial_radius_km
        if "location_label" in fields_set:
            user.location_label = payload.location_label
        if "latitude" in fields_set:
            user.latitude = payload.latitude
        if "longitude" in fields_set:
            user.longitude = payload.longitude
        if "buffer_minutes" in fields_set and payload.buffer_minutes is not None:
            user.buffer_minutes = payload.buffer_minutes
        if "gcal_synced" in fields_set and payload.gcal_synced is not None:
            user.gcal_synced = payload.gcal_synced
        if "gcal_calendar_email" in fields_set:
            user.gcal_calendar_email = payload.gcal_calendar_email

        await db.commit()
        await db.refresh(user)
        return cls.to_response(user)

    @classmethod
    async def enroll_biometrics(
        cls,
        db: AsyncSession,
        user: User,
        payload: BiometricEnrollRequest,
    ) -> UserProfileResponse:
        cls._ensure_defaults(user)
        embedding_json, face_hash, enrolled_at = BiometricService.enroll_face(
            image_base64=payload.image_base64,
            frames=payload.frames,
            lighting_score=payload.lighting_score,
            face_centered=payload.face_centered,
        )
        user.biometric_embedding = embedding_json
        user.biometric_face_hash = face_hash
        user.biometric_enrolled_at = enrolled_at

        await db.commit()
        await db.refresh(user)
        return cls.to_response(user)

    @classmethod
    async def verify_identity(
        cls,
        db: AsyncSession,
        user: User,
        payload: IdentityVerifyRequest,
    ) -> UserProfileResponse:
        """
        Verifica la identidad del usuario de forma 100% automática contrastando
        la fotografía de su carnet de identidad CI/DNI contra su rostro en vivo.
        Previene completamente el fraude de suplantación en el origen.
        """
        cls._ensure_defaults(user)
        try:
            embedding_json, face_hash, similarity, verified_at = (
                BiometricService.verify_identity_with_id_card(
                    id_card_base64=payload.id_card_base64,
                    selfie_base64=payload.selfie_base64,
                    id_number=payload.id_number,
                    declared_full_name=payload.full_name,
                    account_full_name=user.full_name,
                    lighting_score=payload.lighting_score,
                    face_centered=payload.face_centered,
                )
            )
            user.identity_status = "VERIFIED"
            user.id_document_number = payload.id_number.strip().upper()
            user.id_document_type = "CI"
            user.id_face_similarity_score = similarity
            user.identity_verified_at = verified_at
            user.identity_rejection_reason = None
            user.biometric_embedding = embedding_json
            user.biometric_face_hash = face_hash
            user.biometric_enrolled_at = verified_at

            await db.commit()
            await db.refresh(user)
            return cls.to_response(user)
        except Exception as exc:
            if getattr(exc, "statuscode", None) == 503:
                # Un fallo de la plataforma (modelos biométricos ausentes) no es un rechazo del miembro.
                raise
            user.identity_status = "REJECTED"
            user.identity_rejection_reason = getattr(exc, "message", str(exc))
            await db.commit()
            raise exc
