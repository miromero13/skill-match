"""`evaluate_skill`: measurements + skill configuration (+ optional calibration) -> Validation result.

Implements the Rules of odd/tasks/skill-validation-engine.md exactly. Never raises and never invents a
pass: anything that cannot be measured is either score 0 (the user's video) or ``evaluable: false``
(missing reference / model) with a Spanish explanation.
"""
from __future__ import annotations

import logging
import math
from typing import Any

from app.skill_validation import similarity
from app.skill_validation.analysis import (
    BALL_FAILED,
    NOTE_UNREADABLE,
    POSE_FAILED,
    POSE_MODEL_UNAVAILABLE,
    POSE_NOT_REQUESTED,
    POSE_OK,
)
from app.skill_validation.contract import (
    ENGINE_VERSION,
    METRIC_BALL_TOUCH_STREAK,
    METRIC_REFERENCE_REPLICATION,
    CriterionSpec,
    LevelSpec,
    SkillSpec,
)

logger = logging.getLogger("skillmatch.skill_validation.evaluation")

IMPLICIT_CRITERION_KEY = "reference"
IMPLICIT_CRITERION_NAME = "Replicar el video de referencia"

REASON_NO_REFERENCE = "El nivel no tiene un video de referencia cargado."
REASON_REFERENCE_UNUSABLE = (
    "El video de referencia no tiene una pose utilizable (no se detectó a la persona o falta su análisis)."
)
REASON_POSE_MODEL = "El modelo de pose no está disponible; no se pudo comparar con la referencia."
REASON_POSE_NOT_ANALYZED = "El video no se analizó con pose; no se pudo comparar con la referencia."
REASON_POSE_FAILED = "Falló el análisis de pose del video; no se pudo comparar con la referencia."
REASON_BALL_NOT_ANALYZED = "El video no se analizó para detectar el balón."
REASON_BALL_FAILED = "Falló el análisis del balón; no se pudo medir la racha de toques."
REASON_BAD_TARGET = "El criterio no tiene un objetivo de toques válido (debe ser mayor que 0)."
REASON_UNKNOWN_METRIC = "Tipo de métrica no soportado: {code}."

NOTE_CRIT_UNREADABLE = "No se pudo leer el video del usuario."
NOTE_CRIT_NO_PERSON = "No se detectó a la persona en suficientes fotogramas para comparar el movimiento."
NOTE_CRIT_STATIC = "El movimiento del usuario es mucho menor que el de la referencia."
NOTE_CRIT_PARTIAL = "El usuario solo replicó una parte de la referencia."
NOTE_CRIT_NO_BALL = "No se detectó balón en el video."
NOTE_NO_LEVELS = "La habilidad no tiene niveles configurados."
NOTE_TARGET_MISSING = "El nivel solicitado no está configurado en esta habilidad."
NOTE_INTERNAL = "Ocurrió un fallo interno al evaluar el video; no se otorgó aprobación."
NOTE_STALE_REFERENCE = (
    "La referencia del nivel «{name}» cambió después del entrenamiento; se usaron tolerancias por defecto. "
    "Vuelve a entrenar el modelo."
)


