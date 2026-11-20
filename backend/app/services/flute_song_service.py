"""
Flute song mode ("Canción") for the admin live validator.

- Catalog: songs live in code, stored in beats (quarter note = 1 beat);
  seconds = beats * 60 / tempo_bpm.
- Scoring (pure, see odd/tasks/flute-song-mode.md "Scoring rules"): the
  measured pitch decides each note; latency is compensated from the first
  voiced onset; repeated notes are timed by their RMS dip (articulation).
  With an active current flute model the MLP confirms the sound is a flute and
  the finger head judges fingering (25 % of the total when evaluable).
- Pitch and fingering logic is reused from `flute_training_service`.
"""
from __future__ import annotations

import bisect
import copy
from collections import Counter
from typing import Any

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import SkillMatchException
from app.services import flute_training_service as fts
from app.services.flute_training_service import (
    AUDIO_FEATURE_DIM,
    AUDIO_FEATURE_SCHEMA,
    FRONT_HOLES,
    MODEL_NAME,
    NO_FLUTE,
    SOUND_CLASSES,
    VISUAL_FEATURE_DIM,
    VISUAL_FEATURE_SCHEMA,
    ModelVersion,
    _finger_head_reliable,
    _has_required_hands,
    _is_current_model,
    _validate_vector,
    nearest_flute_note,
    posture_decision,
)

# --------------------------------------------------------------------------- #
# Catalog
# --------------------------------------------------------------------------- #
_HIMNO_PASS_1: tuple[tuple[str, float, float], ...] = (
    ("MI", 0, 1), ("MI", 1, 1), ("FA", 2, 1), ("SOL", 3, 1), ("SOL", 4, 1),
    ("FA", 5, 1), ("MI", 6, 1), ("RE", 7, 1), ("DO", 8, 1), ("DO", 9, 1),
    ("RE", 10, 1), ("MI", 11, 1), ("MI", 12, 1), ("RE", 13, 1), ("RE", 14, 2),
)
# Second pass ends "re do do" (as in the printed score) and starts at beat 16.
_HIMNO_PASS_2 = _HIMNO_PASS_1[:12] + (("RE", 12, 1), ("DO", 13, 1), ("DO", 14, 2))
_HIMNO_PASS_2_OFFSET_BEATS = 16


def _song(
    song_id: str,
    title: str,
    image: str,
    passes: list[tuple[tuple[tuple[str, float, float], ...], float]],
    default_bpm: int = 120,
    min_bpm: int = 60,
    max_bpm: int = 120,
    beats_per_bar: int = 4,
) -> dict[str, Any]:
    notes: list[dict[str, Any]] = []
    for pass_number, (pass_notes, offset) in enumerate(passes, start=1):
        for note, start, duration in pass_notes:
            notes.append({
                "index": len(notes),
                "pass": pass_number,
                "note": note,
                "start_beats": start + offset,
                "duration_beats": duration,
            })
    return {
        "id": song_id,
        "title": title,
        "default_bpm": default_bpm,
        "min_bpm": min_bpm,
        "max_bpm": max_bpm,
        "beats_per_bar": beats_per_bar,
        "image": image,
        "notes": notes,
    }


FLUTE_SONGS: dict[str, dict[str, Any]] = {
    "himno_alegria": _song(
        "himno_alegria",
        "Himno a la Alegría",
        "/flute-songs/himno_la_alegria.png",
        [(_HIMNO_PASS_1, 0), (_HIMNO_PASS_2, _HIMNO_PASS_2_OFFSET_BEATS)],
    ),
}


def list_flute_songs() -> list[dict[str, Any]]:
    return [copy.deepcopy(song) for song in FLUTE_SONGS.values()]


# --------------------------------------------------------------------------- #
# Scoring rules
# --------------------------------------------------------------------------- #
MIN_VOICED_RUN = 3
LATENCY_CLAMP_MS = (-250.0, 500.0)
INNER_MARGIN = 0.2
MIN_VOICED_SHARE = 0.3
ONSET_SEARCH_S = 0.25
TIMING_TOLERANCE_MS = 150.0
DIP_RATIO = 0.5
MIN_PITCH_SHARE = 0.5
FLUTE_THRESHOLD = 0.5
MIN_POSTURE_FRAMES = 2
POSTURE_FRAME_SHARE = 0.5
SOUND_WEIGHT = 0.75
APPROVAL_SCORE = 80.0
_EPS = 1e-6

