import io
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.schemas.passport import (
    AntiFraudAudit,
    AuditedCodeChallenge,
    DockerSuiteReport,
    DockerTestCase,
    OralDefenseAudit,
    PassportSkillItem,
    PublicPassportResponse,
    TechnicalDossier,
)
from app.schemas.reputation import RatingsBreakdown, ReputationBadge, TrustScoreFactors
from app.services.passport_service import PassportService


def _create_mock_passport_response(user_id: uuid.UUID) -> PublicPassportResponse:
    test_cases = [
        DockerTestCase(name="test_cache_miss_queries_database", status="PASSED", duration_seconds=0.04, percentage=25),
        DockerTestCase(name="test_cache_hit_returns_fast", status="PASSED", duration_seconds=0.02, percentage=50),
    ]
    docker_report = DockerSuiteReport(
        passed_count=4,
        total_count=4,
        execution_time_seconds=0.18,
        coverage_percentage=100,
        test_cases=test_cases,
    )
    code_challenge = AuditedCodeChallenge(
        title="Implementación de Endpoint FastAPI con Caché Redis",
        consigna="Implementar endpoint con inyección Depends() y caché Redis.",
        file_name="main.py",
        language="Python 3.12",
        source_code="async def get_stats(): return {}",
        docker_report=docker_report,
    )
    oral_defense = OralDefenseAudit(
        score=95.0,
        question="Pregunta conceptual sobre concurrencia y Event Loop",
        candidate_transcript="Explicación del GIL y asyncio en Python...",
        ai_verdict="Dominio arquitectónico sobresaliente.",
    )
    anti_fraud = AntiFraudAudit(
        facial_liveness_score=100.0,
        voice_verification_status="Voz única confirmada",
        screen_violations_count=0,
        clipboard_abuse_detected=False,
    )
    technical_dossier = TechnicalDossier(
        has_technical_audit=True,
        technical_score=98.0,
        oral_defense_score=95.0,
        code_challenge=code_challenge,
        oral_defense=oral_defense,
        anti_fraud=anti_fraud,
    )

    return PublicPassportResponse(
        public_uuid=user_id,
        certificate_id="#SM-PY-9842",
        full_name="Lucía Méndez",
        avatar_url=None,
        bio="Fullstack Developer & AI Engineer",
        location_label="Montevideo, Uruguay",
        member_since=datetime(2025, 1, 10, tzinfo=timezone.utc),
        issued_at=datetime.now(timezone.utc),
        verification_hash="0x8f4b12ac...e3b0",
        verification_node="Nodo Central SkillMatch #04",
        qr_endpoint_url=f"http://testserver/api/passports/{user_id}/qr",
        pdf_download_url=f"http://testserver/api/passports/{user_id}/pdf",
        public_shareable_url=f"http://localhost:5173/passport/{user_id}",
        trust_score=94.0,
        overall_rating=4.9,
        total_reviews=12,
        ratings_breakdown=RatingsBreakdown(punctuality=5.0, pedagogy=4.8, domain=4.9),
        factors=TrustScoreFactors(
            ia_verified_score=90.0,
            peer_feedback_score=96.0,
            attendance_score=100.0,
            tenure_score=85.0,
        ),
        badges=[
            ReputationBadge(
                code="MASTER_TUTOR",
                title="Tutor Destacado",
                description="Calificaciones promedio superiores a 4.8★.",
                icon="Star",
                is_active=True,
            )
        ],
        skills=[
            PassportSkillItem(
                id=uuid.uuid4(),
                name="Python FastAPI",
                category_name="Desarrollo Backend",
                declared_level="AVANZADO",
                status="VERIFICADA",
                years_of_experience=4,
            )
        ],
        technical_dossier=technical_dossier,
    )


def test_passport_hash_deterministic():
    """
    Verifica que la firma criptográfica HMAC-SHA256 sea determinística y tenga formato 0x...
    """
    sample_id = uuid.uuid4()
    now = datetime(2026, 11, 19, 12, 0, 0, tzinfo=timezone.utc)
    hash_1 = PassportService.generate_verification_hash(sample_id, now)
    hash_2 = PassportService.generate_verification_hash(sample_id, now)

    assert hash_1 == hash_2
    assert hash_1.startswith("0x")
    assert "..." in hash_1


def test_passport_qr_generation():
    """
    Verifica que la generación de QR retorne bytes válidos de imagen PNG.
    """
    url = "https://skillmatch.app/passport/123e4567-e89b-12d3-a456-426614174000"
    qr_bytes = PassportService.generate_qr_png_bytes(url)

    assert isinstance(qr_bytes, bytes)
    assert len(qr_bytes) > 100
    assert qr_bytes.startswith(b"\x89PNG\r\n\x1a\n")


def test_passport_pdf_generation_direct():
    """
    Verifica que la generación de PDF cree un documento institucional con firma y magic bytes %PDF.
    """
    user_id = uuid.uuid4()
    passport_obj = _create_mock_passport_response(user_id)
    pdf_bytes = PassportService.generate_passport_pdf(passport_obj)

    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 500
    assert pdf_bytes.startswith(b"%PDF")


@pytest.mark.asyncio
async def test_passport_public_endpoint_json(client: AsyncClient):
    """
    Verifica que el endpoint GET /api/passports/{uuid} retorne el sobre canónico APIResponse.
    """
    user_id = uuid.uuid4()
    mock_data = _create_mock_passport_response(user_id)

    with patch.object(PassportService, "get_public_passport", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_data
        response = await client.get(f"/api/passports/{user_id}")

        assert response.status_code == 200
        payload = response.json()
        assert payload["statuscode"] == 200
        assert "auditado exitosamente" in payload["message"]
        data = payload["data"]
        assert data["full_name"] == "Lucía Méndez"
        assert data["certificate_id"] == "#SM-PY-9842"
        assert data["verification_hash"].startswith("0x")
        assert data["technical_dossier"]["technical_score"] == 98.0


@pytest.mark.asyncio
async def test_passport_public_qr_endpoint(client: AsyncClient):
    """
    Verifica que el endpoint GET /api/passports/{uuid}/qr retorne un stream PNG con encabezados correctos.
    """
    user_id = uuid.uuid4()
    mock_data = _create_mock_passport_response(user_id)

    with patch.object(PassportService, "get_public_passport", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_data
        response = await client.get(f"/api/passports/{user_id}/qr")

        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"
        assert response.content.startswith(b"\x89PNG\r\n\x1a\n")


@pytest.mark.asyncio
async def test_passport_public_pdf_endpoint(client: AsyncClient):
    """
    Verifica que el endpoint GET /api/passports/{uuid}/pdf retorne un stream de descarga PDF con encabezados de descarga.
    """
    user_id = uuid.uuid4()
    mock_data = _create_mock_passport_response(user_id)

    with patch.object(PassportService, "get_public_passport", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_data
        response = await client.get(f"/api/passports/{user_id}/pdf")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert f"pasaporte-skillmatch-{user_id}.pdf" in response.headers["content-disposition"]
        assert response.content.startswith(b"%PDF")
