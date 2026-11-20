"""S6: the public engine functions never raise and always return a complete, JSON-serializable result."""
from __future__ import annotations

import json

import pytest

from app.skill_validation import (
    METRIC_REFERENCE_REPLICATION,
    CriterionSpec,
    LevelSpec,
    SkillSpec,
    calibrate_skill,
    evaluate_skill,
)
from tests.skill_validation import synthetic as syn

REFERENCE = syn.analysis(syn.signature(syn.squat, seconds=6, noise_deg=2, seed=1))


def skill(**level_kwargs) -> SkillSpec:
    defaults = {"level_id": "l1", "level_number": 1, "name": "Uno", "min_score": 50.0, "criteria": (),
                "reference": REFERENCE}
    return SkillSpec("s", "Hab", 50.0, (LevelSpec(**{**defaults, **level_kwargs}),))


GARBAGE_ANALYSES = [
    None,
    {},
    "text",
    {"readable": True},
    {"readable": True, "pose": {"signature": "x"}},
    {"readable": True, "pose": {"signature": [[None] * 13, [1, 2], "row", None], "visibility": "bad"}},
    {"readable": True, "pose": {"signature": [[float("nan")] * 13] * 30, "fps": "fast", "detected_ratio": None}},
    {"readable": True, "pose": None, "ball": {"max_streak": "many", "ball_detected": True}},
    {"readable": True, "duration_seconds": "long", "notes": [None, 3, "ok"]},
]


@pytest.mark.parametrize("analysis", GARBAGE_ANALYSES)
def test_evaluate_skill_never_raises_on_garbage_analysis(analysis):
    result = evaluate_skill(skill(), analysis)
    json.dumps(result, allow_nan=False)
    assert result["approved"] is False and result["achieved_level"] is None


@pytest.mark.parametrize(
    "spec",
    [
        None,
        "skill",
        SkillSpec("s", "Hab", None, ()),  # type: ignore[arg-type]
        skill(criteria=(CriterionSpec("k", "X", None, "UNKNOWN"),)),  # type: ignore[arg-type]
        skill(criteria=(CriterionSpec("k", "X", 100.0, METRIC_REFERENCE_REPLICATION),), criterion_references=None),
        skill(reference={"pose": "garbage"}),
        skill(min_score=None),  # type: ignore[arg-type]
    ],
)
def test_evaluate_skill_never_raises_on_garbage_skill(spec):
    result = evaluate_skill(spec, REFERENCE, calibration={"levels": None}, target_level_id=123)
    json.dumps(result, allow_nan=False)
    assert result["approved"] is False


def test_unknown_metric_is_not_evaluable_with_reason():
    result = evaluate_skill(skill(criteria=(CriterionSpec("k", "X", 100.0, "UNKNOWN"),)), REFERENCE)
    criterion = result["levels"][0]["criteria"][0]
    assert criterion["evaluable"] is False and criterion["note"] == "Tipo de métrica no soportado: UNKNOWN."


def test_calibrate_skill_never_raises():
    for spec, samples in ((None, None), ("x", ["y"]), (skill(), [None]), (skill(reference={"pose": 1}), [])):
        out = calibrate_skill(spec, samples)  # type: ignore[arg-type]
        json.dumps(out, allow_nan=False)
        assert set(out) == {"calibration", "metrics", "notes"}
        assert "loo_level_accuracy" in out["metrics"] and "samples_per_level" in out["metrics"]
