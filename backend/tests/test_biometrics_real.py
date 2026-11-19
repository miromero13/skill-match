import base64
import json
import cv2
import numpy as np
import pytest
from fastapi import status

from app.core.exceptions import SkillMatchException
from app.services import vision_models
from app.services.biometric_service import (
    BiometricService,
    EMBEDDING_DIMENSIONS,
    SFACE_COSINE_THRESHOLD,
)


# Real-model assertions need the weights provisioned by scripts/install_vision_models.py.
requires_face_models = pytest.mark.skipif(
    not vision_models.vision_models_status().identity_ready,
    reason="YuNet/SFace weights not installed (run scripts/install_vision_models.py)",
)


def _encode_to_base64_jpeg(img: np.ndarray) -> str:
    _, buf = cv2.imencode(".jpg", img)
    return base64.b64encode(buf).decode("utf-8")


def test_reject_empty_or_corrupt_payload():
    with pytest.raises(SkillMatchException) as exc_info:
        BiometricService.enroll_face(image_base64="")
    assert exc_info.value.statuscode == status.HTTP_400_BAD_REQUEST

    with pytest.raises(SkillMatchException) as exc_info:
        BiometricService.enroll_face(image_base64="not_base64!!!")
    assert exc_info.value.statuscode == status.HTTP_400_BAD_REQUEST


def test_reject_dark_image():
    dark_img = np.zeros((480, 640, 3), dtype=np.uint8)
    b64 = _encode_to_base64_jpeg(dark_img)

    with pytest.raises(SkillMatchException) as exc_info:
        BiometricService.enroll_face(image_base64=b64)
    assert exc_info.value.statuscode == status.HTTP_400_BAD_REQUEST
    assert "Iluminación insuficiente" in exc_info.value.message


@requires_face_models
def test_reject_blank_image_without_face():
    # Imagen clara pero sin rostro humano
    blank_img = np.full((480, 640, 3), 200, dtype=np.uint8)
    b64 = _encode_to_base64_jpeg(blank_img)

    with pytest.raises(SkillMatchException) as exc_info:
        BiometricService.enroll_face(image_base64=b64)
    assert exc_info.value.statuscode == status.HTTP_400_BAD_REQUEST
    assert "No se detectó ningún rostro" in exc_info.value.message


def test_compare_faces_same_and_different():
    vec_a = [0.1] * EMBEDDING_DIMENSIONS
    vec_b = [0.1] * EMBEDDING_DIMENSIONS
    vec_c = [-0.1] * EMBEDDING_DIMENSIONS

    match_same, sim_same = BiometricService.compare_faces(vec_a, vec_b)
    assert match_same is True
    assert sim_same >= 0.99

    match_diff, sim_diff = BiometricService.compare_faces(vec_a, vec_c)
    assert match_diff is False
    assert sim_diff < SFACE_COSINE_THRESHOLD


def test_compare_faces_with_serialized_json():
    vec_a = [0.05] * EMBEDDING_DIMENSIONS
    json_a = json.dumps(vec_a)
    json_b = json.dumps(vec_a)

    is_match, similarity = BiometricService.compare_faces(json_a, json_b)
    assert is_match is True
    assert similarity >= 0.99
