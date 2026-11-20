"""S5: few-shot calibration (tolerances + level prototypes) from labeled training analyses."""
from __future__ import annotations

import json
from functools import partial

import pytest

from app.skill_validation import (
    METRIC_REFERENCE_REPLICATION,
    CriterionSpec,
    LabeledSample,
    LevelSpec,
    SkillSpec,
    calibrate_skill,
    evaluate_skill,
)
from app.skill_validation import similarity
from tests.skill_validation import synthetic as syn

SQUAT = syn.signature(syn.squat, seconds=6, noise_deg=2, seed=1)
JACK = syn.signature(syn.jumping_jack, seconds=6, noise_deg=2, seed=1)
SHALLOW = partial(syn.shallow_squat, depth=0.75)
VERY_SHALLOW = partial(syn.shallow_squat, depth=0.5)

D_FULL, D_ZERO = similarity.DEFAULT_D_FULL, similarity.DEFAULT_D_ZERO
NOTE_NO_TIGHTEN = "Con menos de 5 videos por nivel la tolerancia no se reduce; solo puede ampliarse."


def sample(level_id: str, motion, seed: int, criterion_key: str | None = None) -> LabeledSample:
    return LabeledSample(level_id, criterion_key, syn.analysis(syn.signature(motion, seconds=6, noise_deg=2, seed=seed)))


def user(motion, seed: int = 50) -> dict:
    return syn.analysis(syn.signature(motion, seconds=6, noise_deg=2, seed=seed))


def single_level(min_score: float = 70.0) -> SkillSpec:
    return SkillSpec("s", "Sentadilla", 60.0, (
        LevelSpec("l1", 1, "Básico", min_score, (), reference=syn.analysis(SQUAT)),
    ))


def test_zero_samples_yields_valid_default_calibration():
    out = calibrate_skill(single_level(), [])
    json.dumps(out, allow_nan=False)
    assert set(out) == {"calibration", "metrics", "notes"}
    assert out["calibration"]["default_tolerance"] == {"d_full": D_FULL, "d_zero": D_ZERO}
    assert out["calibration"]["estimator"] is None
    assert out["metrics"]["samples_per_level"] == {"l1": 0}
    assert out["metrics"]["loo_level_accuracy"] is None
    assert "No hay videos de entrenamiento; se usan las tolerancias por defecto." in out["notes"]
    assert "Se recomienda al menos 3 videos por nivel." in out["notes"]
    result = evaluate_skill(single_level(), user(syn.squat), calibration=out["calibration"])
    assert result["levels"][0]["score"] == pytest.approx(100.0)
    assert result["model_level_estimate"] is None


def test_genuine_imperfect_examples_loosen_tolerance_within_bounds():
    skill = single_level(min_score=70.0)
    before = evaluate_skill(skill, user(VERY_SHALLOW))["levels"][0]["score"]
    assert before < 70  # with defaults a beginner's genuine squat would fail this level

    out = calibrate_skill(skill, [sample("l1", VERY_SHALLOW, seed) for seed in (11, 12, 13)])
    tol = out["calibration"]["levels"]["l1"]["tolerance"]
    assert D_FULL < tol["d_full"] <= D_FULL * 1.5
    assert D_ZERO * 0.75 <= tol["d_zero"] <= D_ZERO * 1.5
    assert out["metrics"]["samples_per_level"] == {"l1": 3}
    assert out["metrics"]["fit"]["l1"]["mean_score_calibrated"] > out["metrics"]["fit"]["l1"]["mean_score_default"]

    after = evaluate_skill(skill, user(VERY_SHALLOW), calibration=out["calibration"])["levels"][0]
    assert after["score"] >= 70 and after["passed"] is True
    assert after["criteria"][0]["detail"]["tolerance"]["source"] == "level"
    # Still no free pass: a different motion keeps failing.
    assert evaluate_skill(skill, user(syn.jumping_jack), calibration=out["calibration"])["levels"][0]["score"] < 40


def squat_levels(advanced_min_score: float = 80.0) -> SkillSpec:
    return SkillSpec("s", "Sentadilla", 60.0, (
        LevelSpec("l1", 1, "Básico", 60.0, (), reference=syn.analysis(syn.signature(SHALLOW, seconds=6, seed=1))),
        LevelSpec("l2", 2, "Avanzado", advanced_min_score, (), reference=syn.analysis(SQUAT)),
    ))


