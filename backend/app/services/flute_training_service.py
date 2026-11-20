"""
Flute (recorder) dual neural classifier: sound timbre head + fingering/posture head.

- Sound head: 48-dim pure acoustic timbre vector (32 L2-normalized log-Mel bands
  + 13 MFCCs + RMS + spectral flatness + low-band ratio). Zero pitch/Hz measurement.
- Posture head: 148-dim hand landmark + finger flexion vector (`hand-landmarks-palm-v3`).
- Training data: music dataset samples with reviewed label sidecars
  (`datasets/musica/features/{sample_id}.json`).
- Split is grouped by participant when >= 2 participants exist.
- Artifact: real ONNX ModelProto (protobuf, opset 13) with 2-layer MLP per head
  built without extra dependencies. Inference loads parameters back from that file.
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

import numpy as np
from sqlalchemy import desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import SkillMatchException
from app.football.models import ModelVersion
from app.football.services.storage import garage_s3_storage
from app.models.dataset_sample import DatasetSample

logger = logging.getLogger("skillmatch.flute_training_service")

FLUTE_NOTES: tuple[str, ...] = (
    "DO", "RE", "MI", "FA", "FA#", "SOL", "LA", "SI", "DO6", "RE6", "MI6",
)

# Feature layout shared with frontend/src/components/admin/flute/
AUDIO_FEATURE_DIM = 48  # 32 log-Mel + 13 MFCCs + rms + spectral flatness + low-band ratio
VISUAL_HAND_SLOT_DIM = 25  # 1 presence + 5 curls + 5 palm dists + 5 mcp dists + 4 spreads + 5 heights
VISUAL_FEATURE_DIM = VISUAL_HAND_SLOT_DIM * 2  # 50
VISUAL_FEATURE_SCHEMA = "hand-landmarks-palm-v4"
LEGACY_V3_VISUAL_SCHEMA = "hand-landmarks-palm-v3"
LEGACY_V3_HAND_SLOT_DIM = 74
LEGACY_V3_VISUAL_DIM = LEGACY_V3_HAND_SLOT_DIM * 2  # 148

_FINGER_CHAINS: tuple[tuple[int, int, int, int], ...] = (
    (1, 2, 3, 4),      # Thumb
    (5, 6, 7, 8),      # Index
    (9, 10, 11, 12),   # Middle
    (13, 14, 15, 16),  # Ring
    (17, 18, 19, 20),  # Pinky
)
_ADJACENT_TIP_PAIRS: tuple[tuple[int, int], ...] = (
    (4, 8), (8, 12), (12, 16), (16, 20),
)

NO_FLUTE = "NO_FLAUTA"
WRONG_POSTURE = "INCORRECTA"
SOUND_CLASSES: list[str] = [*FLUTE_NOTES, NO_FLUTE]
POSTURE_CLASSES: list[str] = [*FLUTE_NOTES, WRONG_POSTURE]
SOUND_LABELS = ("flauta", "voz", "ruido")
POSTURE_LABELS = ("correcta", "incorrecta", "sin_manos")
MODEL_NAME = "flute_dual_classifier"
MUSIC_DISCIPLINES = ["musica", "música", "flauta"]
DECISION_THRESHOLD = 0.5
POSTURE_TOP_K = 3
POSTURE_APPROX_MIN_PROB = 0.15
POSTURE_MIN_PEAK_CONF = 0.25
LATENCY_RUNS = 300

_PARAMS_CACHE: dict[str, dict[str, np.ndarray]] = {}


# --------------------------------------------------------------------------- #
# Storage helpers
# --------------------------------------------------------------------------- #
def _storage_key(path: str) -> str:
    if path.startswith("s3://"):
        parts = path.replace("s3://", "", 1).split("/", 1)
        return parts[1] if len(parts) > 1 else path
    return path


def _load_sample_bytes(sample: DatasetSample) -> bytes:
    """Read raw sample bytes from Garage S3 or local storage fallback."""
    if not sample.storage_path:
        return b""
    key = _storage_key(sample.storage_path)
    try:
        return garage_s3_storage.get_object_bytes(key)
    except Exception:  # noqa: BLE001
        local_path = Path("storage") / key
        return local_path.read_bytes() if local_path.exists() else b""


def _labels_key(sample_id: uuid.UUID | str) -> str:
    return f"datasets/musica/features/{sample_id}.json"


def _read_labels(sample_id: uuid.UUID | str) -> dict[str, Any] | None:
    try:
        raw = garage_s3_storage.get_object_bytes(_labels_key(sample_id))
        return json.loads(raw.decode("utf-8"))
    except (FileNotFoundError, ValueError, UnicodeDecodeError):
        return None


def _validate_vector(values: list[float], dim: int, name: str) -> list[float]:
    if len(values) != dim:
        raise SkillMatchException(
            statuscode=400,
            message=f"El vector {name} debe tener {dim} valores (recibido: {len(values)}).",
        )
    if not all(math.isfinite(float(v)) for v in values):
        raise SkillMatchException(statuscode=400, message=f"El vector {name} contiene valores no numéricos.")
    return [float(v) for v in values]


# --------------------------------------------------------------------------- #
# Labels (review step of the capture tool)
# --------------------------------------------------------------------------- #
async def save_flute_labels(
    db: AsyncSession,
    sample_id: uuid.UUID,
    participant_id: str,
    note_label: str | None,
    sound_label: str,
    posture_label: str,
    audio_features: list[float],
    visual_features: list[float],
    visual_schema: str,
    feature_frames: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    sample = await db.scalar(select(DatasetSample).where(DatasetSample.id == sample_id))
    if sample is None:
        raise SkillMatchException(statuscode=404, message="Muestra de dataset no encontrada.")
    if sample.discipline.strip().lower() not in MUSIC_DISCIPLINES:
        raise SkillMatchException(statuscode=400, message="Solo se pueden etiquetar muestras de música.")

    participant = participant_id.strip()
    if not participant:
        raise SkillMatchException(statuscode=400, message="El identificador de participante es obligatorio.")
    if note_label is not None and note_label not in FLUTE_NOTES:
        raise SkillMatchException(statuscode=400, message=f"Nota inválida: {note_label}.")
    if sound_label not in SOUND_LABELS:
        raise SkillMatchException(statuscode=400, message=f"Etiqueta de sonido inválida: {sound_label}.")
    if posture_label not in POSTURE_LABELS:
        raise SkillMatchException(statuscode=400, message=f"Etiqueta de postura inválida: {posture_label}.")
    if (sound_label == "flauta" or posture_label == "correcta") and note_label is None:
        raise SkillMatchException(
            statuscode=400,
            message="Sonido de flauta o digitación correcta requieren indicar la nota.",
        )

    if visual_schema != VISUAL_FEATURE_SCHEMA:
        raise SkillMatchException(
            statuscode=400,
            message="Formato de features antiguo. Reprocesá los videos con timbre y flexión de dedos antes de entrenar.",
        )
    frames = feature_frames or [{"audio_features": audio_features, "visual_features": visual_features}]
    if len(frames) > 120:
        raise SkillMatchException(statuscode=400, message="Se permiten como máximo 120 fotogramas por muestra.")
    checked_frames = []
    for frame in frames:
        audio = _validate_vector(frame["audio_features"], AUDIO_FEATURE_DIM, "de audio")
        visual = _validate_vector(frame["visual_features"], VISUAL_FEATURE_DIM, "visual")
        if posture_label == "correcta" and not _has_required_hands(visual, note_label):
            continue  # Missing landmarks are not examples of correct fingering.
        checked_frames.append({"audio_features": audio, "visual_features": visual})
    if len(checked_frames) < 3:
        raise SkillMatchException(
            statuscode=400,
            message="Se necesitan al menos 3 fotogramas con las manos requeridas detectadas. La muestra no fue etiquetada.",
        )

    payload = {
        "visual_schema": VISUAL_FEATURE_SCHEMA,
        "feature_frames": checked_frames,
        "sample_id": str(sample.id),
        "participant_id": participant,
        "note_label": note_label,
        "sound_label": sound_label,
        "posture_label": posture_label,
        "audio_features": _validate_vector(audio_features, AUDIO_FEATURE_DIM, "de audio"),
        "visual_features": _validate_vector(visual_features, VISUAL_FEATURE_DIM, "visual"),
        "reviewed": True,
        "labeled_at": datetime.now(timezone.utc).isoformat(),
    }
    garage_s3_storage.put_object_bytes(
        object_key=_labels_key(sample.id),
        payload=json.dumps(payload).encode("utf-8"),
        content_type="application/json",
    )
    sample.participant_id = participant
    sample.level_label = note_label or NO_FLUTE
    sample.noise_level = sound_label
    await db.flush()
    return {k: payload[k] for k in ("sample_id", "participant_id", "note_label", "sound_label", "posture_label")}


def _has_required_hands(visual: list[float], note: str | None) -> bool:
    count = int(visual[0] == 1) + int(visual[VISUAL_HAND_SLOT_DIM] == 1)
    if note is None:
        return count >= 1
    required = 2 if note in {"DO", "RE", "MI", "FA", "FA#", "MI6"} else 1
    return count >= required


def _sound_class(lbl: dict[str, Any]) -> str:
    return lbl["note_label"] if lbl["sound_label"] == "flauta" and lbl.get("note_label") else NO_FLUTE


def _posture_class(lbl: dict[str, Any]) -> str:
    return lbl["note_label"] if lbl["posture_label"] == "correcta" and lbl.get("note_label") else WRONG_POSTURE


async def _music_samples(db: AsyncSession) -> list[DatasetSample]:
    result = await db.execute(
        select(DatasetSample)
        .where(func.lower(DatasetSample.discipline).in_(MUSIC_DISCIPLINES))
        .order_by(DatasetSample.created_at.desc())
    )
    return list(result.scalars().all())


def _finger_curl_cos(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> float:
    v1 = b - a
    v2 = c - b
    denom = float(np.linalg.norm(v1) * np.linalg.norm(v2))
    if denom < 1e-6:
        return 0.0
    return float(np.clip(np.dot(v1, v2) / denom, -1.0, 1.0))


def _convert_v3_visual_to_v4(visual_v3: list[float]) -> list[float]:
    """Exact geometric conversion from hand-landmarks-palm-v3 (148) to v4 (50)."""
    out = [0.0] * VISUAL_FEATURE_DIM
    for slot in (0, 1):
        src_off = slot * LEGACY_V3_HAND_SLOT_DIM
        dst_off = slot * VISUAL_HAND_SLOT_DIM
        if visual_v3[src_off] != 1.0:
            continue
        out[dst_off] = 1.0
        pts = np.asarray(visual_v3[src_off + 1 : src_off + 64], dtype=np.float64).reshape(21, 3)
        palm_center = (pts[0] + pts[5] + pts[9] + pts[17]) / 4.0
        for idx, (base, mid, joint, tip) in enumerate(_FINGER_CHAINS):
            curl1 = _finger_curl_cos(pts[base], pts[mid], pts[joint])
            curl2 = _finger_curl_cos(pts[mid], pts[joint], pts[tip])
            out[dst_off + 1 + idx] = (curl1 + curl2) / 2.0
            out[dst_off + 6 + idx] = float(np.linalg.norm(pts[tip] - palm_center))
            out[dst_off + 11 + idx] = float(np.linalg.norm(pts[tip] - pts[base]))
            out[dst_off + 20 + idx] = float(pts[tip, 2] - palm_center[2])
        for idx, (a, b) in enumerate(_ADJACENT_TIP_PAIRS):
            out[dst_off + 16 + idx] = float(np.linalg.norm(pts[a] - pts[b]))
    return out


def _labeled_rows(samples: list[DatasetSample]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    listing: list[dict[str, Any]] = []
    for s in samples:
        lbl = _read_labels(s.id)
        schema = lbl.get("visual_schema") if lbl else None
        is_v4 = bool(
            lbl
            and schema == VISUAL_FEATURE_SCHEMA
            and len(lbl.get("audio_features", [])) == AUDIO_FEATURE_DIM
            and len(lbl.get("visual_features", [])) == VISUAL_FEATURE_DIM
            and len(lbl.get("feature_frames", [])) >= 3
        )
        is_convertible_v3 = bool(
            lbl
            and schema == LEGACY_V3_VISUAL_SCHEMA
            and len(lbl.get("audio_features", [])) == AUDIO_FEATURE_DIM
            and len(lbl.get("visual_features", [])) == LEGACY_V3_VISUAL_DIM
            and len(lbl.get("feature_frames", [])) >= 3
        )
        valid = is_v4 or is_convertible_v3
        listing.append({
            "id": str(s.id),
            "labeled": valid,
            "participant_id": lbl.get("participant_id") if lbl else s.participant_id,
            "note_label": lbl.get("note_label") if lbl else None,
            "sound_label": lbl.get("sound_label") if lbl else None,
            "posture_label": lbl.get("posture_label") if lbl else None,
            "file_format": s.file_format,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        })
        if valid and lbl:
            for frame in lbl["feature_frames"]:
                raw_visual = frame["visual_features"]
                if is_convertible_v3:
                    visual_vec = _convert_v3_visual_to_v4(
                        _validate_vector(raw_visual, LEGACY_V3_VISUAL_DIM, "visual")
                    )
                else:
                    visual_vec = _validate_vector(raw_visual, VISUAL_FEATURE_DIM, "visual")
                rows.append({
                    "sample_id": str(s.id),
                    "participant_id": lbl["participant_id"],
                    "sound_class": SOUND_CLASSES.index(_sound_class(lbl)),
                    "posture_class": POSTURE_CLASSES.index(_posture_class(lbl)),
                    "audio": np.asarray(_validate_vector(frame["audio_features"], AUDIO_FEATURE_DIM, "de audio")),
                    "visual": np.asarray(visual_vec),
                })
    return rows, listing


def _counts(rows: list[dict[str, Any]], key: str, classes: list[str]) -> dict[str, int]:
    out = {c: 0 for c in classes}
    for r in rows:
        out[classes[r[key]]] += 1
    return out


async def preview_flute_dataset(db: AsyncSession) -> dict[str, Any]:
    samples = await _music_samples(db)
    rows, listing = _labeled_rows(samples)
    participants: dict[str, int] = {}
    for r in rows:
        participants[r["participant_id"]] = participants.get(r["participant_id"], 0) + 1
    return {
        "samples": listing,
        "total_count": len(listing),
        "labeled_count": sum(s["labeled"] for s in listing),
        "unlabeled_count": sum(not s["labeled"] for s in listing),
        "feature_frames_count": len(rows),
        "visual_schema": VISUAL_FEATURE_SCHEMA,
        "participants": participants,
        "sound_class_counts": _counts(rows, "sound_class", SOUND_CLASSES),
        "posture_class_counts": _counts(rows, "posture_class", POSTURE_CLASSES),
        "can_validate_independently": len(participants) >= 2,
    }


# --------------------------------------------------------------------------- #
# Training (2-layer MLP with ReLU + class-balanced cross-entropy + Adam)
# --------------------------------------------------------------------------- #
def _split_participants(pids: list[str]) -> tuple[set[str], set[str]]:
    uniq = sorted(set(pids))
    if len(uniq) < 2:
        return set(uniq), set()
    ordered = sorted(uniq, key=lambda p: hashlib.sha256(p.encode("utf-8")).hexdigest())
    n_test = max(1, round(len(uniq) * 0.3))
    return set(ordered[n_test:]), set(ordered[:n_test])


def _train_mlp(
    x: np.ndarray,
    y: np.ndarray,
    n_classes: int,
    hidden_dim: int = 48,
    epochs: int = 350,
    lr: float = 0.02,
    reg: float = 1e-3,
    noise_std: float = 0.0,
) -> tuple[dict[str, np.ndarray], list[dict[str, float]]]:
    mean = x.mean(axis=0)
    scale = np.maximum(x.std(axis=0), 1e-2)
    z = (x - mean) / scale
    n_samples, in_dim = z.shape

    # Balanced per-sample weights so every note has equal influence
    class_counts = np.bincount(y, minlength=n_classes).astype(np.float64)
    present_classes = max(1, int(np.sum(class_counts > 0)))
    sample_weights = np.where(
        class_counts[y] > 0,
        n_samples / (present_classes * np.maximum(class_counts[y], 1.0)),
        1.0,
    )
    sample_weights /= sample_weights.sum()

    rng = np.random.default_rng(42)
    w1 = rng.normal(0.0, math.sqrt(2.0 / in_dim), size=(in_dim, hidden_dim))
    b1 = np.zeros(hidden_dim)
    w2 = rng.normal(0.0, math.sqrt(1.0 / hidden_dim), size=(hidden_dim, n_classes))
    b2 = np.zeros(n_classes)

    params = {"W1": w1, "b1": b1, "W2": w2, "b2": b2}
    m_state = {k: np.zeros_like(v) for k, v in params.items()}
    v_state = {k: np.zeros_like(v) for k, v in params.items()}
    beta1, beta2, eps = 0.9, 0.999, 1e-8

    onehot = np.eye(n_classes)[y]
    history: list[dict[str, float]] = []

    for epoch in range(1, epochs + 1):
        z_in = z + rng.normal(0.0, noise_std, size=z.shape) if noise_std > 0.0 else z
        h_pre = z_in @ params["W1"] + params["b1"]
        h = np.maximum(h_pre, 0.0)
        logits = h @ params["W2"] + params["b2"]
        logits -= logits.max(axis=1, keepdims=True)
        probs = np.exp(logits)
        probs /= probs.sum(axis=1, keepdims=True)

        if epoch == 1 or epoch % 70 == 0 or epoch == epochs:
            loss = float(-np.sum(sample_weights * np.log(probs[np.arange(n_samples), y] + 1e-12)))
            history.append({"epoch": epoch, "loss": round(loss, 4)})

        d_logits = (probs - onehot) * sample_weights[:, None]
        grads = {
            "W2": h.T @ d_logits + reg * params["W2"],
            "b2": d_logits.sum(axis=0),
        }
        d_h = (d_logits @ params["W2"].T) * (h_pre > 0.0)
        grads["W1"] = z_in.T @ d_h + reg * params["W1"]
        grads["b1"] = d_h.sum(axis=0)

        for k in params:
            m_state[k] = beta1 * m_state[k] + (1.0 - beta1) * grads[k]
            v_state[k] = beta2 * v_state[k] + (1.0 - beta2) * (grads[k] ** 2)
            m_hat = m_state[k] / (1.0 - beta1 ** epoch)
            v_hat = v_state[k] / (1.0 - beta2 ** epoch)
            params[k] -= lr * m_hat / (np.sqrt(v_hat) + eps)

    return {"mean": mean, "scale": scale, **params}, history


def _mask_and_normalize_posture(x: np.ndarray, mean: np.ndarray, scale: np.ndarray) -> np.ndarray:
    z = (x - mean) / scale
    if x.shape[1] == VISUAL_FEATURE_DIM:
        for slot in (0, 1):
            off = slot * VISUAL_HAND_SLOT_DIM
            absent = x[:, off] == 0.0
            if np.any(absent):
                z[absent, off : off + VISUAL_HAND_SLOT_DIM] = 0.0
    norms = np.maximum(np.linalg.norm(z, axis=1, keepdims=True), 1e-6)
    return z / norms


def _train_posture_prototypes(
    x: np.ndarray,
    y: np.ndarray,
    n_classes: int,
    temperature: float = 0.35,
) -> tuple[dict[str, np.ndarray], list[dict[str, float]]]:
    """Calibrated cosine-similarity prototype classifier for hand posture.

    Avoids MLP overconfidence on small datasets and masks absent hand slots so
    the non-playing hand entering/leaving frame never corrupts predictions.
    """
    mean = x.mean(axis=0)
    scale = np.maximum(x.std(axis=0), 0.25)
    z = _mask_and_normalize_posture(x, mean, scale)

    in_dim = z.shape[1]
    w = np.zeros((in_dim, n_classes), dtype=np.float64)
    b = np.full(n_classes, -10.0, dtype=np.float64)
    for c in range(n_classes):
        mask = y == c
        if np.any(mask):
            centroid = z[mask].mean(axis=0)
            norm = float(np.linalg.norm(centroid))
            if norm > 1e-6:
                centroid = centroid / norm
            w[:, c] = centroid / temperature
            b[c] = 0.0

    logits = z @ w + b
    logits -= logits.max(axis=1, keepdims=True)
    probs = np.exp(logits)
    probs /= probs.sum(axis=1, keepdims=True)
    loss = float(-np.mean(np.log(probs[np.arange(len(y)), y] + 1e-12)))
    return {"mean": mean, "scale": scale, "W": w, "b": b}, [{"epoch": 1, "loss": round(loss, 4)}]


def _head_probs(params: dict[str, np.ndarray], head: str, x: np.ndarray) -> np.ndarray:
    if f"{head}_W1" in params:
        z = (x - params[f"{head}_mean"]) / params[f"{head}_scale"]
        h = np.maximum(z @ params[f"{head}_W1"] + params[f"{head}_b1"], 0.0)
        logits = h @ params[f"{head}_W2"] + params[f"{head}_b2"]
    elif head == "posture":
        z = _mask_and_normalize_posture(x, params[f"{head}_mean"], params[f"{head}_scale"])
        logits = z @ params[f"{head}_W"] + params[f"{head}_b"]
    else:
        z = (x - params[f"{head}_mean"]) / params[f"{head}_scale"]
        logits = z @ params[f"{head}_W"] + params[f"{head}_b"]
    logits -= logits.max(axis=1, keepdims=True)
    e = np.exp(logits)
    return e / e.sum(axis=1, keepdims=True)


def _accuracy_and_confusion(pred: list[int], true: list[int], n: int) -> tuple[float | None, list[list[int]]]:
    confusion = [[0] * n for _ in range(n)]
    for p, t in zip(pred, true):
        confusion[t][p] += 1
    if not true:
        return None, confusion
    return round(sum(1 for p, t in zip(pred, true) if p == t) / len(true), 4), confusion


async def train_flute_note_model(
    db: AsyncSession,
    version_tag: str | None = None,
    activate: bool = True,
    skill_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    samples = await _music_samples(db)
    rows, listing = _labeled_rows(samples)
    if sum(s["labeled"] for s in listing) < 4:
        raise SkillMatchException(
            statuscode=400,
            message=(
                "Se necesitan al menos 4 videos etiquetados con timbre y articulaciones. "
                "Conservá los videos anteriores para reprocesarlos desde el estudio."
            ),
        )

    train_pids, test_pids = _split_participants([r["participant_id"] for r in rows])
    train_rows = [r for r in rows if r["participant_id"] in train_pids]
    test_rows = [r for r in rows if r["participant_id"] in test_pids]

    sound_train_classes = {r["sound_class"] for r in train_rows}
    posture_train_classes = {r["posture_class"] for r in train_rows}
    if len(sound_train_classes) < 2 or len(posture_train_classes) < 2:
        raise SkillMatchException(
            statuscode=400,
            message=(
                "El conjunto de entrenamiento necesita al menos 2 clases de sonido y 2 de postura. "
                "Graba al menos 2 notas distintas (o ejemplos negativos de voz/ruido)."
            ),
        )

    x_audio = np.stack([r["audio"] for r in train_rows])
    x_visual = np.stack([r["visual"] for r in train_rows])
    y_sound = np.array([r["sound_class"] for r in train_rows], dtype=np.int64)
    y_posture = np.array([r["posture_class"] for r in train_rows], dtype=np.int64)

    sound_params, sound_history = _train_mlp(
        x_audio, y_sound, len(SOUND_CLASSES), hidden_dim=48, reg=1e-3, noise_std=0.0, lr=0.02
    )
    posture_params, posture_history = _train_posture_prototypes(
        x_visual, y_posture, len(POSTURE_CLASSES)
    )

    onnx_bytes = build_flute_onnx({"sound": sound_params, "posture": posture_params})
    # Everything below uses parameters read back from the exported ONNX artifact.
    params = load_onnx_initializers(onnx_bytes)

    sound_train_pred = [int(p) for p in np.argmax(_head_probs(params, "sound", x_audio), axis=1)]
    posture_train_pred = [int(p) for p in np.argmax(_head_probs(params, "posture", x_visual), axis=1)]
    sound_train_acc, _ = _accuracy_and_confusion(sound_train_pred, [int(v) for v in y_sound], len(SOUND_CLASSES))
    posture_train_acc, _ = _accuracy_and_confusion(posture_train_pred, [int(v) for v in y_posture], len(POSTURE_CLASSES))

    validated = len(test_rows) > 0
    sound_true = [r["sound_class"] for r in test_rows]
    posture_true = [r["posture_class"] for r in test_rows]
    sound_pred: list[int] = []
    posture_pred: list[int] = []
    if validated:
        sound_pred = list(np.argmax(_head_probs(params, "sound", np.stack([r["audio"] for r in test_rows])), axis=1))
        posture_pred = list(np.argmax(_head_probs(params, "posture", np.stack([r["visual"] for r in test_rows])), axis=1))
    sound_acc, sound_conf = _accuracy_and_confusion([int(p) for p in sound_pred], sound_true, len(SOUND_CLASSES))
    posture_acc, posture_conf = _accuracy_and_confusion([int(p) for p in posture_pred], posture_true, len(POSTURE_CLASSES))

    sound_majority = int(np.bincount(y_sound, minlength=len(SOUND_CLASSES)).argmax())
    sound_majority_acc, _ = _accuracy_and_confusion([sound_majority] * len(sound_true), sound_true, len(SOUND_CLASSES))
    posture_majority = int(np.bincount(y_posture, minlength=len(POSTURE_CLASSES)).argmax())
    posture_majority_acc, _ = _accuracy_and_confusion([posture_majority] * len(posture_true), posture_true, len(POSTURE_CLASSES))

    # Measured inference latency (single-sample, both heads, params loaded from ONNX).
    bench = test_rows or train_rows
    t0 = time.perf_counter()
    for i in range(LATENCY_RUNS):
        row = bench[i % len(bench)]
        _head_probs(params, "sound", row["audio"][None, :])
        _head_probs(params, "posture", row["visual"][None, :])
    latency_ms = (time.perf_counter() - t0) / LATENCY_RUNS * 1000.0

    if version_tag and version_tag.strip():
        version_str = version_tag.strip().replace(" ", "-")
    else:
        existing = await db.scalar(
            select(func.count()).select_from(ModelVersion).where(ModelVersion.nombre == MODEL_NAME)
        )
        version_str = f"flute-timbre-2.{(existing or 0) + 1}.0"

    onnx_key = f"models/flute/{MODEL_NAME}_{version_str}.onnx"
    storage_uri, onnx_sha = garage_s3_storage.put_object_bytes(
        object_key=onnx_key, payload=onnx_bytes, content_type="application/octet-stream",
    )

    metrics: dict[str, Any] = {
        "visual_schema": VISUAL_FEATURE_SCHEMA,
        "audio_mode": "mel_mfcc_timbre",
        "architecture": "dual_mlp_onnx",
        "metric_unit": "feature_frame",
        "validated": validated,
        "validation_note": (
            "Precisión medida sobre personas que no participaron del entrenamiento."
            if validated
            else "Modo experimental (1 participante): usable en vivo; suma una segunda persona para validación independiente."
        ),
        "train_participants": sorted(train_pids),
        "test_participants": sorted(test_pids),
        "train_samples": len(train_rows),
        "test_samples": len(test_rows),
        "labeled_samples": sum(s["labeled"] for s in listing),
        "unlabeled_samples": sum(not s["labeled"] for s in listing),
        "sound": {
            "classes": SOUND_CLASSES,
            "train_accuracy": sound_train_acc,
            "test_accuracy": sound_acc,
            "majority_baseline_accuracy": sound_majority_acc,
            "confusion_matrix": sound_conf,
            "train_class_counts": _counts(train_rows, "sound_class", SOUND_CLASSES),
            "loss_history": sound_history,
        },
        "posture": {
            "classes": POSTURE_CLASSES,
            "train_accuracy": posture_train_acc,
            "test_accuracy": posture_acc,
            "majority_baseline_accuracy": posture_majority_acc,
            "confusion_matrix": posture_conf,
            "train_class_counts": _counts(train_rows, "posture_class", POSTURE_CLASSES),
            "loss_history": posture_history,
        },
        "latency_ms_per_inference": round(latency_ms, 4),
        "latency_runs": LATENCY_RUNS,
        "onnx_sha256": onnx_sha,
        "onnx_bytes": len(onnx_bytes),
        "feature_dims": {"audio": AUDIO_FEATURE_DIM, "visual": VISUAL_FEATURE_DIM},
        "decision_threshold": DECISION_THRESHOLD,
        "skill_id": str(skill_id) if skill_id else None,
    }

    if activate:
        await db.execute(update(ModelVersion).where(ModelVersion.nombre == MODEL_NAME).values(activa=False))
    row = ModelVersion(
        id=uuid.uuid4(), nombre=MODEL_NAME, version=version_str,
        ruta_onnx=storage_uri, metricas=metrics, activa=activate,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    _PARAMS_CACHE[str(row.id)] = params
    return _model_dict(row)


# --------------------------------------------------------------------------- #
# Model registry + inference
# --------------------------------------------------------------------------- #
def _model_dict(r: ModelVersion) -> dict[str, Any]:
    return {
        "id": str(r.id),
        "nombre": r.nombre,
        "version": r.version,
        "ruta_onnx": r.ruta_onnx,
        "activa": r.activa,
        "metricas": r.metricas,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


async def list_flute_model_versions(db: AsyncSession) -> list[dict[str, Any]]:
    result = await db.execute(
        select(ModelVersion)
        .where(ModelVersion.nombre == MODEL_NAME)
        .order_by(desc(ModelVersion.activa), desc(ModelVersion.created_at))
    )
    return [_model_dict(r) for r in result.scalars().all()]


async def activate_flute_model(db: AsyncSession, model_id: uuid.UUID) -> dict[str, Any]:
    target = await db.scalar(
        select(ModelVersion).where(ModelVersion.id == model_id, ModelVersion.nombre == MODEL_NAME)
    )
    if target is None:
        raise SkillMatchException(statuscode=404, message="Versión de modelo de flauta no encontrada.")
    if (target.metricas or {}).get("visual_schema") != VISUAL_FEATURE_SCHEMA:
        raise SkillMatchException(
            statuscode=409,
            message="Este modelo usa un formato anterior. Reprocesá los videos y entrená una nueva versión.",
        )
    await db.execute(update(ModelVersion).where(ModelVersion.nombre == MODEL_NAME).values(activa=False))
    target.activa = True
    await db.commit()
    await db.refresh(target)
    return _model_dict(target)


def _params_for(model: ModelVersion) -> dict[str, np.ndarray]:
    cached = _PARAMS_CACHE.get(str(model.id))
    if cached is not None:
        return cached
    try:
        raw = garage_s3_storage.get_object_bytes(_storage_key(model.ruta_onnx))
    except FileNotFoundError as exc:
        raise SkillMatchException(
            statuscode=500, message="No se encontró el archivo ONNX del modelo activo.",
        ) from exc
    params = load_onnx_initializers(raw)
    _PARAMS_CACHE[str(model.id)] = params
    return params


def _top_predictions(probs: np.ndarray, classes: list[str], k: int = 3) -> list[dict[str, Any]]:
    top_indices = np.argsort(-probs)[:k]
    return [
        {"label": classes[int(i)], "probability": round(float(probs[int(i)]), 4)}
        for i in top_indices
    ]


def _is_posture_compatible(posture_p: np.ndarray, note: str) -> bool:
    """Approximate fingering check: rejects WRONG_POSTURE, accepts note in Top-3 with >= 15% affinity."""
    if note not in POSTURE_CLASSES:
        return False
    top_idx = int(np.argmax(posture_p))
    if POSTURE_CLASSES[top_idx] == WRONG_POSTURE and float(posture_p[top_idx]) >= DECISION_THRESHOLD:
        return False
    note_idx = POSTURE_CLASSES.index(note)
    top_k_indices = [int(i) for i in np.argsort(-posture_p)[:POSTURE_TOP_K]]
    return note_idx in top_k_indices and float(posture_p[note_idx]) >= POSTURE_APPROX_MIN_PROB


async def infer_flute(
    db: AsyncSession,
    audio_features: list[float],
    visual_features: list[float],
    visual_schema: str,
    target_note: str | None = None,
) -> dict[str, Any]:
    if target_note is not None and target_note not in FLUTE_NOTES:
        raise SkillMatchException(statuscode=400, message=f"Nota objetivo inválida: {target_note}.")
    audio = np.asarray(_validate_vector(audio_features, AUDIO_FEATURE_DIM, "de audio"))[None, :]
    visual = np.asarray(_validate_vector(visual_features, VISUAL_FEATURE_DIM, "visual"))[None, :]

    model = await db.scalar(
        select(ModelVersion).where(ModelVersion.nombre == MODEL_NAME, ModelVersion.activa.is_(True))
    )
    if model is None:
        raise SkillMatchException(
            statuscode=409,
            message="No hay un modelo de flauta activo. Entrená y activá uno en el Estudio de Entrenamiento.",
        )
    metrics = model.metricas or {}
    if visual_schema != VISUAL_FEATURE_SCHEMA or metrics.get("visual_schema") != VISUAL_FEATURE_SCHEMA:
        raise SkillMatchException(
            statuscode=409,
            message="El modelo activo usa un formato anterior. Reprocesá los videos y entrená una nueva versión.",
        )

    params = _params_for(model)
    sound_p = _head_probs(params, "sound", audio)[0]
    posture_p = _head_probs(params, "posture", visual)[0]
    sound_idx = int(np.argmax(sound_p))
    posture_idx = int(np.argmax(posture_p))
    sound_class = SOUND_CLASSES[sound_idx]
    posture_class = POSTURE_CLASSES[posture_idx]
    sound_conf = float(sound_p[sound_idx])
    posture_conf = float(posture_p[posture_idx])

    validated = bool(metrics.get("validated", False))
    posture_metrics = metrics.get("posture", {})
    accuracy = posture_metrics.get("test_accuracy")
    baseline = posture_metrics.get("majority_baseline_accuracy")

    posture_reason = None
    if not _has_required_hands(visual_features, target_note):
        posture_reason = "Articulaciones insuficientes: muestra las manos frente a la cámara."
    elif validated and (accuracy is None or baseline is None or accuracy <= baseline):
        posture_reason = "El modelo visual todavía no supera la línea base en participantes independientes."
    elif target_note is not None and not posture_metrics.get("train_class_counts", {}).get(target_note):
        posture_reason = "El modelo no aprendió ejemplos de esta digitación."
    elif posture_conf < POSTURE_MIN_PEAK_CONF:
        posture_reason = "Confianza visual insuficiente: resultado inconcluso."

    sound_confident = sound_class != NO_FLUTE and sound_conf >= DECISION_THRESHOLD
    combined_match = bool(
        sound_confident and posture_reason is None and _is_posture_compatible(posture_p, sound_class)
    )
    combined_note = sound_class if combined_match else None

    if target_note is not None:
        target_sound_p = float(sound_p[SOUND_CLASSES.index(target_note)])
        target_posture_p = float(posture_p[POSTURE_CLASSES.index(target_note)])
        sound_ok = sound_class == target_note and target_sound_p >= DECISION_THRESHOLD
        posture_ok: bool | None = (
            None if posture_reason else _is_posture_compatible(posture_p, target_note)
        )
    else:
        target_sound_p = sound_conf
        target_posture_p = posture_conf
        sound_ok = sound_confident
        posture_ok = None if posture_reason else (posture_class != WRONG_POSTURE)

    return {
        "model_id": str(model.id),
        "model_version": model.version,
        "validated": validated,
        "experimental": not validated,
        "target_note": target_note,
        "sound_class": sound_class,
        "sound_confidence": round(sound_conf, 4),
        "target_sound_probability": round(target_sound_p, 4),
        "sound_ok": sound_ok,
        "top_sound_classes": _top_predictions(sound_p, SOUND_CLASSES, k=3),
        "posture_class": posture_class,
        "posture_confidence": round(posture_conf, 4),
        "target_posture_probability": round(target_posture_p, 4),
        "posture_ok": posture_ok,
        "posture_evaluable": posture_reason is None,
        "posture_reason": posture_reason,
        "top_posture_classes": _top_predictions(posture_p, POSTURE_CLASSES, k=5),
        "combined_note": combined_note,
        "combined_match": combined_match,
    }


# --------------------------------------------------------------------------- #
# Minimal ONNX (protobuf) writer/reader — no external dependency
# MLP Graph per head:
#   Sub(mean) -> Div(scale) -> MatMul(W1) -> Add(b1) -> Relu -> MatMul(W2) -> Add(b2) -> Softmax(axis=1)
# --------------------------------------------------------------------------- #
def _varint(n: int) -> bytes:
    n &= (1 << 64) - 1
    out = bytearray()
    while True:
        byte = n & 0x7F
        n >>= 7
        if n:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


def _f_varint(field: int, value: int) -> bytes:
    return _varint(field << 3) + _varint(value)


def _f_bytes(field: int, data: bytes) -> bytes:
    return _varint((field << 3) | 2) + _varint(len(data)) + data


def _f_str(field: int, text: str) -> bytes:
    return _f_bytes(field, text.encode("utf-8"))


def _tensor_proto(name: str, arr: np.ndarray) -> bytes:
    data = np.ascontiguousarray(arr, dtype="<f4")
    dims = b"".join(_f_varint(1, int(d)) for d in data.shape)
    return dims + _f_varint(2, 1) + _f_str(8, name) + _f_bytes(9, data.tobytes())


def _value_info(name: str, dims: list[int | str]) -> bytes:
    shape = b"".join(
        _f_bytes(1, _f_varint(1, d) if isinstance(d, int) else _f_str(2, d)) for d in dims
    )
    tensor_type = _f_varint(1, 1) + _f_bytes(2, shape)
    return _f_str(1, name) + _f_bytes(2, _f_bytes(1, tensor_type))


def _node(op: str, inputs: list[str], outputs: list[str], name: str, attrs: bytes = b"") -> bytes:
    body = b"".join(_f_str(1, i) for i in inputs) + b"".join(_f_str(2, o) for o in outputs)
    return body + _f_str(3, name) + _f_str(4, op) + attrs


def build_flute_onnx(heads: dict[str, dict[str, np.ndarray]]) -> bytes:
    nodes = b""
    inits = b""
    outputs = b""
    for head, input_name, output_name in (
        ("sound", "audio_features", "sound_probs"),
        ("posture", "visual_features", "posture_probs"),
    ):
        p = heads[head]
        is_mlp = "W1" in p
        keys = ("mean", "scale", "W1", "b1", "W2", "b2") if is_mlp else ("mean", "scale", "W", "b")
        for key in keys:
            inits += _f_bytes(5, _tensor_proto(f"{head}_{key}", p[key]))
        nodes += _f_bytes(1, _node("Sub", [input_name, f"{head}_mean"], [f"{head}_c"], f"{head}_sub"))
        nodes += _f_bytes(1, _node("Div", [f"{head}_c", f"{head}_scale"], [f"{head}_z"], f"{head}_div"))
        if is_mlp:
            nodes += _f_bytes(1, _node("MatMul", [f"{head}_z", f"{head}_W1"], [f"{head}_m1"], f"{head}_matmul1"))
            nodes += _f_bytes(1, _node("Add", [f"{head}_m1", f"{head}_b1"], [f"{head}_hpre"], f"{head}_add1"))
            nodes += _f_bytes(1, _node("Relu", [f"{head}_hpre"], [f"{head}_h"], f"{head}_relu"))
            nodes += _f_bytes(1, _node("MatMul", [f"{head}_h", f"{head}_W2"], [f"{head}_m2"], f"{head}_matmul2"))
            nodes += _f_bytes(1, _node("Add", [f"{head}_m2", f"{head}_b2"], [f"{head}_logits"], f"{head}_add2"))
            out_dim = int(p["b2"].shape[0])
        else:
            nodes += _f_bytes(1, _node("MatMul", [f"{head}_z", f"{head}_W"], [f"{head}_m"], f"{head}_matmul"))
            nodes += _f_bytes(1, _node("Add", [f"{head}_m", f"{head}_b"], [f"{head}_logits"], f"{head}_add"))
            out_dim = int(p["b"].shape[0])
        axis_attr = _f_bytes(5, _f_str(1, "axis") + _f_varint(3, 1) + _f_varint(20, 2))
        nodes += _f_bytes(1, _node("Softmax", [f"{head}_logits"], [output_name], f"{head}_softmax", axis_attr))
        outputs += _f_bytes(12, _value_info(output_name, ["N", out_dim]))

    graph = (
        nodes
        + _f_str(2, "skillmatch_flute_dual_mlp")
        + inits
        + _f_bytes(11, _value_info("audio_features", ["N", AUDIO_FEATURE_DIM]))
        + _f_bytes(11, _value_info("visual_features", ["N", VISUAL_FEATURE_DIM]))
        + outputs
    )
    opset = _f_str(1, "") + _f_varint(2, 13)
    return _f_varint(1, 8) + _f_str(2, "skillmatch") + _f_bytes(7, graph) + _f_bytes(8, opset)


def _read_varint(buf: bytes, pos: int) -> tuple[int, int]:
    result = shift = 0
    while True:
        byte = buf[pos]
        pos += 1
        result |= (byte & 0x7F) << shift
        shift += 7
        if not byte & 0x80:
            return result, pos


def _fields(buf: bytes) -> Iterator[tuple[int, int, Any]]:
    pos = 0
    while pos < len(buf):
        key, pos = _read_varint(buf, pos)
        field, wire = key >> 3, key & 7
        if wire == 0:
            value, pos = _read_varint(buf, pos)
        elif wire == 2:
            length, pos = _read_varint(buf, pos)
            value = buf[pos:pos + length]
            pos += length
        elif wire == 5:
            value, pos = buf[pos:pos + 4], pos + 4
        elif wire == 1:
            value, pos = buf[pos:pos + 8], pos + 8
        else:
            raise ValueError(f"Unsupported protobuf wire type {wire}")
        yield field, wire, value


def load_onnx_initializers(data: bytes) -> dict[str, np.ndarray]:
    graph = next((v for f, w, v in _fields(data) if f == 7 and w == 2), None)
    if graph is None:
        raise SkillMatchException(statuscode=500, message="Artefacto ONNX inválido: falta el grafo.")
    params: dict[str, np.ndarray] = {}
    for field, wire, tensor in _fields(graph):
        if field != 5 or wire != 2:
            continue
        dims: list[int] = []
        name = ""
        raw = b""
        for tf, tw, tv in _fields(tensor):
            if tf == 1 and tw == 0:
                dims.append(tv)
            elif tf == 1 and tw == 2:
                pos = 0
                while pos < len(tv):
                    d, pos = _read_varint(tv, pos)
                    dims.append(d)
            elif tf == 8:
                name = bytes(tv).decode("utf-8")
            elif tf == 9:
                raw = bytes(tv)
        params[name] = np.frombuffer(raw, dtype="<f4").reshape(dims).astype(np.float64)
    return params


def _infer_note_from_sample(sample: DatasetSample) -> str:
    if sample.level_label and sample.level_label in FLUTE_NOTES:
        return sample.level_label
    challenge = sample.challenge or ""
    for note in ("FA#", "DO6", "RE6", "MI6", "DO", "RE", "MI", "FA", "SOL", "LA", "SI"):
        if f"Nota {note}" in challenge or f"Nota: {note}" in challenge:
            return note
    return "UNKNOWN"


def _infer_variation_from_sample(sample: DatasetSample) -> str:
    if sample.surface:
        return sample.surface
    challenge = sample.challenge or ""
    for var in ("lenta", "rapida", "media", "vibrato", "staccato"):
        if var in challenge.lower():
            return var
    return "normal"