REASON_NO_MODEL = "Digitación no evaluable: no hay un modelo de flauta activo; solo se evalúa el sonido."
REASON_UNRELIABLE = "Digitación no evaluable: el modelo de dedos todavía no supera la línea base en las tomas de prueba."
REASON_HANDS = "Digitación no evaluable: muestra las manos requeridas frente a la cámara."


def _voiced(hz: Any) -> bool:
    return hz is not None and float(hz) > 0


def _latency_offset_s(times: list[float], voiced: list[bool], first_start_s: float) -> float:
    """Rule 1: first run of >= 3 voiced frames vs the first expected start, clamped."""
    run = 0
    for i, is_voiced in enumerate(voiced):
        run = run + 1 if is_voiced else 0
        if run == MIN_VOICED_RUN:
            offset_ms = (times[i - MIN_VOICED_RUN + 1] - first_start_s) * 1000.0
            low, high = LATENCY_CLAMP_MS
            return max(low, min(high, offset_ms)) / 1000.0
    return 0.0


def _range(times: list[float], lo: float, hi: float) -> range:
    return range(bisect.bisect_left(times, lo - _EPS), bisect.bisect_right(times, hi + _EPS))


def _dip_onset(times: list[float], rms: list[float], search: range, threshold: float) -> tuple[float | None, bool]:
    """Rule 3 (repeated notes): end of the first RMS dip below `threshold` inside `search`."""
    if threshold <= 0:
        return None, False
    for k in search:
        if rms[k] < threshold:
            j = k
            while j < len(times) and rms[j] < threshold:
                j += 1
            return (times[j] if j < len(times) else None), True
    return None, False


def _hole_state_seen(per_hole: list[dict[str, Any]], hole: int, covered: bool) -> bool:
    entry = next((h for h in per_hole if h.get("hole") == hole), None)
    if entry is None:
        return False
    return int(entry.get("covered_count" if covered else "open_count") or 0) > 0


def _round(value: float | None, digits: int) -> float | None:
    return None if value is None else round(float(value), digits)


def _message(approved: bool, correct: int, total: int, posture_score: float | None, total_score: float) -> str:
    verdict = "Aprobado" if approved else "Reprobado"
    if posture_score is None:
        return f"{verdict}: {correct} de {total} notas correctas ({round(total_score)}%)."
    return (
        f"{verdict}: {correct} de {total} notas correctas, digitación {round(posture_score)}% "
        f"(puntaje total {round(total_score)}%)."
    )


