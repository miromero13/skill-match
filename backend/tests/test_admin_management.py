import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.db.session import get_db
from app.core.security import create_access_token
from app.core.config import settings
from app.models.user import User, UserRole

class MockAdminDbSession:
    """Mock de sesión para simular consultas del servicio de administración."""
    def __init__(self, current_admin: User, target_admin: User | None = None, existing_email: bool = False):
        self.current_admin = current_admin
        self.target_admin = target_admin
        self.existing_email = existing_email
        self.added_users: list[User] = []

    async def execute(self, statement, *args, **kwargs):
        stmt_str = str(statement).lower()
        class MockResult:
            def __init__(self, item, count_val=1):
                self._item = item
                self._count_val = count_val

            def scalar_one_or_none(self):
                return self._item

            def scalar(self):
                return self._count_val

            def scalars(self):
                class MockScalars:
                    def __init__(self, items):
                        self._items = items
                    def all(self):
                        return self._items
                if isinstance(self._item, list):
                    return MockScalars(self._item)
                return MockScalars([self._item] if self._item else [])

        # 1. Conteo total: SELECT count(users.id)
        if "count(" in stmt_str:
            return MockResult(None, count_val=2)

        # 2. Listado: SELECT ... ORDER BY users.created_at
        if "order by" in stmt_str:
            items = [self.current_admin]
            if self.target_admin and self.target_admin.id != self.current_admin.id:
                items.append(self.target_admin)
            return MockResult(items)

        # 3. Verificación de existencia de correo: WHERE users.email =
        if "where users.email =" in stmt_str:
            return MockResult(self.current_admin if self.existing_email else None)

        # 4. Búsqueda por ID en WHERE users.id =
        # Obtener parámetros compilados
        try:
            compiled = statement.compile()
            params = compiled.params
            searched_id = None
            for k, v in params.items():
                if isinstance(v, uuid.UUID) or (isinstance(v, str) and len(v) == 36):
                    searched_id = str(v)
                    break

            if searched_id and self.target_admin and str(self.target_admin.id) == searched_id:
                return MockResult(self.target_admin)
            if searched_id and str(self.current_admin.id) == searched_id:
                return MockResult(self.current_admin)
        except Exception:
            pass

        return MockResult(self.target_admin or self.current_admin)

    def add(self, instance):
        self.added_users.append(instance)

    async def commit(self):
        pass

    async def refresh(self, instance):
        pass

@pytest.fixture
def active_admin_user() -> User:
    return User(
        id=uuid.uuid4(),
        email=settings.ADMIN_EMAIL,
        full_name="Gonzalo Administrador Central",
        role=UserRole.ADMIN,
        is_active=True,
        is_locked=False,
    )

@pytest.fixture
def regular_member_user() -> User:
    return User(
        id=uuid.uuid4(),
        email="member.martin@skillmatch.io",
        full_name="Martín Silva",
        role=UserRole.MEMBER,
        is_active=True,
        is_locked=False,
    )

