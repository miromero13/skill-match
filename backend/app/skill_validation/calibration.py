"""Few-shot "training" of a skill validator: per-level/criterion tolerances + level prototypes.

No deep training: the pretrained vision models already turned every video into measurements. From a few
labeled videos per level this module (1) fits how tolerant the reference comparison must be so genuine
examples of a level score well while lower-level examples do not pass it, bounded around the defaults,
and (2) stores one prototype per level over a small feature vector (similarity to every level reference
+ ball streak) for a nearest-prototype level estimate with a confidence. Works with zero samples.

People are not perfect and do not all film from the same angle (S6), so a level/criterion tolerance may
always be loosened, but it is only tightened below the defaults with ``MIN_SAMPLES_TO_TIGHTEN`` genuine
examples, and never so far that one of those genuine examples fails its own level when that is avoidable.
"""
from __future__ import annotations

import logging
import math
from typing import Any

import numpy as np

from app.skill_validation import similarity
from app.skill_validation.contract import (
    ENGINE_VERSION,
    METRIC_BALL_TOUCH_STREAK,
    METRIC_REFERENCE_REPLICATION,
    LabeledSample,
    LevelSpec,
    SkillSpec,
)
from app.skill_validation.evaluation import Comparator, criterion_reference, level_criteria

logger = logging.getLogger("skillmatch.skill_validation.calibration")

RECOMMENDED_SAMPLES_PER_LEVEL = 3
MIN_SAMPLES_TO_TIGHTEN = 5  # genuine examples a level/criterion needs before its tolerance may go below the default
FIT_D_FULL_RANGE = (0.6, 2.0)  # multipliers of the default
FIT_D_ZERO_RANGE = (0.7, 1.6)
FIT_GRID = 13
FIT_MARGIN = 15.0
FIT_REGULARIZATION = 0.15
ESTIMATOR_TEMPERATURE = 0.1

NOTE_NO_SAMPLES = "No hay videos de entrenamiento; se usan las tolerancias por defecto."
NOTE_RECOMMENDED = "Se recomienda al menos 3 videos por nivel."
NOTE_FEW_SAMPLES = "El nivel «{name}» tiene {n} video(s) de entrenamiento."
NOTE_UNKNOWN_LEVEL = "Se ignoraron {n} video(s) de niveles que no existen en la habilidad."
NOTE_NO_POSE = "{n} video(s) de entrenamiento no tienen una pose utilizable y no ajustaron tolerancias."
NOTE_NO_LEVEL_REFERENCE = "El nivel «{name}» no tiene video de referencia; sus videos no ajustaron tolerancias."
NOTE_ESTIMATOR_NEEDS_LEVELS = "Se necesitan videos de al menos 2 niveles para estimar el nivel del usuario."
NOTE_LOO_NEEDS_SAMPLES = "Se necesitan al menos 2 videos en algún nivel para medir la precisión del modelo."
NOTE_NO_TIGHTEN = (
    f"Con menos de {MIN_SAMPLES_TO_TIGHTEN} videos por nivel la tolerancia no se reduce; solo puede ampliarse."
)
NOTE_INTERNAL = "Ocurrió un fallo interno al entrenar; se guardó una calibración por defecto."


def _tol(f: float, z: float) -> dict[str, float]:
    return {"d_full": round(float(f), 2), "d_zero": round(float(z), 2)}


def _default_calibration(skill_id: str) -> dict[str, Any]:
    return {
        "engine_version": ENGINE_VERSION,
        "kind": "skill_validator",
        "skill_id": skill_id,
        "default_tolerance": _tol(similarity.DEFAULT_D_FULL, similarity.DEFAULT_D_ZERO),
        "levels": {},
        "estimator": None,
    }


def _grid(default: float, bounds: tuple[float, float]) -> list[float]:
    values = {float(v) for v in np.geomspace(default * bounds[0], default * bounds[1], FIT_GRID)}
    values.add(float(default))
    return sorted(values)


