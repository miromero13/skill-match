"""Flute pipeline: pitch-first sound decision, per-finger posture head, grouped
evaluation splits, label quality gates and ONNX/NumPy parity."""
import json
import math
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import numpy as np
import pytest
from pydantic import ValidationError

from app.api.ai.datasets import FluteFeaturesRequest, FluteInferRequest, FluteLabelsRequest
from app.core.exceptions import SkillMatchException
from app.services import flute_training_service as service

NOTES = service.FLUTE_NOTES


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def audio_for(note: str | None, cents: float = 0.0, timbre: float = 0.0, rng=None) -> list[float]:
    """62-dim audio vector: 48 timbre values + pitch block for `note` (None = silence)."""
    rng = rng or np.random.default_rng(0)
    base = list(rng.normal(timbre, 0.05, service.TIMBRE_FEATURE_DIM))
    if note is None:
        return base + service.build_pitch_features(None, 0.0)
    hz = service.NOTE_FREQUENCIES_HZ[note] * 2 ** (cents / 1200)
    return base + service.build_pitch_features(hz, 0.95)


def visual_for(note: str | None, hands: int = 2, rng=None, noise: float = 0.03) -> list[float]:
    """50-dim hand vector whose curl features encode the note's front holes."""
    rng = rng or np.random.default_rng(1)
    vec = [0.0] * service.VISUAL_FEATURE_DIM
    holes = service.FRONT_HOLES[note] if note else (False,) * 7
    # Left slot fingers 1-3 (index, middle, ring) -> holes 1-3; right slot 1-4 -> holes 4-7.
    layout = ((0, (1, 2, 3), holes[:3]), (25, (1, 2, 3, 4), holes[3:]))
    for slot, (off, fingers, states) in enumerate(layout):
        if hands < slot + 1:
            continue
        vec[off] = 1.0
        for finger, covered in zip(fingers, states):
            curl = 0.9 if covered else -0.4
            vec[off + 1 + finger] = curl + float(rng.normal(0, noise))
            vec[off + 6 + finger] = (0.6 if covered else 1.4) + float(rng.normal(0, noise))
        for j in range(off + 11, off + 25):
            vec[j] = 0.5 + float(rng.normal(0, noise))
    return vec


def features(hands=2, note="SI"):
    return {
        "audio_features": audio_for(note),
        "audio_schema": service.AUDIO_FEATURE_SCHEMA,
        "visual_features": visual_for(note, hands),
        "visual_schema": service.VISUAL_FEATURE_SCHEMA,
    }


# --------------------------------------------------------------------------- #
# Contract
# --------------------------------------------------------------------------- #
def test_request_contract_requires_pitch_audio_and_v5_hands():
    FluteFeaturesRequest(**features())
    FluteInferRequest(**features())
    assert len(features()["audio_features"]) == 62
    with pytest.raises(ValidationError):  # legacy 48-dim timbre-only vector
        FluteFeaturesRequest(**dict(features(), audio_features=[0.0] * 48))
    with pytest.raises(ValidationError):
        FluteFeaturesRequest(**dict(features(), visual_schema="hand-landmarks-palm-v4"))
    with pytest.raises(ValidationError):
        FluteFeaturesRequest(**dict(features(), audio_schema="mel_mfcc_timbre"))
    with pytest.raises(ValidationError):
        FluteFeaturesRequest(**dict(features(), visual_features=[float("nan")] * 50))
    with pytest.raises(ValidationError):
        FluteLabelsRequest(**features(), participant_id="p1", note_label="SI", sound_label="flauta",
                           posture_label="correcta", feature_frames=[])


def test_build_pitch_features_layout_matches_frontend_contract():
    sol = service.build_pitch_features(service.NOTE_FREQUENCIES_HZ["SOL"], 0.9)
    assert len(sol) == 14
    assert sol[0] == 1.0 and sol[1] == pytest.approx(0.9)
    assert sol[2] == pytest.approx(math.log2(783.9909 / 523.2511), abs=1e-4)
    affinities = sol[3:]
    assert affinities[NOTES.index("SOL")] == pytest.approx(1.0)
    assert affinities[NOTES.index("LA")] < 0.01
    assert service.build_pitch_features(None, 0.3) == [0.0, 0.3] + [0.0] * 12


