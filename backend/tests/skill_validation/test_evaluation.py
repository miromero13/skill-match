"""S6: `evaluate_skill` follows the Rules of the Validation result exactly and never invents a pass."""
from __future__ import annotations

import json

import pytest

from app.skill_validation import (
    ENGINE_VERSION,
    METRIC_BALL_TOUCH_STREAK,
    METRIC_REFERENCE_REPLICATION,
    METRIC_TYPES,
    CriterionSpec,
    LevelSpec,
    SkillSpec,
    evaluate_skill,
)
from tests.skill_validation import synthetic as syn

RESULT_KEYS = {
    "skill_id", "skill_name", "engine_version", "model_version", "analysis_complete", "target_level_id",
    "achieved_level", "score", "min_approval_threshold", "meets_skill_threshold", "approved",
    "model_level_estimate", "levels", "pose_detected_ratio", "duration_seconds", "notes",
}
LEVEL_KEYS = {"level_id", "level_number", "name", "min_score", "evaluable", "score", "passed",
              "not_evaluable_reason", "criteria"}
CRITERION_KEYS = {"key", "name", "weight", "metric_type", "evaluable", "score", "detail", "note"}

SQUAT = syn.signature(syn.squat, seconds=6, noise_deg=2, seed=1)
JACK = syn.signature(syn.jumping_jack, seconds=6, noise_deg=2, seed=1)
WAVE = syn.signature(syn.right_arm_wave, seconds=6, noise_deg=2, seed=1)


def ref(pose: dict) -> dict:
    return syn.analysis(pose)


def ball(max_streak: int, detected: bool = True) -> dict:
    return {"ball_detected": detected, "total_touches": max_streak, "max_streak": max_streak,
            "streaks": [max_streak], "ground_contacts": 0}


def three_level_skill(threshold: float = 70.0) -> SkillSpec:
    """L1 squat (ref only), L2 squat (60% ref + 40% ball, target 10), L3 jumping jack."""
    return SkillSpec(
        skill_id="s1", name="Habilidad", min_approval_threshold=threshold,
        levels=(
            LevelSpec("l3", 3, "Avanzado", 60.0, (), reference=ref(JACK)),
            LevelSpec("l1", 1, "Básico", 60.0, (), reference=ref(SQUAT)),
            LevelSpec(
                "l2", 2, "Intermedio", 75.0,
                (CriterionSpec("c-ref", "Replicar", 60.0, METRIC_REFERENCE_REPLICATION),
                 CriterionSpec("c-ball", "Toques", 40.0, METRIC_BALL_TOUCH_STREAK, target=10)),
                reference=ref(SQUAT),
            ),
        ),
    )


def user(pose_motion=syn.squat, streak: int = 5, **kwargs) -> dict:
    pose = syn.signature(pose_motion, seconds=6, noise_deg=2, seed=9, **kwargs)
    return syn.analysis(pose, ball=ball(streak))


def by_id(result: dict) -> dict[str, dict]:
    return {lv["level_id"]: lv for lv in result["levels"]}


def assert_shape(result: dict) -> None:
    assert set(result) == RESULT_KEYS
    for level in result["levels"]:
        assert set(level) == LEVEL_KEYS
        for criterion in level["criteria"]:
            assert set(criterion) == CRITERION_KEYS
    json.dumps(result, allow_nan=False)


def test_metric_types_catalog():
    assert [m["code"] for m in METRIC_TYPES] == [METRIC_REFERENCE_REPLICATION, METRIC_BALL_TOUCH_STREAK]
    for item in METRIC_TYPES:
        assert set(item) == {"code", "name", "description", "requires_target", "requires_reference"}
    assert METRIC_TYPES[0]["requires_reference"] is True and METRIC_TYPES[0]["requires_target"] is False
    assert METRIC_TYPES[1]["requires_target"] is True and METRIC_TYPES[1]["requires_reference"] is False


