import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from jose import jwt
from app.main import app
from app.db.session import get_db
from app.core.config import settings
from app.core.security import get_password_hash, create_access_token
from app.models.user import User, UserRole

class MockUserSession:
    """Mock de sesión para simular consultas y mutaciones de User."""
    def __init__(self, user: User | None = None):
        self.user = user
        self.committed = False

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
        self.committed = True

    async def rollback(self):
        pass

    async def close(self):
        pass

@pytest.mark.asyncio
async def test_admin_login_success():
    """Prueba autenticación exitosa con credenciales correctas de ADMIN."""
    admin_id = uuid.uuid4()
    mock_admin = User(
        id=admin_id,
        email="admin.gonzalo@skillmatch.io",
        full_name="Gonzalo Administrador",
        role=UserRole.ADMIN,
        hashed_password=get_password_hash("PasswordAdmin123!"),
        is_active=True,
        is_locked=False,
        failed_login_attempts=0
    )

    session = MockUserSession(mock_admin)
    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.post(
                "/api/admin/auth/login",
                json={
                    "email": "admin.gonzalo@skillmatch.io",
                    "password": "PasswordAdmin123!",
                    "remember_me": True
                }
            )

            assert response.status_code == 200
            body = response.json()
            assert body["statuscode"] == 200
            assert "access_token" in body["data"]
            assert "refresh_token" in body["data"]
            assert body["data"]["user"]["email"] == "admin.gonzalo@skillmatch.io"
            assert body["data"]["user"]["role"] == "ADMIN"

            # Verificar que el JWT contenga claim "role": "ADMIN"
            token = body["data"]["access_token"]
            payload = jwt.decode(
                token,
                settings.SECRET_KEY.get_secret_value(),
                algorithms=[settings.ALGORITHM]
            )
            assert payload["role"] == "ADMIN"
            assert payload["sub"] == str(admin_id)
    finally:
        app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_admin_login_wrong_password_increments_attempts():
    """Prueba que una contraseña incorrecta incremente el contador de intentos fallidos."""
    mock_admin = User(
        id=uuid.uuid4(),
        email="admin.gonzalo@skillmatch.io",
        full_name="Gonzalo Administrador",
        role=UserRole.ADMIN,
        hashed_password=get_password_hash("CorrectPassword123!"),
        is_active=True,
        is_locked=False,
        failed_login_attempts=2
    )

    session = MockUserSession(mock_admin)
    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.post(
                "/api/admin/auth/login",
                json={
                    "email": "admin.gonzalo@skillmatch.io",
                    "password": "WrongPassword123!"
                }
            )

            assert response.status_code == 401
            body = response.json()
            assert body["statuscode"] == 401
            assert "intentos" in body["message"].lower() or "inválidas" in body["message"].lower()
            assert mock_admin.failed_login_attempts == 3
            assert mock_admin.is_locked is False
            assert session.committed is True
    finally:
        app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_admin_login_fifth_failed_attempt_locks_account():
    """Prueba que el 5to intento fallido consecutivo active is_locked=True (RF-USR-16)."""
    mock_admin = User(
        id=uuid.uuid4(),
        email="admin.gonzalo@skillmatch.io",
        full_name="Gonzalo Administrador",
        role=UserRole.ADMIN,
        hashed_password=get_password_hash("CorrectPassword123!"),
        is_active=True,
        is_locked=False,
        failed_login_attempts=4  # Este intento será el quinto
    )

    session = MockUserSession(mock_admin)
    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.post(
                "/api/admin/auth/login",
                json={
                    "email": "admin.gonzalo@skillmatch.io",
                    "password": "WrongPassword123!"
                }
            )

            assert response.status_code == 423  # Locked
            body = response.json()
            assert body["statuscode"] == 423
            assert "bloqueada" in body["message"].lower()
            assert mock_admin.failed_login_attempts == 5
            assert mock_admin.is_locked is True
            assert mock_admin.locked_until is not None
            assert session.committed is True
    finally:
        app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_admin_login_rejects_already_locked_account():
    """Prueba que una cuenta ya bloqueada sea rechazada de inmediato sin verificar clave."""
    mock_admin = User(
        id=uuid.uuid4(),
        email="admin.gonzalo@skillmatch.io",
        full_name="Gonzalo Administrador",
        role=UserRole.ADMIN,
        hashed_password=get_password_hash("CorrectPassword123!"),
        is_active=True,
        is_locked=True,
        failed_login_attempts=5
    )

    session = MockUserSession(mock_admin)
    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.post(
                "/api/admin/auth/login",
                json={
                    "email": "admin.gonzalo@skillmatch.io",
                    "password": "CorrectPassword123!"
                }
            )

            assert response.status_code == 423
            body = response.json()
            assert body["statuscode"] == 423
            assert "bloqueada preventivamente" in body["message"].lower()
    finally:
        app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_admin_login_rejects_member_role():
    """Prueba que un usuario con rol MEMBER no pueda autenticarse en el login administrativo."""
    mock_member = User(
        id=uuid.uuid4(),
        email="miembro@skillmatch.io",
        full_name="Miembro Común",
        role=UserRole.MEMBER,
        hashed_password=get_password_hash("PasswordMember123!"),
        is_active=True,
        is_locked=False
    )

    session = MockUserSession(mock_member)
    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.post(
                "/api/admin/auth/login",
                json={
                    "email": "miembro@skillmatch.io",
                    "password": "PasswordMember123!"
                }
            )

            assert response.status_code == 401
            body = response.json()
            assert body["statuscode"] == 401
            assert "inválidas" in body["message"].lower()
    finally:
        app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_admin_login_rejects_inactive_account():
    """Prueba que una cuenta inactiva sea rechazada con 403."""
    mock_admin = User(
        id=uuid.uuid4(),
        email="admin.inactivo@skillmatch.io",
        full_name="Admin Inactivo",
        role=UserRole.ADMIN,
        hashed_password=get_password_hash("PasswordAdmin123!"),
        is_active=False,
        is_locked=False
    )

    session = MockUserSession(mock_admin)
    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.post(
                "/api/admin/auth/login",
                json={
                    "email": "admin.inactivo@skillmatch.io",
                    "password": "PasswordAdmin123!"
                }
            )

            assert response.status_code == 403
            body = response.json()
            assert body["statuscode"] == 403
            assert "suspendida o inactiva" in body["message"].lower()
    finally:
        app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_admin_route_obfuscates_with_404_for_member():
    """Prueba la política de seguridad por ofuscación: un MEMBER en ruta protegida de ADMIN recibe 404."""
    member_id = uuid.uuid4()
    mock_member = User(
        id=member_id,
        email="miembro.curioso@skillmatch.io",
        full_name="Miembro Curioso",
        role=UserRole.MEMBER,
        is_active=True,
        is_locked=False
    )

    member_token = create_access_token(subject=str(member_id), role="MEMBER")

    session = MockUserSession(mock_member)
    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get(
                "/api/admin/auth/verify",
                headers={"Authorization": f"Bearer {member_token}"}
            )

            # Debe ser estrictamente 404 Not Found (nunca 403)
            assert response.status_code == 404
            body = response.json()
            assert body["statuscode"] == 404
            assert "recurso no encontrado" in body["message"].lower()
    finally:
        app.dependency_overrides.clear()