# --------------------------------------------------------------------------- #
# Pitch (S3, S4)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("note", NOTES)
def test_nearest_note_identifies_every_note_including_close_pairs(note):
    hz = service.NOTE_FREQUENCIES_HZ[note]
    found, cents = service.nearest_flute_note(hz)
    assert found == note
    assert abs(cents) < 1.0


def test_nearest_note_rejects_out_of_tune_and_applies_tuning_offset():
    sol_hz = service.NOTE_FREQUENCIES_HZ["SOL"]
    assert service.nearest_flute_note(sol_hz * 2 ** (75 / 1200))[0] is None  # quarter-tone off
    sharp = sol_hz * 2 ** (40 / 1200)
    note, cents = service.nearest_flute_note(sharp, tuning_offset_cents=40.0)
    assert note == "SOL" and abs(cents) < 1.0
    assert service.nearest_flute_note(None)[0] is None


def test_sound_decision_is_pitch_first_and_mlp_only_rejects_non_flute():
    probs = np.zeros(len(service.SOUND_CLASSES))
    probs[service.SOUND_CLASSES.index("LA")] = 0.9  # timbre head is wrong about the note
    probs[service.SOUND_CLASSES.index(service.NO_FLUTE)] = 0.1
    decision = service.sound_decision(np.asarray(audio_for("SOL")), probs)
    assert decision["sound_class"] == "SOL"
    assert decision["voiced"] is True
    assert decision["flute_probability"] == pytest.approx(0.9)

    silent = service.sound_decision(np.asarray(audio_for(None)), probs)
    assert silent["sound_class"] == service.NO_FLUTE and silent["voiced"] is False

    voice = np.zeros(len(service.SOUND_CLASSES))
    voice[service.SOUND_CLASSES.index(service.NO_FLUTE)] = 0.8
    voice[service.SOUND_CLASSES.index("SOL")] = 0.2
    assert service.sound_decision(np.asarray(audio_for("SOL")), voice)["sound_class"] == service.NO_FLUTE


def test_tuning_offset_is_median_cents_of_labeled_flute_frames():
    rows = [
        {"sound_class": service.SOUND_CLASSES.index("SOL"), "audio": np.asarray(audio_for("SOL", cents=c))}
        for c in (20.0, 25.0, 30.0)
    ] + [{"sound_class": service.SOUND_CLASSES.index(service.NO_FLUTE), "audio": np.asarray(audio_for("LA", 90))}]
    assert service.estimate_tuning_offset(rows) == pytest.approx(25.0, abs=0.5)
    assert service.estimate_tuning_offset([]) == 0.0


# --------------------------------------------------------------------------- #
# Labels quality gates (S5, S8)
# --------------------------------------------------------------------------- #
def frame(note, hands=2, voiced=True, cents=0.0):
    return {
        "audio_features": audio_for(note if voiced else None, cents),
        "audio_schema": service.AUDIO_FEATURE_SCHEMA,
        "visual_features": visual_for(note, hands),
        "visual_schema": service.VISUAL_FEATURE_SCHEMA,
    }


async def save(note, sound, posture, frames):
    sample = SimpleNamespace(id=uuid4(), discipline="musica")
    db = SimpleNamespace(scalar=AsyncMock(return_value=sample), flush=AsyncMock())
    top = frames[0]
    with patch.object(service.garage_s3_storage, "put_object_bytes") as store:
        try:
            result = await service.save_flute_labels(
                db, sample.id, "person-01", note, sound, posture,
                audio_features=top["audio_features"], audio_schema=top["audio_schema"],
                visual_features=top["visual_features"], visual_schema=top["visual_schema"],
                feature_frames=frames,
            )
        except SkillMatchException as exc:
            store.assert_not_called()
            raise exc
        payload = json.loads(store.call_args.kwargs["payload"])
    return result, payload, sample


