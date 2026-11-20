"""Skill lab T8 (S10): signed preview URL + Range file endpoint, through HTTP and the APIResponse envelope.

Same hygiene as `test_skill_lab_api.py` (reused `lab` fixture): throwaway PostgreSQL schema rolled back,
stored files under the pytest tmp path (cwd is switched there), `analyze_video` replaced by `FakeAnalyzer`.
"""
# ruff: noqa: F811 - pytest fixtures (`lab`, `isolated_db`) are imported and then requested by name.
import time
import uuid
from datetime import datetime
from urllib.parse import parse_qs, urlsplit

import pytest
from sqlalchemy import select

from app.models.dataset_sample import DatasetSample
from app.services import skill_lab_service
from auth_catalog_fixtures import isolated_db  # noqa: F401 - required by `lab`
from test_skill_lab_api import (  # noqa: F401 - `lab` is a fixture
    LAB,
    NOT_FOUND,
    _create_skill,
    _samples,
    _stored_files,
    _upload,
    lab,
)

CONTENT = b"motion=juggle;seed=0;yaw=0;streak=0;" + bytes(range(256)) * 4
PREVIEW_MESSAGE = "URL de previsualización generada exitosamente."
SAMPLE_NOT_FOUND = "Muestra no encontrada."
FILE_UNAVAILABLE = "El video de la muestra no está disponible."
CONTENT_TYPES = {"mp4": "video/mp4", "webm": "video/webm", "mov": "video/quicktime"}


async def _sample(ctx, *, filename="clip.mp4", content=CONTENT, role="TRAINING"):
    if "skill" not in ctx.catalog:
        ctx.catalog["skill"], _ = await _create_skill(ctx)
    skill = ctx.catalog["skill"]
    response = await _upload(ctx, skill["id"], skill["levels"][0]["id"], role=role, filename=filename,
                             content=content)
    assert response.status_code == 201, response.text
    return response.json()["data"]


async def _preview(ctx, sample_id, headers=None):
    return await ctx.client.post(f"{LAB}/samples/{sample_id}/preview-url",
                                 headers=ctx.admin if headers is None else headers)


async def _preview_url(ctx, sample_id) -> str:
    response = await _preview(ctx, sample_id)
    assert response.status_code == 200, response.text
    return response.json()["data"]["url"]


def _token(url: str) -> str:
    return parse_qs(urlsplit(url).query)["token"][0]


def _assert_not_found(response):
    assert response.status_code == 404
    assert response.json() == NOT_FOUND
    assert "content-disposition" not in response.headers


async def _db_samples(ctx) -> list[tuple]:
    rows = (await ctx.db.execute(select(DatasetSample.id, DatasetSample.storage_path))).all()
    return sorted((str(row.id), row.storage_path) for row in rows)


# ---------------------------------------------------------------- POST /samples/{id}/preview-url


@pytest.mark.asyncio
@pytest.mark.parametrize("ext", ["mp4", "webm", "mov"])
async def test_admin_gets_a_signed_url_bound_to_the_sample(lab, ext):
    sample = await _sample(lab, filename=f"clip.{ext}")
    rows_before = await _db_samples(lab)
    before = time.time()

    response = await _preview(lab, sample["id"])

    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) <= {"statuscode", "message", "data", "count"}
    assert body["statuscode"] == 200
    assert body["message"] == PREVIEW_MESSAGE
    data = body["data"]
    assert set(data) == {"url", "expires_at", "content_type"}
    assert data["content_type"] == CONTENT_TYPES[ext]
    assert data["url"].startswith(f"/api/admin/skill-lab/samples/{sample['id']}/file?token=")
    assert _token(data["url"])
    expires_at = datetime.fromisoformat(data["expires_at"]).timestamp()
    assert before + 600 - 5 <= expires_at <= time.time() + 600 + 5
    assert await _db_samples(lab) == rows_before


