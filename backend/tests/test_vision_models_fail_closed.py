"""S13 / T2: vision models are provisioned explicitly and every consumer fails closed without them."""
import base64
import importlib.util
import logging
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import cv2
import numpy as np
import pytest

from app.core.exceptions import SkillMatchException
from app.models.user import User, UserRole
from app.schemas.user_profile import BiometricEnrollRequest, IdentityVerifyRequest
from app.services import vision_models
from app.services.biometric_service import BiometricService
from app.services.continuous_supervision_service import ContinuousSupervisionService
from app.services.user_profile_service import UserProfileService

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "install_vision_models.py"
OLD_EMBEDDING = "[0.1,0.2]"


def jpeg_b64(img: np.ndarray) -> str:
    ok, buf = cv2.imencode(".jpg", img)
    assert ok
    return base64.b64encode(buf).decode("ascii")


def bright_jpeg_b64() -> str:
    return jpeg_b64(np.full((240, 320, 3), 180, dtype=np.uint8))


def sharp_jpeg_b64() -> str:
    rng = np.random.default_rng(7)
    return jpeg_b64(rng.integers(0, 255, (240, 320, 3), dtype=np.uint8))


@pytest.fixture
def no_vision_models(monkeypatch, tmp_path):
    """Point every model path at an empty directory and reset all cached model state."""
    monkeypatch.setattr(vision_models, "MODELS_DIR", tmp_path)
    monkeypatch.setattr(vision_models, "YUNET_MODEL_PATH", tmp_path / "yunet.onnx")
    monkeypatch.setattr(vision_models, "SFACE_MODEL_PATH", tmp_path / "sface.onnx")
    monkeypatch.setattr(vision_models, "MEDIAPIPE_TASK_PATH", tmp_path / "face_landmarker.task")
    monkeypatch.setattr(BiometricService, "_init_failed_at", None)
    monkeypatch.setattr(BiometricService, "_detector", None)
    monkeypatch.setattr(BiometricService, "_recognizer", None)
    monkeypatch.setattr(ContinuousSupervisionService, "_mp_landmarker", None)
    monkeypatch.setattr(ContinuousSupervisionService, "_mp_failed_at", None)
    return tmp_path


def make_user() -> User:
    return User(
        id=uuid.uuid4(), email="enroll@skillmatch.io", full_name="Ana Lopez Rios",
        role=UserRole.MEMBER, is_active=True, biometric_embedding=OLD_EMBEDDING,
        biometric_face_hash="old-hash", biometric_enrolled_at=None,
    )


def mock_db() -> MagicMock:
    db = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    return db


# ---- readiness ---------------------------------------------------------------------------------

def test_status_reports_every_missing_model(no_vision_models):
    status = vision_models.vision_models_status()
    assert status.ready is False
    assert status.identity_ready is False
    assert status.detection_ready is False
    assert set(status.missing) == {"yunet", "sface", "face_landmarker"}
    assert all(not item.present and not item.loadable for item in status.models.values())


def test_status_present_but_corrupt_file_is_not_loadable(no_vision_models):
    (no_vision_models / "yunet.onnx").write_bytes(b"not an onnx model")
    status = vision_models.vision_models_status()
    assert status.models["yunet"].present is True
    assert status.models["yunet"].loadable is False
    assert status.detection_ready is False


def test_startup_report_logs_error_and_does_not_raise(no_vision_models, caplog, monkeypatch):
    # alembic's fileConfig (migration tests) disables pre-existing loggers for the rest of the run.
    monkeypatch.setattr(vision_models.logger, "disabled", False)
    with caplog.at_level(logging.ERROR, logger="skillmatch.vision_models"):
        status = vision_models.log_vision_models_status()
    assert status.ready is False
    errors = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    assert errors, "a missing model must be logged at ERROR level"
    joined = " ".join(errors)
    assert "install_vision_models.py" in joined
    for name in ("yunet", "sface", "face_landmarker"):
        assert name in joined


@pytest.mark.asyncio
async def test_startup_hook_never_crashes_the_app(monkeypatch):
    def boom():
        raise RuntimeError("probe exploded")

    monkeypatch.setattr(vision_models, "vision_models_status", boom)
    await vision_models.report_vision_models_readiness()  # must swallow and log


