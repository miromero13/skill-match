"""Contract and fail-closed coverage for the hand-landmark feature migration."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import numpy as np
import pytest
from pydantic import ValidationError

from app.api.ai.datasets import FluteFeaturesRequest, FluteLabelsRequest
from app.core.exceptions import SkillMatchException
from app.services import flute_training_service as service


def features(hands=2):
    visual = [0.0] * 128
    visual[0] = float(hands >= 1)
    visual[64] = float(hands >= 2)
    return {"audio_features": [0.0] * 28, "visual_features": visual,
            "visual_schema": service.VISUAL_FEATURE_SCHEMA}


def test_request_rejects_old_grid_and_nonfinite_landmarks():
    FluteFeaturesRequest(**features())
    with pytest.raises(ValidationError):
        FluteFeaturesRequest(**dict(features(), visual_features=[0.0] * 97))
    with pytest.raises(ValidationError):
        FluteFeaturesRequest(**dict(features(), visual_features=[float("nan")] * 128))
    with pytest.raises(ValidationError):
        FluteFeaturesRequest(**dict(features(), visual_schema="grid-v1"))
    with pytest.raises(ValidationError):
        FluteLabelsRequest(**features(), participant_id="p1", note_label="SI",
                           sound_label="flauta", posture_label="correcta", feature_frames=[])


def test_legacy_samples_are_excluded_but_labels_remain_for_reprocessing():
    sample = SimpleNamespace(id=uuid4(), participant_id="p1", file_format="mp4", created_at=None)
    legacy = {"participant_id": "p1", "note_label": "SI", "sound_label": "flauta",
              "posture_label": "correcta", "audio_features": [0.0]*28, "visual_features": [0.0]*97}
    with patch.object(service, "_read_labels", return_value=legacy):
        rows, listing = service._labeled_rows([sample])
    assert rows == []
    assert listing[0]["labeled"] is False
    assert listing[0]["note_label"] == "SI"


def test_all_frames_keep_their_participant_and_exported_onnx_dimension():
    sample = SimpleNamespace(id=uuid4(), participant_id="p1", file_format="mp4", created_at=None)
    labeled = dict(features(), participant_id="p1", note_label="SI", sound_label="flauta",
                   posture_label="correcta", feature_frames=[features()] * 4)
    with patch.object(service, "_read_labels", return_value=labeled):
        rows, listing = service._labeled_rows([sample])
    assert listing[0]["labeled"] is True
    assert len(rows) == 4
    assert {r["participant_id"] for r in rows} == {"p1"}
    assert all(r["visual"].shape == (128,) for r in rows)
    heads = {}
    for head, dim in (("sound", 28), ("posture", 128)):
        heads[head] = {"mean": np.zeros(dim), "scale": np.ones(dim),
                       "W": np.zeros((dim, 12)), "b": np.zeros(12)}
    params = service.load_onnx_initializers(service.build_flute_onnx(heads))
    assert params["posture_W"].shape == (128, 12)
    assert service._head_probs(params, "posture", rows[0]["visual"][None, :]).shape == (1, 12)


@pytest.mark.asyncio
async def test_save_preserves_multiple_frames_and_participant():
    sample = SimpleNamespace(id=uuid4(), discipline="musica")
    db = SimpleNamespace(scalar=AsyncMock(return_value=sample), flush=AsyncMock())
    with patch.object(service.garage_s3_storage, "put_object_bytes") as store:
        result = await service.save_flute_labels(db, sample.id, "person-01", "SI", "flauta", "correcta",
                                                **features(), feature_frames=[features()] * 4)
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
            await service.save_flute_labels(db, sample.id, "p1", "DO", "flauta", "correcta",
                                             **features(1), feature_frames=[features(1)] * 3)
        store.assert_not_called()


def model(validated=True, accuracy=0.9, baseline=0.1):
    return SimpleNamespace(id=uuid4(), version="hands-v1", metricas={
        "visual_schema": service.VISUAL_FEATURE_SCHEMA, "validated": validated,
        "posture": {"test_accuracy": accuracy, "majority_baseline_accuracy": baseline,
                    "train_class_counts": {"SI": 5, "DO": 5}}})


@pytest.mark.asyncio
async def test_old_active_model_is_rejected_before_loading_weights():
    old = model()
    old.metricas.pop("visual_schema")
    with patch.object(service, "_params_for") as params:
        with pytest.raises(SkillMatchException) as exc:
            await service.infer_flute(SimpleNamespace(scalar=AsyncMock(return_value=old)), "SI", **features())
        assert exc.value.statuscode == 409
        params.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("hands,validated,accuracy,baseline,confidence", [
    (0, True, 0.9, 0.1, 0.9), (2, False, 0.9, 0.1, 0.9),
    (2, True, 0.091, 0.091, 0.9), (2, True, 0.9, 0.1, 0.3),
])
async def test_unreliable_posture_is_inconclusive(hands, validated, accuracy, baseline, confidence):
    probs = np.zeros((1, 12))
    probs[0, service.POSTURE_CLASSES.index("SI")] = confidence
    db = SimpleNamespace(scalar=AsyncMock(return_value=model(validated, accuracy, baseline)))
    with patch.object(service, "_params_for", return_value={}), patch.object(service, "_head_probs", return_value=probs):
        result = await service.infer_flute(db, "SI", **features(hands))
    assert result["posture_ok"] is None
    assert result["posture_evaluable"] is False
    assert result["posture_reason"]


@pytest.mark.asyncio
async def test_supported_confident_prediction_can_match_learned_fingering():
    probs = np.zeros((1, 12))
    probs[0, service.POSTURE_CLASSES.index("SI")] = 0.9
    db = SimpleNamespace(scalar=AsyncMock(return_value=model()))
    with patch.object(service, "_params_for", return_value={}), patch.object(service, "_head_probs", return_value=probs):
        result = await service.infer_flute(db, "SI", **features())
    assert result["posture_ok"] is True
    assert result["posture_evaluable"] is True