def fit_tolerance(
    positives: list[similarity.Comparison], negatives: list[similarity.Comparison], min_score: float,
    default: tuple[float, float], *, allow_tighten: bool = True,
) -> tuple[float, float]:
    """Bounded grid search: positives above ``min_score``, negatives below, close to the default.

    Without ``allow_tighten`` no candidate is below the default. Candidates that keep every positive at or
    above ``min_score`` win over any that fails one; only when none exists does the plain objective decide.
    """
    f0, z0 = default
    best: tuple[bool, float, float, float] | None = None
    for f in _grid(f0, FIT_D_FULL_RANGE):
        for z in _grid(z0, FIT_D_ZERO_RANGE):
            clean = similarity.sanitize_tolerance(round(f, 2), round(z, 2))
            if clean is None:
                continue
            f_c, z_c = clean
            if not allow_tighten and (f_c < f0 - 1e-9 or z_c < z0 - 1e-9):
                continue
            scores = [c.score(f_c, z_c) for c in positives]
            all_pass = bool(scores) and all(score >= min_score for score in scores)
            pos = np.mean([np.clip((score - min_score) / FIT_MARGIN, -1, 1) for score in scores])
            neg = (np.mean([np.clip((min_score - c.score(f_c, z_c)) / FIT_MARGIN, -1, 1) for c in negatives])
                   if negatives else 0.0)
            reg = FIT_REGULARIZATION * (abs(math.log(f_c / f0)) + abs(math.log(z_c / z0)))
            objective = float(pos + neg - reg)
            if (best is None or (all_pass and not best[0])
                    or (all_pass == best[0] and objective > best[1] + 1e-9)):
                best = (all_pass, objective, f_c, z_c)
    if best is None:
        return default
    return best[2], best[3]


def _fit(
    positives: list[similarity.Comparison], negatives: list[similarity.Comparison], min_score: float,
    default: tuple[float, float],
) -> tuple[float, float, dict[str, Any]]:
    """Fit with the sample-count rule; ``info`` says whether tightening was allowed or skipped."""
    allowed = len(positives) >= MIN_SAMPLES_TO_TIGHTEN
    f, z = fit_tolerance(positives, negatives, min_score, default, allow_tighten=allowed)
    skipped = False
    if not allowed:
        f_free, z_free = fit_tolerance(positives, negatives, min_score, default, allow_tighten=True)
        skipped = f_free < default[0] - 1e-9 or z_free < default[1] - 1e-9
    info = {
        "tightening_allowed": allowed,
        "tightening_skipped": skipped,
        "positives_pass": bool(positives) and all(c.score(f, z) >= min_score for c in positives),
    }
    return f, z, info


def _usable_reference(reference: dict | None) -> bool:
    if not isinstance(reference, dict):
        return False
    seq = similarity.parse_pose(reference.get("pose"))
    return seq is not None and len(seq.angles) >= similarity.MIN_POSE_FRAMES


def _ball_target(skill: SkillSpec) -> float | None:
    targets = []
    for level in skill.levels:
        for c in level_criteria(level):
            if c.metric_type == METRIC_BALL_TOUCH_STREAK:
                try:
                    t = float(c.target) if c.target is not None else 0.0
                except (TypeError, ValueError):
                    t = 0.0
                if math.isfinite(t) and t > 0:
                    targets.append(t)
    return max(targets) if targets else None


def _feature_spec(skill: SkillSpec) -> dict[str, Any] | None:
    features: list[str] = []
    fingerprints: list[str | None] = []
    for level in sorted(skill.levels, key=lambda lv: lv.level_number):
        if _usable_reference(level.reference):
            features.append(f"ref:{level.level_id}")
            fingerprints.append(similarity.pose_fingerprint(level.reference.get("pose")))
    target = _ball_target(skill)
    if target is not None:
        features.append("ball_streak")
        fingerprints.append(None)
    if not features:
        return None
    return {"features": features, "fingerprints": fingerprints, "ball_target": target}


