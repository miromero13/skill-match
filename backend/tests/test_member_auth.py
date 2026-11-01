import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from jose import jwt
from app.main import app
from app.db.session import get_db
from app.core.config import settings
from app.core.security import clear_revoked_tokens
from app.models.user import User, UserRole

class MockDbSession:
    """Mock de sesión AsyncSession para pruebas de autenticación de miembros."""
    def __init__(self, existing_user: User | None = None):
        self.existing_user = existing_user
        self.added_users = []

    async def execute(self, statement, *args, **kwargs):
        class MockResult:
            def __init__(self, item):
                self._item = item
            def scalar_one_or_none(self):
                return self._item
            def scalar(self):
                return 1
        return MockResult(self.existing_user)

    def add(self, entity):
        if isinstance(entity, User):
            if not entity.id:
                entity.id = uuid.uuid4()
            self.added_users.append(entity)
            self.existing_user = entity

    async def commit(self):
        pass

    async def refresh(self, entity):
        pass

    async def rollback(self):
        pass

    async def close(self):
        pass

@pytest.fixture(autouse=True)
def clean_tokens():
    clear_revoked_tokens()
    yield
    clear_revoked_tokens()

def create_mock_google_token(email: str, name: str, sub: str = "google-sub-123", picture: str = "https://example.com/avatar.jpg") -> str:
    """Genera un token JWT simulado con los claims estándar de Google OAuth."""
    payload = {
        "iss": "https://accounts.google.com",
        "sub": sub,
        "email": email,
        "email_verified": True,
        "name": name,
        "picture": picture,
        "aud": settings.GOOGLE_CLIENT_ID or "mock-client-id"
    }
    return jwt.encode(payload, "mock-secret-not-verified", algorithm="HS256")

@pytest.mark.asyncio
async def test_google_oauth_jit_provisioning_new_member():
    """Prueba aprovisionamiento Just-In-Time de un nuevo miembro con rol MEMBER."""
    session = MockDbSession(existing_user=None)
    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    try:
        token = create_mock_google_token(
            email="nuevo.miembro@skillmatch.io",
            name="Nuevo Miembro",
            sub="sub-google-999"
        )
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.post(
                "/api/auth/oauth/google",
                json={"id_token": token}
            )

        assert response.status_code == 200
        body = response.json()
        assert body["statuscode"] == 200
        assert "Autenticación con Google completada" in body["message"]

        data = body["data"]
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["email"] == "nuevo.miembro@skillmatch.io"
        assert data["user"]["role"] == "MEMBER"

        # Validar claim de rol en el token emitido
        claims = jwt.decode(data["access_token"], settings.SECRET_KEY.get_secret_value(), algorithms=[settings.ALGORITHM])
        assert claims["role"] == "MEMBER"
        assert claims["type"] == "access"
    finally:
        app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_google_oauth_existing_member_login():
    """Prueba inicio de sesión exitoso de un miembro ya existente."""
    user_id = uuid.uuid4()
    existing_user = User(
        id=user_id,
        email="laura.dev@skillmatch.io",
        full_name="Laura Desarrolladora",
        role=UserRole.MEMBER,
        is_active=True,
        is_locked=False,
        provider="google",
        provider_user_id="sub-laura-1"
    )

    session = MockDbSession(existing_user=existing_user)
    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    try:
        token = create_mock_google_token(
            email="laura.dev@skillmatch.io",
            name="Laura Desarrolladora"
        )
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.post(
                "/api/auth/oauth/google",
                json={"id_token": token}
            )

        assert response.status_code == 200
        body = response.json()
        assert body["statuscode"] == 200
        data = body["data"]
        assert data["user"]["id"] == str(user_id)
        assert data["user"]["role"] == "MEMBER"
    finally:
        app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_google_oauth_inactive_user_forbidden():
    """Prueba que un usuario inactivo o suspendido no pueda iniciar sesión con Google."""
    inactive_user = User(
        id=uuid.uuid4(),
        email="suspendido@skillmatch.io",
        full_name="Usuario Suspendido",
        role=UserRole.MEMBER,
        is_active=False,
        is_locked=False
    )

    session = MockDbSession(existing_user=inactive_user)
    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    try:
        token = create_mock_google_token(
            email="suspendido@skillmatch.io",
            name="Usuario Suspendido"
        )
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.post(
                "/api/auth/oauth/google",
                json={"id_token": token}
            )

        assert response.status_code == 403
        body = response.json()
        assert body["statuscode"] == 403
        assert "suspendida o inactiva" in body["message"]
    finally:
        app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_google_oauth_empty_token_bad_request():
    """Prueba que un payload con token vacío retorne 400 Bad Request."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/auth/oauth/google",
            json={"id_token": "   "}
        )

    assert response.status_code == 400
    body = response.json()
    assert body["statuscode"] == 400
    assert "es obligatorio" in body["message"]
