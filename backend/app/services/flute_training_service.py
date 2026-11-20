"""
Flute (soprano recorder, German fingering) evaluation: pitch-first sound decision
plus a per-finger (front hole) posture head.

- Audio vector (`flute-audio-pitch-v1`, 62 floats, extracted in the browser):
  [0..47] timbre (32 log-Mel + 13 MFCC + RMS + flatness + low-band ratio),
  [48] voiced flag, [49] YIN clarity, [50] octaves above C5, [51..61] Gaussian
  affinity (sigma 35 cents) to each note in `FLUTE_NOTES` order.
- Sound decision: the measured pitch decides the note; the MLP sound head only
  confirms that the frame sounds like a flute (1 - P(NO_FLAUTA)).
- Posture: multi-label MLP predicting whether each of the 7 front holes is
  covered. Labels derive from the fingering table (`FRONT_HOLES`), so every
  correct take supervises all fingers. The back thumb is not visible to the
  camera and is never evaluated (DO6/RE6 and MI/MI6 share front holes).
- Evaluation split: participants -> sessions (participant + capture day) ->
  takes. Metrics are reported per frame and per take (video).
- Artifact: ONNX ModelProto (opset 13) written without extra dependencies; the
  served NumPy inference reads its parameters back from that artifact and is
  parity-tested against the exported graph.
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
import time
import uuid
from collections import Counter, defaultdict
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

# Equal temperament, A4 = 440 Hz. Soprano recorder sounds C5..E6.
NOTE_FREQUENCIES_HZ: dict[str, float] = {
    "DO": 523.2511, "RE": 587.3295, "MI": 659.2551, "FA": 698.4565, "FA#": 739.9888,
    "SOL": 783.9909, "LA": 880.0, "SI": 987.7666, "DO6": 1046.502, "RE6": 1174.659, "MI6": 1318.510,
}
C5_HZ = NOTE_FREQUENCIES_HZ["DO"]

# Front holes 1-7 (1-3 left hand, 4-7 right hand), True = covered.
# Mirrors FLUTE_NOTES_MAP in frontend/src/components/admin/flute/flute-note-specs.ts.
FRONT_HOLES: dict[str, tuple[bool, ...]] = {
    "SI": (True, False, False, False, False, False, False),
    "LA": (True, True, False, False, False, False, False),
    "SOL": (True, True, True, False, False, False, False),
    "DO6": (False, True, False, False, False, False, False),
    "RE6": (False, True, False, False, False, False, False),
    "FA": (True, True, True, True, False, False, False),
    "FA#": (True, True, True, False, True, True, False),
    "MI": (True, True, True, True, True, False, False),
    "RE": (True, True, True, True, True, True, False),
    "DO": (True, True, True, True, True, True, True),
    "MI6": (True, True, True, True, True, False, False),
}
TWO_HAND_NOTES = frozenset({"DO", "RE", "MI", "FA", "FA#", "MI6"})
N_HOLES = 7

# Feature layout shared with frontend/src/components/admin/flute/
AUDIO_FEATURE_SCHEMA = "flute-audio-pitch-v1"
TIMBRE_FEATURE_DIM = 48
PITCH_FEATURE_DIM = 3 + len(FLUTE_NOTES)  # voiced, clarity, octaves above C5, 11 affinities
AUDIO_FEATURE_DIM = TIMBRE_FEATURE_DIM + PITCH_FEATURE_DIM  # 62
IDX_VOICED = TIMBRE_FEATURE_DIM
IDX_CLARITY = TIMBRE_FEATURE_DIM + 1
IDX_OCTAVES = TIMBRE_FEATURE_DIM + 2
AFFINITY_SIGMA_CENTS = 35.0

VISUAL_FEATURE_SCHEMA = "hand-landmarks-palm-v5"  # v4 layout, handedness = user's real hand
VISUAL_HAND_SLOT_DIM = 25  # 1 presence + 5 curls + 5 palm dists + 5 mcp dists + 4 spreads + 5 heights
VISUAL_FEATURE_DIM = VISUAL_HAND_SLOT_DIM * 2  # 50

NO_FLUTE = "NO_FLAUTA"
WRONG_POSTURE = "INCORRECTA"  # legacy label value only; not a model class anymore
SOUND_CLASSES: list[str] = [*FLUTE_NOTES, NO_FLUTE]
SOUND_LABELS = ("flauta", "voz", "ruido")
POSTURE_LABELS = ("correcta", "incorrecta", "sin_manos")
MODEL_NAME = "flute_dual_classifier"
MUSIC_DISCIPLINES = ["musica", "música", "flauta"]

DECISION_THRESHOLD = 0.5
PITCH_TOLERANCE_CENTS = 60.0
MAX_TUNING_OFFSET_CENTS = 50.0
MIN_PITCH_AGREEMENT = 0.3
# Adjacent notes differ by a single finger, so no confident mismatch is tolerated.
# A hole is "uncertain" when its covered probability lies inside this band.
FINGER_UNCERTAIN_BAND = (0.35, 0.65)
MAX_UNCERTAIN_HOLES = 1
TEST_FRACTION = 0.3
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
    except Exception:  # noqa: BLE001 - a broken object must not take down preview/training
        logger.warning("Could not read flute label sidecar for sample %s", sample_id, exc_info=True)
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
# Pitch helpers (mirror of the browser extractor)
# --------------------------------------------------------------------------- #
def _cents(hz: float, ref_hz: float) -> float:
    return 1200.0 * math.log2(hz / ref_hz)


def build_pitch_features(hz: float | None, clarity: float) -> list[float]:
    """Pitch block [48..61] of the audio vector; must match the frontend extractor."""
    if hz is None or hz <= 0:
        return [0.0, float(clarity)] + [0.0] * (PITCH_FEATURE_DIM - 2)
    affinities = [
        math.exp(-0.5 * (_cents(hz, NOTE_FREQUENCIES_HZ[n]) / AFFINITY_SIGMA_CENTS) ** 2)
        for n in FLUTE_NOTES
    ]
    return [1.0, float(clarity), math.log2(hz / C5_HZ), *affinities]


def pitch_hz_from_audio(audio: np.ndarray) -> float | None:
    if audio[IDX_VOICED] < 0.5:
        return None
    return C5_HZ * 2.0 ** float(audio[IDX_OCTAVES])


def nearest_flute_note(hz: float | None, tuning_offset_cents: float = 0.0) -> tuple[str | None, float | None]:
    """Nearest note after removing the instrument's tuning offset; None beyond tolerance."""
    if hz is None or hz <= 0:
        return None, None
    corrected = hz * 2.0 ** (-tuning_offset_cents / 1200.0)
    note = min(FLUTE_NOTES, key=lambda n: abs(_cents(corrected, NOTE_FREQUENCIES_HZ[n])))
    cents = _cents(corrected, NOTE_FREQUENCIES_HZ[note])
    if abs(cents) > PITCH_TOLERANCE_CENTS:
        return None, round(cents, 1)
    return note, round(cents, 1)


