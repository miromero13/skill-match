"""Publication and editing preserve previous question versions over HTTP."""
import pytest

from auth_catalog_fixtures import isolated_db
from test_theory_question_bank import URL, bank, draft


def complete():
    return {"kind": "OPEN", "prompt": "Explain mutability.", "choices": [],
            "correct_choice": None, "reference_answer": "Lists are mutable; tuples are immutable.",
            "criteria": [{"name": "Mutability", "weight": 100, "description": "Distinguishes mutability."}],
            "time_limit_seconds": 90, "max_score": 20}


async def snapshot(client, key):
    latest = await client.get(f"{URL}/{key}")
    history = await client.get(f"{URL}/{key}/versions")
    listing = await client.get(URL)
    assert latest.status_code == history.status_code == listing.status_code == 200
    return latest.json(), history.json(), listing.json()


@pytest.mark.asyncio
async def test_edit_publish_and_archive_preserve_every_version(bank):
    client, skill, _, _ = bank
    created = await client.post(URL, json=draft(skill))
    assert created.status_code == 201
    original = created.json()["data"]
    key = original["id"]
    edited = await client.patch(f"{URL}/{key}", json={"expected_version": 1, "content": complete()})
    assert edited.status_code == 200
    assert edited.json()["message"] == "Nueva versión de pregunta creada."
    revision = edited.json()["data"]
    assert revision == {**original, "version": 2, "content": complete()}
    published = await client.post(f"{URL}/{key}/publish", json={"expected_version": 2})
    assert published.status_code == 200
    assert published.json() == {"statuscode": 200, "message": "Pregunta publicada exitosamente.",
                                "data": {**revision, "version": 3, "status": "PUBLISHED"}}
    page = await client.get(URL, params={"status": "PUBLISHED"})
    assert page.json()["count"] == 1 and page.json()["data"] == [published.json()["data"]]
    archived = await client.post(f"{URL}/{key}/archive", json={"expected_version": 3})
    assert archived.status_code == 200
    assert archived.json() == {"statuscode": 200, "message": "Pregunta archivada exitosamente.",
                               "data": {**revision, "version": 4, "status": "ARCHIVED"}}
    _, history, listing = await snapshot(client, key)
    assert history == {"statuscode": 200, "message": "Versiones de pregunta recuperadas exitosamente.",
                       "data": [original, revision, published.json()["data"], archived.json()["data"]], "count": 4}
    assert listing["data"] == [archived.json()["data"]] and listing["count"] == 1
    assert (await client.get(URL, params={"status": "PUBLISHED"})).json()["count"] == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("change,message", [
    ({"reference_answer": " "}, "Completá la respuesta de referencia y una rúbrica con pesos que sumen 100."),
    ({"criteria": []}, "Completá la respuesta de referencia y una rúbrica con pesos que sumen 100."),
    ({"criteria": [{"name": "Concept", "weight": 50, "description": "Explain."}]},
     "Completá la respuesta de referencia y una rúbrica con pesos que sumen 100."),
    ({"kind": "MULTIPLE_CHOICE", "choices": [{"code": "A", "text": "One"}, {"code": "A", "text": "Two"}], "correct_choice": "A"},
     "La pregunta debe tener opciones únicas y una respuesta correcta válida."),
    ({"kind": "TRUE_FALSE", "choices": [{"code": "A", "text": "Yes"}, {"code": "B", "text": "No"}], "correct_choice": "A"},
     "Verdadero/falso requiere las opciones TRUE y FALSE."),
    ({"choices": [{"code": "A", "text": "One"}]}, "Las preguntas abiertas no admiten opciones."),
])
async def test_incomplete_publication_has_no_persisted_effect(bank, change, message):
    client, skill, _, _ = bank
    item = (await client.post(URL, json=draft(skill, **{**complete(), **change}))).json()["data"]
    before = await snapshot(client, item["id"])
    rejected = await client.post(f"{URL}/{item['id']}/publish", json={"expected_version": 1})
    assert rejected.status_code == 400
    assert rejected.json() == {"statuscode": 400, "message": message, "data": None}
    assert await snapshot(client, item["id"]) == before


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["edit", "publish", "archive"])
async def test_stale_version_conflict_does_not_overwrite(bank, action):
    client, skill, _, _ = bank
    item = (await client.post(URL, json=draft(skill, **complete()))).json()["data"]
    before = await snapshot(client, item["id"])
    base = f"{URL}/{item['id']}"
    response = (await client.patch(base, json={"expected_version": 2, "content": complete()}) if action == "edit"
                else await client.post(f"{base}/{action}", json={"expected_version": 2}))
    assert response.status_code == 409
    assert response.json() == {"statuscode": 409, "message": "La pregunta cambió. Recargá la última versión antes de guardar.", "data": None}
    assert await snapshot(client, item["id"]) == before


@pytest.mark.asyncio
@pytest.mark.parametrize("actor", ["member", "anonymous"])
async def test_history_and_mutations_are_admin_only(bank, actor):
    client, skill, admin, member = bank
    item = (await client.post(URL, json=draft(skill, **complete()))).json()["data"]
    before = await snapshot(client, item["id"])
    if actor == "member":
        client.headers["Authorization"] = member
    else:
        client.headers.pop("Authorization")
    base = f"{URL}/{item['id']}"
    for response in [await client.get(f"{base}/versions"),
                     await client.patch(base, json={"expected_version": 1, "content": complete()}),
                     await client.post(f"{base}/publish", json={"expected_version": 1}),
                     await client.post(f"{base}/archive", json={"expected_version": 1})]:
        assert response.status_code == 404
        assert response.json() == {"statuscode": 404, "message": "Recurso no encontrado", "data": None}
    client.headers["Authorization"] = admin
    assert await snapshot(client, item["id"]) == before