@pytest.mark.asyncio
async def test_reference_samples_can_be_previewed_too(lab):
    sample = await _sample(lab, role="REFERENCE")
    url = await _preview_url(lab, sample["id"])
    response = await lab.client.get(url)
    assert response.status_code == 200
    assert response.content == CONTENT


@pytest.mark.asyncio
@pytest.mark.parametrize("who", ["anonymous", "member"])
async def test_preview_url_is_hidden_from_members_and_anonymous(lab, who):
    sample = await _sample(lab)
    response = await _preview(lab, sample["id"], headers={} if who == "anonymous" else lab.member)
    assert response.status_code == 404
    assert response.json() == NOT_FOUND


@pytest.mark.asyncio
async def test_preview_url_of_unknown_sample_is_404(lab):
    await _sample(lab)
    response = await _preview(lab, uuid.uuid4())
    assert response.status_code == 404
    assert response.json() == {"statuscode": 404, "message": SAMPLE_NOT_FOUND, "data": None}


@pytest.mark.asyncio
async def test_preview_url_of_sample_whose_file_is_missing_is_404(lab):
    sample = await _sample(lab)
    [stored] = _stored_files(lab)
    stored.unlink()  # under the pytest tmp path
    rows_before = await _db_samples(lab)

    response = await _preview(lab, sample["id"])

    assert response.status_code == 404
    assert response.json() == {"statuscode": 404, "message": FILE_UNAVAILABLE, "data": None}
    assert await _db_samples(lab) == rows_before


@pytest.mark.asyncio
async def test_preview_url_of_deleted_sample_is_404_and_its_old_url_stops_working(lab):
    sample = await _sample(lab)
    url = await _preview_url(lab, sample["id"])
    deleted = await lab.client.delete(f"{LAB}/samples/{sample['id']}", headers=lab.admin)
    assert deleted.status_code == 200

    response = await _preview(lab, sample["id"])
    assert response.status_code == 404
    assert response.json() == {"statuscode": 404, "message": SAMPLE_NOT_FOUND, "data": None}
    _assert_not_found(await lab.client.get(url))


# ---------------------------------------------------------------- GET /samples/{id}/file?token=


@pytest.mark.asyncio
async def test_file_is_served_with_only_the_token_no_authorization_header(lab):
    sample = await _sample(lab, filename="../../Mi video «raro».mp4")
    url = await _preview_url(lab, sample["id"])

    response = await lab.client.get(url)  # no Authorization header at all

    assert response.status_code == 200
    assert response.content == CONTENT
    assert response.headers["content-type"] == "video/mp4"
    assert response.headers["content-length"] == str(len(CONTENT))
    assert response.headers["accept-ranges"] == "bytes"
    assert response.headers["cache-control"] == "private, max-age=600"
    assert response.headers["content-disposition"] == f'inline; filename="muestra-{sample["id"]}.mp4"'
    assert "content-encoding" not in response.headers


@pytest.mark.asyncio
async def test_gzip_never_touches_the_video(lab):
    sample = await _sample(lab)
    url = await _preview_url(lab, sample["id"])
    response = await lab.client.get(url, headers={"Accept-Encoding": "gzip"})
    assert response.status_code == 200
    assert "content-encoding" not in response.headers
    assert response.content == CONTENT


@pytest.mark.asyncio
async def test_range_request_returns_206_with_the_requested_bytes(lab):
    sample = await _sample(lab, filename="clip.webm")
    url = await _preview_url(lab, sample["id"])

    response = await lab.client.get(url, headers={"Range": "bytes=0-9"})

    assert response.status_code == 206
    assert response.content == CONTENT[:10]
    assert response.headers["content-range"] == f"bytes 0-9/{len(CONTENT)}"
    assert response.headers["content-length"] == "10"
    assert response.headers["content-type"] == "video/webm"

    tail = await lab.client.get(url, headers={"Range": "bytes=100-"})
    assert tail.status_code == 206
    assert tail.content == CONTENT[100:]