def sound_decision(audio: np.ndarray, sound_probs: np.ndarray, tuning_offset_cents: float = 0.0) -> dict[str, Any]:
    """Pitch decides the note; the MLP head only confirms it sounds like a flute."""
    flute_probability = float(1.0 - sound_probs[SOUND_CLASSES.index(NO_FLUTE)])
    hz = pitch_hz_from_audio(audio)
    pitch_note, cents = nearest_flute_note(hz, tuning_offset_cents)
    voiced = hz is not None
    if voiced and pitch_note is not None and flute_probability >= DECISION_THRESHOLD:
        sound_class = pitch_note
        confidence = flute_probability * math.exp(-0.5 * (cents / AFFINITY_SIGMA_CENTS) ** 2)
    else:
        sound_class = NO_FLUTE
        confidence = 1.0 - flute_probability if flute_probability < DECISION_THRESHOLD else 1.0
    return {
        "sound_class": sound_class,
        "sound_confidence": round(float(confidence), 4),
        "voiced": voiced,
        "pitch_hz": round(hz, 2) if hz is not None else None,
        "pitch_note": pitch_note,
        "pitch_cents_off": cents,
        "flute_probability": round(flute_probability, 4),
    }


def estimate_tuning_offset(rows: list[dict[str, Any]]) -> float:
    """Median cents deviation of labeled flute frames (instrument tuning), clipped to ±50."""
    deviations: list[float] = []
    for r in rows:
        label = SOUND_CLASSES[r["sound_class"]]
        if label == NO_FLUTE:
            continue
        hz = pitch_hz_from_audio(r["audio"])
        if hz is None:
            continue
        cents = _cents(hz, NOTE_FREQUENCIES_HZ[label])
        if abs(cents) <= 100.0:
            deviations.append(cents)
    if not deviations:
        return 0.0
    offset = float(np.median(deviations))
    return round(max(-MAX_TUNING_OFFSET_CENTS, min(MAX_TUNING_OFFSET_CENTS, offset)), 2)


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
    audio_schema: str = AUDIO_FEATURE_SCHEMA,
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
    if visual_schema != VISUAL_FEATURE_SCHEMA or audio_schema != AUDIO_FEATURE_SCHEMA:
        raise SkillMatchException(
            statuscode=400,
            message="Formato de features antiguo. Reprocesá los videos con altura (pitch) y manos v5 antes de entrenar.",
        )

    frames = feature_frames or [{"audio_features": audio_features, "visual_features": visual_features}]
    if len(frames) > 120:
        raise SkillMatchException(statuscode=400, message="Se permiten como máximo 120 fotogramas por muestra.")

    checked_frames = []
    voiced_frames = 0
    for frame in frames:
        audio = _validate_vector(frame["audio_features"], AUDIO_FEATURE_DIM, "de audio")
        visual = _validate_vector(frame["visual_features"], VISUAL_FEATURE_DIM, "visual")
        if sound_label == "flauta" and audio[IDX_VOICED] < 0.5:
            continue  # Silence/attack frames are not examples of the note.
        voiced_frames += int(audio[IDX_VOICED] >= 0.5)
        if posture_label == "correcta" and not _has_required_hands(visual, note_label):
            continue  # Missing landmarks are not examples of correct fingering.
        checked_frames.append({"audio_features": audio, "visual_features": visual})

    pitch_agreement: float | None = None
    if sound_label == "flauta":
        if voiced_frames < 3:
            raise SkillMatchException(
                statuscode=400,
                message="No se detectó sonido de flauta estable en la toma (menos de 3 fotogramas con altura). Repetí la toma.",
            )
        matches = sum(
            1 for f in checked_frames
            if nearest_flute_note(pitch_hz_from_audio(np.asarray(f["audio_features"])))[0] == note_label
        )
        pitch_agreement = round(matches / max(1, len(checked_frames)), 4)
        if pitch_agreement < MIN_PITCH_AGREEMENT:
            raise SkillMatchException(
                statuscode=400,
                message=(
                    f"La altura detectada no corresponde a la nota {note_label} "
                    f"(coincidencia {round(pitch_agreement * 100)}%). Repetí la toma."
                ),
            )

    if len(checked_frames) < 3:
        raise SkillMatchException(
            statuscode=400,
            message="Se necesitan al menos 3 fotogramas con las manos requeridas detectadas. La muestra no fue etiquetada.",
        )

    payload = {
        "audio_schema": AUDIO_FEATURE_SCHEMA,
        "visual_schema": VISUAL_FEATURE_SCHEMA,
        "feature_frames": checked_frames,
        "sample_id": str(sample.id),
        "participant_id": participant,
        "note_label": note_label,
        "sound_label": sound_label,
        "posture_label": posture_label,
        "pitch_agreement": pitch_agreement,
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
    return {
        k: payload[k]
        for k in ("sample_id", "participant_id", "note_label", "sound_label", "posture_label", "pitch_agreement")
    }


def _hands_present(visual: list[float] | np.ndarray) -> int:
    return int(visual[0] == 1) + int(visual[VISUAL_HAND_SLOT_DIM] == 1)


def _has_required_hands(visual: list[float] | np.ndarray, note: str | None) -> bool:
    count = _hands_present(visual)
    if note is None:
        return count >= 1
    return count >= (2 if note in TWO_HAND_NOTES else 1)


def _sound_class(lbl: dict[str, Any]) -> str:
    return lbl["note_label"] if lbl["sound_label"] == "flauta" and lbl.get("note_label") else NO_FLUTE


def _finger_labels(lbl: dict[str, Any]) -> np.ndarray | None:
    """Front-hole targets only for takes reviewed as correct fingering of a known note."""
    note = lbl.get("note_label")
    if lbl.get("posture_label") != "correcta" or note not in FRONT_HOLES:
        return None
    return np.asarray(FRONT_HOLES[note], dtype=np.float64)


async def _music_samples(db: AsyncSession) -> list[DatasetSample]:
    result = await db.execute(
        select(DatasetSample)
        .where(func.lower(DatasetSample.discipline).in_(MUSIC_DISCIPLINES))
        .order_by(DatasetSample.created_at.desc())
    )
    return list(result.scalars().all())


def _is_current_sidecar(lbl: dict[str, Any] | None) -> bool:
    return bool(
        lbl
        and lbl.get("audio_schema") == AUDIO_FEATURE_SCHEMA
        and lbl.get("visual_schema") == VISUAL_FEATURE_SCHEMA
        and len(lbl.get("audio_features", [])) == AUDIO_FEATURE_DIM
        and len(lbl.get("visual_features", [])) == VISUAL_FEATURE_DIM
        and len(lbl.get("feature_frames", [])) >= 3
    )


def _session_key(participant: str, created_at: datetime | None) -> str:
    day = created_at.astimezone(timezone.utc).date().isoformat() if created_at else "unknown"
    return f"{participant}|{day}"


def _labeled_rows(samples: list[DatasetSample]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    listing: list[dict[str, Any]] = []
    for s in samples:
        lbl = _read_labels(s.id)
        valid = _is_current_sidecar(lbl)
        listing.append({
            "id": str(s.id),
            "labeled": valid,
            "needs_reprocess": bool(lbl) and not valid,
            "participant_id": lbl.get("participant_id") if lbl else s.participant_id,
            "note_label": lbl.get("note_label") if lbl else None,
            "sound_label": lbl.get("sound_label") if lbl else None,
            "posture_label": lbl.get("posture_label") if lbl else None,
            "pitch_agreement": lbl.get("pitch_agreement") if lbl else None,
            "file_format": s.file_format,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        })
        if not valid or not lbl:
            continue
        fingers = _finger_labels(lbl)
        for frame in lbl["feature_frames"]:
            rows.append({
                "sample_id": str(s.id),
                "participant_id": lbl["participant_id"],
                "session": _session_key(lbl["participant_id"], s.created_at),
                "note_label": lbl.get("note_label"),
                "sound_class": SOUND_CLASSES.index(_sound_class(lbl)),
                "fingers": fingers,
                "audio": np.asarray(_validate_vector(frame["audio_features"], AUDIO_FEATURE_DIM, "de audio")),
                "visual": np.asarray(_validate_vector(frame["visual_features"], VISUAL_FEATURE_DIM, "visual")),
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
    sessions: set[str] = set()
    for r in rows:
        participants[r["participant_id"]] = participants.get(r["participant_id"], 0) + 1
        sessions.add(r["session"])
    finger_counts = {n: 0 for n in FLUTE_NOTES}
    for r in rows:
        if r["fingers"] is not None and r["note_label"] in finger_counts:
            finger_counts[r["note_label"]] += 1
    return {
        "samples": listing,
        "total_count": len(listing),
        "labeled_count": sum(s["labeled"] for s in listing),
        "unlabeled_count": sum(not s["labeled"] for s in listing),
        "needs_reprocess_count": sum(s["needs_reprocess"] for s in listing),
        "feature_frames_count": len(rows),
        "audio_schema": AUDIO_FEATURE_SCHEMA,
        "visual_schema": VISUAL_FEATURE_SCHEMA,
        "participants": participants,
        "sessions_count": len(sessions),
        "sound_class_counts": _counts(rows, "sound_class", SOUND_CLASSES),
        "finger_note_counts": finger_counts,
        "can_validate_independently": len(participants) >= 2,
    }


# --------------------------------------------------------------------------- #
# Evaluation split: participant -> session -> take
# --------------------------------------------------------------------------- #
def _hash_order(keys: set[str]) -> list[str]:
    return sorted(keys, key=lambda k: hashlib.sha256(k.encode("utf-8")).hexdigest())


def _split_rows(rows: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]]]:
    for mode, key in (("participant", "participant_id"), ("session", "session")):
        groups = {r[key] for r in rows}
        if len(groups) >= 2:
            ordered = _hash_order(groups)
            test_groups = set(ordered[: max(1, round(len(ordered) * TEST_FRACTION))])
            return (
                mode,
                [r for r in rows if r[key] not in test_groups],
                [r for r in rows if r[key] in test_groups],
            )

    # Single session: hold out whole takes per sound class, keeping every class in train.
    takes_by_class: dict[int, set[str]] = defaultdict(set)
    for r in rows:
        takes_by_class[r["sound_class"]].add(r["sample_id"])
    test_takes: set[str] = set()
    for takes in takes_by_class.values():
        if len(takes) >= 2:
            ordered = _hash_order(takes)
            test_takes.update(ordered[: min(len(ordered) - 1, max(1, round(len(ordered) * TEST_FRACTION)))])
    if not test_takes:
        return "none", list(rows), []
    return (
        "take",
        [r for r in rows if r["sample_id"] not in test_takes],
        [r for r in rows if r["sample_id"] in test_takes],
    )


def _take_weights(rows: list[dict[str, Any]]) -> np.ndarray:
    """Every take (video) weighs the same regardless of how many frames it kept."""
    frames_per_take = Counter(r["sample_id"] for r in rows)
    return np.asarray([1.0 / frames_per_take[r["sample_id"]] for r in rows], dtype=np.float64)


# --------------------------------------------------------------------------- #
# Training: sound MLP (softmax) + finger MLP (7 sigmoids)
# --------------------------------------------------------------------------- #
def _adam_step(params, grads, m_state, v_state, epoch, lr, beta1=0.9, beta2=0.999, eps=1e-8) -> None:
    for k in params:
        m_state[k] = beta1 * m_state[k] + (1.0 - beta1) * grads[k]
        v_state[k] = beta2 * v_state[k] + (1.0 - beta2) * (grads[k] ** 2)
        m_hat = m_state[k] / (1.0 - beta1 ** epoch)
        v_hat = v_state[k] / (1.0 - beta2 ** epoch)
        params[k] -= lr * m_hat / (np.sqrt(v_hat) + eps)


def _train_mlp(
    x: np.ndarray,
    y: np.ndarray,
    n_classes: int,
    hidden_dim: int = 48,
    epochs: int = 350,
    lr: float = 0.02,
    reg: float = 1e-3,
    frame_weights: np.ndarray | None = None,
) -> tuple[dict[str, np.ndarray], list[dict[str, float]]]:
    mean = x.mean(axis=0)
    scale = np.maximum(x.std(axis=0), 1e-2)
    z = (x - mean) / scale
    n_samples, in_dim = z.shape

    # Class-balanced weights on top of per-take weights: every note and every take count equally.
    base = frame_weights if frame_weights is not None else np.ones(n_samples)
    class_mass = np.bincount(y, weights=base, minlength=n_classes)
    sample_weights = base / np.maximum(class_mass[y], 1e-12)
    sample_weights /= sample_weights.sum()

    rng = np.random.default_rng(42)
    params = {
        "W1": rng.normal(0.0, math.sqrt(2.0 / in_dim), size=(in_dim, hidden_dim)),
        "b1": np.zeros(hidden_dim),
        "W2": rng.normal(0.0, math.sqrt(1.0 / hidden_dim), size=(hidden_dim, n_classes)),
        "b2": np.zeros(n_classes),
    }
    m_state = {k: np.zeros_like(v) for k, v in params.items()}
    v_state = {k: np.zeros_like(v) for k, v in params.items()}
    onehot = np.eye(n_classes)[y]
    history: list[dict[str, float]] = []

    for epoch in range(1, epochs + 1):
        h_pre = z @ params["W1"] + params["b1"]
        h = np.maximum(h_pre, 0.0)
        logits = h @ params["W2"] + params["b2"]
        logits -= logits.max(axis=1, keepdims=True)
        probs = np.exp(logits)
        probs /= probs.sum(axis=1, keepdims=True)
        if epoch == 1 or epoch % 70 == 0 or epoch == epochs:
            loss = float(-np.sum(sample_weights * np.log(probs[np.arange(n_samples), y] + 1e-12)))
            history.append({"epoch": epoch, "loss": round(loss, 4)})
        d_logits = (probs - onehot) * sample_weights[:, None]
        d_h = (d_logits @ params["W2"].T) * (h_pre > 0.0)
        grads = {
            "W2": h.T @ d_logits + reg * params["W2"],
            "b2": d_logits.sum(axis=0),
            "W1": z.T @ d_h + reg * params["W1"],
            "b1": d_h.sum(axis=0),
        }
        _adam_step(params, grads, m_state, v_state, epoch, lr)

    return {"mean": mean, "scale": scale, **params}, history


def _finger_mask_operands() -> tuple[np.ndarray, np.ndarray]:
    """mask = x @ P + c: presence columns stay, the rest of a slot is zeroed when its hand is absent."""
    p = np.zeros((VISUAL_FEATURE_DIM, VISUAL_FEATURE_DIM))
    c = np.zeros(VISUAL_FEATURE_DIM)
    for slot in (0, 1):
        off = slot * VISUAL_HAND_SLOT_DIM
        p[off, off + 1 : off + VISUAL_HAND_SLOT_DIM] = 1.0
        c[off] = 1.0
    return p, c


def _finger_inputs(params: dict[str, np.ndarray], x: np.ndarray) -> np.ndarray:
    z = (x - params["fingers_mean"]) / params["fingers_scale"]
    mask = x @ params["fingers_P"] + params["fingers_c"]
    return z * mask


def _finger_probs(params: dict[str, np.ndarray], x: np.ndarray) -> np.ndarray:
    z = _finger_inputs(params, x)
    h = np.maximum(z @ params["fingers_W1"] + params["fingers_b1"], 0.0)
    logits = h @ params["fingers_W2"] + params["fingers_b2"]
    return 1.0 / (1.0 + np.exp(-logits))


def _train_finger_mlp(
    x: np.ndarray,
    y: np.ndarray,
    frame_weights: np.ndarray,
    hidden_dim: int = 32,
    epochs: int = 400,
    lr: float = 0.01,
    reg: float = 1e-3,
) -> tuple[dict[str, np.ndarray], list[dict[str, float]]]:
    """Multi-label (7 front holes) MLP with BCE; absent hand slots are masked out."""
    p_mat, c_vec = _finger_mask_operands()
    present = np.ones_like(x)
    for slot in (0, 1):
        off = slot * VISUAL_HAND_SLOT_DIM
        present[:, off + 1 : off + VISUAL_HAND_SLOT_DIM] = x[:, [off]]
    # Statistics only over frames where the slot's hand is present.
    counts = np.maximum(present.sum(axis=0), 1.0)
    mean = (x * present).sum(axis=0) / counts
    var = (((x - mean) * present) ** 2).sum(axis=0) / counts
    scale = np.maximum(np.sqrt(var), 0.05)

    base = {"fingers_mean": mean, "fingers_scale": scale, "fingers_P": p_mat, "fingers_c": c_vec}
    z = _finger_inputs(base, x)
    weights = frame_weights / frame_weights.sum()

    rng = np.random.default_rng(42)
    in_dim = z.shape[1]
    params = {
        "W1": rng.normal(0.0, math.sqrt(2.0 / in_dim), size=(in_dim, hidden_dim)),
        "b1": np.zeros(hidden_dim),
        "W2": rng.normal(0.0, math.sqrt(1.0 / hidden_dim), size=(hidden_dim, N_HOLES)),
        "b2": np.zeros(N_HOLES),
    }
    m_state = {k: np.zeros_like(v) for k, v in params.items()}
    v_state = {k: np.zeros_like(v) for k, v in params.items()}
    history: list[dict[str, float]] = []
    for epoch in range(1, epochs + 1):
        h_pre = z @ params["W1"] + params["b1"]
        h = np.maximum(h_pre, 0.0)
        probs = 1.0 / (1.0 + np.exp(-(h @ params["W2"] + params["b2"])))
        if epoch == 1 or epoch % 80 == 0 or epoch == epochs:
            bce = -(y * np.log(probs + 1e-12) + (1 - y) * np.log(1 - probs + 1e-12)).mean(axis=1)
            history.append({"epoch": epoch, "loss": round(float(np.sum(weights * bce)), 4)})
        d_logits = (probs - y) * weights[:, None] / N_HOLES
        d_h = (d_logits @ params["W2"].T) * (h_pre > 0.0)
        grads = {
            "W2": h.T @ d_logits + reg * params["W2"],
            "b2": d_logits.sum(axis=0),
            "W1": z.T @ d_h + reg * params["W1"],
            "b1": d_h.sum(axis=0),
        }
        _adam_step(params, grads, m_state, v_state, epoch, lr)

    return {"mean": mean, "scale": scale, "P": p_mat, "c": c_vec, **params}, history


def _head_probs(params: dict[str, np.ndarray], head: str, x: np.ndarray) -> np.ndarray:
    z = (x - params[f"{head}_mean"]) / params[f"{head}_scale"]
    h = np.maximum(z @ params[f"{head}_W1"] + params[f"{head}_b1"], 0.0)
    logits = h @ params[f"{head}_W2"] + params[f"{head}_b2"]
    logits -= logits.max(axis=1, keepdims=True)
    e = np.exp(logits)
    return e / e.sum(axis=1, keepdims=True)


# --------------------------------------------------------------------------- #
# Posture decision (shared by exam and free mode)
# --------------------------------------------------------------------------- #
def posture_decision(covered_probs: np.ndarray, note: str | None) -> dict[str, Any]:
    """Compare camera-estimated front holes with the note's fingering.

    A hole is a mismatch only when the camera is confident it is in the wrong
    state; holes inside FINGER_UNCERTAIN_BAND are uncertain (match = None).
    Posture is OK with no mismatches and at most MAX_UNCERTAIN_HOLES uncertain.
    """
    expected = FRONT_HOLES.get(note) if note else None
    low, high = FINGER_UNCERTAIN_BAND
    states = []
    mismatched: list[int] = []
    uncertain: list[int] = []
    matches = 0
    for i in range(N_HOLES):
        covered_p = round(float(covered_probs[i]), 4)
        if expected is None:
            states.append({"hole": i + 1, "expected": None, "covered_probability": covered_p, "match": None})
            continue
        matches += int((covered_p >= DECISION_THRESHOLD) == expected[i])
        if low < covered_p < high:
            uncertain.append(i + 1)
            match: bool | None = None
        else:
            match = (covered_p >= high) == expected[i]
            if not match:
                mismatched.append(i + 1)
        states.append({"hole": i + 1, "expected": expected[i], "covered_probability": covered_p, "match": match})
    if expected is None:
        return {
            "finger_states": states, "finger_match_ratio": None,
            "mismatched_holes": [], "uncertain_holes": [], "posture_ok": None,
        }
    return {
        "finger_states": states,
        "finger_match_ratio": round(matches / N_HOLES, 4),
        "mismatched_holes": mismatched,
        "uncertain_holes": uncertain,
        "posture_ok": not mismatched and len(uncertain) <= MAX_UNCERTAIN_HOLES,
    }


# --------------------------------------------------------------------------- #
# Metrics
# --------------------------------------------------------------------------- #
def _accuracy_and_confusion(pred: list[int], true: list[int], n: int) -> tuple[float | None, list[list[int]]]:
    confusion = [[0] * n for _ in range(n)]
    for p, t in zip(pred, true):
        confusion[t][p] += 1
    if not true:
        return None, confusion
    return round(sum(1 for p, t in zip(pred, true) if p == t) / len(true), 4), confusion


def _per_class_report(pred: list[int], true: list[int], classes: list[str]) -> dict[str, dict[str, Any]]:
    report: dict[str, dict[str, Any]] = {}
    for idx, name in enumerate(classes):
        tp = sum(1 for p, t in zip(pred, true) if p == idx and t == idx)
        predicted = sum(1 for p in pred if p == idx)
        support = sum(1 for t in true if t == idx)
        report[name] = {
            "precision": round(tp / predicted, 4) if predicted else None,
            "recall": round(tp / support, 4) if support else None,
            "support": support,
        }
    return report


def _sound_frame_predictions(params, rows, tuning_offset) -> list[int]:
    if not rows:
        return []
    x = np.stack([r["audio"] for r in rows])
    probs = _head_probs(params, "sound", x)
    return [
        SOUND_CLASSES.index(sound_decision(x[i], probs[i], tuning_offset)["sound_class"])
        for i in range(len(rows))
    ]


def _take_votes(rows: list[dict[str, Any]], frame_values: list[Any]) -> dict[str, list[Any]]:
    votes: dict[str, list[Any]] = defaultdict(list)
    for r, v in zip(rows, frame_values):
        votes[r["sample_id"]].append(v)
    return votes


def _sound_metrics(params, train_rows, test_rows, tuning_offset, history) -> dict[str, Any]:
    n = len(SOUND_CLASSES)
    train_pred = _sound_frame_predictions(params, train_rows, tuning_offset)
    train_acc, _ = _accuracy_and_confusion(train_pred, [r["sound_class"] for r in train_rows], n)
    test_pred = _sound_frame_predictions(params, test_rows, tuning_offset)
    test_true = [r["sound_class"] for r in test_rows]
    frame_acc, _ = _accuracy_and_confusion(test_pred, test_true, n)

    # Take-level: majority vote of frame decisions inside each held-out video.
    votes = _take_votes(test_rows, test_pred)
    take_true = {r["sample_id"]: r["sound_class"] for r in test_rows}
    take_pid = {r["sample_id"]: r["participant_id"] for r in test_rows}
    take_ids = sorted(votes)
    take_pred = [Counter(votes[t]).most_common(1)[0][0] for t in take_ids]
    take_labels = [take_true[t] for t in take_ids]
    sample_acc, confusion = _accuracy_and_confusion(take_pred, take_labels, n)

    train_take_labels = {r["sample_id"]: r["sound_class"] for r in train_rows}
    majority = Counter(train_take_labels.values()).most_common(1)[0][0] if train_take_labels else 0
    baseline, _ = _accuracy_and_confusion([majority] * len(take_labels), take_labels, n)

    per_participant: dict[str, float | None] = {}
    for pid in sorted({take_pid[t] for t in take_ids}):
        idx = [i for i, t in enumerate(take_ids) if take_pid[t] == pid]
        per_participant[pid], _ = _accuracy_and_confusion(
            [take_pred[i] for i in idx], [take_labels[i] for i in idx], n
        )
    return {
        "classes": SOUND_CLASSES,
        "decision": "pitch_first",
        "train_accuracy": train_acc,
        "test_accuracy": frame_acc,
        "sample_test_accuracy": sample_acc,
        "majority_baseline_accuracy": baseline,
        "confusion_matrix": confusion,
        "per_class": _per_class_report(take_pred, take_labels, SOUND_CLASSES),
        "per_participant": per_participant,
        "train_class_counts": _counts(train_rows, "sound_class", SOUND_CLASSES),
        "test_takes": len(take_ids),
        "loss_history": history,
    }


def _finger_metrics(params, train_rows, test_rows, history) -> dict[str, Any]:
    def per_hole_accuracy(rows):
        if not rows:
            return None, None
        pred = _finger_probs(params, np.stack([r["visual"] for r in rows])) >= DECISION_THRESHOLD
        true = np.stack([r["fingers"] for r in rows]) >= 0.5
        return (pred == true).mean(axis=0), pred

    train_hole_acc, _ = per_hole_accuracy(train_rows)
    test_hole_acc, test_pred = per_hole_accuracy(test_rows)
    train_true = np.stack([r["fingers"] for r in train_rows]) >= 0.5
    majority_state = train_true.mean(axis=0) >= 0.5
    baseline_per_hole = None
    sample_acc = None
    if test_rows:
        test_true = np.stack([r["fingers"] for r in test_rows]) >= 0.5
        baseline_per_hole = (test_true == majority_state).mean(axis=0)
        frame_ok = (test_pred == test_true).all(axis=1).tolist()
        votes = _take_votes(test_rows, frame_ok)
        sample_acc = round(sum(1 for v in votes.values() if np.mean(v) >= 0.5) / len(votes), 4)

    def r4(value):
        return round(float(value), 4) if value is not None else None

    return {
        "holes": list(range(1, N_HOLES + 1)),
        "uncertain_band": list(FINGER_UNCERTAIN_BAND),
        "train_accuracy": r4(train_hole_acc.mean()) if train_hole_acc is not None else None,
        "test_accuracy": r4(test_hole_acc.mean()) if test_hole_acc is not None else None,
        "majority_baseline_accuracy": r4(baseline_per_hole.mean()) if baseline_per_hole is not None else None,
        "sample_test_accuracy": sample_acc,
        "per_hole": [
            {
                "hole": i + 1,
                "test_accuracy": r4(test_hole_acc[i]) if test_hole_acc is not None else None,
                "baseline": r4(baseline_per_hole[i]) if baseline_per_hole is not None else None,
                "covered_count": int(train_true[:, i].sum()),
                "open_count": int((~train_true[:, i]).sum()),
            }
            for i in range(N_HOLES)
        ],
        "train_frames": len(train_rows),
        "test_frames": len(test_rows),
        "loss_history": history,
    }


def _passes_sound_gate(metrics: dict[str, Any]) -> bool:
    """A model may serve only if its take-level sound accuracy beats the majority baseline."""
    sound = metrics.get("sound") or {}
    accuracy = sound.get("sample_test_accuracy")
    if metrics.get("split_mode") == "none" or accuracy is None:
        return True  # Experimental: nothing held out to compare against.
    baseline = sound.get("majority_baseline_accuracy")
    return baseline is None or accuracy > baseline


def _finger_head_reliable(metrics: dict[str, Any]) -> bool:
    fingers = metrics.get("fingers") or {}
    accuracy = fingers.get("test_accuracy")
    baseline = fingers.get("majority_baseline_accuracy")
    return accuracy is None or baseline is None or accuracy > baseline


_SPLIT_NOTES = {
    "participant": "Precisión medida sobre personas que no participaron del entrenamiento.",
    "session": "Intra-persona: medido sobre otra sesión (otro día) de los mismos participantes.",
    "take": "Intra-persona: medido sobre otras tomas de la misma sesión (optimista).",
    "none": "Modo experimental: no hay tomas suficientes para separar una prueba. Grabá 2+ tomas por nota.",
}


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
                "Se necesitan al menos 4 videos etiquetados con altura (pitch) y manos v5. "
                "Reprocesá los videos anteriores desde el estudio."
            ),
        )

    split_mode, train_rows, test_rows = _split_rows(rows)
    if len({r["sound_class"] for r in train_rows}) < 2:
        raise SkillMatchException(
            statuscode=400,
            message=(
                "El conjunto de entrenamiento necesita al menos 2 clases de sonido. "
                "Graba al menos 2 notas distintas (o ejemplos negativos de voz/ruido)."
            ),
        )
    finger_train = [r for r in train_rows if r["fingers"] is not None]
    finger_test = [r for r in test_rows if r["fingers"] is not None]
    if len({r["note_label"] for r in finger_train}) < 2:
        raise SkillMatchException(
            statuscode=400,
            message="Se necesitan tomas con digitación correcta de al menos 2 notas para entrenar los dedos.",
        )

    tuning_offset = estimate_tuning_offset(train_rows)
    sound_params, sound_history = _train_mlp(
        np.stack([r["audio"] for r in train_rows]),
        np.array([r["sound_class"] for r in train_rows], dtype=np.int64),
        len(SOUND_CLASSES),
        frame_weights=_take_weights(train_rows),
    )
    finger_params, finger_history = _train_finger_mlp(
        np.stack([r["visual"] for r in finger_train]),
        np.stack([r["fingers"] for r in finger_train]),
        _take_weights(finger_train),
    )

    onnx_bytes = build_flute_onnx({"sound": sound_params, "fingers": finger_params})
    # Everything below uses parameters read back from the exported ONNX artifact.
    params = load_onnx_initializers(onnx_bytes)

    sound_metrics = _sound_metrics(params, train_rows, test_rows, tuning_offset, sound_history)
    finger_metrics = _finger_metrics(params, finger_train, finger_test, finger_history)

    bench = test_rows or train_rows
    t0 = time.perf_counter()
    for i in range(LATENCY_RUNS):
        row = bench[i % len(bench)]
        _head_probs(params, "sound", row["audio"][None, :])
        _finger_probs(params, row["visual"][None, :])
    latency_ms = (time.perf_counter() - t0) / LATENCY_RUNS * 1000.0

    if version_tag and version_tag.strip():
        version_str = version_tag.strip().replace(" ", "-")
    else:
        existing = await db.scalar(
            select(func.count()).select_from(ModelVersion).where(ModelVersion.nombre == MODEL_NAME)
        )
        version_str = f"flute-pitch-3.{(existing or 0) + 1}.0"

    onnx_key = f"models/flute/{MODEL_NAME}_{version_str}.onnx"
    storage_uri, onnx_sha = garage_s3_storage.put_object_bytes(
        object_key=onnx_key, payload=onnx_bytes, content_type="application/octet-stream",
    )

    metrics: dict[str, Any] = {
        "audio_schema": AUDIO_FEATURE_SCHEMA,
        "visual_schema": VISUAL_FEATURE_SCHEMA,
        "audio_mode": "pitch_first_timbre_confirm",
        "architecture": "sound_mlp_finger_multilabel_onnx",
        "metric_unit": "take",
        "split_mode": split_mode,
        "validated": split_mode == "participant",
        "validation_note": _SPLIT_NOTES[split_mode],
        "train_participants": sorted({r["participant_id"] for r in train_rows}),
        "test_participants": sorted({r["participant_id"] for r in test_rows}),
        "train_samples": len(train_rows),
        "test_samples": len(test_rows),
        "train_takes": len({r["sample_id"] for r in train_rows}),
        "test_takes": len({r["sample_id"] for r in test_rows}),
        "labeled_samples": sum(s["labeled"] for s in listing),
        "unlabeled_samples": sum(not s["labeled"] for s in listing),
        "tuning_offset_cents": tuning_offset,
        "pitch_tolerance_cents": PITCH_TOLERANCE_CENTS,
        "sound": sound_metrics,
        "fingers": finger_metrics,
        "latency_ms_per_inference": round(latency_ms, 4),
        "latency_runs": LATENCY_RUNS,
        "onnx_sha256": onnx_sha,
        "onnx_bytes": len(onnx_bytes),
        "feature_dims": {"audio": AUDIO_FEATURE_DIM, "visual": VISUAL_FEATURE_DIM},
        "decision_threshold": DECISION_THRESHOLD,
        # Informational tag only: activation is global for MODEL_NAME, not filtered by skill.
        "skill_id": str(skill_id) if skill_id else None,
    }

    gate_ok = _passes_sound_gate(metrics)
    metrics["activation_blocked_reason"] = (
        None if gate_ok else "El sonido no supera la línea base por mayoría en las tomas de prueba."
    )
    should_activate = activate and gate_ok
    if should_activate:
        await db.execute(update(ModelVersion).where(ModelVersion.nombre == MODEL_NAME).values(activa=False))
    row = ModelVersion(
        id=uuid.uuid4(), nombre=MODEL_NAME, version=version_str,
        ruta_onnx=storage_uri, metricas=metrics, activa=should_activate,
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
        "created_at": r.created_at.isoformat() if getattr(r, "created_at", None) else None,
    }


