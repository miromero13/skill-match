"""Shared stubs and synthetic images for the T7 tests (extra faces, identity, occlusion, camera health).

Detector stubs return YuNet-shaped rows (x, y, w, h, 5 landmarks, score) on a 320x240 frame; the synthetic
face drawn by ``face_image`` has its eyes, nose and mouth exactly where ``row()`` says they are, so the same
geometry drives the pixel-level occlusion measurements.
"""
import base64
import types

import cv2
import numpy as np

from app.services.integrity.audio_analyzer import AudioAnalyzer
from app.services.integrity.engine import IntegrityEngine
from app.services.integrity.frame_analyzer import FrameAnalyzer
from app.services.integrity.models import FrameObservation
from app.services.integrity.policy import SupervisionProfile
from app.services.integrity.state import InMemoryStateStore

WIDTH, HEIGHT = 320, 240
BASE_MS = 1_700_000_000_000
QUIET = [0.0] * 38_400


def quiet(duration_ms):
    return [0.0] * (duration_ms * 16)


REFERENCE = np.zeros(128, dtype=np.float32)
REFERENCE[0] = 1.0


def row(x=80, y=40, w=120, h=150, score=0.95, shift=0):
    """A YuNet detection: frontal geometry inside the box (eyes at 95, nose 126, mouth 155 for the default box)."""
    return [x, y, w, h, 115 + shift, 95, 165 + shift, 95, 140 + shift, 126, 120 + shift, 155, 160 + shift, 155, score]


NEUTRAL = row()
SECOND = row(x=10, y=30, w=70, h=90, score=0.9)  # a second, credible person on the left
FAR_FACE = row(x=10, y=10, w=10, h=12, score=0.9)  # 5 % of the frame height: a poster, not a person
WEAK_FACE = row(x=10, y=30, w=70, h=90, score=0.6)  # big enough but not confident


def one_hot(index):
    vec = np.zeros(128, dtype=np.float32)
    vec[index] = 1.0
    return vec


def b64(image):
    ok, buf = cv2.imencode(".jpg", image)
    assert ok
    return "data:image/jpeg;base64," + base64.b64encode(buf).decode("ascii")


def scene(seed, noise=6.0):
    """A varied, noisy background: never mistaken for a covered lens or a frozen camera."""
    rng = np.random.default_rng(seed)
    base = np.linspace(60, 180, WIDTH, dtype=np.float32)[None, :, None] * np.ones((HEIGHT, 1, 3), np.float32)
    base[..., 1] *= 0.9
    return np.clip(base + rng.normal(0, noise, base.shape), 0, 255).astype(np.uint8)


def textured_b64(seed):
    return b64(scene(seed))


SKIN = (105, 150, 200)  # BGR; Cr ~157, Cb ~97
DARK_SKIN = (60, 95, 140)
PALE_SKIN = (170, 190, 235)


def face_image(seed, skin=SKIN, cover=None):
    """A synthetic frontal face on the geometry of ``row()``: skin ellipse, brows, eyes, nose shading, red lips.

    ``cover``: ``mouth_hand`` / ``mouth_mask`` over the lower face, ``face_hand`` / ``face_black`` over the whole face.
    Sensor noise and a small lighting drift change from frame to frame, like a live camera.
    """
    img = scene(seed, noise=4.0)
    cv2.ellipse(img, (140, 115), (62, 82), 0, 0, 360, skin, -1)
    for cx in (115, 165):
        cv2.ellipse(img, (cx, 95), (11, 5), 0, 0, 360, (235, 235, 235), -1)
        cv2.circle(img, (cx, 95), 4, (30, 25, 20), -1)
        cv2.line(img, (cx - 12, 83), (cx + 12, 81), (25, 30, 40), 3)
    cv2.line(img, (140, 100), (138, 124), tuple(int(c * 0.7) for c in skin), 3)
    cv2.circle(img, (133, 128), 2, (40, 40, 60), -1)
    cv2.circle(img, (147, 128), 2, (40, 40, 60), -1)
    cv2.ellipse(img, (140, 155), (20, 6), 0, 0, 360, (80, 70, 180), -1)
    cv2.line(img, (122, 155), (158, 155), (50, 40, 90), 2)
    covers = {
        "mouth_hand": ((98, 138), (182, 180), tuple(min(255, c + 6) for c in skin)),
        "mouth_mask": ((98, 138), (182, 180), (235, 225, 200)),
        "face_hand": ((72, 50), (208, 184), tuple(min(255, c + 6) for c in skin)),
        "face_black": ((72, 50), (208, 184), (8, 8, 8)),
    }
    if cover:
        top, bottom, color = covers[cover]
        cv2.rectangle(img, top, bottom, color, -1)
    rng = np.random.default_rng(seed + 7)
    drift = 1.0 + 0.02 * np.sin(seed)
    return np.clip(img.astype(np.float32) * drift + rng.normal(0, 3.0, img.shape), 0, 255).astype(np.uint8)


