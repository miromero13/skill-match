from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from app.football.config import ScoringConfig, load_football_config

LEVELS: tuple[str, ...] = (
    "Principiante",
    "Intermedio",
    "Avanzado",
    "Experto",
)


@dataclass
class ScoringOutput:
    nivel: str
    probabilidades: dict[str, float]
    confianza: float
    requiere_revision: bool
    retroalimentacion: dict[str, list[str]] = field(default_factory=dict)
    version_modelo: str = "rules-v1"
    version_config: str = ""
    puntaje_1_100: float = 1.0
    puntaje_calibrado: bool = False


class LevelClassifierProtocol(Protocol):
    """Protocol for swappable level classifiers (rule-based, JSON/ONNX model)."""

    @property
    def model_version(self) -> str: ...

    def predict_proba(self, features: dict[str, Any]) -> dict[str, float]: ...


def generate_template_feedback(
    features: dict[str, Any],
    nivel: str,
) -> dict[str, list[str]]:
    """
    Deterministic pedagogical feedback built strictly from templates and numerical
    metrics (Zero Third-Party LLM API compliance).
    """
    strengths: list[str] = []
    improvements: list[str] = []

    max_streak = int(features.get("max_streak", 0))
    total_touches = int(features.get("total_touches", 0))
    regularity = float(features.get("regularity_score", 0.0))
    compliance = float(features.get("mean_challenge_compliance", 0.0))
    drops = int(features.get("drops_count", 0))
    horiz_disp = float(features.get("horizontal_displacement_diameters", 0.0))
    coherence = float(features.get("av_coherence", 0.0))

    if max_streak >= 26:
        strengths.append(
            f"Excelente continuidad de dominio con una racha máxima de {max_streak} toques seguidos."
        )
    elif max_streak >= 8:
        strengths.append(
            f"Buen control sostenido logrando una racha de {max_streak} toques sin caída."
        )
    else:
        improvements.append(
            f"Tu racha máxima fue de {max_streak} toques; practica series cortas de 10 toques controlados."
        )

    if compliance >= 0.80:
        strengths.append(
            f"Sobresaliente adaptación a las órdenes dinámicas del entrenador ({round(compliance * 100)}% de cumplimiento)."
        )
    elif compliance < 0.60:
        improvements.append(
            f"Cumplimiento de retos dinámicos en {round(compliance * 100)}%; ajusta más rápido la altura y velocidad cuando cambie la consigna."
        )

    if regularity >= 0.75:
        strengths.append(
            f"Ritmo de toque muy estable y cadencia consistente (índice de regularidad {regularity:.2f})."
        )
    else:
        improvements.append(
            "Alternaste intervalos irregulares entre toques; busca mantener una cadencia rítmica constante."
        )

    if drops == 0 and total_touches >= 5:
        strengths.append("Completaste la sesión sin interrupciones ni caídas de balón.")
    elif drops >= 2:
        improvements.append(
            f"Se registraron {drops} interrupciones de control; amortigua el impacto con el empeine para evitar caídas."
        )

    if horiz_disp <= 1.2:
        strengths.append("Mantuviste tu posición centrada con mínimo desplazamiento lateral.")
    elif horiz_disp > 2.0:
        improvements.append(
            "El balón se desplazó lateralmente varios diámetros; corrige el ángulo del pie de contacto hacia el centro."
        )

    if coherence >= 0.80 and len(strengths) < 2:
        strengths.append(
            f"Alta nitidez de impacto acústico y visual ({round(coherence * 100)}% de toques confirmados)."
        )

    if not strengths:
        strengths.append(
            f"Nivel {nivel} validado con {total_touches} toques registrados en la sesión."
        )
    if not improvements:
        improvements.append(
            "Incrementa la velocidad en los tramos rápidos manteniendo la altura por debajo de 1,5 diámetros."
        )

    return {
        "fortalezas": strengths,
        "mejoras": improvements,
    }


def _softmax(logits: list[float]) -> list[float]:
    m = max(logits)
    exps = [math.exp(x - m) for x in logits]
    s = sum(exps)
    return [e / s for e in exps]


class RuleBasedLevelClassifier:
    """
    Initial calibrated ordinal rule classifier configured via `config.yaml`.
    """

    def __init__(self, config: ScoringConfig | None = None) -> None:
        self.cfg = config or load_football_config().scoring

    @property
    def model_version(self) -> str:
        return "rules-v1"

    def predict_proba(self, features: dict[str, Any]) -> dict[str, float]:
        max_streak = float(features.get("max_streak", 0))
        compliance = float(features.get("mean_challenge_compliance", 1.0))
        regularity = float(features.get("regularity_score", 0.75))
        drops = float(features.get("drops_count", 0))

        # Effective skill index combining max_streak with compliance and regularity
        quality_multiplier = 0.65 + 0.25 * compliance + 0.15 * regularity
        effective_streak = max(0.0, max_streak * quality_multiplier - 1.5 * drops)

        b_max = float(self.cfg.beginner_max_streak)
        i_max = float(self.cfg.intermediate_max_streak)
        a_max = float(self.cfg.advanced_max_streak)

        centers = [
            b_max * 0.45,
            0.5 * (b_max + 1.0 + i_max),
            0.5 * (i_max + 1.0 + a_max),
            a_max + 20.0,
        ]
        scales = [4.0, 7.5, 14.0, 18.0]
        logits = [
            -abs(effective_streak - c) / s
            for c, s in zip(centers, scales, strict=True)
        ]
        probs = _softmax([logits_i * 2.4 for logits_i in logits])
        return {
            lvl: round(prob, 4)
            for lvl, prob in zip(LEVELS, probs, strict=True)
        }


