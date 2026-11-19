"""Per-frame measurements: decoding, MediaPipe pose/blendshapes, YuNet/SFace identity and the YuNet fallback.

The analyzer measures; it never decides anomalies. The only per-frame judgement is the head-orientation
class (CENTER/DOWN/LEFT/RIGHT), which needs the session baseline and so lives next to the pose math.
Models are injected (``vision_provider``, ``landmarker_provider``) or loaded lazily through
``app.services.vision_models`` (T2); a missing model yields ``FrameObservation.unavailable()`` and is never
a clean face (fail closed).

Calibration mapping (T9): ``CalibrationVisionService`` pose/face checks map to ``FrameAnalyzer.analyze_frame``.
"""
import base64
import binascii
import dataclasses
import json
import logging
import threading
import time
from typing import Any, Callable, Mapping, Optional, Sequence, Union

import cv2
import numpy as np

from app.schemas.browser_supervision import MAX_FRAME_B64_CHARS
from app.services import vision_models
from app.services.integrity import camera, occlusion
from app.services.integrity import thresholds as t
from app.services.integrity.gaze import measure_gaze
from app.services.integrity.models import FrameBatch, FrameObservation, FrameOcclusion, MouthPatch
from app.services.integrity.state import SessionStateStore

logger = logging.getLogger("skillmatch.continuous_supervision")

# The MediaPipe landmarker is a shared native object: every detect() call is serialized.
MP_DETECT_LOCK = threading.Lock()

MediaPipeRunner = Callable[[np.ndarray, Optional[str], Any], Union[FrameObservation, Mapping[str, Any], None]]


def jpeg_dimensions(data: bytes) -> Optional[tuple[int, int]]:
    """Reads (width, height) from the first SOF marker without decoding any pixels."""
    size = len(data)
    pos = 2
    while pos < size:
        if data[pos] != 0xFF:
            return None
        while pos < size and data[pos] == 0xFF:  # fill bytes
            pos += 1
        if pos >= size:
            return None
        marker = data[pos]
        pos += 1
        if marker == 0x01 or 0xD0 <= marker <= 0xD8:  # standalone markers carry no length
            continue
        if marker in (0xD9, 0xDA) or pos + 2 > size:  # EOI / SOS before any SOF
            return None
        length = int.from_bytes(data[pos:pos + 2], "big")
        if length < 2:
            return None
        if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
            if pos + 7 > size:
                return None
            height = int.from_bytes(data[pos + 3:pos + 5], "big")
            width = int.from_bytes(data[pos + 5:pos + 7], "big")
            return (width, height) if width and height else None
        pos += length
    return None


def decode_frame(raw: str) -> Optional[np.ndarray]:
    """Safely decodes a base64 JPEG; oversized or malformed images are rejected before pixel decoding."""
    if not raw:
        return None
    encoded = raw.split(",", 1)[1] if raw.startswith("data:") else raw
    if len(encoded) > MAX_FRAME_B64_CHARS:
        return None
    try:
        data = base64.b64decode(encoded.strip(), validate=False)
    except (ValueError, binascii.Error):
        return None
    if len(data) < 32 or data[:2] != b"\xff\xd8":
        return None
    dims = jpeg_dimensions(data)
    if dims is None:
        return None
    # Either orientation of Full HD is fine; anything larger is a decompression-bomb risk.
    long_side, short_side = max(dims), min(dims)
    if long_side > t.MAX_FRAME_WIDTH or short_side > t.MAX_FRAME_HEIGHT:
        return None
    return cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)


def create_vision_models() -> tuple[Any, Any]:
    """Creates per-request YuNet detector and SFace recognizer instances (None when unavailable)."""
    detector = None
    recognizer = None
    if vision_models.YUNET_MODEL_PATH.is_file():
        try:
            detector = cv2.FaceDetectorYN.create(
                str(vision_models.YUNET_MODEL_PATH), "", t.YUNET_INPUT_SIZE,
                t.YUNET_SCORE_THRESHOLD, t.YUNET_NMS_THRESHOLD, t.YUNET_TOP_K,
            )
        except Exception as exc:
            logger.warning("No se pudo instanciar detector YuNet: %s", exc)
    if vision_models.SFACE_MODEL_PATH.is_file():
        try:
            recognizer = cv2.FaceRecognizerSF.create(str(vision_models.SFACE_MODEL_PATH), "")
        except Exception as exc:
            logger.warning("No se pudo instanciar reconocedor SFace: %s", exc)
    return detector, recognizer