def score_song_performance(
    song: dict[str, Any],
    tempo_bpm: int,
    pitch_track: list[dict[str, Any]],
    audio_frames: list[dict[str, Any]],
    hand_frames: list[dict[str, Any]],
    model_params: dict[str, np.ndarray] | None,
    model_metrics: dict[str, Any] | None,
    model_version: str | None = None,
) -> dict[str, Any]:
    """Per-note verdict for a song take (Contract scoring rules 1-7)."""
    use_model = model_params is not None and model_metrics is not None
    metrics = model_metrics or {}
    tuning = float(metrics.get("tuning_offset_cents") or 0.0) if use_model else 0.0
    sec_per_beat = 60.0 / tempo_bpm

    track = sorted(pitch_track, key=lambda f: float(f["t"]))
    times = [float(f["t"]) for f in track]
    voiced = [_voiced(f.get("hz")) for f in track]
    pitch_notes = [nearest_flute_note(float(f["hz"]), tuning)[0] if v else None for f, v in zip(track, voiced)]
    rms = [float(f.get("rms") or 0.0) for f in track]

    expected = song["notes"]
    latency_s = _latency_offset_s(times, voiced, expected[0]["start_beats"] * sec_per_beat)

    # Rule 5 inputs: flute probability per audio frame.
    audio = sorted(audio_frames, key=lambda f: float(f["t"]))
    audio_times = [float(f["t"]) for f in audio]
    flute_p: np.ndarray | None = None
    if use_model and audio:
        probs = fts._head_probs(model_params, "sound", np.asarray([f["features"] for f in audio], dtype=np.float64))
        flute_p = 1.0 - probs[:, SOUND_CLASSES.index(NO_FLUTE)]

    # Rule 6 inputs: covered probabilities per hand frame.
    hands = sorted(hand_frames, key=lambda f: float(f["t"]))
    hand_times = [float(f["t"]) for f in hands]
    finger_reason: str | None = None
    if not use_model:
        finger_reason = REASON_NO_MODEL
    elif not _finger_head_reliable(metrics):
        finger_reason = REASON_UNRELIABLE
    covered_p: np.ndarray | None = None
    if finger_reason is None and hands:
        covered_p = fts._finger_probs(model_params, np.asarray([f["features"] for f in hands], dtype=np.float64))
    per_hole = (metrics.get("fingers") or {}).get("per_hole") or []

    results: list[dict[str, Any]] = []
    prev_inner: range | None = None
    for i, spec in enumerate(expected):
        note = spec["note"]
        start_s = spec["start_beats"] * sec_per_beat
        duration_s = spec["duration_beats"] * sec_per_beat
        start = start_s + latency_s
        inner_lo, inner_hi = start + INNER_MARGIN * duration_s, start + duration_s - INNER_MARGIN * duration_s
        inner = _range(times, inner_lo, inner_hi)

        # Rule 2: pitch share and detected note.
        matches = sum(1 for k in inner if pitch_notes[k] == note)
        pitch_share = matches / len(inner) if len(inner) else 0.0
        voiced_in = [k for k in inner if voiced[k]]
        detected_note = None
        if len(inner) and len(voiced_in) / len(inner) >= MIN_VOICED_SHARE:
            counts = Counter(pitch_notes[k] for k in voiced_in if pitch_notes[k] is not None)
            if counts:
                detected_note = counts.most_common(1)[0][0]

        # Rule 3: onset and articulation.
        search = _range(times, start - ONSET_SEARCH_S, start + ONSET_SEARCH_S)
        repeated = i > 0 and expected[i - 1]["note"] == note
        articulation_ok: bool | None = None
        if repeated:
            prev_rms = [rms[k] for k in prev_inner] if prev_inner is not None else []
            threshold = DIP_RATIO * float(np.median(prev_rms)) if prev_rms else 0.0
            onset_t, articulation_ok = _dip_onset(times, rms, search, threshold)
        else:
            onset_t = next((times[k] for k in search if pitch_notes[k] == note), None)
        onset_ms = (onset_t - start) * 1000.0 if onset_t is not None else None
        if onset_ms is not None:
            timing_ok: bool | None = abs(onset_ms) <= TIMING_TOLERANCE_MS + _EPS
        else:
            timing_ok = None if repeated else False

        # Rule 5: flute check.
        flute_ok: bool | None = None
        if flute_p is not None:
            window = _range(audio_times, inner_lo, inner_hi)
            if len(window):
                flute_ok = bool(float(np.mean(flute_p[window.start:window.stop])) >= FLUTE_THRESHOLD)

        # Rule 6: fingering.
        posture_ok: bool | None = None
        posture_reason = finger_reason
        mismatched: list[int] = []
        if posture_reason is None:
            unseen = [
                h + 1 for h, covered in enumerate(FRONT_HOLES[note])
                if not _hole_state_seen(per_hole, h + 1, covered)
            ]
            evaluable = (
                [k for k in _range(hand_times, inner_lo, inner_hi) if _has_required_hands(hands[k]["features"], note)]
                if covered_p is not None else []
            )
            if unseen:
                posture_reason = (
                    "Digitación no evaluable: el entrenamiento no incluyó el estado esperado de "
                    f"{'el agujero' if len(unseen) == 1 else 'los agujeros'} {', '.join(map(str, unseen))}."
                )
            elif len(evaluable) < MIN_POSTURE_FRAMES:
                posture_reason = REASON_HANDS
            else:
                decisions = [posture_decision(covered_p[k], note) for k in evaluable]
                ok_frames = sum(1 for d in decisions if d["posture_ok"] is True)
                posture_ok = ok_frames / len(decisions) >= POSTURE_FRAME_SHARE
                hole_counts = Counter(h for d in decisions for h in d["mismatched_holes"])
                mismatched = sorted(h for h, c in hole_counts.items() if c / len(decisions) > POSTURE_FRAME_SHARE)

        # Rule 4.
        correct = pitch_share >= MIN_PITCH_SHARE and timing_ok is not False and flute_ok is not False
        results.append({
            "index": spec["index"],
            "pass": spec["pass"],
            "note": note,
            "expected_start_s": round(start_s, 4),
            "duration_s": round(duration_s, 4),
            "detected_note": detected_note,
            "pitch_share": round(pitch_share, 4),
            "onset_ms": _round(onset_ms, 1),
            "timing_ok": timing_ok,
            "repeated": repeated,
            "articulation_ok": articulation_ok,
            "flute_ok": flute_ok,
            "posture_ok": posture_ok,
            "posture_reason": posture_reason,
            "mismatched_holes": mismatched,
            "correct": bool(correct),
        })
        prev_inner = inner

    # Rule 7.
    total = len(results)
    notes_correct = sum(1 for r in results if r["correct"])
    sound_score = 100.0 * notes_correct / total if total else 0.0
    posture_evaluable = [r for r in results if r["posture_ok"] is not None]
    posture_score = (
        100.0 * sum(1 for r in posture_evaluable if r["posture_ok"]) / len(posture_evaluable)
        if posture_evaluable else None
    )
    if sound_score == 0:
        total_score = 0.0
    elif posture_score is None:
        total_score = sound_score
    else:
        total_score = SOUND_WEIGHT * sound_score + (1.0 - SOUND_WEIGHT) * posture_score
    approved = total_score >= APPROVAL_SCORE - _EPS

    return {
        "song_id": song["id"],
        "tempo_bpm": tempo_bpm,
        "model_version": model_version if use_model else None,
        "latency_offset_ms": round(latency_s * 1000.0, 1),
        "tuning_offset_cents": round(tuning, 2),
        "notes": results,
        "notes_correct": notes_correct,
        "notes_total": total,
        "sound_score": round(sound_score, 2),
        "posture_score": _round(posture_score, 2),
        "total_score": round(total_score, 2),
        "approved": approved,
        "message": _message(approved, notes_correct, total, posture_score, total_score),
    }


