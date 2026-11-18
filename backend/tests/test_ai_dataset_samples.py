import hashlib
import io
import uuid
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import settings
from app.core.security import create_access_token
from app.db.session import get_db
from app.main import create_application
from app.models.dataset_sample import DatasetSample
from app.models.user import User, UserRole


@pytest.fixture
async def ai_dataset_api():
    engine = create_async_engine(settings.async_database_url, pool_pre_ping=True)
    app = create_application()
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            try:
                async with AsyncSession(
                    bind=connection,
                    expire_on_commit=False,
                    join_transaction_mode="create_savepoint",
                ) as db:
                    suffix = uuid.uuid4().hex[:8]
                    admin_user = User(
                        id=uuid.uuid4(),
                        email=f"admin-capture-{suffix}@example.com",
                        full_name="Admin Capture",
                        role=UserRole.ADMIN,
                        is_active=True,
                        is_locked=False,
                        hashed_password=None,
                    )
                    member_user = User(
                        id=uuid.uuid4(),
                        email=f"member-capture-{suffix}@example.com",
                        full_name="Member Regular",
                        role=UserRole.MEMBER,
                        is_active=True,
                        is_locked=False,
                        hashed_password=None,
                    )
                    db.add_all([admin_user, member_user])
                    await db.flush()

                    async def transaction_db():
                        async with AsyncSession(
                            bind=connection,
                            expire_on_commit=False,
                            join_transaction_mode="create_savepoint",
                        ) as request_db:
                            try:
                                yield request_db
                                await request_db.commit()
                            except Exception:
                                await request_db.rollback()
                                raise

                    await db.commit()
                    app.dependency_overrides[get_db] = transaction_db

                    admin_token = create_access_token(
                        subject=str(admin_user.id), role="ADMIN"
                    )
                    member_token = create_access_token(
                        subject=str(member_user.id), role="MEMBER"
                    )

                    transport = ASGITransport(app=app, raise_app_exceptions=False)
                    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                        yield {
                            "client": client,
                            "admin_token": admin_token,
                            "member_token": member_token,
                            "db": db,
                        }
                    app.dependency_overrides.clear()
            finally:
                await transaction.rollback()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_obfuscation_policy_for_anonymous_and_member(ai_dataset_api):
    client = ai_dataset_api["client"]
    member_token = ai_dataset_api["member_token"]

    # 1. Anonymous access
    res = await client.get("/api/ai/datasets/samples")
    assert res.status_code == 404
    assert res.json()["message"] == "Recurso no encontrado"

    # 2. Member access (must return 404, NEVER 403)
    res = await client.get(
        "/api/ai/datasets/samples",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert res.status_code == 404
    assert res.json()["message"] == "Recurso no encontrado"

    # 3. Member trying to upload
    res = await client.post(
        "/api/ai/datasets/samples/upload",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert res.status_code == 404
    assert res.json()["message"] == "Recurso no encontrado"


@pytest.mark.asyncio
async def test_admin_list_dataset_samples(ai_dataset_api):
    client = ai_dataset_api["client"]
    admin_token = ai_dataset_api["admin_token"]

    res = await client.get(
        "/api/ai/datasets/samples",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["statuscode"] == 200
    assert "data" in body
    assert "count" in body
    assert isinstance(body["data"], list)


@pytest.mark.asyncio
async def test_admin_upload_sample_mp4_with_sha256(ai_dataset_api):
    client = ai_dataset_api["client"]
    admin_token = ai_dataset_api["admin_token"]

    file_content = b"fake video mp4 stream for test"
    client_hash = hashlib.sha256(file_content).hexdigest()

    form_data = {
        "discipline": "futbol",
        "challenge": "dominadas-y-control",
        "hardware_info": "iPhone 13 4K Camera",
        "signed_consent": "true",
        "file_hash_sha256": client_hash,
    }
    files = {
        "file": ("test_capture.mp4", io.BytesIO(file_content), "video/mp4"),
    }

    res = await client.post(
        "/api/ai/datasets/samples/upload",
        data=form_data,
        files=files,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 201
    body = res.json()
    assert body["statuscode"] == 201
    assert body["message"] == "Muestra multimedia subida y procesada exitosamente."
    sample_data = body["data"]
    assert sample_data["discipline"] == "futbol"
    assert sample_data["file_format"] == "mp4"
    assert sample_data["file_hash_sha256"] == client_hash
    assert sample_data["signed_consent"] is True

    # Check that sample is now listed
    list_res = await client.get(
        "/api/ai/datasets/samples",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert list_res.status_code == 200
    list_body = list_res.json()
    assert list_body["count"] >= 1
    sample_ids = [s["id"] for s in list_body["data"]]
    assert sample_data["id"] in sample_ids

    # Delete sample
    del_res = await client.delete(
        f"/api/ai/datasets/samples/{sample_data['id']}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert del_res.status_code == 200
    assert del_res.json()["message"] == "Muestra eliminada exitosamente."


@pytest.mark.asyncio
async def test_admin_upload_rejects_hash_mismatch(ai_dataset_api):
    client = ai_dataset_api["client"]
    admin_token = ai_dataset_api["admin_token"]

    file_content = b"fake audio content"
    mismatched_hash = "c" * 64

    form_data = {
        "discipline": "musica",
        "challenge": "guitarra-acustica",
        "hardware_info": "Built-in Microphone",
        "signed_consent": "true",
        "file_hash_sha256": mismatched_hash,
    }
    files = {
        "file": ("test_audio.wav", io.BytesIO(file_content), "audio/wav"),
    }

    res = await client.post(
        "/api/ai/datasets/samples/upload",
        data=form_data,
        files=files,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 400
    body = res.json()
    assert "no coincide" in body["message"].lower()


@pytest.mark.asyncio
async def test_admin_upload_rejects_invalid_file_format(ai_dataset_api):
    client = ai_dataset_api["client"]
    admin_token = ai_dataset_api["admin_token"]

    file_content = b"binary exe payload"
    form_data = {
        "discipline": "programacion",
        "challenge": "python-fastapi",
        "hardware_info": "Linux VM",
        "signed_consent": "true",
    }
    files = {
        "file": ("exploit.exe", io.BytesIO(file_content), "application/octet-stream"),
    }

    res = await client.post(
        "/api/ai/datasets/samples/upload",
        data=form_data,
        files=files,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 400
    body = res.json()
    assert "formato no permitido" in body["message"].lower()


@pytest.mark.asyncio
async def test_admin_upload_wav_and_py_files(ai_dataset_api):
    client = ai_dataset_api["client"]
    admin_token = ai_dataset_api["admin_token"]

    # 1. Test .wav upload
    wav_content = b"RIFF....WAVEfmt ...."
    res_wav = await client.post(
        "/api/ai/datasets/samples/upload",
        data={
            "discipline": "musica",
            "challenge": "guitarra-acustica",
            "hardware_info": "Focusrite Scarlett Solo",
            "signed_consent": "true",
        },
        files={"file": ("sample.wav", io.BytesIO(wav_content), "audio/wav")},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res_wav.status_code == 201
    assert res_wav.json()["data"]["file_format"] == "wav"

    # 2. Test .py upload
    py_content = b"def solution():\n    return 42\n"
    res_py = await client.post(
        "/api/ai/datasets/samples/upload",
        data={
            "discipline": "programacion",
            "challenge": "algoritmos-python",
            "hardware_info": "MacBook Pro M2",
            "signed_consent": "true",
        },
        files={"file": ("solution.py", io.BytesIO(py_content), "text/x-python")},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res_py.status_code == 201
    assert res_py.json()["data"]["file_format"] == "py"


@pytest.mark.asyncio
async def test_admin_upload_rejects_missing_consent(ai_dataset_api):
    client = ai_dataset_api["client"]
    admin_token = ai_dataset_api["admin_token"]

    res = await client.post(
        "/api/ai/datasets/samples/upload",
        data={
            "discipline": "musica",
            "challenge": "piano",
            "hardware_info": "USB MIDI",
            "signed_consent": "false",
        },
        files={"file": ("test.wav", io.BytesIO(b"audio"), "audio/wav")},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code in (400, 422)


@pytest.mark.asyncio
async def test_admin_delete_non_existent_sample_returns_404(ai_dataset_api):
    client = ai_dataset_api["client"]
    admin_token = ai_dataset_api["admin_token"]

    non_existent = uuid.uuid4()
    res = await client.delete(
        f"/api/ai/datasets/samples/{non_existent}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 404
    assert "no encontrada" in res.json()["message"].lower()