def credible_yunet_rows(rows: Sequence[np.ndarray], frame_height: int) -> list[np.ndarray]:
    """YuNet detections that can be a second person: confident enough and not a tiny background face."""
    return [
        row for row in rows
        if float(row[14]) >= t.MULTI_FACE_MIN_YUNET_SCORE
        and float(row[3]) >= t.MULTI_FACE_MIN_HEIGHT_FRAC * max(frame_height, 1)
    ]


def parse_reference_embedding(embedding_json: Optional[str]) -> Optional[np.ndarray]:
    """Parses a stored 128-d SFace embedding into a unit vector; anything malformed is None."""
    if not embedding_json:
        return None
    try:
        parsed = np.asarray(json.loads(embedding_json), dtype=np.float32)
        norm = float(np.linalg.norm(parsed))
        if parsed.shape == (t.REFERENCE_EMBEDDING_DIM,) and norm > 1e-6:
            return parsed / norm
    except Exception:
        pass
    return None


def extract_mouth_and_cheeks(image: np.ndarray, face: np.ndarray) -> Optional[MouthPatch]:
    """Affine-stabilized mouth and cheek patches for the patch-based mouth fallback (YuNet only)."""
    try:
        rx, ry = float(face[4]), float(face[5])
        lx, ly = float(face[6]), float(face[7])
        nx, ny = float(face[8]), float(face[9])
        rmx, rmy = float(face[10]), float(face[11])
        lmx, lmy = float(face[12]), float(face[13])

        eyes = sorted([[rx, ry], [lx, ly]], key=lambda pt: pt[0])
        anchors = np.asarray([eyes[0], eyes[1], [nx, ny]], dtype=np.float32)
        if float(np.linalg.norm(anchors[1] - anchors[0])) < 10.0:
            return None

        transform = cv2.getAffineTransform(
            anchors, np.float32([[40.0, 42.0], [88.0, 42.0], [64.0, 67.0]])
        )
        if not np.isfinite(transform).all():
            return None

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        aligned = cv2.warpAffine(gray, transform, (128, 128), borderMode=cv2.BORDER_REPLICATE)
        smoothed = cv2.GaussianBlur(aligned, (3, 3), 0).astype(np.float32)

        corners = cv2.transform(
            np.asarray([[[rmx, rmy], [lmx, lmy]]], dtype=np.float32), transform
        )[0]
        center = corners.mean(axis=0)
        box_w = float(np.clip(abs(corners[1, 0] - corners[0, 0]) * 1.5, 24.0, 60.0))
        box_h = box_w * 0.72
        x1 = int(np.clip(center[0] - box_w / 2.0, 0, 116))
        x2 = int(np.clip(center[0] + box_w / 2.0, x1 + 12, 128))
        y1 = int(np.clip(center[1] - box_h / 2.0, 52, 116))
        y2 = int(np.clip(center[1] + box_h / 2.0, y1 + 10, 128))

        mouth_crop = smoothed[y1:y2, x1:x2]
        if mouth_crop.size == 0:
            return None
        mouth_norm = cv2.resize(mouth_crop, (40, 28), interpolation=cv2.INTER_LINEAR)
        cheeks = np.concatenate([smoothed[72:108, 16:32].ravel(), smoothed[72:108, 96:112].ravel()])
        return mouth_norm, cheeks
    except Exception:
        return None


