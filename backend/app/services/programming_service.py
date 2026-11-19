import ast
import asyncio
import re
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.exceptions import SkillMatchException
from app.models.evaluation import Evaluation
from app.models.theory_exam import TheoryExam
from app.models.programming import Challenge, ChallengeSubmission, ChallengeTestCase
from app.models.user import User
from app.schemas.programming import ChallengeCreateRequest, ChallengePreviewRequest, ChallengeRunResponse, ChallengeTestResult
from app.services.programming_sandbox_runner import DockerSandboxRunner, SandboxUnavailableError


_DEFAULT_BLOCKED_IMPORTS = {
    "os", "sys", "subprocess", "socket", "pathlib", "shutil", "ctypes", "resource", "signal",
    "pty", "fcntl", "multiprocessing", "threading", "asyncio", "requests", "urllib", "http", "importlib",
}
_BLOCKED_CALLS = {"eval", "exec", "compile", "__import__", "open"}
_BLOCKED_ATTRIBUTE_CALLS = {"open", "system", "popen", "spawn", "remove", "unlink", "rmdir"}


class ChallengeService:
    runner = DockerSandboxRunner()
    _run_semaphore = asyncio.Semaphore(settings.SANDBOX_MAX_CONCURRENT_RUNS)

    @classmethod
    async def create_challenge(cls, db: AsyncSession, admin: User, payload: ChallengeCreateRequest) -> Challenge:
        if payload.evaluation_modality != "SANDBOX" or payload.execution_profile != "PYTHON_3_12":
            raise SkillMatchException("El evaluador seleccionado todavía no está disponible para retos publicados.", 400)
        from app.models.catalog import Skill
        if await db.scalar(select(Skill.id).where(Skill.id == payload.skill_id)) is None:
            raise SkillMatchException("La habilidad indicada no existe.", 404)
        latest = await db.scalar(
            select(func.max(Challenge.version)).where(
                Challenge.skill_id == payload.skill_id,
                Challenge.level_number == payload.level_number,
            )
        )
        challenge = Challenge(
            skill_id=payload.skill_id,
            challenge_type_id=payload.challenge_type_id,
            level_number=payload.level_number,
            version=(latest or 0) + 1,
            title=payload.title,
            statement=payload.statement,
            evaluation_modality=payload.evaluation_modality,
            execution_profile=payload.execution_profile,
            starter_code=payload.starter_code,
            time_limit_ms=payload.time_limit_ms,
            memory_limit_mb=payload.memory_limit_mb,
            max_output_bytes=payload.max_output_bytes,
            allowed_imports=payload.allowed_imports,
            blocked_imports=payload.blocked_imports,
            created_by_id=admin.id,
        )
        challenge.tests = [ChallengeTestCase(**test.model_dump()) for test in payload.tests]
        db.add(challenge)
        await db.flush()
        await db.refresh(challenge, attribute_names=["tests"])
        return challenge

    @classmethod
    async def preview_challenge(cls, payload: ChallengePreviewRequest) -> ChallengeRunResponse:
        if payload.evaluation_modality != "SANDBOX" or payload.execution_profile != "PYTHON_3_12":
            raise SkillMatchException("El evaluador seleccionado todavía no está disponible para pruebas.", 400)
        challenge = Challenge(
            id=uuid.uuid4(),
            skill_id=payload.skill_id,
            level_number=payload.level_number,
            version=1,
            title=payload.title,
            statement=payload.statement,
            evaluation_modality=payload.evaluation_modality,
            execution_profile=payload.execution_profile,
            starter_code=payload.starter_code,
            time_limit_ms=payload.time_limit_ms,
            memory_limit_mb=payload.memory_limit_mb,
            max_output_bytes=payload.max_output_bytes,
            allowed_imports=payload.allowed_imports,
            blocked_imports=payload.blocked_imports,
            status="DRAFT",
        )
        challenge.tests = [ChallengeTestCase(**test.model_dump()) for test in payload.tests]
        return await cls._run_tests(challenge, payload.code, public_only=False)

    @staticmethod
    async def list_challenges(db: AsyncSession, skill_id: uuid.UUID | None = None) -> list[Challenge]:
        query = select(Challenge).options(selectinload(Challenge.tests)).order_by(
            Challenge.skill_id, Challenge.level_number, Challenge.version.desc()
        )
        if skill_id:
            query = query.where(Challenge.skill_id == skill_id)
        return list((await db.scalars(query)).all())

    @staticmethod
    async def get_challenge_for_evaluation(db: AsyncSession, user: User, evaluation_id: uuid.UUID) -> Challenge:
        evaluation = await db.scalar(select(Evaluation).where(Evaluation.id == evaluation_id, Evaluation.user_id == user.id))
        if evaluation is None:
            raise SkillMatchException("La evaluación no existe o no pertenece al usuario.", 404)
        theory_exam = await db.scalar(select(TheoryExam).where(TheoryExam.evaluation_id == evaluation.id))
        level_number = theory_exam.level_number if theory_exam is not None else 1
        challenge = await db.scalar(
            select(Challenge)
            .options(selectinload(Challenge.tests))
            .where(
                Challenge.skill_id == evaluation.skill_id,
                Challenge.level_number == level_number,
                Challenge.status == "PUBLISHED",
            )
            .order_by(Challenge.version.desc())
        )
        if challenge is None:
            raise SkillMatchException("Todavía no hay un reto publicado para esta evaluación.", 404)
        challenge.tests = [test for test in challenge.tests if test.visibility == "PUBLIC"]
        return challenge

    @staticmethod
    async def get_challenge(db: AsyncSession, challenge_id: uuid.UUID, *, include_hidden: bool) -> Challenge:
        challenge = await db.scalar(
            select(Challenge).options(selectinload(Challenge.tests)).where(
                Challenge.id == challenge_id,
                Challenge.status == "PUBLISHED" if not include_hidden else True,
            )
        )
        if challenge is None:
            raise SkillMatchException("El reto no existe o no está publicado.", 404)
        if challenge.evaluation_modality != "SANDBOX" or challenge.execution_profile != "PYTHON_3_12":
            raise SkillMatchException("El evaluador de este reto todavía no está disponible.", 409)
        if not include_hidden:
            challenge.tests = [test for test in challenge.tests if test.visibility == "PUBLIC"]
        return challenge

    @staticmethod
    async def publish_challenge(db: AsyncSession, challenge_id: uuid.UUID) -> Challenge:
        challenge = await db.scalar(
            select(Challenge).options(selectinload(Challenge.tests)).where(Challenge.id == challenge_id)
        )
        if challenge is None:
            raise SkillMatchException("El reto no existe.", 404)
        if challenge.evaluation_modality != "SANDBOX" or challenge.execution_profile != "PYTHON_3_12":
            raise SkillMatchException("El evaluador de este reto todavía no está disponible.", 409)
        if not any(test.visibility == "HIDDEN" for test in challenge.tests):
            raise SkillMatchException("El reto debe tener al menos una prueba oculta antes de publicarse.", 400)
        if not any(test.visibility == "PUBLIC" for test in challenge.tests):
            raise SkillMatchException("El reto debe tener al menos una prueba pública antes de publicarse.", 400)
        await db.execute(
            update(Challenge)
            .where(
                Challenge.skill_id == challenge.skill_id,
                Challenge.level_number == challenge.level_number,
                Challenge.status == "PUBLISHED",
                Challenge.id != challenge.id,
            )
            .values(status="ARCHIVED")
        )
        challenge.status = "PUBLISHED"
        challenge.published_at = datetime.now(timezone.utc)
        await db.flush()
        return challenge

    @classmethod
    async def run_public_tests(cls, db: AsyncSession, challenge_id: uuid.UUID, code: str) -> ChallengeRunResponse:
        challenge = await cls.get_challenge(db, challenge_id, include_hidden=False)
        return await cls._run_tests(challenge, code, public_only=True)

    @classmethod
    async def submit(cls, db: AsyncSession, user: User, evaluation_id: uuid.UUID, challenge_id: uuid.UUID, code: str) -> ChallengeSubmission:
        evaluation = await db.scalar(select(Evaluation).where(Evaluation.id == evaluation_id, Evaluation.user_id == user.id))
        if evaluation is None:
            raise SkillMatchException("La evaluación no existe o no pertenece al usuario.", 404)
        if evaluation.started_at is None:
            raise SkillMatchException("La evaluación todavía no comenzó.", 409)
        challenge = await cls.get_challenge(db, challenge_id, include_hidden=True)
        if challenge.skill_id != evaluation.skill_id:
            raise SkillMatchException("El reto no corresponde a la habilidad evaluada.", 409)
        result = await cls._run_tests(challenge, code, public_only=False)
        submission = ChallengeSubmission(
            evaluation_id=evaluation.id,
            challenge_id=challenge.id,
            code=code,
            status=result.status,
            passed_tests=result.passed_tests,
            total_tests=result.total_tests,
            result=result.model_dump(mode="json"),
            submitted_at=datetime.now(timezone.utc),
        )
        db.add(submission)
        await db.flush()
        await db.refresh(submission)
        return submission

    @classmethod
    async def _run_tests(cls, challenge: Challenge, code: str, *, public_only: bool) -> ChallengeRunResponse:
        cls._validate_code(code, challenge)
        tests = [test for test in challenge.tests if not public_only or test.visibility == "PUBLIC"]
        if not tests:
            raise SkillMatchException("El reto no tiene pruebas disponibles.", 500)
        results: list[ChallengeTestResult] = []
        async with cls._run_semaphore:
            for test in tests:
                try:
                    execution = await cls.runner.run(
                        code=code,
                        stdin_data=test.stdin_data,
                        time_limit_ms=challenge.time_limit_ms,
                        memory_limit_mb=challenge.memory_limit_mb,
                        max_output_bytes=challenge.max_output_bytes,
                    )
                except SandboxUnavailableError as exc:
                    raise SkillMatchException(str(exc), 503) from exc
                expected = test.expected_stdout.rstrip()
                actual = execution.stdout.rstrip()
                results.append(ChallengeTestResult(
                    name=test.name,
                    passed=(not execution.timed_out and execution.exit_code == 0 and actual == expected and not execution.output_limited),
                    stdout=execution.stdout,
                    stderr=execution.stderr,
                    exit_code=execution.exit_code,
                    timed_out=execution.timed_out,
                ))
        passed = sum(item.passed for item in results)
        status = "PASSED" if passed == len(results) else "FAILED"
        return ChallengeRunResponse(
            challenge_id=challenge.id,
            passed_tests=passed,
            total_tests=len(results),
            status=status,
            results=results,
        )

    @staticmethod
    def _validate_code(code: str, challenge: Challenge) -> None:
        try:
            tree = ast.parse(code, mode="exec")
        except SyntaxError as exc:
            raise SkillMatchException(f"El código tiene un error de sintaxis: línea {exc.lineno or 0}.", 400) from exc
        blocked = _DEFAULT_BLOCKED_IMPORTS | set(challenge.blocked_imports)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name.split(".")[0] for alias in node.names]
                ChallengeService._check_imports(names, blocked, challenge)
            elif isinstance(node, ast.ImportFrom) and node.module:
                ChallengeService._check_imports([node.module.split(".")[0]], blocked, challenge)
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _BLOCKED_CALLS:
                raise SkillMatchException(f"El uso de '{node.func.id}' no está permitido en el sandbox.", 400)
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in _BLOCKED_ATTRIBUTE_CALLS:
                raise SkillMatchException(f"El uso de '{node.func.attr}' no está permitido en el sandbox.", 400)

    @staticmethod
    def _check_imports(names: list[str], blocked: set[str], challenge: Challenge) -> None:
        allowed = set(challenge.allowed_imports)
        for name in names:
            if name in blocked or (allowed and name not in allowed):
                raise SkillMatchException(f"El import '{name}' no está permitido en el sandbox.", 400)
