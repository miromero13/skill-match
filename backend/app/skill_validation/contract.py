"""Public contract of the skill validation engine (odd/tasks/skill-validation-engine.md, Engine contract).

Pure data: no ORM, no FastAPI. Every value the engine returns is JSON-serializable.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

ENGINE_VERSION = "skill-validation-1.1"  # 1.1: dedicated juggling touch counter (S6)

METRIC_REFERENCE_REPLICATION = "REFERENCE_REPLICATION"
METRIC_BALL_TOUCH_STREAK = "BALL_TOUCH_STREAK"

METRIC_TYPES: list[dict] = [
    {
        "code": METRIC_REFERENCE_REPLICATION,
        "name": "Replicar el video de referencia",
        "description": (
            "Compara la postura y el movimiento de la persona (ángulos articulares 3D) con el video de "
            "referencia del nivel. Tolera el ángulo de cámara, el lado (espejo) y el ritmo de ejecución."
        ),
        "requires_target": False,
        "requires_reference": True,
    },
    {
        "code": METRIC_BALL_TOUCH_STREAK,
        "name": "Racha de toques de balón",
        "description": (
            "Cuenta la mayor racha de toques consecutivos sin que el balón caiga. El objetivo es la "
            "cantidad de toques que vale el 100% del criterio."
        ),
        "requires_target": True,
        "requires_reference": False,
    },
]

METRIC_CODES = frozenset(item["code"] for item in METRIC_TYPES)


@dataclass(frozen=True)
class CriterionSpec:
    key: str
    name: str
    weight: float
    metric_type: str
    target: float | None = None


@dataclass(frozen=True)
class LevelSpec:
    level_id: str
    level_number: int
    name: str
    min_score: float
    criteria: tuple[CriterionSpec, ...]
    reference: dict | None = None  # analysis dict of the level reference video
    criterion_references: Mapping[str, dict] = field(default_factory=dict)  # criterion key -> analysis


@dataclass(frozen=True)
class SkillSpec:
    skill_id: str
    name: str
    min_approval_threshold: float
    levels: tuple[LevelSpec, ...]


@dataclass(frozen=True)
class LabeledSample:
    level_id: str
    criterion_key: str | None
    analysis: dict
