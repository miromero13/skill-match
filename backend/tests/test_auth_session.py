import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from jose import jwt
from app.main import app
from app.db.session import get_db
from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    clear_revoked_tokens,
)
from app.models.user import User, UserRole

class MockUserSession:
    """Mock de sesión para simular consultas de User en pruebas de sesión."""
    def __init__(self, user: User | None = None):
        self.user = user

    async def execute(self, statement, *args, **kwargs):
        class MockResult:
            def __init__(self, item):
                self._item = item
            def scalar_one_or_none(self):
                return self._item
            def scalar(self):
                return 1
        return MockResult(self.user)

    async def commit(self):
        pass

    async def rollback(self):
        pass

    async def close(self):
        pass

@pytest.fixture(autouse=True)
def clean_token_revocations():
    """Limpia la denylist de tokens antes y después de cada test."""
    clear_revoked_tokens()
    yield
    clear_revoked_tokens()

@pytest.mark.asyncio
async def test_get_me_success():
    """Prueba consulta exitosa de identidad actual (GET /api/auth/me) con rol ADMIN."""
    admin_id = uuid.uuid4()
    mock_admin = User(
        id=admin_id,
        email="admin.gonzalo@skillmatch.io",
        full_name="Gonzalo Administrador",
        role=UserRole.ADMIN,
        is_active=True,
        is_locked=False
    )

    session = MockUserSession(mock_admin)
    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    try:
        token = create_access_token(subject=str(admin_id), role="ADMIN")
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get(
                "/api/auth/me",
                headers={"Authorization": f"Bearer {token}"}
            )

            assert response.status_code == 200
            body = response.json()
            assert body["statuscode"] == 200
            assert body["data"]["email"] == "admin.gonzalo@skillmatch.io"
            assert body["data"]["role"] == "ADMIN"
            assert body["data"]["full_name"] == "Gonzalo Administrador"
            assert body["data"]["is_active"] is True
    finally:
        app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_get_me_without_token_returns_401():
    """Prueba que solicitar /api/auth/me sin encabezado Authorization retorne 401."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/api/auth/me")

        assert response.status_code == 401
        body = response.json()
        assert body["statuscode"] == 401
        assert "Encabezado de autorización ausente" in body["message"]

@pytest.mark.asyncio
async def test_get_me_with_invalid_token_returns_401():
    """Prueba que un token corrupto o mal firmado sea rechazado con 401."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer token_completamente_invalido_xyz"}
        )

        assert response.status_code == 401
        body = response.json()
        assert body["statuscode"] == 401