# ---- continuous supervision --------------------------------------------------------------------

def test_window_without_models_is_not_a_clean_face(no_vision_models):
    result = ContinuousSupervisionService.assess_window(
        [("data:image/jpeg;base64," + bright_jpeg_b64())], None, trial_id="no-models",
    )
    assert "MODEL_UNAVAILABLE" in result["anomalies"]
    assert result["face_count"] != 1
    assert result["face_count"] == 0
    assert result["identity_match"] is None
    assert result["head_orientation"] == "UNKNOWN"


def test_frame_without_any_model_is_flagged_not_clean(no_vision_models):
    img = np.full((120, 160, 3), 128, dtype=np.uint8)
    res = ContinuousSupervisionService.analyze_frame_face(img, None, None, None)
    assert res["model_unavailable"] is True
    assert res["face_count"] == 0
    assert res["identity_match"] is None


def test_class_name_is_not_sniffed_and_landmarker_is_injected(monkeypatch):
    calls = []

    def fake_mediapipe(image, trial_key, landmarker):
        calls.append(landmarker)
        return {"face_count": 0, "orientation": "UNKNOWN", "mouth_open_score": 0.0, "mouth_patch": None}

    monkeypatch.setattr(ContinuousSupervisionService, "_analyze_with_mediapipe", staticmethod(fake_mediapipe))

    class FaceDetectorYN:  # same name as the real class: production code must not care
        def setInputSize(self, _size):
            pass

        def detect(self, _img):
            return 1, None

    img = np.full((120, 160, 3), 128, dtype=np.uint8)
    ContinuousSupervisionService.analyze_frame_face(img, FaceDetectorYN(), None, None)
    assert calls == []

    sentinel = object()
    ContinuousSupervisionService.analyze_frame_face(img, FaceDetectorYN(), None, None, landmarker=sentinel)
    assert calls == [sentinel]


def test_mediapipe_init_is_retried_after_cooldown(monkeypatch):
    monkeypatch.setattr(ContinuousSupervisionService, "_mp_landmarker", None)
    monkeypatch.setattr(ContinuousSupervisionService, "_mp_failed_at", None)
    clock = {"now": 1000.0}
    monkeypatch.setattr(ContinuousSupervisionService, "_monotonic", staticmethod(lambda: clock["now"]))
    attempts = []
    ready = object()

    def build():
        attempts.append(clock["now"])
        if len(attempts) == 1:
            raise RuntimeError("weights missing")
        return ready

    monkeypatch.setattr(ContinuousSupervisionService, "_build_landmarker", staticmethod(build))

    assert ContinuousSupervisionService.get_mediapipe_landmarker() is None
    clock["now"] += ContinuousSupervisionService.MP_RETRY_COOLDOWN_S - 1
    assert ContinuousSupervisionService.get_mediapipe_landmarker() is None
    assert len(attempts) == 1, "no retry storm inside the cooldown"
    clock["now"] += 2
    assert ContinuousSupervisionService.get_mediapipe_landmarker() is ready
    assert len(attempts) == 2
    assert ContinuousSupervisionService.get_mediapipe_landmarker() is ready
    assert len(attempts) == 2


# ---- enrollment / identity ---------------------------------------------------------------------

@pytest.mark.asyncio
async def test_enroll_undecodable_image_is_400_and_keeps_embedding(no_vision_models):
    user, db = make_user(), mock_db()
    garbage = base64.b64encode(b"definitely-not-an-image-" * 4).decode()
    with pytest.raises(SkillMatchException) as exc:
        await UserProfileService.enroll_biometrics(
            db, user, BiometricEnrollRequest(image_base64=garbage, lighting_score=0.9, face_centered=True),
        )
    assert exc.value.statuscode == 400
    assert "decodificar" in exc.value.message
    assert user.biometric_embedding == OLD_EMBEDDING
    assert user.biometric_face_hash == "old-hash"
    db.commit.assert_not_called()


