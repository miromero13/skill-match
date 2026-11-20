import uuid

import pytest

from app.core.exceptions import SkillMatchException
from app.models.programming import Challenge, ChallengeTestCase
from app.services.programming_service import ChallengeService
from app.services.programming_sandbox_runner import SandboxRunResult
from app.schemas.programming import ChallengePreviewRequest


def challenge() -> Challenge:
    item = Challenge(
        id=uuid.uuid4(),
        skill_id=uuid.uuid4(),
        level_number=1,
        version=1,
        title="Sum",
        statement="Read two integers and print their sum.",
        evaluation_modality="SANDBOX",
        execution_profile="PYTHON_3_12",
        starter_code="",
        time_limit_ms=1000,
        memory_limit_mb=128,
        max_output_bytes=4096,
        allowed_imports=[],
        blocked_imports=[],
        status="PUBLISHED",
        created_by_id=uuid.uuid4(),
    )
    item.tests = [
        ChallengeTestCase(name="basic", stdin_data="2 3\n", expected_stdout="5\n", visibility="PUBLIC", order_index=0),
        ChallengeTestCase(name="hidden", stdin_data="-1 4\n", expected_stdout="3\n", visibility="HIDDEN", order_index=1),
    ]
    return item


@pytest.mark.asyncio
async def test_public_run_uses_only_public_tests(monkeypatch):
    item = challenge()

    async def fake_get(_db, _challenge_id, *, include_hidden):
        assert include_hidden is False
        return item

    async def fake_run(**kwargs):
        assert kwargs["stdin_data"] == "2 3\n"
        return SandboxRunResult(stdout="5\n", stderr="", exit_code=0, timed_out=False, output_limited=False)

    monkeypatch.setattr(ChallengeService, "get_challenge", fake_get)
    monkeypatch.setattr(ChallengeService.runner, "run", fake_run)
    result = await ChallengeService.run_public_tests(object(), item.id, "a, b = map(int, input().split()); print(a + b)")
    assert result.status == "PASSED"
    assert result.passed_tests == 1
    assert result.total_tests == 1


@pytest.mark.asyncio
async def test_preview_runs_unsaved_public_and_hidden_cases(monkeypatch):
    calls = []

    async def fake_run(**kwargs):
        calls.append(kwargs["stdin_data"])
        return SandboxRunResult(stdout=kwargs["stdin_data"], stderr="", exit_code=0, timed_out=False, output_limited=False)

    monkeypatch.setattr(ChallengeService.runner, "run", fake_run)
    payload = ChallengePreviewRequest(
        skill_id=uuid.uuid4(), level_number=1, title="Echo challenge",
        statement="Print the provided input.", evaluation_modality="SANDBOX",
        execution_profile="PYTHON_3_12", code="print(input())",
        tests=[
            {"name": "public", "stdin_data": "public\n", "expected_stdout": "public\n", "visibility": "PUBLIC", "order_index": 0},
            {"name": "hidden", "stdin_data": "hidden\n", "expected_stdout": "hidden\n", "visibility": "HIDDEN", "order_index": 1},
        ],
    )
    result = await ChallengeService.preview_challenge(payload)
    assert result.status == "PASSED"
    assert calls == ["public\n", "hidden\n"]


def test_static_validation_rejects_syntax_and_dangerous_imports():
    item = challenge()
    with pytest.raises(SkillMatchException) as syntax_error:
        ChallengeService._validate_code("def broken(:", item)
    assert syntax_error.value.statuscode == 400

    with pytest.raises(SkillMatchException) as import_error:
        ChallengeService._validate_code("import os\nprint('no')", item)
    assert "no está permitido" in import_error.value.message


def test_static_validation_rejects_dynamic_execution():
    with pytest.raises(SkillMatchException) as error:
        ChallengeService._validate_code("eval('1 + 1')", challenge())
    assert error.value.message == "El uso de 'eval' no está permitido en el sandbox."

    with pytest.raises(SkillMatchException) as attribute_error:
        ChallengeService._validate_code("import builtins\nbuiltins.open('x')", challenge())
    assert attribute_error.value.message == "El uso de 'open' no está permitido en el sandbox."
