import uuid
from datetime import datetime, timezone
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.deps import get_current_user
from app.core.security import create_access_token
from app.db.session import get_db
from app.main import app
from app.models.catalog import Category, Skill
from app.models.teaching_skill import TeachingSkill
from app.models.user import ExchangeModality, User, UserRole


class MockSearchSession:
    """Mock de sesión en memoria para pruebas exhaustivas y determinísticas de búsqueda de instructores (HU-20)."""

    def __init__(self, current_user: User):
        self.current_user = current_user
        self.categories: list[Category] = []
        self.skills: list[Skill] = []
        self.users: list[User] = []
        self.teaching_skills: list[TeachingSkill] = []

    async def execute(self, statement, *args, **kwargs):
        # Evaluar joins entre TeachingSkill, Skill, Category, User
        rows = []
        for ts in self.teaching_skills:
            sk = next((s for s in self.skills if s.id == ts.skill_id), None)
            if not sk or not sk.is_active:
                continue
            cat = next((c for c in self.categories if c.id == sk.category_id), None)
            if not cat:
                continue
            u = next((usr for usr in self.users if usr.id == ts.user_id), None)
            if not u or not u.is_active:
                continue

            rows.append((ts, sk, cat, u))

        class Result:
            def __init__(self, data):
                self.data = data

            def all(self):
                return self.data

        return Result(rows)


