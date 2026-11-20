"""Skill validation engine (odd/tasks/skill-validation-engine.md, T2): pure, local, never raises.

- ``analyze_video``: video -> compact measurements (pose signature from 3D joint angles, ball streaks).
- ``evaluate_skill``: measurements + skill configuration (+ calibration) -> Validation result.
- ``calibrate_skill``: labeled measurements -> few-shot calibration (tolerances + level prototypes).

No ORM, no FastAPI, no network.
"""
from app.skill_validation.analysis import analyze_video
from app.skill_validation.calibration import calibrate_skill
from app.skill_validation.contract import (
    ENGINE_VERSION,
    METRIC_BALL_TOUCH_STREAK,
    METRIC_REFERENCE_REPLICATION,
    METRIC_TYPES,
    CriterionSpec,
    LabeledSample,
    LevelSpec,
    SkillSpec,
)
from app.skill_validation.evaluation import evaluate_skill

__all__ = [
    "ENGINE_VERSION",
    "METRIC_BALL_TOUCH_STREAK",
    "METRIC_REFERENCE_REPLICATION",
    "METRIC_TYPES",
    "CriterionSpec",
    "LabeledSample",
    "LevelSpec",
    "SkillSpec",
    "analyze_video",
    "calibrate_skill",
    "evaluate_skill",
]