def test_weighted_level_score_passed_and_achieved_level():
    result = evaluate_skill(three_level_skill(), user(streak=5))
    assert_shape(result)
    levels = by_id(result)
    assert [lv["level_number"] for lv in result["levels"]] == [1, 2, 3]
    l2 = levels["l2"]
    crit = {c["key"]: c for c in l2["criteria"]}
    assert crit["c-ref"]["score"] == pytest.approx(100.0)
    assert crit["c-ball"]["score"] == pytest.approx(50.0)
    assert l2["score"] == pytest.approx((60 * 100 + 40 * 50) / 100)  # 80.0
    assert l2["passed"] is True  # 80 >= 75
    assert levels["l1"]["passed"] is True
    assert levels["l3"]["passed"] is False
    assert result["achieved_level"] == {"level_id": "l2", "level_number": 2, "name": "Intermedio"}
    assert result["score"] == pytest.approx(80.0)
    assert result["meets_skill_threshold"] is True and result["approved"] is True
    assert result["engine_version"] == ENGINE_VERSION and result["analysis_complete"] is True


def test_level_below_min_score_is_not_passed_and_lower_level_wins():
    result = evaluate_skill(three_level_skill(), user(streak=3))
    l2 = by_id(result)["l2"]
    assert l2["score"] == pytest.approx(60 + 40 * 30 / 100)  # 72 < 75
    assert l2["passed"] is False
    assert result["achieved_level"]["level_id"] == "l1"
    assert result["score"] == pytest.approx(by_id(result)["l1"]["score"])


def test_skill_threshold_blocks_approval_of_an_achieved_level():
    result = evaluate_skill(three_level_skill(threshold=85.0), user(streak=5))
    assert result["achieved_level"]["level_id"] == "l2"
    assert result["score"] == pytest.approx(80.0)  # achieved level's score, below the skill threshold
    assert result["meets_skill_threshold"] is False and result["approved"] is False


def test_no_level_passed_uses_lowest_evaluable_level_score_and_is_not_approved():
    result = evaluate_skill(three_level_skill(threshold=0.0), user(pose_motion=syn.right_arm_wave, streak=0))
    assert result["achieved_level"] is None
    assert result["score"] == by_id(result)["l1"]["score"]
    assert result["score"] < 60
    assert result["meets_skill_threshold"] is True  # score >= 0
    assert result["approved"] is False  # never approved without an achieved level


def test_level_without_criteria_is_one_implicit_reference_criterion():
    result = evaluate_skill(three_level_skill(), user())
    criteria = by_id(result)["l1"]["criteria"]
    assert len(criteria) == 1
    assert criteria[0]["key"] == "reference" and criteria[0]["weight"] == 100.0
    assert criteria[0]["metric_type"] == METRIC_REFERENCE_REPLICATION
    assert by_id(result)["l1"]["score"] == criteria[0]["score"]


def test_missing_reference_makes_criterion_and_level_not_evaluable():
    skill = SkillSpec("s", "Hab", 50.0, (
        LevelSpec("a", 1, "Uno", 50.0, (), reference=None),
        LevelSpec("b", 2, "Dos", 50.0, (CriterionSpec("k", "Ref", 100.0, METRIC_REFERENCE_REPLICATION),)),
    ))
    result = evaluate_skill(skill, user())
    assert_shape(result)
    for level in result["levels"]:
        assert level["evaluable"] is False and level["score"] is None and level["passed"] is False
        assert level["not_evaluable_reason"] == "El nivel no tiene un video de referencia cargado."
        assert level["criteria"][0]["evaluable"] is False and level["criteria"][0]["score"] is None
    assert result["achieved_level"] is None and result["score"] == 0.0 and result["approved"] is False


def test_criterion_reference_overrides_level_reference():
    skill = SkillSpec("s", "Hab", 50.0, (
        LevelSpec("a", 1, "Uno", 50.0, (CriterionSpec("k", "Ref", 100.0, METRIC_REFERENCE_REPLICATION),),
                  reference=ref(SQUAT), criterion_references={"k": ref(JACK)}),
    ))
    assert evaluate_skill(skill, user(pose_motion=syn.jumping_jack))["levels"][0]["score"] >= 95
    assert evaluate_skill(skill, user(pose_motion=syn.squat))["levels"][0]["score"] < 40


