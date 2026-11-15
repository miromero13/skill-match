import base64
import uuid
from datetime import datetime, timezone
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.deps import get_current_user
from app.core.security import create_access_token
from app.db.session import get_db
from app.main import app
from app.models.user import User, UserRole
from app.models.user_availability import UserAvailability


class MockProfileAvailabilitySession:
    """Sesión asíncrona en memoria para pruebas determinísticas de Perfil en User y UserAvailability."""

    def __init__(self, current_user: User):
        self.current_user = current_user
        self.availabilities: list[UserAvailability] = []

    async def execute(self, statement, *args, **kwargs):
        desc = statement.column_descriptions[0]
        entity = desc.get("entity")
        compiled = statement.compile()
        params = compiled.params

        class Result:
            def __init__(self, data):
                self.data = data

            def scalar_one_or_none(self):
                return self.data[-1] if self.data else None

            def scalar_one(self):
                return self.data[-1]

            def scalars(self):
                class Scalars:
                    def __init__(self, data):
                        self.data = data

                    def all(self):
                        return self.data

                    def unique(self):
                        return self

                return Scalars(self.data)

        if entity is UserAvailability:
            u_id = params.get("user_id_1") or params.get("user_id")
            slot_id = params.get("id_1") or params.get("id")
            matched = list(self.availabilities)
            if u_id is not None:
                matched = [a for a in matched if a.user_id == u_id]
            if slot_id is not None:
                matched = [a for a in matched if a.id == slot_id]
            return Result(matched)

        return Result([])

    def add(self, item):
        now = datetime.now(timezone.utc)
        if not getattr(item, "id", None):
            item.id = uuid.uuid4()
        if not getattr(item, "created_at", None):
            item.created_at = now
        if not getattr(item, "updated_at", None):
            item.updated_at = now

        if isinstance(item, UserAvailability):
            self.availabilities.append(item)

    async def commit(self):
        pass

    async def refresh(self, item):
        item.updated_at = datetime.now(timezone.utc)

    async def delete(self, item):
        if item in self.availabilities:
            self.availabilities.remove(item)


@pytest.fixture
def hu13_setup():
    user = User(
        id=uuid.uuid4(),
        email="ilse.member@skillmatch.io",
        full_name="Ilse Romero",
        role=UserRole.MEMBER,
        is_active=True,
        avatar_url="https://skillmatch.io/avatars/ilse.png",
    )
    session = MockProfileAvailabilitySession(user)
    token = create_access_token(user.id, user.role.value)
    headers = {"Authorization": f"Bearer {token}"}

    async def override_db():
        yield session

    async def override_user():
        return user

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user

    yield {
        "user": user,
        "session": session,
        "headers": headers,
    }

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_my_profile_returns_user_defaults(hu13_setup):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/users/me/profile", headers=hu13_setup["headers"])
        assert resp.status_code == 200
        body = resp.json()
        assert body["statuscode"] == 200
        assert body["data"]["email"] == "ilse.member@skillmatch.io"
        assert body["data"]["full_name"] == "Ilse Romero"
        assert body["data"]["exchange_modality"] == "VIRTUAL"
        assert body["data"]["has_biometric_enrollment"] is False
        assert body["data"]["biometric_face_hash"] is None


@pytest.mark.asyncio
async def test_put_and_patch_my_profile(hu13_setup):
    transport = ASGITransport(app=app)
    put_payload = {
        "full_name": "Ilse Romero Dev",
        "bio": "Ingeniera de software e instructora de Python y guitarra acústica.",
        "avatar_url": "https://skillmatch.io/avatars/ilse-v2.png",
        "languages": ["Español", "Inglés", "Portugués"],
        "timezone": "America/La_Paz",
        "links": {
            "github": "https://github.com/ilseromero",
            "linkedin": "https://linkedin.com/in/ilseromero",
        },
        "exchange_modality": "BOTH",
        "presencial_radius_km": 15,
        "location_label": "Santa Cruz de la Sierra - Equipetrol",
        "buffer_minutes": 30,
        "gcal_synced": True,
        "gcal_calendar_email": "ilseromero35@gmail.com",
    }
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        put_resp = await client.put(
            "/api/users/me/profile",
            json=put_payload,
            headers=hu13_setup["headers"],
        )
        assert put_resp.status_code == 200
        put_body = put_resp.json()
        assert put_body["statuscode"] == 200
        assert put_body["data"]["full_name"] == "Ilse Romero Dev"
        assert put_body["data"]["exchange_modality"] == "BOTH"
        assert put_body["data"]["presencial_radius_km"] == 15
        assert put_body["data"]["buffer_minutes"] == 30
        assert put_body["data"]["gcal_synced"] is True

        # Actualización parcial con PATCH directo en User
        patch_resp = await client.patch(
            "/api/users/me/profile",
            json={"bio": "Biografía actualizada parcialmente", "presencial_radius_km": 25},
            headers=hu13_setup["headers"],
        )
        assert patch_resp.status_code == 200
        patch_body = patch_resp.json()
        assert patch_body["data"]["bio"] == "Biografía actualizada parcialmente"
        assert patch_body["data"]["presencial_radius_km"] == 25
        assert patch_body["data"]["exchange_modality"] == "BOTH"