@pytest.fixture
def member_user() -> User:
    return User(
        id=uuid.uuid4(),
        email="aprendiz@skillmatch.local",
        full_name="Aprendiz Buscador",
        role=UserRole.MEMBER,
        is_active=True,
        latitude=-16.5000,
        longitude=-68.1500,
        exchange_modality=ExchangeModality.BOTH,
        presencial_radius_km=15,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def auth_headers(member_user: User) -> dict[str, str]:
    token = create_access_token(
        subject=str(member_user.id), role=member_user.role.value
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def seed_data(member_user: User):
    cat_prog = Category(
        id=uuid.uuid4(),
        name="Programación y Software",
        slug="programacion-y-software",
        is_active=True,
    )
    cat_music = Category(
        id=uuid.uuid4(),
        name="Música e Instrumentos",
        slug="musica-e-instrumentos",
        is_active=True,
    )

    skill_python = Skill(
        id=uuid.uuid4(),
        category_id=cat_prog.id,
        name="Python y Backend",
        slug="python-backend",
        is_active=True,
    )
    skill_guitar = Skill(
        id=uuid.uuid4(),
        category_id=cat_music.id,
        name="Guitarra Acústica",
        slug="guitarra-acustica",
        is_active=True,
    )

    # Tutor 1: Verificado por IA, presencial cercano (a ~5 km)
    tutor_1 = User(
        id=uuid.uuid4(),
        email="tutor1@skillmatch.local",
        full_name="Ana Python Pro",
        role=UserRole.MEMBER,
        bio="Experta en desarrollo FastAPI y arquitectura",
        location_label="La Paz Centro",
        latitude=-16.5050,
        longitude=-68.1400,
        exchange_modality=ExchangeModality.BOTH,
        presencial_radius_km=20,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    ts_1 = TeachingSkill(
        id=uuid.uuid4(),
        user_id=tutor_1.id,
        skill_id=skill_python.id,
        declared_level="EXPERT",
        years_of_experience=6,
        description="6 años en desarrollo backend",
        accepts_points=True,
        hourly_points_rate=30,
        status="VERIFICADA",
    )

    # Tutor 2: No verificado (DECLARADA), modalidad VIRTUAL, tarifa más baja
    tutor_2 = User(
        id=uuid.uuid4(),
        email="tutor2@skillmatch.local",
        full_name="Carlos Dev",
        role=UserRole.MEMBER,
        bio="Estudiante avanzado de ingeniería de sistemas",
        location_label="Cochabamba",
        latitude=-17.3895,
        longitude=-66.1568,
        exchange_modality=ExchangeModality.VIRTUAL,
        presencial_radius_km=10,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    ts_2 = TeachingSkill(
        id=uuid.uuid4(),
        user_id=tutor_2.id,
        skill_id=skill_python.id,
        declared_level="INTERMEDIATE",
        years_of_experience=2,
        description="Clases virtuales de Python básico e intermedio",
        accepts_points=True,
        hourly_points_rate=15,
        status="DECLARADA",
    )

    # Tutor 3: Guitarra, modalidad PRESENCIAL, lejos (> 100 km)
    tutor_3 = User(
        id=uuid.uuid4(),
        email="tutor3@skillmatch.local",
        full_name="Beatriz Acordes",
        role=UserRole.MEMBER,
        bio="Concertista de guitarra clásica",
        location_label="Oruro",
        latitude=-17.9833,
        longitude=-67.1500,
        exchange_modality=ExchangeModality.PRESENCIAL,
        presencial_radius_km=15,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    ts_3 = TeachingSkill(
        id=uuid.uuid4(),
        user_id=tutor_3.id,
        skill_id=skill_guitar.id,
        declared_level="ADVANCED",
        years_of_experience=8,
        description="Clases presenciales de técnica y repertorio",
        accepts_points=False,
        hourly_points_rate=None,
        status="VERIFICADA",
    )

    session = MockSearchSession(current_user=member_user)
    session.categories = [cat_prog, cat_music]
    session.skills = [skill_python, skill_guitar]
    session.users = [member_user, tutor_1, tutor_2, tutor_3]
    session.teaching_skills = [ts_1, ts_2, ts_3]

    return {
        "session": session,
        "categories": [cat_prog, cat_music],
        "skills": [skill_python, skill_guitar],
        "tutors": [tutor_1, tutor_2, tutor_3],
    }


@pytest.mark.asyncio
async def test_search_tutors_unauthenticated():
    """Verifica que solicitudes anónimas sin Bearer token sean rechazadas con 401."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        res = await ac.get("/api/search/tutors")
        assert res.status_code == 401


@pytest.mark.asyncio
async def test_search_tutors_all(member_user: User, auth_headers: dict[str, str], seed_data: dict):
    """Verifica la búsqueda general de instructores devolviendo formato canónico APIResponse y count."""
    app.dependency_overrides[get_current_user] = lambda: member_user
    app.dependency_overrides[get_db] = lambda: seed_data["session"]

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
            res = await ac.get("/api/search/tutors", headers=auth_headers)
            assert res.status_code == 200
            body = res.json()

            assert body["statuscode"] == 200
            assert "Se encontraron" in body["message"]
            assert body["count"] == 3
            assert len(body["data"]) == 3

            # Verificar estructura de datos
            first = body["data"][0]
            assert "id" in first
            assert "full_name" in first
            assert "skills" in first
            assert len(first["skills"]) >= 1
            assert "is_verified" in first["skills"][0]
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_search_tutors_filter_verified_only(member_user: User, auth_headers: dict[str, str], seed_data: dict):
    """Verifica que verified_only=true filtre estrictamente instructores con status 'VERIFICADA' (RF-MAT-11)."""
    app.dependency_overrides[get_current_user] = lambda: member_user
    app.dependency_overrides[get_db] = lambda: seed_data["session"]

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
            res = await ac.get("/api/search/tutors?verified_only=true", headers=auth_headers)
            assert res.status_code == 200
            body = res.json()

            assert body["count"] == 2
            # Solo Ana (tutor_1) y Beatriz (tutor_3) tienen status='VERIFICADA'
            names = [t["full_name"] for t in body["data"]]
            assert "Ana Python Pro" in names
            assert "Beatriz Acordes" in names
            assert "Carlos Dev" not in names
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_search_tutors_filter_by_skill_id(member_user: User, auth_headers: dict[str, str], seed_data: dict):
    """Verifica el filtro por skill_id específico."""
    app.dependency_overrides[get_current_user] = lambda: member_user
    app.dependency_overrides[get_db] = lambda: seed_data["session"]
    guitar_id = str(seed_data["skills"][1].id)

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
            res = await ac.get(f"/api/search/tutors?skill_id={guitar_id}", headers=auth_headers)
            assert res.status_code == 200
            body = res.json()

            assert body["count"] == 1
            assert body["data"][0]["full_name"] == "Beatriz Acordes"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_search_tutors_distance_filtering(member_user: User, auth_headers: dict[str, str], seed_data: dict):
    """Verifica que el radio max_distance filtre perfiles lejanos basándose en cálculo Haversine."""
    app.dependency_overrides[get_current_user] = lambda: member_user
    app.dependency_overrides[get_db] = lambda: seed_data["session"]

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
            # Aprendiz en La Paz (-16.5, -68.15), max_distance=10km
            # Ana está a ~1.2 km (La Paz Centro)
            # Carlos está en Cochabamba (> 200 km)
            # Beatriz está en Oruro (> 150 km)
            res = await ac.get("/api/search/tutors?max_distance=10", headers=auth_headers)
            assert res.status_code == 200
            body = res.json()

            assert body["count"] == 1
            assert body["data"][0]["full_name"] == "Ana Python Pro"
            assert body["data"][0]["distance_km"] is not None
            assert body["data"][0]["distance_km"] < 10.0
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_search_tutors_sort_by_points(member_user: User, auth_headers: dict[str, str], seed_data: dict):
    """Verifica el ordenamiento por tarifas de puntos ascendente."""
    app.dependency_overrides[get_current_user] = lambda: member_user
    app.dependency_overrides[get_db] = lambda: seed_data["session"]

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
            res = await ac.get("/api/search/tutors?sort_by=points_asc", headers=auth_headers)
            assert res.status_code == 200
            body = res.json()

            # Carlos tiene tarifa 15, Ana tiene tarifa 30
            rates = [
                s["hourly_points_rate"]
                for t in body["data"]
                for s in t["skills"]
                if s["accepts_points"] and s["hourly_points_rate"] is not None
            ]
            assert rates[0] <= rates[1]
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_search_tutors_pagination(member_user: User, auth_headers: dict[str, str], seed_data: dict):
    """Verifica la paginación estricta con page y page_size."""
    app.dependency_overrides[get_current_user] = lambda: member_user
    app.dependency_overrides[get_db] = lambda: seed_data["session"]

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
            res = await ac.get("/api/search/tutors?page=1&page_size=2", headers=auth_headers)
            assert res.status_code == 200
            body = res.json()

            assert body["count"] == 3  # Total count de resultados
            assert len(body["data"]) == 2  # Página recortada a 2 elementos

            res_page_2 = await ac.get("/api/search/tutors?page=2&page_size=2", headers=auth_headers)
            assert res_page_2.status_code == 200
            body_2 = res_page_2.json()
            assert body_2["count"] == 3
            assert len(body_2["data"]) == 1
    finally:
        app.dependency_overrides.clear()
