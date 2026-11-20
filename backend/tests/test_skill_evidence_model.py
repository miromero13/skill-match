"""Persistence contract for HU-16, independently of its pending HTTP API."""

from sqlalchemy import CheckConstraint, UniqueConstraint


def test_model_registers_evidence_metadata_and_constraints():
    from app.models import Base, SkillEvidence

    table = SkillEvidence.__table__
    assert Base.metadata.tables["skill_evidences"] is table
    assert set(table.columns.keys()) == {
        "id", "teaching_skill_id", "title", "description", "url",
        "evidence_type", "created_at", "updated_at",
    }
    assert table.c.title.type.length == 150
    assert table.c.description.type.length == 2000
    assert table.c.url.type.length == 2048
    assert table.c.description.nullable
    assert all(not col.nullable for col in table.c if col.name != "description")
    assert table.c.created_at.type.timezone and table.c.updated_at.type.timezone
    foreign_key = next(iter(table.c.teaching_skill_id.foreign_keys))
    assert foreign_key.target_fullname == "user_teaching_skills.id"
    assert foreign_key.ondelete == "CASCADE"
    uniques = [c for c in table.constraints if isinstance(c, UniqueConstraint)]
    assert any([col.name for col in c.columns] == ["teaching_skill_id", "url"] for c in uniques)
    assert {c.name for c in table.constraints if isinstance(c, CheckConstraint)} >= {
        "ck_skill_evidences_type", "ck_skill_evidences_title", "ck_skill_evidences_url_scheme",
    }
    assert any([col.name for col in index.columns] == ["teaching_skill_id"] for index in table.indexes)


def test_evidence_types_match_confirmed_contract():
    from app.models.skill_evidence import EvidenceType

    assert {kind.value for kind in EvidenceType} == {
        "REPOSITORY", "VIDEO", "CERTIFICATE", "OTHER",
    }