@pytest.mark.asyncio
async def test_enroll_biometrics_success_and_rejections(hu13_setup):
    transport = ASGITransport(app=app)
    synthetic_face = base64.b64encode(b"SKILLMATCH_CENTERED_FACE_SAMPLE_PIXELS_2026_128D_TEST" * 4).decode()

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        bad_center = await client.post(
            "/api/users/me/biometrics/enroll",
            json={
                "image_base64": f"data:image/jpeg;base64,{synthetic_face}",
                "lighting_score": 0.9,
                "face_centered": False,
            },
            headers=hu13_setup["headers"],
        )
        assert bad_center.status_code == 400
        assert bad_center.json()["statuscode"] == 400

        bad_light = await client.post(
            "/api/users/me/biometrics/enroll",
            json={
                "image_base64": f"data:image/jpeg;base64,{synthetic_face}",
                "lighting_score": 0.10,
                "face_centered": True,
            },
            headers=hu13_setup["headers"],
        )
        assert bad_light.status_code == 400

        ok_resp = await client.post(
            "/api/users/me/biometrics/enroll",
            json={
                "image_base64": f"data:image/jpeg;base64,{synthetic_face}",
                "lighting_score": 0.92,
                "face_centered": True,
            },
            headers=hu13_setup["headers"],
        )
        assert ok_resp.status_code == 200
        ok_body = ok_resp.json()
        assert ok_body["statuscode"] == 200
        assert ok_body["data"]["has_biometric_enrollment"] is True
        assert len(ok_body["data"]["biometric_face_hash"]) == 64
        assert ok_body["data"]["embedding_dimensions"] == 128
        assert ok_body["data"]["biometric_enrolled_at"] is not None


@pytest.mark.asyncio
async def test_availability_matrix_crud_and_overlap_validation(hu13_setup):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        put_resp = await client.put(
            "/api/users/me/availability",
            json={
                "timezone": "America/La_Paz",
                "buffer_minutes": 15,
                "slots": [
                    {
                        "day_of_week": 0,
                        "start_time": "08:00",
                        "end_time": "09:30",
                        "is_enabled": True,
                        "modality": "VIRTUAL",
                    },
                    {
                        "day_of_week": 2,
                        "start_time": "18:00",
                        "end_time": "19:00",
                        "is_enabled": True,
                        "modality": "BOTH",
                    },
                ],
            },
            headers=hu13_setup["headers"],
        )
        assert put_resp.status_code == 200
        put_body = put_resp.json()
        assert put_body["count"] == 2
        assert len(put_body["data"]) == 2
        first_slot_id = put_body["data"][0]["id"]

        overlap_resp = await client.put(
            "/api/users/me/availability",
            json={
                "slots": [
                    {"day_of_week": 1, "start_time": "10:00", "end_time": "11:00", "is_enabled": True},
                    {"day_of_week": 1, "start_time": "10:30", "end_time": "11:30", "is_enabled": True},
                ]
            },
            headers=hu13_setup["headers"],
        )
        assert overlap_resp.status_code == 422

        del_resp = await client.delete(
            f"/api/users/me/availability/{first_slot_id}",
            headers=hu13_setup["headers"],
        )
        assert del_resp.status_code == 200

        get_resp = await client.get("/api/users/me/availability", headers=hu13_setup["headers"])
        assert get_resp.status_code == 200
        assert get_resp.json()["count"] == 1