@pytest.mark.asyncio
async def test_flute_take_drops_silent_frames_and_records_pitch_agreement():
    frames = [frame("SOL")] * 4 + [frame("SOL", voiced=False)] * 3
    result, payload, sample = await save("SOL", "flauta", "correcta", frames)
    assert len(payload["feature_frames"]) == 4
    assert payload["audio_schema"] == service.AUDIO_FEATURE_SCHEMA
    assert payload["pitch_agreement"] == pytest.approx(1.0)
    assert result["participant_id"] == sample.participant_id == "person-01"


@pytest.mark.asyncio
async def test_flute_take_with_wrong_pitch_is_rejected_without_storing():
    with pytest.raises(SkillMatchException) as exc:
        await save("SOL", "flauta", "correcta", [frame("LA")] * 5)
    assert exc.value.statuscode == 400
    assert "La altura detectada no corresponde a la nota SOL" in exc.value.message


@pytest.mark.asyncio
async def test_silent_flute_take_is_rejected():
    with pytest.raises(SkillMatchException) as exc:
        await save("SOL", "flauta", "correcta", [frame("SOL", voiced=False)] * 5)
    assert "sonido de flauta" in exc.value.message


@pytest.mark.asyncio
async def test_negative_takes_keep_all_frames_and_sin_manos_is_not_a_posture_class():
    _, payload, _ = await save(None, "voz", "sin_manos", [frame(None, hands=0, voiced=False)] * 4)
    assert len(payload["feature_frames"]) == 4
    assert service.WRONG_POSTURE not in getattr(service, "POSTURE_CLASSES", [])


@pytest.mark.asyncio
async def test_missing_hands_cannot_be_saved_as_correct_fingering():
    with pytest.raises(SkillMatchException):
        await save("DO", "flauta", "correcta", [frame("DO", hands=1)] * 4)


# --------------------------------------------------------------------------- #
# Fingers head (S7) + ONNX parity (S12)
# --------------------------------------------------------------------------- #
def test_front_hole_labels_mirror_frontend_fingering_map():
    assert service.FRONT_HOLES["SOL"] == (True, True, True, False, False, False, False)
    assert service.FRONT_HOLES["FA"] == (True, True, True, True, False, False, False)  # German fingering
    assert service.FRONT_HOLES["DO6"] == service.FRONT_HOLES["RE6"]  # differ only by the thumb
    assert service.FRONT_HOLES["MI"] == service.FRONT_HOLES["MI6"]


def _finger_dataset(rng):
    xs, ys = [], []
    for note in ("SI", "LA", "SOL", "DO6", "FA", "MI", "RE", "DO"):
        hands = 1 if note in ("SI", "LA", "SOL", "DO6") else 2
        for _ in range(12):
            xs.append(visual_for(note, hands, rng))
            ys.append(service.FRONT_HOLES[note])
    return np.asarray(xs), np.asarray(ys, dtype=np.float64)


