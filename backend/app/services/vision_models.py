"""Single source of truth for the local face models and their readiness.

The weights are provisioned explicitly with ``scripts/install_vision_models.py`` (SHA-256 pinned);
nothing here downloads anything. Consumers must fail closed when a model is not usable: a missing
model is never a reason to report a clean face or to persist a synthetic embedding.

Paths are read through this module at call time so a deployment (or a test) can relocate them.
"""
import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path

import cv2

logger = logging.getLogger("skillmatch.vision_models")

MODELS_DIR = Path(__file__).resolve().parent.parent / "models" / "weights"
YUNET_MODEL_PATH = MODELS_DIR / "face_detection_yunet_2023mar.onnx"
SFACE_MODEL_PATH = MODELS_DIR / "face_recognition_sface_2021dec.onnx"
MEDIAPIPE_TASK_PATH = MODELS_DIR / "face_landmarker.task"

INSTALL_COMMAND = "cd backend && .venv/bin/python scripts/install_vision_models.py"


@dataclass(frozen=True)
class ModelState:
    path: Path
    present: bool
    loadable: bool
    error: str | None = None


@dataclass(frozen=True)
class VisionModelsStatus:
    models: dict[str, ModelState] = field(default_factory=dict)

    @property
    def missing(self) -> list[str]:
        """Names of the models that are not usable (absent or failing to load)."""
        return [name for name, state in self.models.items() if not state.loadable]

    @property
    def ready(self) -> bool:
        return not self.missing

    @property
    def identity_ready(self) -> bool:
        """Enrollment and identity matching need both YuNet (detection) and SFace (embedding)."""
        return self.models["yunet"].loadable and self.models["sface"].loadable

    @property
    def detection_ready(self) -> bool:
        """A supervision window can be analysed with YuNet or the MediaPipe landmarker."""
        return self.models["yunet"].loadable or self.models["face_landmarker"].loadable


def _probe_onnx(path: Path, create) -> ModelState:
    if not path.is_file():
        return ModelState(path, present=False, loadable=False, error="file not found")
    try:
        create(str(path))
    except Exception as exc:  # corrupt file, unsupported opset, ...
        return ModelState(path, present=True, loadable=False, error=str(exc)[:200])
    return ModelState(path, present=True, loadable=True)


def _probe_landmarker(path: Path) -> ModelState:
    if not path.is_file():
        return ModelState(path, present=False, loadable=False, error="file not found")
    try:
        from mediapipe.tasks import python
        from mediapipe.tasks.python import vision

        options = vision.FaceLandmarkerOptions(base_options=python.BaseOptions(model_asset_path=str(path)))
        landmarker = vision.FaceLandmarker.create_from_options(options)
        landmarker.close()
    except Exception as exc:  # mediapipe not importable or the task file is invalid
        return ModelState(path, present=True, loadable=False, error=str(exc)[:200])
    return ModelState(path, present=True, loadable=True)


def vision_models_status() -> VisionModelsStatus:
    """Probe every model: present on disk and actually loadable. Blocking; run off the event loop."""
    return VisionModelsStatus(
        models={
            "yunet": _probe_onnx(
                YUNET_MODEL_PATH,
                lambda p: cv2.FaceDetectorYN.create(model=p, config="", input_size=(320, 320)),
            ),
            "sface": _probe_onnx(SFACE_MODEL_PATH, lambda p: cv2.FaceRecognizerSF.create(model=p, config="")),
            "face_landmarker": _probe_landmarker(MEDIAPIPE_TASK_PATH),
        }
    )


def log_vision_models_status() -> VisionModelsStatus:
    """Log one ERROR per unusable model with the remediation; never raises on missing models."""
    status = vision_models_status()
    for name in status.missing:
        state = status.models[name]
        reason = "no está instalado" if not state.present else f"no se pudo cargar ({state.error})"
        logger.error(
            "Modelo de visión '%s' %s en %s. Enrolamiento biométrico y supervisión audiovisual "
            "fallan en cerrado hasta instalarlo: %s",
            name, reason, state.path, INSTALL_COMMAND,
        )
    if status.ready:
        logger.info("Modelos de visión locales (YuNet, SFace, FaceLandmarker) listos.")
    return status


async def report_vision_models_readiness() -> None:
    """Startup hook: report readiness off the event loop and never crash the application."""
    try:
        await asyncio.to_thread(log_vision_models_status)
    except Exception as exc:
        logger.error("No se pudo comprobar la disponibilidad de los modelos de visión: %s", exc)
