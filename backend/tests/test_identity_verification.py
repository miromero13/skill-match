import base64
import json
import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
import cv2
import numpy as np

from app.core.exceptions import SkillMatchException
from app.models.user import User, UserRole
from app.schemas.user_profile import IdentityVerifyRequest
from app.services.biometric_service import BiometricService
from app.services.user_profile_service import UserProfileService


def create_mock_jpeg_base64(color=(200, 200, 200), width=320, height=240, draw_face=False) -> str:
    """Genera una imagen JPEG válida codificada en base64."""
    img = np.ones((height, width, 3), dtype=np.uint8) * np.array(color, dtype=np.uint8)
    if draw_face:
        # Dibujar un círculo con ojos y boca para simular estructura facial
        cv2.circle(img, (width // 2, height // 2), 40, (150, 150, 150), -1)
        cv2.circle(img, (width // 2 - 15, height // 2 - 10), 5, (50, 50, 50), -1)
        cv2.circle(img, (width // 2 + 15, height // 2 - 10), 5, (50, 50, 50), -1)
        cv2.ellipse(img, (width // 2, height // 2 + 15), (15, 8), 0, 0, 180, (50, 50, 50), 2)
    success, buffer = cv2.imencode(".jpg", img)
    assert success
    return f"data:image/jpeg;base64,{base64.b64encode(buffer).decode('utf-8')}"


def test_name_similarity_matching():
    """Valida que el cotejo difuso de nombres admita variantes legítimas y rechace suplantaciones."""
    # Coincidencia exacta
    score, ok = BiometricService.check_name_similarity("Juan Carlos Perez Gomez", "Juan Carlos Perez Gomez")
    assert ok is True
    assert score == 1.0

    # Nombre sin acentos o con pequeñas variaciones
    score, ok = BiometricService.check_name_similarity("Juan Pérez Gómez", "Juan Perez Gomez")
    assert ok is True

    # Nombres invertidos o segundo nombre omitido
    score, ok = BiometricService.check_name_similarity("Juan Perez", "Juan Carlos Perez Gomez")
    assert ok is True

    # Persona completamente distinta (intento de fraude con carnet de otra persona)
    score, ok = BiometricService.check_name_similarity("Rodrigo Fernandez Ramos", "Ana Maria Garcia Lopez")
    assert ok is False
    assert score < 0.50


def test_identity_verification_rejects_name_mismatch():
    """Valida rechazo si el carnet presentado no pertenece al titular de la cuenta."""
    card_b64 = create_mock_jpeg_base64()
    selfie_b64 = create_mock_jpeg_base64()

    with pytest.raises(SkillMatchException) as exc_info:
        BiometricService.verify_identity_with_id_card(
            id_card_base64=card_b64,
            selfie_base64=selfie_b64,
            id_number="8392102",
            declared_full_name="Carlos Mendez Hurtado",
            account_full_name="Lucia Morales Ruiz",
        )
    assert exc_info.value.statuscode == 400
    assert "no coincide con el titular de la cuenta" in exc_info.value.message


def test_identity_verification_rejects_face_impersonation():
    """Valida rechazo estricto si el rostro en vivo no coincide con el del carnet."""
    card_b64 = create_mock_jpeg_base64()
    selfie_b64 = create_mock_jpeg_base64()

    # Simulamos que el detector devuelve vectores distintos para carnet y selfie
    vec_card = [1.0] + [0.0] * 127
    vec_selfie = [0.0, 1.0] + [0.0] * 126  # Ortogonal -> similitud 0.0

    with patch.object(BiometricService, "_process_id_card_face", return_value=vec_card):
        with patch.object(BiometricService, "_process_frame_with_opencv", return_value=vec_selfie):
            with pytest.raises(SkillMatchException) as exc_info:
                BiometricService.verify_identity_with_id_card(
                    id_card_base64=card_b64,
                    selfie_base64=selfie_b64,
                    id_number="8392102",
                    declared_full_name="Juan Perez Gomez",
                    account_full_name="Juan Perez Gomez",
                )
            assert exc_info.value.statuscode == 400
            assert "Suplantación detectada" in exc_info.value.message


def test_identity_verification_success():
    """Valida flujo exitoso de verificación cuando el carnet y la selfie coinciden."""
    card_b64 = create_mock_jpeg_base64()
    selfie_b64 = create_mock_jpeg_base64()

    # Mismo vector para simular que es la misma persona legítima
    vec = [0.5] * 4 + [0.0] * 124

    with patch.object(BiometricService, "_process_id_card_face", return_value=vec):
        with patch.object(BiometricService, "_process_frame_with_opencv", return_value=vec):
            emb_json, face_hash, similarity, verified_at = BiometricService.verify_identity_with_id_card(
                id_card_base64=card_b64,
                selfie_base64=selfie_b64,
                id_number="8392102",
                declared_full_name="Juan Perez Gomez",
                account_full_name="Juan Perez Gomez",
            )
            assert similarity >= 0.99
            assert face_hash is not None
            assert verified_at is not None


@pytest.mark.asyncio
async def test_user_profile_service_verify_identity():
    """Valida que UserProfileService actualice correctamente las columnas del usuario."""
    mock_db = AsyncMock()
    user = User(
        id=uuid.uuid4(),
        email="juan.perez@skillmatch.io",
        full_name="Juan Perez Gomez",
        role=UserRole.MEMBER,
        is_active=True,
    )

    card_b64 = create_mock_jpeg_base64()
    selfie_b64 = create_mock_jpeg_base64()
    vec = [0.5] * 4 + [0.0] * 124

    req = IdentityVerifyRequest(
        id_card_base64=card_b64,
        selfie_base64=selfie_b64,
        id_number="8392102",
        full_name="Juan Perez Gomez",
    )

    with patch.object(BiometricService, "_process_id_card_face", return_value=vec):
        with patch.object(BiometricService, "_process_frame_with_opencv", return_value=vec):
            response = await UserProfileService.verify_identity(mock_db, user, req)

            assert response.identity_status == "VERIFIED"
            assert response.id_document_number == "8392102"
            assert response.has_biometric_enrollment is True
            assert response.id_face_similarity_score is not None
            assert user.identity_status == "VERIFIED"
            assert user.id_document_number == "8392102"
            assert mock_db.commit.called
