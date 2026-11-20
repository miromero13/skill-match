"""Contract, MLP ONNX export, timbre audio, and free-mode inference tests for flute."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import numpy as np
import pytest
from pydantic import ValidationError

from app.api.ai.datasets import FluteFeaturesRequest, FluteInferRequest, FluteLabelsRequest
from app.core.exceptions import SkillMatchException
from app.services import flute_training_service as service


def features(hands=2):
    visual = [0.0] * service.VISUAL_FEATURE_DIM
    visual[0] = float(hands >= 1)
    visual[service.VISUAL_HAND_SLOT_DIM] = float(hands >= 2)
    return {
        "audio_features": [0.0] * service.AUDIO_FEATURE_DIM,
        "visual_features": visual,
        "visual_schema": service.VISUAL_FEATURE_SCHEMA,
    }


def test_request_rejects_old_schemas_and_nonfinite_features():
    FluteFeaturesRequest(**features())
    FluteInferRequest(**features())  # target_note is optional for free-mode detection
    with pytest.raises(ValidationError):
        FluteFeaturesRequest(**dict(features(), visual_features=[0.0] * 128))
    with pytest.raises(ValidationError):
        FluteFeaturesRequest(**dict(features(), audio_features=[0.0] * 28))
    with pytest.raises(ValidationError):
        FluteFeaturesRequest(**dict(features(), visual_features=[float("nan")] * service.VISUAL_FEATURE_DIM))
    with pytest.raises(ValidationError):
        FluteFeaturesRequest(**dict(features(), visual_schema="hand-landmarks-palm-v2"))
    with pytest.raises(ValidationError):
        FluteLabelsRequest(
            **features(),
            participant_id="p1",
            note_label="SI",
            sound_label="flauta",
            posture_label="correcta",
            feature_frames=[],
        )


def test_legacy_samples_are_excluded_but_labels_remain_for_reprocessing():
    sample = SimpleNamespace(id=uuid4(), participant_id="p1", file_format="mp4", created_at=None)
    legacy = {
        "participant_id": "p1",
        "note_label": "SI",
        "sound_label": "flauta",
        "posture_label": "correcta",
        "visual_schema": "hand-landmarks-palm-v2",
        "audio_features": [0.0] * 28,
        "visual_features": [0.0] * 128,
        "feature_frames": [{"audio_features": [0.0] * 28, "visual_features": [0.0] * 128}] * 3,
    }
    with patch.object(service, "_read_labels", return_value=legacy):
        rows, listing = service._labeled_rows([sample])
    assert rows == []
    assert listing[0]["labeled"] is False
    assert listing[0]["note_label"] == "SI"


def test_v3_samples_are_automatically_converted_to_v4_without_reprocessing():
    sample = SimpleNamespace(id=uuid4(), participant_id="p1", file_format="mp4", created_at=None)
    v3_visual = [0.0] * 148
    v3_visual[0] = 1.0  # Left hand present
    for i in range(21):
        v3_visual[1 + i * 3] = (i % 5) * 0.2
        v3_visual[2 + i * 3] = (i // 5) * 0.3
        v3_visual[3 + i * 3] = (i % 3) * 0.05
    v3_payload = {
        "participant_id": "p1",
        "note_label": "SI",
        "sound_label": "flauta",
        "posture_label": "correcta",
        "visual_schema": "hand-landmarks-palm-v3",
        "audio_features": [0.1] * 48,
        "visual_features": v3_visual,
        "feature_frames": [{"audio_features": [0.1] * 48, "visual_features": v3_visual}] * 4,
    }
    with patch.object(service, "_read_labels", return_value=v3_payload):
        rows, listing = service._labeled_rows([sample])
    assert listing[0]["labeled"] is True
    assert len(rows) == 4
    assert all(r["visual"].shape == (50,) for r in rows)
    assert rows[0]["visual"][0] == 1.0
    assert rows[0]["visual"][25] == 0.0


def test_posture_prototypes_onnx_and_absent_second_hand_resilience():
    rng = np.random.default_rng(11)
    si_left = np.concatenate([[1.0], rng.normal(0.8, 0.05, 24)])
    sol_left = np.concatenate([[1.0], rng.normal(-0.8, 0.05, 24)])
    right_present = np.concatenate([[1.0], rng.normal(0.2, 0.05, 24)])

    # Train SI and SOL with right hand visible in frame
    x_vis = np.vstack([
        np.concatenate([si_left + rng.normal(0, 0.02, 25), right_present])
        for _ in range(10)
    ] + [
        np.concatenate([sol_left + rng.normal(0, 0.02, 25), right_present])
        for _ in range(10)
    ])
    x_vis[:, 0] = 1.0
    x_vis[:, 25] = 1.0
    y_pos = np.array([service.POSTURE_CLASSES.index("SI")] * 10 + [service.POSTURE_CLASSES.index("SOL")] * 10)

    sound_params, _ = service._train_mlp(
        rng.normal(0, 1, size=(20, service.AUDIO_FEATURE_DIM)),
        y_pos,
        len(service.SOUND_CLASSES),
        hidden_dim=16,
        epochs=20,
    )
    posture_params, _ = service._train_posture_prototypes(x_vis, y_pos, len(service.POSTURE_CLASSES))
    loaded = service.load_onnx_initializers(
        service.build_flute_onnx({"sound": sound_params, "posture": posture_params})
    )
    assert loaded["posture_W"].shape == (service.VISUAL_FEATURE_DIM, len(service.POSTURE_CLASSES))

    # At inference time, right hand drops out of frame (all zeros in slot 1)
    si_no_right = np.concatenate([si_left, np.zeros(25)])[None, :]
    probs = service._head_probs(loaded, "posture", si_no_right)[0]
    assert service.POSTURE_CLASSES[int(np.argmax(probs))] == "SI"
    assert service._is_posture_compatible(probs, "SI") is True


def test_mlp_training_and_onnx_roundtrip_dimensions():
    rng = np.random.default_rng(7)
    x_audio = np.vstack([
        rng.normal(0.0, 0.2, size=(12, service.AUDIO_FEATURE_DIM)),
        rng.normal(2.0, 0.2, size=(12, service.AUDIO_FEATURE_DIM)),
    ])
    y_sound = np.array([service.SOUND_CLASSES.index("SI")] * 12 + [service.SOUND_CLASSES.index("SOL")] * 12)
    x_visual = np.vstack([
        rng.normal(0.0, 0.2, size=(12, service.VISUAL_FEATURE_DIM)),
        rng.normal(2.0, 0.2, size=(12, service.VISUAL_FEATURE_DIM)),
    ])
    y_posture = np.array([service.POSTURE_CLASSES.index("SI")] * 12 + [service.POSTURE_CLASSES.index("SOL")] * 12)

    sound_params, _ = service._train_mlp(x_audio, y_sound, len(service.SOUND_CLASSES), hidden_dim=32, epochs=120)
    posture_params, _ = service._train_mlp(x_visual, y_posture, len(service.POSTURE_CLASSES), hidden_dim=48, epochs=120)
    onnx_bytes = service.build_flute_onnx({"sound": sound_params, "posture": posture_params})
    loaded = service.load_onnx_initializers(onnx_bytes)

    assert loaded["sound_W1"].shape == (service.AUDIO_FEATURE_DIM, 32)
    assert loaded["sound_W2"].shape == (32, len(service.SOUND_CLASSES))
    assert loaded["posture_W1"].shape == (service.VISUAL_FEATURE_DIM, 48)
    assert loaded["posture_W2"].shape == (48, len(service.POSTURE_CLASSES))

    sound_probs = service._head_probs(loaded, "sound", x_audio)
    posture_probs = service._head_probs(loaded, "posture", x_visual)
    assert np.mean(np.argmax(sound_probs, axis=1) == y_sound) >= 0.95
    assert np.mean(np.argmax(posture_probs, axis=1) == y_posture) >= 0.95


@pytest.mark.asyncio
async def test_save_preserves_multiple_frames_and_participant():
    sample = SimpleNamespace(id=uuid4(), discipline="musica")
    db = SimpleNamespace(scalar=AsyncMock(return_value=sample), flush=AsyncMock())
    with patch.object(service.garage_s3_storage, "put_object_bytes") as store:
        result = await service.save_flute_labels(
            db, sample.id, "person-01", "SI", "flauta", "correcta", **features(), feature_frames=[features()] * 4
        )
        import json
        payload = json.loads(store.call_args.kwargs["payload"])
    assert len(payload["feature_frames"]) == 4
    assert payload["visual_schema"] == service.VISUAL_FEATURE_SCHEMA
    assert result["participant_id"] == sample.participant_id == "person-01"


@pytest.mark.asyncio
async def test_missing_hands_cannot_be_saved_as_correct_fingering():
    sample = SimpleNamespace(id=uuid4(), discipline="musica")
    db = SimpleNamespace(scalar=AsyncMock(return_value=sample))
    with patch.object(service.garage_s3_storage, "put_object_bytes") as store:
        with pytest.raises(SkillMatchException):
            await service.save_flute_labels(
                db, sample.id, "p1", "DO", "flauta", "correcta", **features(1), feature_frames=[features(1)] * 3
            )
        store.assert_not_called()


def model(validated=True, accuracy=0.9, baseline=0.1):
    return SimpleNamespace(
        id=uuid4(),
        version="timbre-v2",
        metricas={
            "visual_schema": service.VISUAL_FEATURE_SCHEMA,
            "validated": validated,
            "posture": {
                "test_accuracy": accuracy,
                "majority_baseline_accuracy": baseline,
                "train_class_counts": {"SI": 5, "DO": 5},
            },
        },
    )


@pytest.mark.asyncio
async def test_old_active_model_is_rejected_before_loading_weights():
    old = model()
    old.metricas["visual_schema"] = "hand-landmarks-palm-v2"
    with patch.object(service, "_params_for") as params:
        with pytest.raises(SkillMatchException) as exc:
            await service.infer_flute(SimpleNamespace(scalar=AsyncMock(return_value=old)), target_note="SI", **features())
        assert exc.value.statuscode == 409
        params.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("hands,validated,accuracy,baseline,confidence", [
    (0, True, 0.9, 0.1, 0.9),
    (2, True, 0.091, 0.091, 0.9),
    (2, True, 0.9, 0.1, 0.2),
])
async def test_unreliable_posture_is_inconclusive(hands, validated, accuracy, baseline, confidence):
    probs = np.zeros((1, 12))
    probs[0, service.POSTURE_CLASSES.index("SI")] = confidence
    db = SimpleNamespace(scalar=AsyncMock(return_value=model(validated, accuracy, baseline)))
    with patch.object(service, "_params_for", return_value={}), patch.object(service, "_head_probs", return_value=probs):
        result = await service.infer_flute(db, target_note="SI", **features(hands))
    assert result["posture_ok"] is None
    assert result["posture_evaluable"] is False
    assert result["posture_reason"]


@pytest.mark.asyncio
async def test_approximate_top3_posture_accepts_close_note_and_rejects_wrong_posture():
    # Close fingerings: LA=0.42, SI=0.35 -> SI is in Top-3 with >= 15% affinity and not INCORRECTA
    sound_probs = np.zeros((1, 12))
    sound_probs[0, service.SOUND_CLASSES.index("SI")] = 0.85
    posture_probs = np.zeros((1, 12))
    posture_probs[0, service.POSTURE_CLASSES.index("LA")] = 0.42
    posture_probs[0, service.POSTURE_CLASSES.index("SI")] = 0.35
    db = SimpleNamespace(scalar=AsyncMock(return_value=model(validated=False, accuracy=None, baseline=None)))

    def fake_head(_params, head, _x):
        return sound_probs if head == "sound" else posture_probs

    with patch.object(service, "_params_for", return_value={}), patch.object(service, "_head_probs", side_effect=fake_head):
        res_ok = await service.infer_flute(db, target_note="SI", **features(1))
        res_free = await service.infer_flute(db, target_note=None, **features(1))
    assert res_ok["posture_ok"] is True
    assert res_free["combined_match"] is True
    assert res_free["combined_note"] == "SI"

    # Explicit INCORRECTA >= 0.5 must be rejected even if SI has 0.25
    wrong_probs = np.zeros((1, 12))
    wrong_probs[0, service.POSTURE_CLASSES.index(service.WRONG_POSTURE)] = 0.65
    wrong_probs[0, service.POSTURE_CLASSES.index("SI")] = 0.25
    with patch.object(service, "_params_for", return_value={}), patch.object(
        service, "_head_probs", side_effect=lambda _p, h, _x: sound_probs if h == "sound" else wrong_probs
    ):
        res_wrong = await service.infer_flute(db, target_note="SI", **features(1))
    assert res_wrong["posture_ok"] is False


@pytest.mark.asyncio
async def test_free_mode_detection_works_even_in_single_participant_experimental_mode():
    probs = np.zeros((1, 12))
    probs[0, service.SOUND_CLASSES.index("SI")] = 0.88
    db = SimpleNamespace(scalar=AsyncMock(return_value=model(validated=False, accuracy=None, baseline=None)))
    with patch.object(service, "_params_for", return_value={}), patch.object(service, "_head_probs", return_value=probs):
        result = await service.infer_flute(db, target_note=None, **features(1))
    assert result["experimental"] is True
    assert result["posture_evaluable"] is True
    assert result["combined_match"] is True
    assert result["combined_note"] == "SI"
    assert len(result["top_sound_classes"]) == 3
    assert len(result["top_posture_classes"]) == 5