# --------------------------------------------------------------------------- #
# Service entry point
# --------------------------------------------------------------------------- #
async def score_flute_song(
    db: AsyncSession,
    song_id: str,
    tempo_bpm: int,
    pitch_track: list[dict[str, Any]],
    audio_frames: list[dict[str, Any]] | None = None,
    hand_frames: list[dict[str, Any]] | None = None,
    audio_schema: str = AUDIO_FEATURE_SCHEMA,
    visual_schema: str = VISUAL_FEATURE_SCHEMA,
) -> dict[str, Any]:
    song = FLUTE_SONGS.get(song_id)
    if song is None:
        raise SkillMatchException(statuscode=404, message="Canción no encontrada.")
    if not song["min_bpm"] <= tempo_bpm <= song["max_bpm"]:
        raise SkillMatchException(
            statuscode=400,
            message=f"El tempo debe estar entre {song['min_bpm']} y {song['max_bpm']} BPM.",
        )
    if audio_schema != AUDIO_FEATURE_SCHEMA or visual_schema != VISUAL_FEATURE_SCHEMA:
        raise SkillMatchException(
            statuscode=400,
            message="Formato de features no soportado. Actualizá el validador en vivo.",
        )
    track = [
        {"t": float(f["t"]), "hz": f.get("hz"), "clarity": float(f.get("clarity") or 0.0), "rms": float(f.get("rms") or 0.0)}
        for f in pitch_track
    ]
    audio = [
        {"t": float(f["t"]), "features": _validate_vector(f["features"], AUDIO_FEATURE_DIM, "de audio")}
        for f in audio_frames or []
    ]
    hands = [
        {"t": float(f["t"]), "features": _validate_vector(f["features"], VISUAL_FEATURE_DIM, "visual")}
        for f in hand_frames or []
    ]

    model = await db.scalar(
        select(ModelVersion).where(ModelVersion.nombre == MODEL_NAME, ModelVersion.activa.is_(True))
    )
    params: dict[str, np.ndarray] | None = None
    metrics: dict[str, Any] | None = None
    version: str | None = None
    if model is not None and _is_current_model(model.metricas or {}):
        metrics = model.metricas or {}
        params = fts._params_for(model)
        version = model.version
    return score_song_performance(song, tempo_bpm, track, audio, hands, params, metrics, model_version=version)