class TrainedArtifactLevelClassifier:
    """
    Loads a trained ordinal linear/MLP/ONNX-exported model artifact (registered in
    `model_versions`) and computes calibrated level probabilities.

    `artifact_path` is either a local filesystem path or an `s3://bucket/key` URI
    (what `model_versions.ruta_onnx` holds after training); S3 URIs are fetched
    through the Garage S3 storage service.
    """

    def __init__(self, artifact_path: str | Path, version_tag: str) -> None:
        self.artifact_path = artifact_path
        self._version_tag = version_tag
        raw_bytes = self._read_artifact_bytes(artifact_path)
        # Support JSON-serialized weights inside `.onnx` / `.json` artifact header
        text = raw_bytes.decode("utf-8", errors="ignore")
        json_start = text.find("{")
        json_end = text.rfind("}")
        if json_start == -1 or json_end == -1:
            raise ValueError(f"Invalid model artifact format: {artifact_path}")
        self.meta: dict[str, Any] = json.loads(text[json_start : json_end + 1])

    @staticmethod
    def _read_artifact_bytes(artifact_path: str | Path) -> bytes:
        location = str(artifact_path)
        if location.startswith("s3://"):
            # Imported lazily: the storage service pulls in boto3 and app settings.
            from app.football.services.storage import garage_s3_storage

            parts = location.removeprefix("s3://").split("/", 1)
            if len(parts) < 2 or not parts[1]:
                raise ValueError(f"Invalid S3 model artifact URI: {location}")
            return garage_s3_storage.get_object_bytes(parts[1])
        return Path(artifact_path).read_bytes()

    @property
    def model_version(self) -> str:
        return self._version_tag

    def predict_proba(self, features: dict[str, Any]) -> dict[str, float]:
        feature_names: list[str] = self.meta["feature_names"]
        means: list[float] = self.meta["scaler_mean"]
        stds: list[float] = self.meta["scaler_scale"]
        weights: list[list[float]] = self.meta["weights"]
        biases: list[float] = self.meta["biases"]

        x_norm = [
            (float(features.get(fname, 0.0)) - m) / max(1e-6, s)
            for fname, m, s in zip(feature_names, means, stds, strict=True)
        ]
        logits: list[float] = []
        for w_row, b_val in zip(weights, biases, strict=True):
            dot = sum(w * xi for w, xi in zip(w_row, x_norm, strict=True)) + b_val
            logits.append(dot)
        probs = _softmax(logits)
        return {
            lvl: round(prob, 4)
            for lvl, prob in zip(LEVELS, probs, strict=True)
        }


def _probabilities_to_score_1_100(probs: dict[str, float]) -> float:
    """
    Map level probabilities to a 1-100 score via the expected level index:
    `expected = sum(i * p_i)` over `LEVELS` (range 0..len(LEVELS)-1), linearly
    rescaled to [1, 100]. Monotonic in each `p_i` shift toward a higher level,
    bounded, and deterministic. NOT calibrated against real human performance
    (see `ScoringOutput.puntaje_calibrado`): the centers/scales behind `probs`
    itself (`RuleBasedLevelClassifier`) are still hand-picked, not fit to data.
    """
    max_idx = len(LEVELS) - 1
    expected_idx = sum(i * probs.get(lvl, 0.0) for i, lvl in enumerate(LEVELS))
    score = 1.0 + (expected_idx / max_idx) * 99.0
    return round(min(100.0, max(1.0, score)), 2)


def score_session_features(
    features: dict[str, Any],
    classifier: LevelClassifierProtocol | None = None,
    config: ScoringConfig | None = None,
) -> ScoringOutput:
    """
    Pure pipeline step (`scoring`):
    `features` -> `ScoringOutput` (`nivel`, `probabilidades`, `confianza`,
    `requiere_revision`, `retroalimentacion`, `version_modelo`, `version_config`).
    """
    full_cfg = load_football_config()
    cfg = config or full_cfg.scoring
    active_clf = classifier or RuleBasedLevelClassifier(config=cfg)

    total_touches = int(features.get("total_touches", 0))
    if total_touches == 0:
        return ScoringOutput(
            nivel="No calificado",
            probabilidades={
                "Principiante": 1.0,
                "Intermedio": 0.0,
                "Avanzado": 0.0,
                "Experto": 0.0,
            },
            confianza=0.0,
            requiere_revision=True,
            retroalimentacion={
                "fortalezas": [],
                "mejoras": [
                    "No se detectó ningún balón de fútbol ni toques válidos en la grabación. Asegúrate de enfocar la cámara de cuerpo entero mostrando el balón en juego."
                ],
            },
            version_modelo=active_clf.model_version,
            version_config=f"{full_cfg.version}:{full_cfg.config_hash[:12]}",
            puntaje_1_100=1.0,
            puntaje_calibrado=False,
        )

    probs = active_clf.predict_proba(features)
    best_level = max(LEVELS, key=lambda lvl: probs.get(lvl, 0.0))
    confidence = round(float(probs[best_level]), 4)
    needs_review = confidence < cfg.min_confidence_for_auto_approval or not bool(
        features.get("plan_coherent", True)
    )
    feedback = generate_template_feedback(features=features, nivel=best_level)

    return ScoringOutput(
        nivel=best_level,
        probabilidades=probs,
        confianza=confidence,
        requiere_revision=needs_review,
        retroalimentacion=feedback,
        version_modelo=active_clf.model_version,
        version_config=f"{full_cfg.version}:{full_cfg.config_hash[:12]}",
        puntaje_1_100=_probabilities_to_score_1_100(probs),
        puntaje_calibrado=False,
    )