@pytest.mark.asyncio
async def test_get_me_with_inactive_user_returns_403():
    """Prueba que una cuenta inactiva sea rechazada con 403 Forbidden."""
    admin_id = uuid.uuid4()
    mock_admin = User(
        id=admin_id,
        email="inactive@skillmatch.io",
        full_name="Usuario Inactivo",
        role=UserRole.ADMIN,
        is_active=False,
        is_locked=False
    )

    session = MockUserSession(mock_admin)
    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    try:
        token = create_access_token(subject=str(admin_id), role="ADMIN")
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get(
                "/api/auth/me",
                headers={"Authorization": f"Bearer {token}"}
            )

            assert response.status_code == 403
            body = response.json()
            assert body["statuscode"] == 403
            assert "suspendida o inactiva" in body["message"]
    finally:
        app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_get_me_with_locked_user_returns_423():
    """Prueba que una cuenta bloqueada sea rechazada con 423 Locked."""
    admin_id = uuid.uuid4()
    mock_admin = User(
        id=admin_id,
        email="locked@skillmatch.io",
        full_name="Usuario Bloqueado",
        role=UserRole.ADMIN,
        is_active=True,
        is_locked=True
    )

    session = MockUserSession(mock_admin)
    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    try:
        token = create_access_token(subject=str(admin_id), role="ADMIN")
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get(
                "/api/auth/me",
                headers={"Authorization": f"Bearer {token}"}
            )

            assert response.status_code == 423
            body = response.json()
            assert body["statuscode"] == 423
            assert "bloqueada por seguridad" in body["message"]
    finally:
        app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_refresh_token_rotation_success():
    """
    Prueba rotación exitosa de Refresh Token (POST /api/auth/refresh).
    Verifica que se emita un nuevo par de tokens y se preserve el rol ADMIN.
    """
    admin_id = uuid.uuid4()
    mock_admin = User(
        id=admin_id,
        email="admin.gonzalo@skillmatch.io",
        full_name="Gonzalo Administrador",
        role=UserRole.ADMIN,
        is_active=True,
        is_locked=False
    )

    session = MockUserSession(mock_admin)
    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    try:
        initial_refresh_token = create_refresh_token(subject=str(admin_id), role="ADMIN")
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.post(
                "/api/auth/refresh",
                json={"refresh_token": initial_refresh_token}
            )

            assert response.status_code == 200
            body = response.json()
            assert body["statuscode"] == 200
            data = body["data"]
            assert "access_token" in data
            assert "refresh_token" in data
            assert data["refresh_token"] != initial_refresh_token

            # Verificar que el nuevo access token conserve el claim "role": "ADMIN"
            payload = jwt.decode(
                data["access_token"],
                settings.SECRET_KEY.get_secret_value(),
                algorithms=[settings.ALGORITHM]
            )
            assert payload["role"] == "ADMIN"
            assert payload["sub"] == str(admin_id)
            assert payload["type"] == "access"

            # REUSO INDEBIDO: Verificar que el refresh_token inicial quedó revocado tras rotar
            second_attempt = await client.post(
                "/api/auth/refresh",
                json={"refresh_token": initial_refresh_token}
            )
            assert second_attempt.status_code == 401
            second_body = second_attempt.json()
            assert "revocado" in second_body["message"].lower() or "inválido" in second_body["message"].lower()
    finally:
        app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_refresh_token_rejects_access_token():
    """Prueba que intentar refrescar enviando un Access Token sea rechazado con 401."""
    admin_id = uuid.uuid4()
    session = MockUserSession(None)
    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    try:
        access_token = create_access_token(subject=str(admin_id), role="ADMIN")
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.post(
                "/api/auth/refresh",
                json={"refresh_token": access_token}
            )

            assert response.status_code == 401
            body = response.json()
            assert body["statuscode"] == 401
            assert "no es un Refresh Token válido" in body["message"]
    finally:
        app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_logout_revokes_tokens():
    """
    Prueba que el logout revoque el token de acceso y refresh token,
    impidiendo consultas posteriores con ese mismo token.
    """
    admin_id = uuid.uuid4()
    mock_admin = User(
        id=admin_id,
        email="admin.gonzalo@skillmatch.io",
        full_name="Gonzalo Administrador",
        role=UserRole.ADMIN,
        is_active=True,
        is_locked=False
    )

    session = MockUserSession(mock_admin)
    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    try:
        access_token = create_access_token(subject=str(admin_id), role="ADMIN")
        refresh_token = create_refresh_token(subject=str(admin_id), role="ADMIN")

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            # 1. Llamar a logout
            logout_resp = await client.post(
                "/api/auth/logout",
                headers={"Authorization": f"Bearer {access_token}"},
                json={"refresh_token": refresh_token}
            )

            assert logout_resp.status_code == 200
            logout_body = logout_resp.json()
            assert logout_body["statuscode"] == 200
            assert "Sesión cerrada" in logout_body["message"]

            # 2. Intentar usar el access_token revocado en /api/auth/me
            me_resp = await client.get(
                "/api/auth/me",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            assert me_resp.status_code == 401

            # 3. Intentar usar el refresh_token revocado en /api/auth/refresh
            ref_resp = await client.post(
                "/api/auth/refresh",
                json={"refresh_token": refresh_token}
            )
            assert ref_resp.status_code == 401
    finally:
        app.dependency_overrides.clear()