def face_b64(seed, **kwargs):
    return b64(face_image(seed, **kwargs))


class Scripted:
    """YuNet stand-in: call N returns ``script[N]`` (the last entry repeats); ``None``/``[]`` is no face."""

    def __init__(self, script):
        self.script = list(script)
        self.calls = 0

    def setInputSize(self, _size):
        pass

    def detect(self, _img):
        rows = self.script[min(self.calls, len(self.script) - 1)]
        self.calls += 1
        return 1, (np.asarray(rows, dtype=np.float32) if rows else None)


class ScriptedRecognizer:
    """SFace stand-in: call N returns the feature ``features[N]`` (the last entry repeats)."""

    def __init__(self, features):
        self.features = [np.asarray(f, dtype=np.float32) for f in features]
        self.calls = 0

    def alignCrop(self, image, _face):
        return image

    def feature(self, _aligned):
        value = self.features[min(self.calls, len(self.features) - 1)]
        self.calls += 1
        return value


class Harness:
    """One trial: a state store shared by the frame analyzer and the policy, windows of 2.4 s."""

    def __init__(self, recognizer=None, reference=None, mediapipe=None, stateful=True):
        self.state = InMemoryStateStore()
        self.detector = Scripted([[]])
        self.recognizer = recognizer
        self.reference = reference
        self.mediapipe = mediapipe  # script of FrameObservation per call, or None (MediaPipe not used)
        self.mp_calls = 0
        self.frames = FrameAnalyzer(
            self.state,
            vision_provider=lambda: (self.detector, self.recognizer),
            landmarker_provider=lambda: object() if self.mediapipe is not None else None,
            mediapipe_runner=self._mediapipe,
        )
        self.engine = IntegrityEngine(self.frames, AudioAnalyzer(self.state))
        self.profile = SupervisionProfile(gaze_runs=self.state if stateful else None)
        self.stateful = stateful
        self.windows = 0
        self.clock = 0  # ms elapsed since the first window

    def _mediapipe(self, _image, _key, _landmarker):
        value = self.mediapipe[min(self.mp_calls, len(self.mediapipe) - 1)]
        self.mp_calls += 1
        return value

    def window(self, script, images=None, times=None, mediapipe=None, gaze_samples=(), duration_ms=2400):
        """Runs one window: ``script`` is the YuNet rows per frame; ``images`` default to textured scenes."""
        count = len(script)
        times = list(times) if times is not None else [round(i * duration_ms / count) for i in range(count)]
        self.detector = Scripted(script)
        if mediapipe is not None:
            self.mediapipe, self.mp_calls = mediapipe, 0
        frames = images if images is not None else [textured_b64(1000 * self.windows + i) for i in range(count)]
        result = self.engine.assess_window(
            frames, quiet(duration_ms), duration_ms=duration_ms, reference_embedding=self.reference, session_key="trial",
            profile=self.profile, frame_times_ms=times, gaze_samples=gaze_samples,
            window_start_ms=BASE_MS + self.clock,
        )
        self.windows += 1
        self.clock += duration_ms
        return result.to_dict()


def mp_faces(count, orientation="CENTER"):
    """A MediaPipe observation stub with ``count`` faces."""
    if count == 1:
        return FrameObservation(face_count=1, orientation=orientation, pitch_deg=0.0, yaw_deg=0.0)
    return FrameObservation(face_count=count)


def landmarks_result(face_sets):
    """A FaceLandmarker result with several faces; each entry is the (cx, cy, height) of a landmark cloud."""
    clouds = []
    for cx, cy, height in face_sets:
        pts = np.full((478, 3), 0.0)
        pts[:, 0] = cx
        pts[:, 1] = cy
        pts[10] = (cx, cy - height / 2, 0.0)
        pts[152] = (cx, cy + height / 2, 0.0)
        pts[1] = (cx, cy, 0.0)
        pts[78] = (cx - 0.07, cy + 0.15 * height, 0.0)
        pts[308] = (cx + 0.07, cy + 0.15 * height, 0.0)
        pts[13] = (cx, cy + 0.14 * height, 0.0)
        pts[14] = (cx, cy + 0.16 * height, 0.0)
        clouds.append([types.SimpleNamespace(x=float(p[0]), y=float(p[1]), z=float(p[2])) for p in pts])
    return types.SimpleNamespace(
        face_landmarks=clouds, face_blendshapes=[[] for _ in clouds],
        facial_transformation_matrixes=[np.eye(4) for _ in clouds],
    )