@pytest.mark.asyncio
async def test_tampered_token_is_404(lab):
    sample = await _sample(lab)
    url = await _preview_url(lab, sample["id"])
    token = _token(url)
    tampered = token[:-1] + ("0" if token[-1] != "0" else "1")
    _assert_not_found(await lab.client.get(f"{LAB}/samples/{sample['id']}/file", params={"token": tampered}))
    expires, signature = token.split(".", 1)
    longer = f"{int(expires) + 3600}.{signature}"  # extending the expiry breaks the signature
    _assert_not_found(await lab.client.get(f"{LAB}/samples/{sample['id']}/file", params={"token": longer}))
    _assert_not_found(await lab.client.get(f"{LAB}/samples/{sample['id']}/file", params={"token": "garbage"}))


@pytest.mark.asyncio
async def test_token_of_another_sample_is_404(lab):
    first = await _sample(lab)
    second = await _sample(lab)
    token = _token(await _preview_url(lab, first["id"]))
    _assert_not_found(await lab.client.get(f"{LAB}/samples/{second['id']}/file", params={"token": token}))


@pytest.mark.asyncio
async def test_expired_token_is_404(lab, monkeypatch):
    sample = await _sample(lab)
    url = await _preview_url(lab, sample["id"])
    assert (await lab.client.get(url)).status_code == 200
    real_time = time.time
    monkeypatch.setattr(skill_lab_service.time, "time", lambda: real_time() + 601)
    _assert_not_found(await lab.client.get(url))


@pytest.mark.asyncio
async def test_missing_token_or_malformed_sample_id_is_404(lab):
    sample = await _sample(lab)
    _assert_not_found(await lab.client.get(f"{LAB}/samples/{sample['id']}/file"))
    _assert_not_found(await lab.client.get(f"{LAB}/samples/{sample['id']}/file", params={"token": ""}))
    _assert_not_found(await lab.client.get(f"{LAB}/samples/not-a-uuid/file", params={"token": "1.abc"}))


@pytest.mark.asyncio
async def test_admin_bearer_alone_does_not_open_the_file(lab):
    sample = await _sample(lab)
    _assert_not_found(await lab.client.get(f"{LAB}/samples/{sample['id']}/file", headers=lab.admin))


@pytest.mark.asyncio
async def test_file_removed_after_minting_the_url_is_404(lab):
    sample = await _sample(lab)
    url = await _preview_url(lab, sample["id"])
    [stored] = _stored_files(lab)
    stored.unlink()  # under the pytest tmp path
    _assert_not_found(await lab.client.get(url))


@pytest.mark.asyncio
async def test_stored_path_outside_the_storage_root_is_never_served(lab, tmp_path):
    sample = await _sample(lab)
    outside = tmp_path / "outside.mp4"  # sibling of tmp_path/storage, i.e. outside the storage root
    outside.write_bytes(b"secret-bytes")
    row = await lab.db.get(DatasetSample, uuid.UUID(sample["id"]))
    row.storage_path = "../outside.mp4"
    await lab.db.commit()

    response = await _preview(lab, sample["id"])
    assert response.status_code == 404
    assert response.json() == {"statuscode": 404, "message": FILE_UNAVAILABLE, "data": None}
    token = skill_lab_service.sign_preview_token(uuid.UUID(sample["id"]), int(time.time()) + 300)
    _assert_not_found(await lab.client.get(f"{LAB}/samples/{sample['id']}/file", params={"token": token}))
    assert outside.read_bytes() == b"secret-bytes"


@pytest.mark.asyncio
async def test_existing_lab_routes_keep_requiring_admin(lab):
    """PRESERVE: mounting the token route did not open the admin router (sample list stays hidden)."""
    sample = await _sample(lab)
    response = await lab.client.get(f"{LAB}/skills/{sample['skill_id']}/samples")
    assert response.status_code == 404
    assert response.json() == NOT_FOUND
    listed = await _samples(lab, sample["skill_id"])
    assert listed["count"] == 1