@pytest.mark.asyncio
async def test_enroll_without_models_is_503_and_persists_nothing(no_vision_models):
    user, db = make_user(), mock_db()
    with pytest.raises(SkillMatchException) as exc:
        await UserProfileService.enroll_biometrics(
            db, user, BiometricEnrollRequest(image_base64=bright_jpeg_b64(), lighting_score=0.9, face_centered=True),
        )
    assert exc.value.statuscode == 503
    assert exc.value.message.startswith("Servicio biométrico no disponible")
    assert user.biometric_embedding == OLD_EMBEDDING
    assert user.biometric_face_hash == "old-hash"
    db.commit.assert_not_called()


def test_no_synthetic_embedding_helper_remains():
    assert not hasattr(BiometricService, "_fallback_128d_embedding")


@pytest.mark.asyncio
async def test_identity_verification_without_models_is_503_and_not_a_rejection(no_vision_models):
    user, db = make_user(), mock_db()
    user.identity_status = "PENDING"
    user.identity_rejection_reason = None
    request = IdentityVerifyRequest(
        id_card_base64=sharp_jpeg_b64(), selfie_base64=bright_jpeg_b64(),
        id_number="8392102", full_name="Ana Lopez Rios",
    )
    with pytest.raises(SkillMatchException) as exc:
        await UserProfileService.verify_identity(db, user, request)
    assert exc.value.statuscode == 503
    assert user.identity_status == "PENDING", "a platform outage must not reject the member"
    assert user.identity_rejection_reason is None
    assert user.biometric_embedding == OLD_EMBEDDING


# ---- installer ---------------------------------------------------------------------------------

@pytest.fixture(scope="module")
def installer():
    spec = importlib.util.spec_from_file_location("install_vision_models", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_installer_pins_exactly_the_runtime_models(installer):
    assert set(installer.MODELS) == {
        vision_models.YUNET_MODEL_PATH.name,
        vision_models.SFACE_MODEL_PATH.name,
        vision_models.MEDIAPIPE_TASK_PATH.name,
    }
    assert installer.ROOT == vision_models.MODELS_DIR
    for url, sha in installer.MODELS.values():
        assert url.startswith("https://")
        assert len(sha) == 64 and int(sha, 16) >= 0


def test_installer_refuses_hash_mismatch_and_leaves_nothing(installer, tmp_path):
    expected = "0" * 64

    def fetch(temp: Path):
        temp.write_bytes(b"tampered model")

    with pytest.raises(RuntimeError, match="[Cc]hecksum"):
        installer.install_atomically(tmp_path, "face_landmarker.task", expected, fetch)
    assert list(tmp_path.iterdir()) == []


def test_installer_installs_atomically_when_hash_matches(installer, tmp_path):
    payload = b"genuine model bytes"
    import hashlib

    expected = hashlib.sha256(payload).hexdigest()
    installer.install_atomically(tmp_path, "m.onnx", expected, lambda temp: temp.write_bytes(payload))
    assert [p.name for p in tmp_path.iterdir()] == ["m.onnx"]
    assert (tmp_path / "m.onnx").read_bytes() == payload


def test_installer_never_overwrites_an_existing_mismatching_file(installer, tmp_path):
    (tmp_path / "face_landmarker.task").write_bytes(b"locally modified")
    with pytest.raises(RuntimeError, match="Refusing to overwrite"):
        installer.verify_existing(tmp_path, {"face_landmarker.task": ("https://x", "0" * 64)})
    assert (tmp_path / "face_landmarker.task").read_bytes() == b"locally modified"


def test_installer_download_rejects_wrong_bytes(installer, tmp_path, monkeypatch):
    class Response:
        url = "https://example.test/model"

        def __init__(self):
            self.chunks = [b"abc", b""]

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self, _size):
            return self.chunks.pop(0)

    monkeypatch.setattr(installer.urllib.request, "urlopen", lambda *a, **k: Response())
    with pytest.raises(RuntimeError, match="[Cc]hecksum"):
        installer.install_atomically(
            tmp_path, "m.onnx", "0" * 64,
            lambda temp: installer.download("https://example.test/model", temp, "0" * 64),
        )
    assert list(tmp_path.iterdir()) == []


def test_installer_refuses_insecure_url(installer, tmp_path):
    with pytest.raises(RuntimeError, match="HTTPS"):
        installer.download("http://example.test/model", tmp_path / "m", "0" * 64)