class LandmarkerLifecycle:
    """Lazily builds the process-wide MediaPipe FaceLandmarker; a failed init is retried after a cooldown.

    State is class-level on purpose (one native model per process). ``ContinuousSupervisionService``
    subclasses this so its historical test seams (``_build_landmarker``, ``_monotonic``, ...) keep working.
    """

    _mp_landmarker: Any = None
    # Monotonic time of the last failed MediaPipe init; a failure is retried after the cooldown.
    _mp_failed_at: Optional[float] = None
    _mp_lock = threading.Lock()
    MP_RETRY_COOLDOWN_S = t.MP_RETRY_COOLDOWN_S

    @staticmethod
    def _monotonic() -> float:
        return time.monotonic()

    @staticmethod
    def _build_landmarker() -> Any:
        """Creates the local MediaPipe FaceLandmarker (blendshapes + 3D matrices). Raises on failure."""
        task_path = vision_models.MEDIAPIPE_TASK_PATH
        if not task_path.is_file():
            raise FileNotFoundError(f"Modelo MediaPipe no encontrado en {task_path}")
        from mediapipe.tasks import python
        from mediapipe.tasks.python import vision

        base_options = python.BaseOptions(model_asset_path=str(task_path))
        options = vision.FaceLandmarkerOptions(
            base_options=base_options,
            output_face_blendshapes=True,
            output_facial_transformation_matrixes=True,
            num_faces=t.MP_NUM_FACES,
            min_face_detection_confidence=t.MP_MIN_FACE_CONFIDENCE,
            min_face_presence_confidence=t.MP_MIN_FACE_CONFIDENCE,
        )
        return vision.FaceLandmarker.create_from_options(options)

    @classmethod
    def get_mediapipe_landmarker(cls) -> Any:
        """Returns the shared landmarker, or None while it is unavailable."""
        if cls._mp_landmarker is not None:
            return cls._mp_landmarker
        with cls._mp_lock:
            if cls._mp_landmarker is not None:
                return cls._mp_landmarker
            now = cls._monotonic()
            if cls._mp_failed_at is not None and now - cls._mp_failed_at < cls.MP_RETRY_COOLDOWN_S:
                return None
            try:
                cls._mp_landmarker = cls._build_landmarker()
                cls._mp_failed_at = None
                return cls._mp_landmarker
            except Exception as exc:
                cls._mp_failed_at = now
                logger.error(
                    "MediaPipe FaceLandmarker no disponible (reintento en %.0fs): %s",
                    cls.MP_RETRY_COOLDOWN_S,
                    exc,
                )
                return None


def _orientation(is_left: bool, is_right: bool, is_down: bool) -> str:
    if is_left:
        return "LEFT"
    if is_right:
        return "RIGHT"
    if is_down:
        return "DOWN"
    return "CENTER"