def _run_onnx_graph(onnx_bytes: bytes, feeds: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    """Tiny reference evaluator of the exported graph (independent of service math)."""
    graph = next(v for f, w, v in service._fields(onnx_bytes) if f == 7 and w == 2)
    env = dict(feeds)
    env.update({k: v for k, v in service.load_onnx_initializers(onnx_bytes).items()})
    ops = {
        "Sub": lambda a, b: a - b, "Div": lambda a, b: a / b, "Mul": lambda a, b: a * b,
        "Add": lambda a, b: a + b, "MatMul": lambda a, b: a @ b,
        "Relu": lambda a: np.maximum(a, 0.0), "Sigmoid": lambda a: 1.0 / (1.0 + np.exp(-a)),
        "Softmax": lambda a: np.exp(a - a.max(axis=1, keepdims=True))
        / np.exp(a - a.max(axis=1, keepdims=True)).sum(axis=1, keepdims=True),
    }
    for field, wire, node in service._fields(graph):
        if field != 1 or wire != 2:
            continue
        ins, outs, op = [], [], ""
        for nf, _nw, nv in service._fields(node):
            if nf == 1:
                ins.append(bytes(nv).decode())
            elif nf == 2:
                outs.append(bytes(nv).decode())
            elif nf == 4:
                op = bytes(nv).decode()
        env[outs[0]] = ops[op](*[env[i] for i in ins])
    return env


def test_finger_head_learns_holes_and_onnx_graph_matches_numpy_inference():
    rng = np.random.default_rng(3)
    x_vis, y_holes = _finger_dataset(rng)
    finger_params, history = service._train_finger_mlp(x_vis, y_holes, np.ones(len(x_vis)))
    assert history[-1]["loss"] < history[0]["loss"]

    x_audio = np.asarray([audio_for(n, rng=rng) for n in ("SI", "SOL") for _ in range(10)])
    y_sound = np.asarray([service.SOUND_CLASSES.index(n) for n in ("SI", "SOL") for _ in range(10)])
    sound_params, _ = service._train_mlp(x_audio, y_sound, len(service.SOUND_CLASSES), epochs=40)

    onnx_bytes = service.build_flute_onnx({"sound": sound_params, "fingers": finger_params})
    params = service.load_onnx_initializers(onnx_bytes)

    test_x = np.asarray([visual_for(n, 2, rng) for n in ("SOL", "MI", "DO")] + [visual_for("LA", 1, rng)])
    numpy_fingers = service._finger_probs(params, test_x)
    numpy_sound = service._head_probs(params, "sound", x_audio[:4])
    graph = _run_onnx_graph(onnx_bytes, {"audio_features": x_audio[:4], "visual_features": test_x})
    np.testing.assert_allclose(graph["finger_covered_probs"], numpy_fingers, atol=1e-5)
    np.testing.assert_allclose(graph["sound_probs"], numpy_sound, atol=1e-5)

    predicted = numpy_fingers >= 0.5
    expected = np.asarray([service.FRONT_HOLES[n] for n in ("SOL", "MI", "DO", "LA")])
    assert (predicted == expected).mean() >= 0.95

    # Absent right hand (zeroed slot) must not break the left-hand holes.
    left_only = np.asarray([visual_for("SOL", 1, rng)])
    assert np.all(np.isfinite(service._finger_probs(params, left_only)))
    assert list(service._finger_probs(params, left_only)[0, :3] >= 0.5) == [True, True, True]


@pytest.mark.parametrize("probs,ok,mismatched,uncertain", [
    ([0.9, 0.9, 0.9, 0.1, 0.1, 0.1, 0.1], True, [], []),
    ([0.9, 0.9, 0.9, 0.55, 0.1, 0.1, 0.1], True, [], [4]),     # one unsure hole is tolerated
    ([0.9, 0.9, 0.9, 0.55, 0.6, 0.1, 0.1], False, [], [4, 5]),  # two unsure holes are not
    ([0.9, 0.9, 0.9, 0.8, 0.1, 0.1, 0.1], False, [4], []),     # LA->SOL style: one confident wrong finger
    ([0.9, 0.2, 0.9, 0.8, 0.1, 0.1, 0.1], False, [2, 4], []),
])
def test_posture_decision_rejects_any_confident_wrong_finger(probs, ok, mismatched, uncertain):
    result = service.posture_decision(np.asarray(probs), "SOL")
    assert result["posture_ok"] is ok
    assert result["mismatched_holes"] == mismatched
    assert result["uncertain_holes"] == uncertain
    wrong_side = sum(1 for p, e in zip(probs, service.FRONT_HOLES["SOL"]) if (p >= 0.5) != e)
    assert result["finger_match_ratio"] == pytest.approx((7 - wrong_side) / 7, abs=1e-4)
    assert [s["hole"] for s in result["finger_states"]] == [1, 2, 3, 4, 5, 6, 7]
    assert result["finger_states"][0] == {"hole": 1, "expected": True,
                                          "covered_probability": 0.9, "match": True}


def test_posture_decision_without_note_reports_holes_only():
    result = service.posture_decision(np.asarray([0.9] * 7), None)
    assert result["posture_ok"] is None and result["finger_match_ratio"] is None
    assert all(s["expected"] is None and s["match"] is None for s in result["finger_states"])


# --------------------------------------------------------------------------- #
# Grouped split (S2)
# --------------------------------------------------------------------------- #
def _rows(spec):
    rows = []
    for sample_id, pid, day, note in spec:
        for _ in range(3):
            rows.append({"sample_id": sample_id, "participant_id": pid, "session": f"{pid}|{day}",
                         "sound_class": service.SOUND_CLASSES.index(note)})
    return rows


def test_split_prefers_participants_then_sessions_then_takes():
    two_people = _rows([("a", "p1", "d1", "SI"), ("b", "p2", "d1", "SI")])
    mode, train, test = service._split_rows(two_people)
    assert mode == "participant" and train and test
    assert {r["participant_id"] for r in train}.isdisjoint({r["participant_id"] for r in test})

    two_days = _rows([("a", "p1", "d1", "SI"), ("b", "p1", "d2", "SI"), ("c", "p1", "d2", "LA")])
    mode, train, test = service._split_rows(two_days)
    assert mode == "session"
    assert {r["session"] for r in train}.isdisjoint({r["session"] for r in test})

    one_session = _rows([("a", "p1", "d1", "SI"), ("b", "p1", "d1", "SI"),
                         ("c", "p1", "d1", "LA"), ("d", "p1", "d1", "LA")])
    mode, train, test = service._split_rows(one_session)
    assert mode == "take"
    assert {r["sample_id"] for r in train}.isdisjoint({r["sample_id"] for r in test})
    assert {r["sound_class"] for r in train} == {r["sound_class"] for r in one_session}

    single_takes = _rows([("a", "p1", "d1", "SI"), ("c", "p1", "d1", "LA")])
    mode, train, test = service._split_rows(single_takes)
    assert mode == "none" and test == [] and len(train) == len(single_takes)


def test_per_class_report_precision_recall():
    report = service._per_class_report(pred=[0, 0, 1, 1], true=[0, 1, 1, 1], classes=["A", "B", "C"])
    assert report["A"] == {"precision": 0.5, "recall": 1.0, "support": 1}
    assert report["B"] == {"precision": 1.0, "recall": pytest.approx(0.6667, abs=1e-4), "support": 3}
    assert report["C"] == {"precision": None, "recall": None, "support": 0}


# --------------------------------------------------------------------------- #
# Training end-to-end (S1, S2, S11) with mocked storage/DB
# --------------------------------------------------------------------------- #
def _sample(day: int):
    return SimpleNamespace(id=uuid4(), participant_id="p1", file_format="mp4",
                           created_at=datetime(2026, 11, day, tzinfo=timezone.utc))


def _fake_db():
    db = MagicMock()
    db.scalar = AsyncMock(return_value=0)
    db.execute = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    return db


def _labels_for(note, sound, posture, rng, n=6):
    frames = []
    for _ in range(n):
        frames.append({
            "audio_features": audio_for(note if sound == "flauta" else None,
                                        timbre=0.0 if sound == "flauta" else 3.0, rng=rng),
            "visual_features": visual_for(note, 1 if note in ("SI", "LA", "SOL") else 2, rng),
        })
    return {
        "participant_id": "p1", "note_label": note, "sound_label": sound, "posture_label": posture,
        "audio_schema": service.AUDIO_FEATURE_SCHEMA, "visual_schema": service.VISUAL_FEATURE_SCHEMA,
        "audio_features": frames[0]["audio_features"], "visual_features": frames[0]["visual_features"],
        "feature_frames": frames,
    }


@pytest.mark.asyncio
async def test_training_reports_take_level_metrics_with_session_split():
    rng = np.random.default_rng(5)
    labels = {}
    samples = []
    for day in (1, 2):
        for note in ("SI", "LA", "SOL"):
            s = _sample(day)
            samples.append(s)
            labels[s.id] = _labels_for(note, "flauta", "correcta", rng)
        s = _sample(day)
        samples.append(s)
        labels[s.id] = _labels_for(None, "voz", "sin_manos", rng)

    with patch.object(service, "_music_samples", AsyncMock(return_value=samples)), \
            patch.object(service, "_read_labels", side_effect=lambda sid: labels.get(sid)), \
            patch.object(service.garage_s3_storage, "put_object_bytes", return_value=("s3://m.onnx", "sha")):
        result = await service.train_flute_note_model(_fake_db(), activate=True)

    m = result["metricas"]
    assert m["split_mode"] == "session"
    assert m["validated"] is False
    assert m["audio_schema"] == service.AUDIO_FEATURE_SCHEMA
    assert m["visual_schema"] == service.VISUAL_FEATURE_SCHEMA
    assert m["sound"]["sample_test_accuracy"] == 1.0
    assert set(m["sound"]["per_class"]) == set(service.SOUND_CLASSES)
    assert m["sound"]["per_participant"] == {"p1": 1.0}
    assert len(m["sound"]["confusion_matrix"]) == len(service.SOUND_CLASSES)
    assert sum(map(sum, m["sound"]["confusion_matrix"])) == 4  # one held-out session = 4 takes
    assert m["fingers"]["holes"] == [1, 2, 3, 4, 5, 6, 7]
    assert m["fingers"]["test_accuracy"] >= 0.9
    assert len(m["fingers"]["per_hole"]) == 7
    assert "posture" not in m
    assert result["activa"] is True


def test_activation_gate_requires_sound_to_beat_baseline():
    assert service._passes_sound_gate({"sound": {"sample_test_accuracy": 0.8, "majority_baseline_accuracy": 0.3}})
    assert not service._passes_sound_gate({"sound": {"sample_test_accuracy": 0.3, "majority_baseline_accuracy": 0.3}})
    assert service._passes_sound_gate({"split_mode": "none", "sound": {"sample_test_accuracy": None}})


@pytest.mark.asyncio
async def test_activate_rejects_legacy_audio_schema_and_failing_sound_gate():
    legacy = SimpleNamespace(id=uuid4(), metricas={"visual_schema": service.VISUAL_FEATURE_SCHEMA})
    db = SimpleNamespace(scalar=AsyncMock(return_value=legacy), execute=AsyncMock(), commit=AsyncMock())
    with pytest.raises(SkillMatchException) as exc:
        await service.activate_flute_model(db, legacy.id)
    assert exc.value.statuscode == 409

    weak = SimpleNamespace(id=uuid4(), metricas={
        "visual_schema": service.VISUAL_FEATURE_SCHEMA, "audio_schema": service.AUDIO_FEATURE_SCHEMA,
        "split_mode": "take", "sound": {"sample_test_accuracy": 0.2, "majority_baseline_accuracy": 0.4},
    })
    db.scalar = AsyncMock(return_value=weak)
    with pytest.raises(SkillMatchException) as exc:
        await service.activate_flute_model(db, weak.id)
    assert exc.value.statuscode == 409
    assert "línea base" in exc.value.message


# --------------------------------------------------------------------------- #
# Inference (S4, S7, S8)
# --------------------------------------------------------------------------- #
def model(**overrides):
    metricas = {
        "visual_schema": service.VISUAL_FEATURE_SCHEMA,
        "audio_schema": service.AUDIO_FEATURE_SCHEMA,
        "validated": False,
        "split_mode": "take",
        "tuning_offset_cents": 0.0,
        "fingers": {"test_accuracy": 0.95, "majority_baseline_accuracy": 0.6},
    }
    metricas.update(overrides)
    return SimpleNamespace(id=uuid4(), version="flute-pitch-3.1.0", metricas=metricas)


def _patched(sound_probs, finger_probs):
    return (
        patch.object(service, "_params_for", return_value={}),
        patch.object(service, "_head_probs", return_value=np.asarray([sound_probs])),
        patch.object(service, "_finger_probs", return_value=np.asarray([finger_probs])),
    )


FLUTE = [0.0] * 11 + [0.05]
SOL_FINGERS = [0.9, 0.9, 0.9, 0.1, 0.1, 0.1, 0.1]


@pytest.mark.asyncio
async def test_infer_exam_mode_uses_pitch_and_fingers():
    db = SimpleNamespace(scalar=AsyncMock(return_value=model()))
    p1, p2, p3 = _patched(FLUTE, SOL_FINGERS)
    with p1, p2, p3:
        res = await service.infer_flute(db, target_note="SOL", **dict(features(1, "SOL")))
    assert res["sound_class"] == "SOL" and res["sound_ok"] is True
    assert res["pitch_note"] == "SOL" and res["voiced"] is True
    assert abs(res["pitch_hz"] - 783.99) < 0.5
    assert res["posture_ok"] is True and res["posture_evaluable"] is True
    assert res["mismatched_holes"] == []
    assert len(res["finger_states"]) == 7

    p1, p2, p3 = _patched(FLUTE, SOL_FINGERS)
    with p1, p2, p3:
        wrong = await service.infer_flute(db, target_note="LA", **dict(features(1, "SOL")))
    assert wrong["sound_ok"] is False
    assert wrong["posture_ok"] is False  # SOL fingering differs from LA only in hole 3
    assert wrong["mismatched_holes"] == [3]
    assert wrong["finger_match_ratio"] == pytest.approx(6 / 7, abs=1e-4)


@pytest.mark.asyncio
async def test_infer_free_mode_combines_detected_pitch_note_with_fingers():
    db = SimpleNamespace(scalar=AsyncMock(return_value=model()))
    p1, p2, p3 = _patched(FLUTE, SOL_FINGERS)
    with p1, p2, p3:
        res = await service.infer_flute(db, target_note=None, **dict(features(1, "SOL")))
    assert res["combined_match"] is True and res["combined_note"] == "SOL"
    assert res["experimental"] is True
    assert len(res["top_sound_classes"]) == 3


@pytest.mark.asyncio
async def test_infer_silence_makes_posture_not_evaluable_in_free_mode():
    db = SimpleNamespace(scalar=AsyncMock(return_value=model()))
    silent = dict(features(1, "SOL"), audio_features=audio_for(None))
    p1, p2, p3 = _patched(FLUTE, SOL_FINGERS)
    with p1, p2, p3:
        res = await service.infer_flute(db, target_note=None, **silent)
    assert res["sound_class"] == service.NO_FLUTE and res["voiced"] is False
    assert res["posture_ok"] is None and res["posture_reason"]
    assert all(s["expected"] is None for s in res["finger_states"])


@pytest.mark.asyncio
@pytest.mark.parametrize("hands,metric_overrides", [
    (1, {}),  # DO needs both hands
    (2, {"fingers": {"test_accuracy": 0.5, "majority_baseline_accuracy": 0.6}}),
])
async def test_unreliable_posture_is_inconclusive(hands, metric_overrides):
    db = SimpleNamespace(scalar=AsyncMock(return_value=model(**metric_overrides)))
    p1, p2, p3 = _patched(FLUTE, [0.9] * 7)
    with p1, p2, p3:
        res = await service.infer_flute(db, target_note="DO", **dict(features(hands, "DO")))
    assert res["posture_ok"] is None
    assert res["posture_evaluable"] is False
    assert res["posture_reason"]


@pytest.mark.asyncio
async def test_old_active_model_is_rejected_before_loading_weights():
    old = model()
    old.metricas.pop("audio_schema")
    with patch.object(service, "_params_for") as params:
        with pytest.raises(SkillMatchException) as exc:
            await service.infer_flute(SimpleNamespace(scalar=AsyncMock(return_value=old)),
                                      target_note="SI", **features())
        assert exc.value.statuscode == 409
        params.assert_not_called()


def test_legacy_sidecars_are_listed_as_needing_reprocessing():
    sample = SimpleNamespace(id=uuid4(), participant_id="p1", file_format="mp4", created_at=None)
    legacy = {
        "participant_id": "p1", "note_label": "SI", "sound_label": "flauta", "posture_label": "correcta",
        "visual_schema": "hand-landmarks-palm-v4",
        "audio_features": [0.0] * 48, "visual_features": [0.0] * 50,
        "feature_frames": [{"audio_features": [0.0] * 48, "visual_features": [0.0] * 50}] * 3,
    }
    with patch.object(service, "_read_labels", return_value=legacy):
        rows, listing = service._labeled_rows([sample])
    assert rows == []
    assert listing[0]["labeled"] is False
    assert listing[0]["needs_reprocess"] is True
    assert listing[0]["note_label"] == "SI"