@pytest.mark.asyncio
async def test_list_administrators_success(active_admin_user):
    """
    Prueba que un ADMIN autenticado obtenga la lista de administradores
    con conteo y datos completos (GET /api/admin).
    """
    session = MockAdminDbSession(active_admin_user)
    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    try:
        token = create_access_token(subject=str(active_admin_user.id), role="ADMIN")
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get(
                "/api/admin",
                headers={"Authorization": f"Bearer {token}"}
            )

            assert response.status_code == 200
            body = response.json()
            assert body["statuscode"] == 200
            assert "data" in body
            assert body["count"] >= 1
            assert any(item["email"] == active_admin_user.email for item in body["data"])
    finally:
        app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_non_super_admin_cannot_list_administrators(active_admin_user, monkeypatch):
    session = MockAdminDbSession(active_admin_user)
    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    monkeypatch.setattr(settings, "ADMIN_EMAIL", "configured-root@skillmatch.io")
    try:
        token = create_access_token(subject=str(active_admin_user.id), role="ADMIN")
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get(
                "/api/admin",
                headers={"Authorization": f"Bearer {token}"}
            )

            assert response.status_code == 404
            assert response.json()["message"] == "Recurso no encontrado"
    finally:
        app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_list_administrators_by_member_returns_404(regular_member_user):
    """
    POLÍTICA DE OFUSCACIÓN 404:
    Un usuario con rol MEMBER debe recibir 404 Not Found (nunca 403)
    al intentar consultar /api/admin.
    """
    session = MockAdminDbSession(regular_member_user)
    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    try:
        token = create_access_token(subject=str(regular_member_user.id), role="MEMBER")
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get(
                "/api/admin",
                headers={"Authorization": f"Bearer {token}"}
            )

            assert response.status_code == 404
            body = response.json()
            assert body["statuscode"] == 404
            assert body["message"] == "Recurso no encontrado"
    finally:
        app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_list_administrators_anonymous_returns_404():
    """
    POLÍTICA DE OFUSCACIÓN 404:
    Una solicitud anónima (sin token) a /api/admin debe recibir 404 Not Found (nunca 401).
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/api/admin")

        assert response.status_code == 404
        body = response.json()
        assert body["statuscode"] == 404
        assert body["message"] == "Recurso no encontrado"

@pytest.mark.asyncio
async def test_create_administrator_success(active_admin_user):
    """
    Prueba alta exitosa de un nuevo administrador por parte de un ADMIN existente (POST /api/admin).
    """
    session = MockAdminDbSession(active_admin_user, existing_email=False)
    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    try:
        token = create_access_token(subject=str(active_admin_user.id), role="ADMIN")
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            payload = {
                "email": "nuevo.auditor@admin.skillmatch.io",
                "full_name": "Ing. Gonzalo Martínez",
                "password": "Password123!Secure"
            }
            response = await client.post(
                "/api/admin",
                headers={"Authorization": f"Bearer {token}"},
                json=payload
            )

            assert response.status_code == 201
            body = response.json()
            assert body["statuscode"] == 201
            assert body["data"]["email"] == "nuevo.auditor@admin.skillmatch.io"
            assert body["data"]["full_name"] == "Ing. Gonzalo Martínez"
            assert body["data"]["role"] == "ADMIN"
            assert body["data"]["is_active"] is True
            assert "hashed_password" not in body["data"]
    finally:
        app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_create_administrator_duplicate_email_returns_400(active_admin_user):
    """
    Prueba rechazo con 400 Bad Request si el email del nuevo administrador ya existe.
    """
    session = MockAdminDbSession(active_admin_user, existing_email=True)
    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    try:
        token = create_access_token(subject=str(active_admin_user.id), role="ADMIN")
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            payload = {
                "email": active_admin_user.email,
                "full_name": "Duplicado",
                "password": "Password123!Secure"
            }
            response = await client.post(
                "/api/admin",
                headers={"Authorization": f"Bearer {token}"},
                json=payload
            )

            assert response.status_code == 400
            body = response.json()
            assert body["statuscode"] == 400
            assert "ya se encuentra registrado" in body["message"]
    finally:
        app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_create_administrator_weak_password_returns_422(active_admin_user):
    """
    Prueba que contraseñas que no cumplan los criterios de robustez sean rechazadas con 422.
    """
    session = MockAdminDbSession(active_admin_user)
    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    try:
        token = create_access_token(subject=str(active_admin_user.id), role="ADMIN")
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            # Contraseña sin número ni carácter especial
            payload = {
                "email": "inseguro@admin.skillmatch.io",
                "full_name": "Inseguro",
                "password": "sololetrasynumero"
            }
            response = await client.post(
                "/api/admin",
                headers={"Authorization": f"Bearer {token}"},
                json=payload
            )

            assert response.status_code == 422
            body = response.json()
            assert body["statuscode"] == 422
    finally:
        app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_super_admin_can_inspect_and_change_admin_password(active_admin_user):
    target_admin = User(
        id=uuid.uuid4(),
        email="secondary@admin.skillmatch.io",
        full_name="Secondary Admin",
        role=UserRole.ADMIN,
        is_active=True,
        is_locked=False,
        hashed_password="old-hash",
    )
    session = MockAdminDbSession(active_admin_user, target_admin=target_admin)
    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    try:
        token = create_access_token(subject=str(active_admin_user.id), role="ADMIN")
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            inspected = await client.get(
                f"/api/admin/{target_admin.id}",
                headers={"Authorization": f"Bearer {token}"},
            )
            edited = await client.patch(
                f"/api/admin/{target_admin.id}",
                headers={"Authorization": f"Bearer {token}"},
                json={"full_name": "Updated Secondary Admin"},
            )
            changed = await client.patch(
                f"/api/admin/{target_admin.id}/password",
                headers={"Authorization": f"Bearer {token}"},
                json={"password": "NewPassword123!"},
            )

        assert inspected.status_code == 200
        assert inspected.json()["data"]["email"] == target_admin.email
        assert edited.status_code == 200
        assert edited.json()["data"]["full_name"] == "Updated Secondary Admin"
        assert changed.status_code == 200
        assert target_admin.hashed_password != "old-hash"
        assert "hashed_password" not in changed.json()["data"]
    finally:
        app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_update_administrator_status_suspend_success(active_admin_user):
    """
    Prueba suspensión exitosa de una cuenta administrativa secundaria (PATCH /api/admin/{id}/status).
    """
    target_id = uuid.uuid4()
    target_admin = User(
        id=target_id,
        email="laura@admin.sm",
        full_name="Laura Benítez",
        role=UserRole.ADMIN,
        is_active=True,
        is_locked=False
    )

    session = MockAdminDbSession(active_admin_user, target_admin=target_admin)
    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    try:
        token = create_access_token(subject=str(active_admin_user.id), role="ADMIN")
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.patch(
                f"/api/admin/{target_id}/status",
                headers={"Authorization": f"Bearer {token}"},
                json={"is_active": False, "reason": "Auditoría preventiva de seguridad"}
            )

            assert response.status_code == 200
            body = response.json()
            assert body["statuscode"] == 200
            assert body["data"]["is_active"] is False
            assert "suspendida" in body["message"]
    finally:
        app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_update_administrator_status_prevent_self_suspension(active_admin_user):
    """
    Prueba que un administrador no pueda suspender su propia cuenta activa.
    """
    session = MockAdminDbSession(active_admin_user, target_admin=active_admin_user)
    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    try:
        token = create_access_token(subject=str(active_admin_user.id), role="ADMIN")
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.patch(
                f"/api/admin/{active_admin_user.id}/status",
                headers={"Authorization": f"Bearer {token}"},
                json={"is_active": False, "reason": "Intento de auto-suspensión"}
            )

            assert response.status_code == 400
            body = response.json()
            assert body["statuscode"] == 400
            assert "No podés suspender tu propia cuenta" in body["message"]
    finally:
        app.dependency_overrides.clear()