def test_lower_level_examples_tighten_a_higher_level_with_five_genuine_examples():
    skill = squat_levels()
    before = {lv["level_id"]: lv for lv in evaluate_skill(skill, user(SHALLOW))["levels"]}
    assert before["l2"]["passed"] is True  # defaults alone let a shallow squat pass the advanced level

    positives = [sample("l2", syn.squat, s) for s in (31, 32, 33, 34, 35)]
    out = calibrate_skill(skill, [sample("l1", SHALLOW, s) for s in (21, 22, 23)] + positives)
    tol = out["calibration"]["levels"]["l2"]["tolerance"]
    assert D_FULL * 0.6 <= tol["d_full"] < D_FULL
    assert D_ZERO * 0.7 <= tol["d_zero"] <= D_ZERO
    assert out["metrics"]["fit"]["l2"]["tightening_allowed"] is True
    assert out["metrics"]["tolerances"]["l2"]["tightening_allowed"] is True
    assert NOTE_NO_TIGHTEN not in out["notes"]

    after = {lv["level_id"]: lv for lv in evaluate_skill(skill, user(SHALLOW), calibration=out["calibration"])["levels"]}
    assert after["l2"]["passed"] is False and after["l1"]["passed"] is True
    good = evaluate_skill(skill, user(syn.squat), calibration=out["calibration"])
    assert good["achieved_level"]["level_id"] == "l2"
    for p in positives:
        assert evaluate_skill(skill, p.analysis, calibration=out["calibration"])["levels"][1]["passed"] is True


def test_few_genuine_examples_never_tighten_below_the_defaults():
    # The observed defect: 1 video for level 1 and 2 for level 2 used to shrink level 2 to ~14°/24°.
    skill = squat_levels()
    out = calibrate_skill(skill, [sample("l1", SHALLOW, 21)] + [sample("l2", syn.squat, s) for s in (31, 32)])
    tol = out["calibration"]["levels"]["l2"]["tolerance"]
    assert tol["d_full"] >= D_FULL and tol["d_zero"] >= D_ZERO
    assert NOTE_NO_TIGHTEN in out["notes"]
    assert out["notes"].count(NOTE_NO_TIGHTEN) == 1
    assert out["metrics"]["fit"]["l2"]["tightening_allowed"] is False
    assert out["metrics"]["tolerances"]["l2"]["tightening_allowed"] is False
    assert out["metrics"]["fit"]["l2"]["positives"] == 2

    # An unseen genuine example scores like it would with the defaults.
    unseen = user(syn.squat, seed=77)
    default_score = evaluate_skill(skill, unseen)["levels"][1]["score"]
    calibrated = evaluate_skill(skill, unseen, calibration=out["calibration"])["levels"][1]
    assert calibrated["score"] >= default_score and calibrated["passed"] is True


def test_few_examples_of_a_criterion_never_tighten_its_tolerance():
    skill = SkillSpec("s", "Sentadilla", 60.0, (
        LevelSpec("l1", 1, "Básico", 60.0, (), reference=syn.analysis(syn.signature(SHALLOW, seconds=6, seed=1))),
        LevelSpec("l2", 2, "Avanzado", 80.0, (CriterionSpec("k", "Profunda", 100.0, METRIC_REFERENCE_REPLICATION),),
                  reference=syn.analysis(SQUAT)),
    ))
    out = calibrate_skill(skill, [sample("l1", SHALLOW, s) for s in (21, 22, 23)]
                          + [sample("l2", syn.squat, s, "k") for s in (31, 32)])
    tol = out["calibration"]["levels"]["l2"]["criteria"]["k"]["tolerance"]
    assert tol["d_full"] >= D_FULL and tol["d_zero"] >= D_ZERO
    assert out["metrics"]["fit"]["l2"]["criteria"]["k"]["tightening_allowed"] is False
    assert NOTE_NO_TIGHTEN in out["notes"]


def test_tightening_never_fails_its_own_genuine_examples():
    # Without the guard, the closest-to-negatives genuine example (a slightly shallow squat) scored ~73 < 80.
    skill = squat_levels(80.0)
    positives = [sample("l2", syn.squat, s) for s in (31, 32, 33, 34)] + [
        sample("l2", partial(syn.shallow_squat, depth=0.8), 35)]
    out = calibrate_skill(skill, [sample("l1", SHALLOW, s) for s in (21, 22, 23)] + positives)
    tol = out["calibration"]["levels"]["l2"]["tolerance"]
    assert out["metrics"]["fit"]["l2"]["tightening_allowed"] is True
    assert tol["d_full"] < D_FULL or tol["d_zero"] < D_ZERO
    for p in positives:
        level = evaluate_skill(skill, p.analysis, calibration=out["calibration"])["levels"][1]
        assert level["score"] >= 80.0 and level["passed"] is True