def test_target_level_restricts_evaluation():
    result = evaluate_skill(three_level_skill(), user(), target_level_id="l1")
    assert [lv["level_id"] for lv in result["levels"]] == ["l1"]
    assert result["target_level_id"] == "l1"
    assert result["achieved_level"]["level_id"] == "l1"

    missing = evaluate_skill(three_level_skill(), user(), target_level_id="nope")
    assert missing["levels"] == [] and missing["score"] == 0.0 and missing["approved"] is False
    assert "El nivel solicitado no está configurado en esta habilidad." in missing["notes"]


def test_pose_model_missing_marks_reference_criteria_not_evaluable():
    analysis = syn.analysis(None, ball=ball(10))
    analysis["notes"] = ["El modelo de pose no está instalado; no se pudo analizar el movimiento."]
    result = evaluate_skill(three_level_skill(), analysis)
    l2 = by_id(result)["l2"]
    crit = {c["key"]: c for c in l2["criteria"]}
    assert crit["c-ref"]["evaluable"] is False
    assert crit["c-ref"]["note"] == "El modelo de pose no está disponible; no se pudo comparar con la referencia."
    assert crit["c-ball"]["evaluable"] is True and crit["c-ball"]["score"] == 100.0
    assert l2["evaluable"] is False and l2["passed"] is False
    assert result["achieved_level"] is None and result["approved"] is False
    assert analysis["notes"][0] in result["notes"]


def test_unreadable_analysis_scores_zero_with_note():
    result = evaluate_skill(three_level_skill(threshold=0.0), {"readable": False, "notes": []})
    assert_shape(result)
    assert result["analysis_complete"] is False
    assert result["score"] == 0.0 and result["achieved_level"] is None and result["approved"] is False
    assert "No se pudo leer el video (formato no soportado o archivo dañado)." in result["notes"]


def test_nobody_visible_scores_zero_with_note():
    pose = syn.signature(syn.squat, seconds=6, missing_every=1)
    assert pose["detected_ratio"] == 0.0
    result = evaluate_skill(three_level_skill(), syn.analysis(pose, ball=ball(0, detected=False)))
    l1 = by_id(result)["l1"]
    assert l1["evaluable"] is True and l1["score"] == 0.0 and l1["passed"] is False
    assert l1["criteria"][0]["note"] == (
        "No se detectó a la persona en suficientes fotogramas para comparar el movimiento."
    )
    ball_crit = {c["key"]: c for c in by_id(result)["l2"]["criteria"]}["c-ball"]
    assert ball_crit["score"] == 0.0 and ball_crit["note"] == "No se detectó balón en el video."
    assert result["approved"] is False and result["pose_detected_ratio"] == 0.0


def test_ball_criterion_capped_at_100_and_requires_ball_analysis():
    result = evaluate_skill(three_level_skill(), user(streak=25))
    assert {c["key"]: c for c in by_id(result)["l2"]["criteria"]}["c-ball"]["score"] == 100.0
    no_ball = syn.analysis(syn.signature(syn.squat, seconds=6, seed=9))
    crit = {c["key"]: c for c in by_id(evaluate_skill(three_level_skill(), no_ball))["l2"]["criteria"]}["c-ball"]
    assert crit["evaluable"] is False and crit["note"] == "El video no se analizó para detectar el balón."


def test_static_user_never_passes_a_moving_reference():
    result = evaluate_skill(three_level_skill(threshold=0.0), user(pose_motion=syn.static, streak=0))
    assert by_id(result)["l1"]["score"] < 20
    assert result["achieved_level"] is None and result["approved"] is False


def test_detail_reports_distance_mirror_coverage():
    result = evaluate_skill(three_level_skill(), user(pose_motion=syn.mirrored(syn.squat)))
    detail = by_id(result)["l1"]["criteria"][0]["detail"]
    assert {"distance_deg", "mirrored", "coverage", "motion_ratio", "tolerance"} <= set(detail)
    assert detail["tolerance"] == {"d_full": 17.0, "d_zero": 28.0, "source": "default"}