def _feature_vector(
    skill: SkillSpec, spec: dict[str, Any], analysis: Any, comparator: Comparator
) -> list[float] | None:
    """Similarity (default tolerance, 0-1) to each level reference + ball streak ratio; None if unavailable."""
    if not isinstance(analysis, dict) or analysis.get("readable") is not True:
        return None
    levels = {f"ref:{lv.level_id}": lv for lv in skill.levels}
    vector: list[float] = []
    for name, fingerprint in zip(spec["features"], spec["fingerprints"]):
        if name == "ball_streak":
            ball = analysis.get("ball")
            target = spec.get("ball_target")
            if not isinstance(ball, dict) or not target:
                return None
            streak = float(ball.get("max_streak") or 0) if ball.get("ball_detected") else 0.0
            vector.append(min(1.0, max(0.0, streak / float(target))))
            continue
        level = levels.get(name)
        if level is None or not isinstance(level.reference, dict):
            return None
        if similarity.pose_fingerprint(level.reference.get("pose")) != fingerprint:
            return None
        if comparator.user is None:
            return None
        comparison = comparator.compare(level.reference)
        if comparison is None:
            return None
        vector.append(comparison.score(similarity.DEFAULT_D_FULL, similarity.DEFAULT_D_ZERO) / 100.0)
    return vector


def _predict(vector: list[float], prototypes: dict[str, list[float]]) -> tuple[str, float] | None:
    if len(prototypes) < 2:
        return None
    v = np.asarray(vector, dtype=np.float64)
    ids = list(prototypes)
    dists = np.array([np.linalg.norm(v - np.asarray(prototypes[i])) / math.sqrt(len(v)) for i in ids])
    logits = -dists / ESTIMATOR_TEMPERATURE
    probs = np.exp(logits - logits.max())
    probs /= probs.sum()
    k = int(np.argmax(probs))
    return ids[k], float(probs[k])


def estimate_level(skill: Any, analysis: Any, calibration: Any, comparator: Comparator | None = None) -> dict | None:
    """Nearest-prototype level estimate from a calibration; None when it cannot be computed honestly."""
    if not isinstance(calibration, dict) or not isinstance(skill, SkillSpec):
        return None
    estimator = calibration.get("estimator")
    if not isinstance(estimator, dict):
        return None
    features, fingerprints = estimator.get("features"), estimator.get("fingerprints")
    prototypes = estimator.get("prototypes")
    if not (isinstance(features, list) and isinstance(fingerprints, list) and isinstance(prototypes, dict)):
        return None
    if len(features) != len(fingerprints) or not features:
        return None
    levels = {str(lv.level_id): lv for lv in skill.levels}
    clean: dict[str, list[float]] = {}
    for level_id, proto in prototypes.items():
        if str(level_id) not in levels or not isinstance(proto, list) or len(proto) != len(features):
            continue
        try:
            values = [float(x) for x in proto]
        except (TypeError, ValueError):
            continue
        if all(math.isfinite(x) for x in values):
            clean[str(level_id)] = values
    spec = {"features": features, "fingerprints": fingerprints, "ball_target": estimator.get("ball_target")}
    vector = _feature_vector(skill, spec, analysis, comparator or Comparator(analysis))
    if vector is None:
        return None
    prediction = _predict(vector, clean)
    if prediction is None:
        return None
    level_id, confidence = prediction
    return {"level_id": level_id, "name": str(levels[level_id].name), "confidence": round(confidence, 2)}


def calibrate_skill(skill: SkillSpec, samples: list[LabeledSample]) -> dict:
    """Fit tolerances and level prototypes from labeled analyses. Never raises; valid with zero samples."""
    skill_id = str(getattr(skill, "skill_id", "") or "")
    try:
        return _calibrate(skill, list(samples or []))
    except Exception:
        logger.exception("Unexpected failure calibrating a skill validator")
        return {
            "calibration": _default_calibration(skill_id),
            "metrics": {"samples_per_level": {}, "loo_level_accuracy": None},
            "notes": [NOTE_INTERNAL],
        }