def _num(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if math.isfinite(out) else default


def _round(value: float | None, digits: int = 2) -> float | None:
    if value is None or not math.isfinite(value):
        return None
    return round(float(value), digits)


def level_criteria(level: LevelSpec) -> tuple[CriterionSpec, ...]:
    """A level without criteria is one implicit REFERENCE_REPLICATION criterion (weight 100)."""
    criteria = tuple(c for c in (getattr(level, "criteria", None) or ()) if isinstance(c, CriterionSpec))
    if criteria:
        return criteria
    return (CriterionSpec(IMPLICIT_CRITERION_KEY, IMPLICIT_CRITERION_NAME, 100.0, METRIC_REFERENCE_REPLICATION),)


def criterion_reference(level: LevelSpec, criterion: CriterionSpec) -> tuple[dict | None, bool]:
    """(reference analysis, is_own_criterion_reference)."""
    refs = getattr(level, "criterion_references", None)
    if isinstance(refs, dict) or hasattr(refs, "get"):
        try:
            own = refs.get(criterion.key)
        except Exception:
            own = None
        if isinstance(own, dict):
            return own, True
    ref = getattr(level, "reference", None)
    return (ref if isinstance(ref, dict) else None), False


def user_pose_problem(analysis: Any) -> str | None:
    """Reason why the user's pose cannot be compared for a reason that is not the user's fault."""
    if not isinstance(analysis, dict) or analysis.get("readable") is not True:
        return None  # unreadable: the user's video scores 0, handled by the caller
    if isinstance(analysis.get("pose"), dict):
        return None
    status = analysis.get("pose_status")
    if status == POSE_MODEL_UNAVAILABLE:
        return REASON_POSE_MODEL
    if status == POSE_FAILED:
        return REASON_POSE_FAILED
    if status == POSE_NOT_REQUESTED:
        return REASON_POSE_NOT_ANALYZED
    return REASON_POSE_NOT_ANALYZED if status != POSE_OK else None


class Comparator:
    """Caches reference parsing and comparisons against one user analysis."""

    def __init__(self, analysis: Any) -> None:
        pose = analysis.get("pose") if isinstance(analysis, dict) else None
        self.user = similarity.parse_pose(pose)
        self._cache: dict[str, similarity.Comparison | None] = {}

    def compare(self, reference: dict | None) -> similarity.Comparison | None:
        """None when the reference itself has no usable pose."""
        if not isinstance(reference, dict):
            return None
        pose = reference.get("pose")
        key = similarity.pose_fingerprint(pose) or f"id:{id(reference)}"
        if key in self._cache:
            return self._cache[key]
        ref_seq = similarity.parse_pose(pose)
        if ref_seq is None or len(ref_seq.angles) < similarity.MIN_POSE_FRAMES:
            result = None
        elif self.user is None:
            result = similarity.Comparison(ok=False, reason="user", reference_frames=len(ref_seq.angles))
        else:
            result = similarity.compare_sequences(ref_seq, self.user)
            if not result.ok and result.reason == "reference":
                result = None
        self._cache[key] = result
        return result


def default_tolerance(calibration: Any) -> tuple[float, float]:
    if isinstance(calibration, dict):
        tol = calibration.get("default_tolerance")
        if isinstance(tol, dict):
            clean = similarity.sanitize_tolerance(tol.get("d_full"), tol.get("d_zero"))
            if clean:
                return clean
    return similarity.DEFAULT_D_FULL, similarity.DEFAULT_D_ZERO


def resolve_tolerance(
    calibration: Any, level: LevelSpec, criterion: CriterionSpec, reference: dict, own_reference: bool,
    stale_levels: set[str],
) -> tuple[tuple[float, float], str]:
    fallback = default_tolerance(calibration)
    if not isinstance(calibration, dict):
        return fallback, "default"
    levels = calibration.get("levels")
    entry = levels.get(str(level.level_id)) if isinstance(levels, dict) else None
    if not isinstance(entry, dict):
        return fallback, "default"
    fingerprint = similarity.pose_fingerprint(reference.get("pose"))
    criteria = entry.get("criteria")
    crit_entry = criteria.get(criterion.key) if isinstance(criteria, dict) else None
    if isinstance(crit_entry, dict) and isinstance(crit_entry.get("tolerance"), dict):
        if crit_entry.get("reference_fingerprint") == fingerprint:
            tol = similarity.sanitize_tolerance(crit_entry["tolerance"].get("d_full"), crit_entry["tolerance"].get("d_zero"))
            if tol:
                return tol, "criterion"
        else:
            stale_levels.add(str(level.level_id))
    if not own_reference and isinstance(entry.get("tolerance"), dict):
        if entry.get("reference_fingerprint") == fingerprint:
            tol = similarity.sanitize_tolerance(entry["tolerance"].get("d_full"), entry["tolerance"].get("d_zero"))
            if tol:
                return tol, "level"
        else:
            stale_levels.add(str(level.level_id))
    return fallback, "default"


def _criterion_result(criterion: CriterionSpec) -> dict[str, Any]:
    return {
        "key": str(criterion.key),
        "name": str(criterion.name),
        "weight": _round(_num(criterion.weight)),
        "metric_type": str(criterion.metric_type),
        "evaluable": True,
        "score": 0.0,
        "detail": {},
        "note": None,
    }


def _not_evaluable(out: dict[str, Any], reason: str) -> dict[str, Any]:
    out.update(evaluable=False, score=None, note=reason)
    return out


def evaluate_reference(
    level: LevelSpec, criterion: CriterionSpec, analysis: Any, comparator: Comparator, calibration: Any,
    stale_levels: set[str],
) -> dict[str, Any]:
    out = _criterion_result(criterion)
    reference, own = criterion_reference(level, criterion)
    if reference is None:
        return _not_evaluable(out, REASON_NO_REFERENCE)
    ref_seq_ok = similarity.parse_pose(reference.get("pose"))
    if ref_seq_ok is None or len(ref_seq_ok.angles) < similarity.MIN_POSE_FRAMES:
        return _not_evaluable(out, REASON_REFERENCE_UNUSABLE)
    if not isinstance(analysis, dict) or analysis.get("readable") is not True:
        out["note"] = NOTE_CRIT_UNREADABLE
        return out
    problem = user_pose_problem(analysis)
    if problem:
        return _not_evaluable(out, problem)
    comparison = comparator.compare(reference)
    if comparison is None:
        return _not_evaluable(out, REASON_REFERENCE_UNUSABLE)
    (d_full, d_zero), source = resolve_tolerance(calibration, level, criterion, reference, own, stale_levels)
    detail = comparison.detail()
    detail["tolerance"] = {"d_full": round(d_full, 2), "d_zero": round(d_zero, 2), "source": source}
    out["detail"] = detail
    if not comparison.ok:
        out["note"] = NOTE_CRIT_NO_PERSON
        return out
    out["score"] = _round(comparison.score(d_full, d_zero))
    if comparison.motion_factor < 1.0:
        out["note"] = NOTE_CRIT_STATIC
    elif comparison.coverage_factor < 1.0:
        out["note"] = NOTE_CRIT_PARTIAL
    return out


def evaluate_ball(criterion: CriterionSpec, analysis: Any) -> dict[str, Any]:
    out = _criterion_result(criterion)
    target = _num(criterion.target, 0.0)
    if target <= 0:
        return _not_evaluable(out, REASON_BAD_TARGET)
    if not isinstance(analysis, dict) or analysis.get("readable") is not True:
        out["note"] = NOTE_CRIT_UNREADABLE
        return out
    ball = analysis.get("ball")
    if not isinstance(ball, dict):
        status = analysis.get("ball_status")
        return _not_evaluable(out, REASON_BALL_FAILED if status == BALL_FAILED else REASON_BALL_NOT_ANALYZED)
    max_streak = max(0, int(_num(ball.get("max_streak"))))
    detected = bool(ball.get("ball_detected"))
    out["detail"] = {
        "ball_detected": detected,
        "max_streak": max_streak,
        "total_touches": max(0, int(_num(ball.get("total_touches")))),
        "target": _round(target),
    }
    if not detected:
        out["note"] = NOTE_CRIT_NO_BALL
        return out
    out["score"] = _round(min(100.0, 100.0 * max_streak / target))
    return out


def evaluate_criterion(
    level: LevelSpec, criterion: CriterionSpec, analysis: Any, comparator: Comparator, calibration: Any,
    stale_levels: set[str],
) -> dict[str, Any]:
    metric = str(criterion.metric_type or METRIC_REFERENCE_REPLICATION)
    if metric == METRIC_REFERENCE_REPLICATION:
        return evaluate_reference(level, criterion, analysis, comparator, calibration, stale_levels)
    if metric == METRIC_BALL_TOUCH_STREAK:
        return evaluate_ball(criterion, analysis)
    return _not_evaluable(_criterion_result(criterion), REASON_UNKNOWN_METRIC.format(code=metric))


def evaluate_level(
    level: LevelSpec, analysis: Any, comparator: Comparator, calibration: Any, stale_levels: set[str]
) -> dict[str, Any]:
    criteria = [
        evaluate_criterion(level, c, analysis, comparator, calibration, stale_levels) for c in level_criteria(level)
    ]
    evaluable = all(c["evaluable"] for c in criteria)
    min_score = _num(level.min_score)
    score = None
    if evaluable:
        score = sum(_num(c["weight"]) * _num(c["score"]) for c in criteria) / 100.0
    reasons: list[str] = []
    for c in criteria:
        if not c["evaluable"] and c["note"] and c["note"] not in reasons:
            reasons.append(c["note"])
    return {
        "level_id": str(level.level_id),
        "level_number": int(_num(level.level_number)),
        "name": str(level.name),
        "min_score": _round(min_score),
        "evaluable": evaluable,
        "score": _round(score) if score is not None else None,
        "passed": bool(evaluable and score is not None and score >= min_score),
        "not_evaluable_reason": " ".join(reasons) if reasons else None,
        "criteria": criteria,
    }


def _base_result(skill: Any, analysis: Any, calibration: Any, target_level_id: Any) -> dict[str, Any]:
    model_version = None
    if isinstance(calibration, dict):
        raw = calibration.get("model_version", calibration.get("version"))
        model_version = str(raw) if raw is not None else None
    pose = analysis.get("pose") if isinstance(analysis, dict) else None
    ratio = pose.get("detected_ratio") if isinstance(pose, dict) else None
    return {
        "skill_id": str(getattr(skill, "skill_id", "") or ""),
        "skill_name": str(getattr(skill, "name", "") or ""),
        "engine_version": ENGINE_VERSION,
        "model_version": model_version,
        "analysis_complete": bool(isinstance(analysis, dict) and analysis.get("readable") is True),
        "target_level_id": str(target_level_id) if target_level_id is not None else None,
        "achieved_level": None,
        "score": 0.0,
        "min_approval_threshold": _round(_num(getattr(skill, "min_approval_threshold", 0.0))),
        "meets_skill_threshold": False,
        "approved": False,
        "model_level_estimate": None,
        "levels": [],
        "pose_detected_ratio": _round(_num(ratio), 3) if ratio is not None else None,
        "duration_seconds": _round(_num(analysis.get("duration_seconds"))) if isinstance(analysis, dict) else 0.0,
        "notes": [],
    }


def evaluate_skill(
    skill: SkillSpec, analysis: dict, calibration: dict | None = None, target_level_id: str | None = None
) -> dict:
    """Validation result (see the feature document). Never raises."""
    try:
        return _evaluate(skill, analysis, calibration, target_level_id)
    except Exception:
        logger.exception("Unexpected failure evaluating a skill video")
        try:
            result = _base_result(skill, analysis, calibration, target_level_id)
        except Exception:
            result = _base_result(None, None, None, None)
        result["analysis_complete"] = False
        result["notes"] = [NOTE_INTERNAL]
        return result


def _evaluate(skill: Any, analysis: Any, calibration: Any, target_level_id: Any) -> dict[str, Any]:
    from app.skill_validation.calibration import estimate_level

    result = _base_result(skill, analysis, calibration, target_level_id)
    notes: list[str] = result["notes"]
    if isinstance(analysis, dict) and isinstance(analysis.get("notes"), list):
        notes.extend(str(n) for n in analysis["notes"] if isinstance(n, str))
    if not result["analysis_complete"] and NOTE_UNREADABLE not in notes:
        notes.append(NOTE_UNREADABLE)

    levels = [lv for lv in (getattr(skill, "levels", None) or ()) if isinstance(lv, LevelSpec)]
    levels.sort(key=lambda lv: _num(lv.level_number))
    if not levels:
        notes.append(NOTE_NO_LEVELS)
    if target_level_id is not None:
        levels = [lv for lv in levels if str(lv.level_id) == str(target_level_id)]
        if not levels and NOTE_NO_LEVELS not in notes:
            notes.append(NOTE_TARGET_MISSING)

    comparator = Comparator(analysis)
    stale: set[str] = set()
    level_results = [evaluate_level(lv, analysis, comparator, calibration, stale) for lv in levels]
    result["levels"] = level_results
    for lv in levels:
        if str(lv.level_id) in stale:
            notes.append(NOTE_STALE_REFERENCE.format(name=lv.name))

    passed = [lv for lv in level_results if lv["passed"]]
    achieved = max(passed, key=lambda lv: lv["level_number"]) if passed else None
    if achieved is not None:
        score = achieved["score"]
        result["achieved_level"] = {
            "level_id": achieved["level_id"], "level_number": achieved["level_number"], "name": achieved["name"],
        }
    else:
        evaluable = [lv for lv in level_results if lv["evaluable"]]
        score = min(evaluable, key=lambda lv: lv["level_number"])["score"] if evaluable else 0.0
    score = _num(score)
    threshold = _num(getattr(skill, "min_approval_threshold", 0.0))
    result["score"] = _round(score)
    result["meets_skill_threshold"] = bool(score >= threshold)
    result["approved"] = bool(achieved is not None and score >= threshold)

    if result["analysis_complete"]:
        try:
            result["model_level_estimate"] = estimate_level(skill, analysis, calibration, comparator)
        except Exception:
            logger.exception("Level estimate failed")
            result["model_level_estimate"] = None
    return result