class FrameAnalyzer:
    """Measures one frame (or a batch) with injectable models and a per-session baseline store."""

    def __init__(
        self,
        state: SessionStateStore,
        vision_provider: Optional[Callable[[], tuple[Any, Any]]] = None,
        landmarker_provider: Optional[Callable[[], Any]] = None,
        mediapipe_runner: Optional[MediaPipeRunner] = None,
        identity_threshold: float = t.IDENTITY_COSINE_THRESHOLD,
        keep_landmarks: bool = False,
    ) -> None:
        self.state = state
        self.vision_provider = vision_provider or create_vision_models
        self.landmarker_provider = landmarker_provider or LandmarkerLifecycle.get_mediapipe_landmarker
        self.mediapipe_runner: MediaPipeRunner = mediapipe_runner or self.analyze_mediapipe
        self.identity_threshold = identity_threshold
        self.keep_landmarks = keep_landmarks

    # ---- window level ---------------------------------------------------------------------------

    def analyze_frames(
        self,
        frames_b64: Sequence[str],
        reference_embedding: Optional[np.ndarray],
        session_key: Optional[str],
        times_ms: Optional[Sequence[int]] = None,
    ) -> FrameBatch:
        """Decodes and measures every frame. Missing models and missing frames are reported, never hidden.

        ``times_ms`` (one capture offset per input frame) is carried over to the usable observations.
        """
        detector, recognizer = self.vision_provider()
        landmarker = self.landmarker_provider()
        vision_available = detector is not None or landmarker is not None

        images = [
            (index, img) for index, img in ((i, decode_frame(raw)) for i, raw in enumerate(frames_b64))
            if img is not None
        ]
        model_unavailable = not vision_available
        usable: list[FrameObservation] = []
        usable_times: list[int] = []
        if vision_available:
            previous = self.state.get_track(session_key, "last_thumbnail") if session_key else None
            thumb = None if previous is None else np.asarray(previous["pixels"], dtype=np.uint8)
            for index, img in images:
                obs = self.analyze_frame(
                    img, detector, recognizer, reference_embedding, session_key=session_key,
                    landmarker=landmarker,
                )
                health = camera.measure_health(img)
                delta = camera.thumbnail_delta(thumb, health.thumbnail)
                thumb = health.thumbnail
                if obs.model_unavailable:
                    model_unavailable = True
                    continue
                usable.append(dataclasses.replace(obs, camera_blocked=health.blocked, frame_delta=delta))
                if times_ms is not None and index < len(times_ms):
                    usable_times.append(int(times_ms[index]))
            if session_key and thumb is not None:
                self.state.set_track(session_key, "last_thumbnail", {"pixels": thumb.tolist()})
        return FrameBatch(
            frames=tuple(usable), video_missing=not images, model_unavailable=model_unavailable,
            times_ms=tuple(usable_times) if len(usable_times) == len(usable) else (),
        )

    # ---- single frame ---------------------------------------------------------------------------

    def analyze_frame(
        self,
        image: np.ndarray,
        detector: Any,
        recognizer: Any,
        reference_embedding: Optional[np.ndarray],
        session_key: Optional[str] = None,
        landmarker: Any = None,
    ) -> FrameObservation:
        """Analyzes one frame with the injected models: MediaPipe landmarker (optional), YuNet, SFace.

        ``landmarker=None`` means MediaPipe is not used. When no model produced a result the frame is
        flagged ``model_unavailable`` and never reported as a clean face (fail closed).
        """
        h, w = image.shape[:2]

        mp_res: Optional[FrameObservation] = None
        if landmarker is not None:
            raw = self.mediapipe_runner(image, session_key, landmarker)
            if raw is not None:
                mp_res = raw if isinstance(raw, FrameObservation) else FrameObservation.from_mapping(raw)

        if detector is None and mp_res is None:
            return FrameObservation.unavailable()

        # YuNet gives the face box (needed for SFace alignment) and the fallback pose
        faces = None
        if detector is not None:
            detector.setInputSize((w, h))
            _, faces = detector.detect(image)
        rows = [] if faces is None else list(faces)
        credible = credible_yunet_rows(rows, h)

        # An extra face needs every detector that ran to see it, at a credible size (and score for YuNet);
        # whether it persists is judged over time by the policy (T7 / S6).
        votes: list[int] = []
        if mp_res is not None:
            votes.append(mp_res.face_count)
        if detector is not None:
            votes.append(len(credible))
        multi = any(count > 1 for count in votes)
        agreed = all(count > 1 for count in votes)
        primary = max(rows, key=lambda row: float(row[2]) * float(row[3])) if rows else None

        if mp_res is not None and mp_res.face_count > 0:
            if multi:
                return FrameObservation(face_count=max(votes), faces_agreed=agreed)
            similarity = match = None
            if (
                recognizer is not None
                and reference_embedding is not None
                and primary is not None
                and mp_res.orientation == "CENTER"
            ):
                similarity, match = self._identity(image, primary, recognizer, reference_embedding)
            obs = dataclasses.replace(
                mp_res, face_count=1, identity_similarity=similarity, identity_match=match, mouth_patch=None
            )
        elif primary is None:  # fallback to YuNet: MediaPipe saw 0 faces, or only a detector stub was provided
            return FrameObservation(face_count=0)
        elif multi:
            return FrameObservation(face_count=len(credible), faces_agreed=agreed)
        else:
            obs = self._analyze_yunet(image, primary, recognizer, reference_embedding, session_key, h)
        return self._with_occlusion(
            obs, image, primary, session_key, mediapipe_saw_face=mp_res is not None and mp_res.face_count > 0,
            yunet_ran=detector is not None,
        )

    def _with_occlusion(
        self, obs: FrameObservation, image: np.ndarray, primary: Optional[np.ndarray], session_key: Optional[str],
        mediapipe_saw_face: bool, yunet_ran: bool,
    ) -> FrameObservation:
        """Adds the per-frame occlusion verdict (S7) of a single frontal face, judged against the trial's reference."""
        geometry = obs.face_geometry
        if geometry is None and primary is not None:
            geometry = tuple(float(v) for v in primary[4:14])
        if geometry is None or obs.orientation != "CENTER":
            return obs
        measured = occlusion.measure(image, geometry)
        if measured is None:
            return obs
        yunet_score = float(primary[14]) if primary is not None else None
        ref = self.state.get_track(session_key, "occlusion_ref") if session_key else None
        building = ref is None or ref["n"] < t.OCC_REF_MIN_SAMPLES
        if building:
            verdict = FrameOcclusion()  # still learning this person's reference: no verdict yet
        else:
            verdict = occlusion.judge(
                measured, ref, obs.identity_similarity, yunet_score, mediapipe_saw_face, yunet_ran
            )
        # Only clean, confidently detected frames teach the reference, so a cover never becomes the norm.
        confident = (yunet_score or 0.0) >= t.OCC_REF_MIN_YUNET_SCORE if yunet_ran else True
        if session_key and confident and (building or not verdict.signals):
            matching = obs.identity_similarity if obs.identity_match else None
            self.state.set_track(session_key, "occlusion_ref",
                                 occlusion.fold_reference(ref, measured, matching, yunet_score))
        return dataclasses.replace(obs, occlusion=verdict)

    def _identity(
        self, image: np.ndarray, face: np.ndarray, recognizer: Any, reference_embedding: np.ndarray
    ) -> tuple[Optional[float], Optional[bool]]:
        try:
            aligned = recognizer.alignCrop(image, face)
            feat = np.asarray(recognizer.feature(aligned), dtype=np.float32).reshape(-1)
            norm = float(np.linalg.norm(feat))
            if norm > 1e-6:
                similarity = float(np.dot(feat / norm, reference_embedding))
                return similarity, similarity >= self.identity_threshold
        except Exception as exc:
            logger.debug("Error en verificación facial periódica: %s", exc)
        return None, None

    # ---- MediaPipe ------------------------------------------------------------------------------

    def analyze_mediapipe(
        self, image_bgr: np.ndarray, session_key: Optional[str], landmarker: Any
    ) -> Optional[FrameObservation]:
        """Runs the injected MediaPipe FaceLandmarker for 3D head pose, blendshapes and mouth aperture."""
        if landmarker is None:
            return None
        try:
            import mediapipe as mp

            rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            with MP_DETECT_LOCK:
                result = landmarker.detect(mp_image)

            face_count = len(result.face_landmarks) if result.face_landmarks else 0
            index = 0
            if face_count > 1:
                # Tiny faces (a poster far behind, a reflection) are not people: only credible ones count.
                heights = [
                    max(float(p.y) for p in face) - min(float(p.y) for p in face) for face in result.face_landmarks
                ]
                credible = sum(1 for height in heights if height >= t.MULTI_FACE_MIN_HEIGHT_FRAC)
                if credible > 1:
                    return FrameObservation(face_count=credible)
                index = max(range(face_count), key=lambda i: heights[i])
                face_count = 1
            if face_count != 1:
                return FrameObservation(face_count=face_count)

            lm = result.face_landmarks[index]
            bs_map: dict[str, float] = {}
            if result.face_blendshapes and len(result.face_blendshapes) > index:
                for cat in result.face_blendshapes[index]:
                    bs_map[cat.category_name] = float(cat.score)

            # 1. Mouth opening: neural blendshapes + 3D inner-lip aspect ratio (MAR)
            jaw_open = bs_map.get("jawOpen", 0.0)
            mouth_close = bs_map.get("mouthClose", 0.0)
            mouth_funnel = bs_map.get("mouthFunnel", 0.0) + 0.5 * bs_map.get("mouthPucker", 0.0)

            # Inner lip vertical distance (#13 upper, #14 lower) normalized by mouth width (#78, #308)
            lip_vert = float(np.hypot(lm[14].x - lm[13].x, lm[14].y - lm[13].y))
            mouth_width = max(float(np.hypot(lm[308].x - lm[78].x, lm[308].y - lm[78].y)), 1e-4)
            inner_mar = lip_vert / mouth_width

            mouth_open_score = float(
                max(
                    jaw_open * max(0.2, 1.0 - 0.55 * mouth_close),
                    inner_mar * 1.4,
                    mouth_funnel * 0.55,
                )
            )

            # 2. 3D head pose (pitch & yaw in degrees) from the 4x4 transformation matrix and the 3D mesh
            # Landmarks: forehead(#10), chin(#152), nose_tip(#1), left_eye(#33), right_eye(#263)
            forehead_y, forehead_z = float(lm[10].y), float(lm[10].z)
            chin_y, chin_z = float(lm[152].y), float(lm[152].z)
            # Head tilted down: forehead comes closer to the camera (z more negative), chin goes further
            lm_pitch_deg = float(
                np.degrees(np.arctan2(chin_z - forehead_z, max(chin_y - forehead_y, 1e-4)))
            )

            eye_mid_x = 0.5 * (float(lm[33].x) + float(lm[263].x))
            eye_mid_y = 0.5 * (float(lm[33].y) + float(lm[263].y))
            eye_dist = max(float(np.hypot(lm[263].x - lm[33].x, lm[263].y - lm[33].y)), 1e-4)
            mouth_mid_y = 0.5 * (float(lm[78].y) + float(lm[308].y))
            nose_x, nose_y = float(lm[1].x), float(lm[1].y)

            lm_yaw_deg = float(np.degrees(np.arctan2(nose_x - eye_mid_x, eye_dist * 0.75)))

            matrix_pitch_deg = lm_pitch_deg
            matrix_yaw_deg = lm_yaw_deg
            if (
                result.facial_transformation_matrixes
                and len(result.facial_transformation_matrixes) > index
            ):
                M = np.asarray(result.facial_transformation_matrixes[index], dtype=np.float64)
                if M.shape == (4, 4):
                    R = M[:3, :3]
                    forward = R[:, 2] / max(float(np.linalg.norm(R[:, 2])), 1e-6)
                    matrix_yaw_deg = float(np.degrees(np.arctan2(forward[0], abs(forward[2]))))
                    matrix_pitch_deg = float(np.degrees(np.arcsin(np.clip(-forward[1], -1.0, 1.0))))

            pitch_deg = t.MP_MATRIX_WEIGHT * matrix_pitch_deg + t.MP_LANDMARK_WEIGHT * lm_pitch_deg
            yaw_deg = t.MP_MATRIX_WEIGHT * matrix_yaw_deg + t.MP_LANDMARK_WEIGHT * lm_yaw_deg

            eye_look_down = 0.5 * (
                bs_map.get("eyeLookDownLeft", 0.0) + bs_map.get("eyeLookDownRight", 0.0)
            )
            eye_to_mouth = max(mouth_mid_y - eye_mid_y, 1e-4)
            pitch_ratio = (nose_y - eye_mid_y) / eye_to_mouth
            nose_mouth_eye_ratio = (mouth_mid_y - nose_y) / eye_dist

            metrics = {
                "pitch_deg": pitch_deg,
                "yaw_deg": yaw_deg,
                "eye_look_down": eye_look_down,
                "pitch_ratio": pitch_ratio,
                "nose_mouth_eye_ratio": nose_mouth_eye_ratio,
            }

            is_extreme_down = pitch_deg >= t.MP_EXTREME_DOWN_PITCH_DEG or (
                pitch_deg >= t.MP_DOWN_PITCH_WITH_EYES_DEG and eye_look_down >= t.MP_DOWN_EYE_LOOK
            )
            is_frontal_candidate = abs(yaw_deg) <= t.MP_FRONTAL_MAX_YAW_DEG and not is_extreme_down
            baseline = self.state.update_baseline(session_key, metrics, is_frontal_candidate)

            is_left = yaw_deg < -t.MP_SIDE_YAW_DEG
            is_right = yaw_deg > t.MP_SIDE_YAW_DEG
            is_down = is_extreme_down

            if baseline is not None:
                delta_pitch_deg = pitch_deg - baseline["pitch_deg"]
                delta_yaw_deg = yaw_deg - baseline["yaw_deg"]
                delta_eye_down = eye_look_down - baseline["eye_look_down"]
                rel_drop_nm = (
                    baseline["nose_mouth_eye_ratio"] - nose_mouth_eye_ratio
                ) / max(baseline["nose_mouth_eye_ratio"], 0.1)

                is_left = is_left or (delta_yaw_deg < -t.MP_SIDE_DELTA_YAW_DEG)
                is_right = is_right or (delta_yaw_deg > t.MP_SIDE_DELTA_YAW_DEG)
                is_down = (
                    is_extreme_down
                    or delta_pitch_deg >= t.MP_DOWN_DELTA_PITCH_DEG
                    or (
                        delta_pitch_deg >= t.MP_DOWN_DELTA_PITCH_SOFT_DEG
                        and (
                            delta_eye_down >= t.MP_DOWN_DELTA_EYE_SOFT
                            or rel_drop_nm >= t.MP_DOWN_REL_DROP_SOFT
                        )
                    )
                    or (
                        delta_eye_down >= t.MP_DOWN_DELTA_EYE_STRONG
                        and delta_pitch_deg >= t.MP_DOWN_DELTA_PITCH_WITH_EYES_DEG
                    )
                    or (
                        rel_drop_nm >= t.MP_DOWN_REL_DROP_STRONG
                        and delta_pitch_deg >= t.MP_DOWN_DELTA_PITCH_WITH_DROP_DEG
                    )
                )

            landmarks = None
            if self.keep_landmarks:
                landmarks = np.asarray([[p.x, p.y, p.z] for p in lm], dtype=np.float32)

            # 3. Eye gaze (T6): iris vs eye corners/lids blended with the eyeLook* blendshapes
            gaze = measure_gaze(np.asarray([[p.x, p.y] for p in lm], dtype=np.float64), bs_map)

            img_h, img_w = image_bgr.shape[:2]

            def at(*indexes: int) -> tuple[float, float]:
                return (
                    float(np.mean([lm[i].x for i in indexes])) * img_w,
                    float(np.mean([lm[i].y for i in indexes])) * img_h,
                )

            geometry = (*at(33, 133), *at(362, 263), *at(1), *at(78), *at(308))

            return FrameObservation(
                face_count=1,
                face_geometry=geometry,
                orientation=_orientation(is_left, is_right, is_down),
                pitch_deg=pitch_deg,
                yaw_deg=yaw_deg,
                blendshapes=bs_map,
                mouth_open_score=mouth_open_score,
                landmarks=landmarks,
                gaze_h=gaze.gaze_h,
                gaze_v=gaze.gaze_v,
                blink=gaze.blink,
            )
        except Exception as exc:
            logger.debug("Error en análisis MediaPipe: %s", exc)
            return None

    # ---- YuNet fallback -------------------------------------------------------------------------

    def _analyze_yunet(
        self,
        image: np.ndarray,
        face: np.ndarray,
        recognizer: Any,
        reference_embedding: Optional[np.ndarray],
        session_key: Optional[str],
        h: int,
    ) -> FrameObservation:
        by = float(face[1])
        bh = max(float(face[3]), 1.0)
        rx, ry = float(face[4]), float(face[5])
        lx, ly = float(face[6]), float(face[7])
        nx, ny = float(face[8]), float(face[9])
        rmx, rmy = float(face[10]), float(face[11])
        lmx, lmy = float(face[12]), float(face[13])

        eye_mid_x = (rx + lx) / 2.0
        eye_mid_y = (ry + ly) / 2.0
        eye_distance = max(float(np.hypot(lx - rx, ly - ry)), 1.0)
        mouth_mid_x = (rmx + lmx) / 2.0
        mouth_mid_y = (rmy + lmy) / 2.0
        eye_to_mouth = max(mouth_mid_y - eye_mid_y, 1.0)

        yaw_eye = (nx - eye_mid_x) / eye_distance
        yaw_mouth = (nx - mouth_mid_x) / eye_distance
        yaw_ratio = 0.75 * yaw_eye + 0.25 * yaw_mouth

        pitch_ratio = (ny - eye_mid_y) / eye_to_mouth
        nose_mouth_eye_ratio = (mouth_mid_y - ny) / eye_distance
        e2m_eye_ratio = eye_to_mouth / eye_distance
        nose_box_ratio = (ny - by) / bh
        eye_box_ratio = (eye_mid_y - by) / bh
        face_center_y = (by + 0.5 * bh) / max(float(h), 1.0)

        pitch_deg = (pitch_ratio - t.YN_PITCH_BASE) * t.YN_PITCH_DEG_SCALE
        yaw_deg = yaw_ratio * t.YN_YAW_DEG_SCALE
        metrics = {
            "yaw_ratio": yaw_ratio,
            "pitch_ratio": pitch_ratio,
            "nose_mouth_eye_ratio": nose_mouth_eye_ratio,
            "e2m_eye_ratio": e2m_eye_ratio,
            "nose_box_ratio": nose_box_ratio,
            "eye_box_ratio": eye_box_ratio,
            "face_center_y": face_center_y,
            "pitch_deg": pitch_deg,
            "yaw_deg": yaw_deg,
            "eye_look_down": 0.0,
        }

        is_extreme_down_abs = (
            pitch_ratio > t.YN_EXTREME_DOWN_PITCH_RATIO
            or nose_mouth_eye_ratio < t.YN_EXTREME_DOWN_NOSE_MOUTH
            or (pitch_ratio > t.YN_DOWN_PITCH_RATIO and nose_mouth_eye_ratio < t.YN_DOWN_NOSE_MOUTH)
        )
        is_frontal_candidate = abs(yaw_ratio) <= t.YN_FRONTAL_MAX_YAW_RATIO and not is_extreme_down_abs
        baseline = self.state.update_baseline(session_key, metrics, is_frontal_candidate)

        is_left = yaw_ratio < -t.YN_SIDE_YAW_RATIO
        is_right = yaw_ratio > t.YN_SIDE_YAW_RATIO

        if baseline is not None:
            delta_pitch = pitch_ratio - baseline.get("pitch_ratio", pitch_ratio)
            base_nm = baseline.get("nose_mouth_eye_ratio", nose_mouth_eye_ratio)
            rel_drop_nm = (base_nm - nose_mouth_eye_ratio) / max(base_nm, 0.1)
            base_e2m = baseline.get("e2m_eye_ratio", e2m_eye_ratio)
            rel_drop_e2m = (base_e2m - e2m_eye_ratio) / max(base_e2m, 0.1)
            delta_nose_box = nose_box_ratio - baseline.get("nose_box_ratio", nose_box_ratio)
            delta_eye_box = eye_box_ratio - baseline.get("eye_box_ratio", eye_box_ratio)
            delta_face_y = face_center_y - baseline.get("face_center_y", face_center_y)

            is_down = (
                is_extreme_down_abs
                or (
                    delta_pitch >= t.YN_DOWN_DELTA_PITCH
                    and (rel_drop_nm >= t.YN_DOWN_REL_DROP_NM or delta_nose_box >= t.YN_DOWN_DELTA_NOSE_BOX)
                )
                or (
                    rel_drop_nm >= t.YN_DOWN_REL_DROP_NM_STRONG
                    and (
                        rel_drop_e2m >= t.YN_DOWN_REL_DROP_E2M
                        or delta_nose_box >= t.YN_DOWN_DELTA_NOSE_BOX_SOFT
                        or delta_eye_box >= t.YN_DOWN_DELTA_EYE_BOX_SOFT
                    )
                )
                or (
                    rel_drop_e2m >= t.YN_DOWN_REL_DROP_E2M_STRONG
                    and (
                        delta_nose_box >= t.YN_DOWN_DELTA_NOSE_BOX
                        or delta_eye_box >= t.YN_DOWN_DELTA_EYE_BOX
                        or delta_face_y >= t.YN_DOWN_DELTA_FACE_Y
                    )
                )
                or delta_pitch >= t.YN_DOWN_DELTA_PITCH_STRONG
                or rel_drop_nm >= t.YN_DOWN_REL_DROP_NM_EXTREME
            )
            base_yaw = baseline.get("yaw_ratio", yaw_ratio)
            is_left = is_left or ((yaw_ratio - base_yaw) < -t.YN_SIDE_DELTA_YAW_RATIO)
            is_right = is_right or ((yaw_ratio - base_yaw) > t.YN_SIDE_DELTA_YAW_RATIO)
        else:
            is_down = is_extreme_down_abs

        orientation = _orientation(is_left, is_right, is_down)

        similarity = match = None
        if recognizer is not None and reference_embedding is not None and orientation == "CENTER":
            similarity, match = self._identity(image, face, recognizer, reference_embedding)

        return FrameObservation(
            face_count=1,
            orientation=orientation,
            pitch_deg=pitch_deg,
            yaw_deg=yaw_deg,
            identity_similarity=similarity,
            identity_match=match,
            mouth_patch=extract_mouth_and_cheeks(image, face),
        )