async def list_flute_model_versions(db: AsyncSession) -> list[dict[str, Any]]:
    result = await db.execute(
        select(ModelVersion)
        .where(ModelVersion.nombre == MODEL_NAME)
        .order_by(desc(ModelVersion.activa), desc(ModelVersion.created_at))
    )
    return [_model_dict(r) for r in result.scalars().all()]


def _is_current_model(metrics: dict[str, Any]) -> bool:
    return (
        metrics.get("visual_schema") == VISUAL_FEATURE_SCHEMA
        and metrics.get("audio_schema") == AUDIO_FEATURE_SCHEMA
    )


async def activate_flute_model(db: AsyncSession, model_id: uuid.UUID) -> dict[str, Any]:
    target = await db.scalar(
        select(ModelVersion).where(ModelVersion.id == model_id, ModelVersion.nombre == MODEL_NAME)
    )
    if target is None:
        raise SkillMatchException(statuscode=404, message="Versión de modelo de flauta no encontrada.")
    metrics = target.metricas or {}
    if not _is_current_model(metrics):
        raise SkillMatchException(
            statuscode=409,
            message="Este modelo usa un formato anterior. Reprocesá los videos y entrená una nueva versión.",
        )
    if not _passes_sound_gate(metrics):
        raise SkillMatchException(
            statuscode=409,
            message="Este modelo no supera la línea base de sonido en las tomas de prueba; no se puede activar.",
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


async def infer_flute(
    db: AsyncSession,
    audio_features: list[float],
    visual_features: list[float],
    visual_schema: str,
    audio_schema: str = AUDIO_FEATURE_SCHEMA,
    target_note: str | None = None,
) -> dict[str, Any]:
    if target_note is not None and target_note not in FLUTE_NOTES:
        raise SkillMatchException(statuscode=400, message=f"Nota objetivo inválida: {target_note}.")
    audio = np.asarray(_validate_vector(audio_features, AUDIO_FEATURE_DIM, "de audio"))
    visual = np.asarray(_validate_vector(visual_features, VISUAL_FEATURE_DIM, "visual"))

    model = await db.scalar(
        select(ModelVersion).where(ModelVersion.nombre == MODEL_NAME, ModelVersion.activa.is_(True))
    )
    if model is None:
        raise SkillMatchException(
            statuscode=409,
            message="No hay un modelo de flauta activo. Entrená y activá uno en el Estudio de Entrenamiento.",
        )
    metrics = model.metricas or {}
    if (
        visual_schema != VISUAL_FEATURE_SCHEMA
        or audio_schema != AUDIO_FEATURE_SCHEMA
        or not _is_current_model(metrics)
    ):
        raise SkillMatchException(
            statuscode=409,
            message="El modelo activo usa un formato anterior. Reprocesá los videos y entrená una nueva versión.",
        )

    params = _params_for(model)
    sound_p = _head_probs(params, "sound", audio[None, :])[0]
    covered_p = _finger_probs(params, visual[None, :])[0]
    sound = sound_decision(audio, sound_p, float(metrics.get("tuning_offset_cents") or 0.0))
    detected_note = sound["sound_class"] if sound["sound_class"] != NO_FLUTE else None
    posture_note = target_note or detected_note

    posture = posture_decision(covered_p, posture_note)
    posture_reason = None
    if posture_note is None:
        posture_reason = "Sin nota para comparar la digitación: tocá una nota."
    elif not _has_required_hands(visual, posture_note):
        posture_reason = "Articulaciones insuficientes: muestra las manos requeridas frente a la cámara."
    elif not _finger_head_reliable(metrics):
        posture_reason = "El modelo de dedos todavía no supera la línea base en las tomas de prueba."
    posture_ok = None if posture_reason else posture["posture_ok"]

    if target_note is not None:
        sound_ok = sound["sound_class"] == target_note
    else:
        sound_ok = detected_note is not None
    combined_match = bool(target_note is None and detected_note is not None and posture_ok is True)
    validated = bool(metrics.get("validated", False))

    return {
        "model_id": str(model.id),
        "model_version": model.version,
        "validated": validated,
        "experimental": not validated,
        "target_note": target_note,
        **sound,
        "sound_ok": sound_ok,
        "top_sound_classes": _top_predictions(sound_p, SOUND_CLASSES, k=3),
        "posture_ok": posture_ok,
        "posture_evaluable": posture_reason is None,
        "posture_reason": posture_reason,
        "finger_states": posture["finger_states"],
        "finger_match_ratio": posture["finger_match_ratio"],
        "mismatched_holes": posture["mismatched_holes"],
        "uncertain_holes": posture["uncertain_holes"],
        "combined_note": detected_note if combined_match else None,
        "combined_match": combined_match,
    }


# --------------------------------------------------------------------------- #
# Minimal ONNX (protobuf) writer/reader — no external dependency
#   sound:   Sub(mean) -> Div(scale) -> MatMul(W1) -> Add(b1) -> Relu -> MatMul(W2) -> Add(b2) -> Softmax
#   fingers: Sub(mean) -> Div(scale) -> Mul(MatMul(x, P) + c) -> MatMul(W1) -> Add(b1) -> Relu
#            -> MatMul(W2) -> Add(b2) -> Sigmoid
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


def _mlp_nodes(head: str, z_name: str) -> tuple[bytes, str]:
    nodes = _f_bytes(1, _node("MatMul", [z_name, f"{head}_W1"], [f"{head}_m1"], f"{head}_matmul1"))
    nodes += _f_bytes(1, _node("Add", [f"{head}_m1", f"{head}_b1"], [f"{head}_hpre"], f"{head}_add1"))
    nodes += _f_bytes(1, _node("Relu", [f"{head}_hpre"], [f"{head}_h"], f"{head}_relu"))
    nodes += _f_bytes(1, _node("MatMul", [f"{head}_h", f"{head}_W2"], [f"{head}_m2"], f"{head}_matmul2"))
    nodes += _f_bytes(1, _node("Add", [f"{head}_m2", f"{head}_b2"], [f"{head}_logits"], f"{head}_add2"))
    return nodes, f"{head}_logits"


def build_flute_onnx(heads: dict[str, dict[str, np.ndarray]]) -> bytes:
    nodes = b""
    inits = b""

    sound = heads["sound"]
    for key in ("mean", "scale", "W1", "b1", "W2", "b2"):
        inits += _f_bytes(5, _tensor_proto(f"sound_{key}", sound[key]))
    nodes += _f_bytes(1, _node("Sub", ["audio_features", "sound_mean"], ["sound_c"], "sound_sub"))
    nodes += _f_bytes(1, _node("Div", ["sound_c", "sound_scale"], ["sound_z"], "sound_div"))
    mlp, logits = _mlp_nodes("sound", "sound_z")
    nodes += mlp
    axis_attr = _f_bytes(5, _f_str(1, "axis") + _f_varint(3, 1) + _f_varint(20, 2))
    nodes += _f_bytes(1, _node("Softmax", [logits], ["sound_probs"], "sound_softmax", axis_attr))

    fingers = heads["fingers"]
    for key in ("mean", "scale", "P", "c", "W1", "b1", "W2", "b2"):
        inits += _f_bytes(5, _tensor_proto(f"fingers_{key}", fingers[key]))
    nodes += _f_bytes(1, _node("Sub", ["visual_features", "fingers_mean"], ["fingers_cen"], "fingers_sub"))
    nodes += _f_bytes(1, _node("Div", ["fingers_cen", "fingers_scale"], ["fingers_z0"], "fingers_div"))
    nodes += _f_bytes(1, _node("MatMul", ["visual_features", "fingers_P"], ["fingers_pm"], "fingers_presence"))
    nodes += _f_bytes(1, _node("Add", ["fingers_pm", "fingers_c"], ["fingers_mask"], "fingers_mask_add"))
    nodes += _f_bytes(1, _node("Mul", ["fingers_z0", "fingers_mask"], ["fingers_z"], "fingers_mask_mul"))
    mlp, logits = _mlp_nodes("fingers", "fingers_z")
    nodes += mlp
    nodes += _f_bytes(1, _node("Sigmoid", [logits], ["finger_covered_probs"], "fingers_sigmoid"))

    outputs = _f_bytes(12, _value_info("sound_probs", ["N", int(sound["b2"].shape[0])]))
    outputs += _f_bytes(12, _value_info("finger_covered_probs", ["N", int(fingers["b2"].shape[0])]))
    graph = (
        nodes
        + _f_str(2, "skillmatch_flute_pitch_fingers")
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


FLUTE_VARIATIONS = ("sostenida", "rapida", "angulo_suave")


def _infer_variation_from_sample(sample: DatasetSample) -> str:
    if sample.surface:
        return sample.surface
    challenge = (sample.challenge or "").lower()
    for var in FLUTE_VARIATIONS:
        if var in challenge:
            return var
    return "sostenida"