def _calibrate(skill: SkillSpec, samples: list[Any]) -> dict[str, Any]:
    skill_id = str(skill.skill_id)
    calibration = _default_calibration(skill_id)
    default = (similarity.DEFAULT_D_FULL, similarity.DEFAULT_D_ZERO)
    notes: list[str] = []
    levels = sorted([lv for lv in skill.levels if isinstance(lv, LevelSpec)], key=lambda lv: lv.level_number)
    by_id = {str(lv.level_id): lv for lv in levels}

    per_level: dict[str, list[LabeledSample]] = {str(lv.level_id): [] for lv in levels}
    samples_per_criterion: dict[str, int] = {}
    unknown = 0
    for sample in samples:
        if not isinstance(sample, LabeledSample) or str(sample.level_id) not in by_id:
            unknown += 1
            continue
        per_level[str(sample.level_id)].append(sample)
        if sample.criterion_key:
            samples_per_criterion[str(sample.criterion_key)] = samples_per_criterion.get(str(sample.criterion_key), 0) + 1

    comparators: dict[int, Comparator] = {}

    def comparator_for(sample: LabeledSample) -> Comparator:
        key = id(sample)
        if key not in comparators:
            comparators[key] = Comparator(sample.analysis)
        return comparators[key]

    def comparisons(reference: dict, group: list[LabeledSample]) -> list[similarity.Comparison]:
        out = []
        for s in group:
            c = comparator_for(s)
            if c.user is None:
                continue
            comp = c.compare(reference)
            if comp is not None:
                out.append(comp)
        return out

    no_pose = sum(1 for group in per_level.values() for s in group if comparator_for(s).user is None)
    metrics_tol: dict[str, Any] = {}
    metrics_fit: dict[str, Any] = {}
    tightening_skipped = False
    for level in levels:
        lid = str(level.level_id)
        group = per_level[lid]
        lower = [s for lv in levels if lv.level_number < level.level_number for s in per_level[str(lv.level_id)]]
        entry: dict[str, Any] = {
            "reference_fingerprint": similarity.pose_fingerprint((level.reference or {}).get("pose"))
            if isinstance(level.reference, dict) else None,
            "tolerance": None,
            "samples": len(group),
            "criteria": {},
        }
        if group and not _usable_reference(level.reference) and any(
            c.metric_type == METRIC_REFERENCE_REPLICATION and not criterion_reference(level, c)[1]
            for c in level_criteria(level)
        ):
            notes.append(NOTE_NO_LEVEL_REFERENCE.format(name=level.name))
        if group and _usable_reference(level.reference):
            pos = comparisons(level.reference, group)
            neg = comparisons(level.reference, lower)
            if pos:
                f, z, info = _fit(pos, neg, float(level.min_score), default)
                tightening_skipped = tightening_skipped or info["tightening_skipped"]
                entry["tolerance"] = _tol(f, z)
                metrics_tol[lid] = {**_tol(f, z), "source": "level", "tightening_allowed": info["tightening_allowed"]}
                metrics_fit[lid] = {
                    "positives": len(pos),
                    "negatives": len(neg),
                    "mean_distance_deg": round(float(np.mean([c.distance for c in pos])), 2),
                    "mean_score_default": round(float(np.mean([c.score(*default) for c in pos])), 2),
                    "mean_score_calibrated": round(float(np.mean([c.score(f, z) for c in pos])), 2),
                    **info,
                }
        for criterion in level_criteria(level):
            if criterion.metric_type != METRIC_REFERENCE_REPLICATION:
                continue
            reference, own = criterion_reference(level, criterion)
            labeled = [s for s in group if s.criterion_key == criterion.key]
            if not _usable_reference(reference) or not (own or labeled):
                continue
            crit_group = [s for s in group if s.criterion_key in (None, criterion.key)] if own else labeled
            pos = comparisons(reference, crit_group)
            if not pos:
                continue
            neg = comparisons(reference, lower)
            f, z, info = _fit(pos, neg, float(level.min_score), default)
            tightening_skipped = tightening_skipped or info["tightening_skipped"]
            entry["criteria"][str(criterion.key)] = {
                "reference_fingerprint": similarity.pose_fingerprint(reference.get("pose")),
                "tolerance": _tol(f, z),
                "samples": len(crit_group),
            }
            metrics_tol.setdefault(lid, {}).setdefault("criteria", {})[str(criterion.key)] = {
                **_tol(f, z), "tightening_allowed": info["tightening_allowed"],
            }
            metrics_fit.setdefault(lid, {}).setdefault("criteria", {})[str(criterion.key)] = {
                "positives": len(pos), "negatives": len(neg), **info,
            }
        calibration["levels"][lid] = entry

    # Level prototypes for the estimate.
    spec = _feature_spec(skill)
    exemplars: list[tuple[str, list[float]]] = []
    if spec is not None:
        for lid, group in per_level.items():
            for s in group:
                vector = _feature_vector(skill, spec, s.analysis, comparator_for(s))
                if vector is not None:
                    exemplars.append((lid, vector))
    prototypes: dict[str, list[float]] = {}
    for lid in per_level:
        vectors = [v for l, v in exemplars if l == lid]
        if vectors:
            prototypes[lid] = [round(float(x), 4) for x in np.mean(np.asarray(vectors), axis=0)]
    if spec is not None and len(prototypes) >= 2:
        calibration["estimator"] = {
            **spec,
            "prototypes": prototypes,
            "temperature": ESTIMATOR_TEMPERATURE,
        }

    loo_accuracy: float | None = None
    loo_evaluated = 0
    if len(prototypes) >= 2:
        hits = 0
        for i, (lid, vector) in enumerate(exemplars):
            rest = [(l, v) for k, (l, v) in enumerate(exemplars) if k != i]
            if not any(l == lid for l, _ in rest):
                continue
            protos = {}
            for l in {l for l, _ in rest}:
                protos[l] = list(np.mean(np.asarray([v for ll, v in rest if ll == l]), axis=0))
            prediction = _predict(vector, protos)
            loo_evaluated += 1
            hits += int(prediction is not None and prediction[0] == lid)
        loo_accuracy = round(hits / loo_evaluated, 3) if loo_evaluated else None

    total = sum(len(g) for g in per_level.values())
    if total == 0:
        notes.append(NOTE_NO_SAMPLES)
    if any(len(g) < RECOMMENDED_SAMPLES_PER_LEVEL for g in per_level.values()):
        notes.append(NOTE_RECOMMENDED)
        for level in levels:
            n = len(per_level[str(level.level_id)])
            if 0 < n < RECOMMENDED_SAMPLES_PER_LEVEL:
                notes.append(NOTE_FEW_SAMPLES.format(name=level.name, n=n))
    if tightening_skipped:
        notes.append(NOTE_NO_TIGHTEN)
    if unknown:
        notes.append(NOTE_UNKNOWN_LEVEL.format(n=unknown))
    if no_pose:
        notes.append(NOTE_NO_POSE.format(n=no_pose))
    if total and len(prototypes) < 2:
        notes.append(NOTE_ESTIMATOR_NEEDS_LEVELS)
    elif len(prototypes) >= 2 and loo_accuracy is None:
        notes.append(NOTE_LOO_NEEDS_SAMPLES)

    metrics = {
        "samples_total": total,
        "samples_per_level": {lid: len(g) for lid, g in per_level.items()},
        "samples_per_criterion": samples_per_criterion,
        "ignored_samples": unknown,
        "samples_without_pose": no_pose,
        "levels_with_samples": sum(1 for g in per_level.values() if g),
        "loo_level_accuracy": loo_accuracy,
        "loo_evaluated": loo_evaluated,
        "tolerances": metrics_tol,
        "fit": metrics_fit,
        "default_tolerance": _tol(*default),
        "min_samples_to_tighten": MIN_SAMPLES_TO_TIGHTEN,
    }
    return {"calibration": calibration, "metrics": metrics, "notes": notes}