def test_a_single_genuine_example_farther_than_the_default_still_loosens():
    skill = single_level(min_score=70.0)
    assert evaluate_skill(skill, user(VERY_SHALLOW, seed=11))["levels"][0]["passed"] is False
    out = calibrate_skill(skill, [sample("l1", VERY_SHALLOW, 11)])
    tol = out["calibration"]["levels"]["l1"]["tolerance"]
    assert tol["d_full"] > D_FULL and tol["d_zero"] >= D_ZERO
    assert out["metrics"]["fit"]["l1"]["tightening_allowed"] is False
    assert NOTE_NO_TIGHTEN not in out["notes"]  # nothing would have been tightened
    assert evaluate_skill(skill, user(VERY_SHALLOW, seed=11), calibration=out["calibration"])["levels"][0]["passed"] is True


def two_level_skill() -> SkillSpec:
    return SkillSpec("s", "Rutina", 50.0, (
        LevelSpec("l1", 1, "Uno", 60.0, (), reference=syn.analysis(SQUAT)),
        LevelSpec("l2", 2, "Dos", 60.0, (CriterionSpec("k", "Saltos", 100.0, METRIC_REFERENCE_REPLICATION),),
                  reference=syn.analysis(JACK)),
    ))


def test_level_prototypes_estimate_the_level_with_confidence():
    skill = two_level_skill()
    samples = [sample("l1", syn.squat, s) for s in (41, 42)] + [sample("l2", syn.jumping_jack, s, "k") for s in (43, 44)]
    out = calibrate_skill(skill, samples)
    assert out["metrics"]["samples_per_level"] == {"l1": 2, "l2": 2}
    assert out["metrics"]["samples_per_criterion"] == {"k": 2}
    assert out["metrics"]["loo_level_accuracy"] == 1.0
    assert set(out["calibration"]["estimator"]["prototypes"]) == {"l1", "l2"}
    assert "k" in out["calibration"]["levels"]["l2"]["criteria"]
    json.dumps(out, allow_nan=False)

    for motion, expected in ((syn.squat, "l1"), (syn.jumping_jack, "l2")):
        estimate = evaluate_skill(skill, user(motion), calibration=out["calibration"])["model_level_estimate"]
        assert estimate["level_id"] == expected
        assert set(estimate) == {"level_id", "name", "confidence"}
        assert 0.5 < estimate["confidence"] <= 1.0


def test_estimator_needs_two_levels_and_loo_needs_two_samples():
    skill = two_level_skill()
    one_level = calibrate_skill(skill, [sample("l1", syn.squat, 41)])
    assert one_level["calibration"]["estimator"] is None
    assert one_level["metrics"]["loo_level_accuracy"] is None
    assert "Se necesitan videos de al menos 2 niveles para estimar el nivel del usuario." in one_level["notes"]

    singles = calibrate_skill(skill, [sample("l1", syn.squat, 41), sample("l2", syn.jumping_jack, 42)])
    assert singles["calibration"]["estimator"] is not None
    assert singles["metrics"]["loo_level_accuracy"] is None


def test_replaced_reference_after_training_falls_back_to_defaults_with_note():
    skill = single_level()
    out = calibrate_skill(skill, [sample("l1", VERY_SHALLOW, s) for s in (11, 12, 13)])
    new_reference = syn.analysis(syn.signature(syn.squat, seconds=6, noise_deg=2, seed=99))
    replaced = SkillSpec("s", "Sentadilla", 60.0, (LevelSpec("l1", 1, "Básico", 70.0, (), reference=new_reference),))
    result = evaluate_skill(replaced, user(syn.squat), calibration=out["calibration"])
    assert result["levels"][0]["criteria"][0]["detail"]["tolerance"]["source"] == "default"
    assert any("cambió después del entrenamiento" in note for note in result["notes"])


def test_garbage_samples_and_unknown_levels_never_raise():
    skill = single_level()
    out = calibrate_skill(skill, [
        LabeledSample("ghost", None, user(syn.squat)),
        LabeledSample("l1", None, {}),
        LabeledSample("l1", None, None),  # type: ignore[arg-type]
        "not a sample",  # type: ignore[list-item]
    ])
    json.dumps(out, allow_nan=False)
    assert out["metrics"]["ignored_samples"] == 2
    assert out["metrics"]["samples_without_pose"] == 2
    assert out["calibration"]["levels"]["l1"]["tolerance"] is None
    assert calibrate_skill(None, None)["calibration"]["levels"] == {}  # type: ignore[arg-type]


def test_garbage_calibration_is_ignored_by_evaluation():
    for calibration in ({"levels": "x", "estimator": [1]}, {"default_tolerance": {"d_full": "nan"}}, {"levels": {"l1": 5}}):
        result = evaluate_skill(single_level(), user(syn.squat), calibration=calibration)
        assert result["levels"][0]["score"] == pytest.approx(100.0)
