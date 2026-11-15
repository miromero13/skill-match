import json
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

VALID = {
    "title": "Proyecto",
    "url": "https://example.com/project",
    "evidence_type": "REPOSITORY",
}


@pytest.fixture(params=["SkillEvidenceCreate", "SkillEvidenceUpdate"])
def write_schema(request):
    from app.schemas import skill_evidence

    return getattr(skill_evidence, request.param)


def test_normalizes_without_losing_url_path_query_or_fragment(write_schema):
    item = write_schema.model_validate({
        **VALID, "title": "  Proyecto  ", "description": " \n ",
        "url": "HTTPS://EXAMPLE.COM:443/a%2Fb?next=One%20Two#Section",
    })
    data = item.model_dump(mode="json")
    assert data == {
        "title": "Proyecto", "description": None,
        "url": "https://example.com/a%2Fb?next=One%20Two#Section",
        "evidence_type": "REPOSITORY",
    }


@pytest.mark.parametrize("field", ["title", "url", "evidence_type"])
def test_all_editable_required_fields_are_required(write_schema, field):
    with pytest.raises(ValidationError):
        write_schema.model_validate({key: value for key, value in VALID.items() if key != field})


@pytest.mark.parametrize("changes", [
    {"title": "\t \n"}, {"title": "x" * 151}, {"title": 12},
    {"description": "x" * 2001}, {"description": ["invalid"]},
    {"evidence_type": "UNKNOWN"}, {"evidence_type": "video"},
    {"url": "relative/path"}, {"url": "javascript:alert(1)"},
    {"url": "file:///tmp/example"}, {"url": "ftp://example.com"},
    {"url": "https:example.com"}, {"url": "https://user:password@example.com"},
    {"url": "https://@example.com"}, {"url": "https://user@example.com"},
    {"url": "https://example.com/" + "x" * 2048},
    {"url": "https://example.com/" + "é" * 500},
    {"url": 123}, {"url": None}, {"title": None},
    {"id": str(uuid4())}, {"user_id": str(uuid4())},
    {"teaching_skill_id": str(uuid4())}, {"created_at": "2026-01-01T00:00:00Z"},
    {"updated_at": "2026-01-01T00:00:00Z"}, {"status": "VERIFICADA"},
])
def test_invalid_inputs_and_server_fields_are_rejected(write_schema, changes):
    with pytest.raises(ValidationError):
        write_schema.model_validate({**VALID, **changes})


@pytest.mark.parametrize("kind", ["REPOSITORY", "VIDEO", "CERTIFICATE", "OTHER"])
@pytest.mark.parametrize("scheme", ["http", "https"])
def test_permitted_types_and_schemes(write_schema, kind, scheme):
    item = write_schema.model_validate({**VALID, "url": f"{scheme}://example.com", "evidence_type": kind})
    assert item.model_dump(mode="json")["url"] == f"{scheme}://example.com/"


def test_limits_apply_after_normalizing_text_and_url(write_schema):
    prefix = "https://example.com/"
    url = prefix + "x" * (2048 - len(prefix))
    item = write_schema.model_validate({
        **VALID, "title": " " + "x" * 150 + " ",
        "description": " " + "x" * 2000 + " ", "url": url,
    })
    assert len(item.title) == 150 and len(item.description) == 2000
    assert len(str(item.url)) == 2048


def test_read_schema_serializes_orm_attributes():
    from app.models import SkillEvidence
    from app.schemas.skill_evidence import SkillEvidenceResponse

    now = datetime.now(timezone.utc)
    instance = SkillEvidence(
        id=uuid4(), teaching_skill_id=uuid4(), description=None,
        created_at=now, updated_at=now, **VALID,
    )
    output = SkillEvidenceResponse.model_validate(instance)
    data = json.loads(output.model_dump_json())
    assert data["id"] == str(instance.id)
    assert data["teaching_skill_id"] == str(instance.teaching_skill_id)
    assert data["created_at"].endswith("Z")
    assert data["evidence_type"] == "REPOSITORY"


def test_write_json_schema_documents_the_contract(write_schema):
    schema = write_schema.model_json_schema()
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {"title", "url", "evidence_type"}
    assert schema["properties"]["title"]["maxLength"] == 150
    assert schema["properties"]["url"]["maxLength"] == 2048
    assert schema["properties"]["url"]["format"] == "uri"
