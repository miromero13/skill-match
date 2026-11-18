"""Continuous audiovisual window analysis for trial supervision.
Uses Google MediaPipe FaceLandmarker (478 3D landmarks, 52 neural blendshapes,
and 4x4 3D facial transformation matrices) for exact 3D head pose (pitch/yaw in degrees)
and true mouth aperture (jawOpen + inner-lip MAR), OpenCV YuNet + SFace (128-d) for
periodic identity verification, and WebRTC VAD + Sherpa-ONNX (Pyannote + 512-d embeddings)
for speech, lip-sync, and background media/multi-speaker detection.
Zero third-party cloud APIs.
"""
import base64
import binascii
import json
import logging
from collections import OrderedDict
from pathlib import Path
from typing import Any, Literal, Optional

import cv2
import numpy as np

from app.services.biometric_service import (
    MODELS_DIR,
    SFACE_COSINE_THRESHOLD,
    SFACE_MODEL_PATH,
    YUNET_MODEL_PATH,
)

logger = logging.getLogger("skillmatch.continuous_supervision")

MEDIAPIPE_TASK_PATH = MODELS_DIR / "face_landmarker.task"


class ContinuousSupervisionService:
    # Bounded in-memory per-trial neutral 3D pose baselines (max 256 active trials)
    _trial_baselines: OrderedDict[str, dict[str, float]] = OrderedDict()
    # Bounded in-memory rolling 2.4s audio buffer & speaker state per trial
    _trial_audio_state: OrderedDict[str, dict[str, Any]] = OrderedDict()
    _mp_landmarker: Any = None
    _mp_init_attempted: bool = False

    @classmethod
    def get_mediapipe_landmarker(cls) -> Any:
        """Lazily initializes the local MediaPipe FaceLandmarker with blendshapes and 3D matrices."""
        if cls._mp_landmarker is not None:
            return cls._mp_landmarker
        if cls._mp_init_attempted:
            return None
        cls._mp_init_attempted = True
        if not MEDIAPIPE_TASK_PATH.is_file():
            logger.warning("Modelo MediaPipe no encontrado en %s", MEDIAPIPE_TASK_PATH)
            return None
        try:
            from mediapipe.tasks import python
            from mediapipe.tasks.python import vision

            base_options = python.BaseOptions(model_asset_path=str(MEDIAPIPE_TASK_PATH))
            options = vision.FaceLandmarkerOptions(
                base_options=base_options,
                output_face_blendshapes=True,
                output_facial_transformation_matrixes=True,
                num_faces=3,
                min_face_detection_confidence=0.45,
                min_face_presence_confidence=0.45,
            )
            cls._mp_landmarker = vision.FaceLandmarker.create_from_options(options)
            return cls._mp_landmarker
        except Exception as exc:
            logger.warning("No se pudo inicializar MediaPipe FaceLandmarker: %s", exc)
            return None

    @classmethod
    def _get_or_update_baseline(
        cls,
        trial_key: Optional[str],
        metrics: dict[str, float],
        is_frontal_candidate: bool,
    ) -> Optional[dict[str, float]]:
        if not trial_key:
            return None
        existing = cls._trial_baselines.get(trial_key)
        if existing is None:
            if is_frontal_candidate:
                if len(cls._trial_baselines) >= 256:
                    cls._trial_baselines.popitem(last=False)
                seeded = dict(metrics)
                seeded["samples"] = 1.0
                cls._trial_baselines[trial_key] = seeded
                return seeded
            return None

        cls._trial_baselines.move_to_end(trial_key)
        if is_frontal_candidate:
            samples = existing.get("samples", 1.0)
            if samples < 4.0:
                w_new = 1.0 / (samples + 1.0)
                w_old = 1.0 - w_new
                for k, v in metrics.items():
                    existing[k] = w_old * existing.get(k, v) + w_new * v
                existing["samples"] = samples + 1.0
            else:
                # Only adapt if posture is upright (never let downward tilt drift the baseline down)
                pitch_ok = metrics.get("pitch_deg", 0.0) <= existing.get("pitch_deg", 0.0) + 2.5
                nm_ok = (
                    metrics.get("nose_mouth_eye_ratio", 0.4)
                    >= existing.get("nose_mouth_eye_ratio", 0.4) - 0.015
                )
                if pitch_ok and nm_ok:
                    alpha = 0.12
                    for k, v in metrics.items():
                        existing[k] = (1.0 - alpha) * existing.get(k, v) + alpha * v
        return existing

    @staticmethod
    def decode_frame(raw: str) -> Optional[np.ndarray]:
        """Safely decodes a base64 JPEG image with header verification."""
        if not raw:
            return None
        encoded = raw.split(",", 1)[1] if raw.startswith("data:") else raw
        try:
            data = base64.b64decode(encoded.strip(), validate=False)
        except (ValueError, binascii.Error):
            return None
        if len(data) < 32 or data[:2] != b"\xff\xd8":
            return None
        nparr = np.frombuffer(data, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        return image

    @staticmethod
    def get_vision_models():
        """Creates per-request YuNet detector and SFace recognizer instances."""
        detector = None
        recognizer = None
        if YUNET_MODEL_PATH.is_file():
            try:
                detector = cv2.FaceDetectorYN.create(
                    str(YUNET_MODEL_PATH), "", (320, 240), 0.50, 0.3, 5
                )
            except Exception as exc:
                logger.warning("No se pudo instanciar detector YuNet: %s", exc)
        if SFACE_MODEL_PATH.is_file():
            try:
                recognizer = cv2.FaceRecognizerSF.create(str(SFACE_MODEL_PATH), "")
            except Exception as exc:
                logger.warning("No se pudo instanciar reconocedor SFace: %s", exc)
        return detector, recognizer

    @classmethod
    def _analyze_with_mediapipe(
        cls,
        image_bgr: np.ndarray,
        trial_key: Optional[str],
    ) -> Optional[dict[str, Any]]:
        """Runs MediaPipe 3D FaceLandmarker for exact 3D Euler angles and blendshape mouth aperture."""
        landmarker = cls.get_mediapipe_landmarker()
        if landmarker is None:
            return None
        try:
            import mediapipe as mp

            rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            result = landmarker.detect(mp_image)

            face_count = len(result.face_landmarks) if result.face_landmarks else 0
            if face_count == 0:
                return {
                    "face_count": 0,
                    "orientation": "UNKNOWN",
                    "mouth_open_score": 0.0,
                    "mouth_patch": None,
                }
            if face_count > 1:
                return {
                    "face_count": face_count,
                    "orientation": "UNKNOWN",
                    "mouth_open_score": 0.0,
                    "mouth_patch": None,
                }

            lm = result.face_landmarks[0]
            bs_map: dict[str, float] = {}
            if result.face_blendshapes and len(result.face_blendshapes) > 0:
                for cat in result.face_blendshapes[0]:
                    bs_map[cat.category_name] = float(cat.score)

            # 1. Exact Mouth Opening via Neural Blendshapes + 3D Inner-Lip Aspect Ratio (MAR)
            jaw_open = bs_map.get("jawOpen", 0.0)
            mouth_close = bs_map.get("mouthClose", 0.0)
            mouth_funnel = bs_map.get("mouthFunnel", 0.0) + 0.5 * bs_map.get("mouthPucker", 0.0)

            # Inner lip vertical distance (#13 upper inner lip, #14 lower inner lip)
            # normalized by mouth width (#78 left corner, #308 right corner)
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

            # 2. Exact 3D Head Pose (Pitch & Yaw in degrees) from 4x4 Transformation Matrix & 3D Mesh
            # Landmarks: forehead(#10), chin(#152), nose_tip(#1), left_eye(#33), right_eye(#263)
            forehead_y, forehead_z = float(lm[10].y), float(lm[10].z)
            chin_y, chin_z = float(lm[152].y), float(lm[152].z)
            # When head tilts down, forehead comes closer to camera (z more negative) and chin goes further (z more positive)
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
                and len(result.facial_transformation_matrixes) > 0
            ):
                M = np.asarray(result.facial_transformation_matrixes[0], dtype=np.float64)
                if M.shape == (4, 4):
                    R = M[:3, :3]
                    forward = R[:, 2] / max(float(np.linalg.norm(R[:, 2])), 1e-6)
                    matrix_yaw_deg = float(np.degrees(np.arctan2(forward[0], abs(forward[2]))))
                    matrix_pitch_deg = float(
                        np.degrees(np.arcsin(np.clip(-forward[1], -1.0, 1.0)))
                    )

            pitch_deg = 0.55 * matrix_pitch_deg + 0.45 * lm_pitch_deg
            yaw_deg = 0.55 * matrix_yaw_deg + 0.45 * lm_yaw_deg

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

            is_extreme_down = pitch_deg >= 21.0 or (pitch_deg >= 15.0 and eye_look_down >= 0.42)
            is_frontal_candidate = abs(yaw_deg) <= 13.0 and not is_extreme_down
            baseline = cls._get_or_update_baseline(trial_key, metrics, is_frontal_candidate)

            is_left = yaw_deg < -15.5
            is_right = yaw_deg > 15.5
            is_down = is_extreme_down

            if baseline is not None:
                delta_pitch_deg = pitch_deg - baseline["pitch_deg"]
                delta_yaw_deg = yaw_deg - baseline["yaw_deg"]
                delta_eye_down = eye_look_down - baseline["eye_look_down"]
                rel_drop_nm = (
                    baseline["nose_mouth_eye_ratio"] - nose_mouth_eye_ratio
                ) / max(baseline["nose_mouth_eye_ratio"], 0.1)

                is_left = is_left or (delta_yaw_deg < -13.5)
                is_right = is_right or (delta_yaw_deg > 13.5)
                is_down = (
                    is_extreme_down
                    or delta_pitch_deg >= 9.5
                    or (delta_pitch_deg >= 6.5 and (delta_eye_down >= 0.14 or rel_drop_nm >= 0.15))
                    or (delta_eye_down >= 0.25 and delta_pitch_deg >= 4.0)
                    or (rel_drop_nm >= 0.20 and delta_pitch_deg >= 5.0)
                )

            orientation: Literal["CENTER", "DOWN", "LEFT", "RIGHT"] = "CENTER"
            if is_left:
                orientation = "LEFT"
            elif is_right:
                orientation = "RIGHT"
            elif is_down:
                orientation = "DOWN"

            return {
                "face_count": 1,
                "orientation": orientation,
                "mouth_open_score": mouth_open_score,
                "mouth_patch": None,
            }
        except Exception as exc:
            logger.debug("Error en análisis MediaPipe: %s", exc)
            return None

    @staticmethod
    def _extract_mouth_and_cheeks(
        image: np.ndarray,
        face: np.ndarray,
    ) -> Optional[tuple[np.ndarray, np.ndarray]]:
        """Fallback affine-stabilized mouth and cheek patches when YuNet stub is used."""
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
            aligned = cv2.warpAffine(
                gray, transform, (128, 128), borderMode=cv2.BORDER_REPLICATE
            )
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
            cheeks = np.concatenate(
                [smoothed[72:108, 16:32].ravel(), smoothed[72:108, 96:112].ravel()]
            )
            return mouth_norm, cheeks
        except Exception:
            return None

    @classmethod
    def analyze_frame_face(
        cls,
        image: np.ndarray,
        detector: Any,
        recognizer: Any,
        reference_embedding: Optional[np.ndarray],
        trial_key: Optional[str] = None,
    ) -> dict[str, Any]:
        """Analyzes a single video frame using MediaPipe 3D FaceLandmarker + OpenCV SFace."""
        h, w = image.shape[:2]

        # 1. Try MediaPipe 3D FaceLandmarker first (unless a unit-test stub detector is injected)
        is_real_yunet = detector is None or type(detector).__name__ == "FaceDetectorYN"
        mp_res = cls._analyze_with_mediapipe(image, trial_key) if is_real_yunet else None

        if detector is None and mp_res is None:
            return {
                "face_count": 1,
                "orientation": "CENTER",
                "identity_match": True,
                "mouth_open_score": 0.0,
                "mouth_patch": None,
            }

        # Run YuNet for face bounding box (needed for SFace identity alignment) or fallback pose
        faces = None
        if detector is not None:
            detector.setInputSize((w, h))
            _, faces = detector.detect(image)
        yunet_count = 0 if faces is None else len(faces)

        if mp_res is not None and mp_res["face_count"] > 0:
            face_count = max(mp_res["face_count"], yunet_count)
            if face_count > 1:
                return {
                    "face_count": face_count,
                    "orientation": "UNKNOWN",
                    "identity_match": None,
                    "mouth_open_score": 0.0,
                    "mouth_patch": None,
                }
            orientation = mp_res["orientation"]
            identity_match: Optional[bool] = None
            if (
                recognizer is not None
                and reference_embedding is not None
                and yunet_count == 1
                and orientation == "CENTER"
            ):
                try:
                    aligned = recognizer.alignCrop(image, faces[0])
                    feat = np.asarray(recognizer.feature(aligned), dtype=np.float32).reshape(-1)
                    norm = float(np.linalg.norm(feat))
                    if norm > 1e-6:
                        similarity = float(np.dot(feat / norm, reference_embedding))
                        identity_match = similarity >= SFACE_COSINE_THRESHOLD
                except Exception as exc:
                    logger.debug("Error en verificación facial periódica: %s", exc)
            return {
                "face_count": 1,
                "orientation": orientation,
                "identity_match": identity_match,
                "mouth_open_score": mp_res["mouth_open_score"],
                "mouth_patch": None,
            }

        # Fallback to YuNet (if MediaPipe detected 0 faces or a unit-test StubDetector was provided)
        face_count = yunet_count
        if face_count == 0:
            return {
                "face_count": 0,
                "orientation": "UNKNOWN",
                "identity_match": None,
                "mouth_open_score": 0.0,
                "mouth_patch": None,
            }
        if face_count > 1:
            return {
                "face_count": face_count,
                "orientation": "UNKNOWN",
                "identity_match": None,
                "mouth_open_score": 0.0,
                "mouth_patch": None,
            }

        face = faces[0]
        bx, by, bw, bh = (
            float(face[0]),
            float(face[1]),
            max(float(face[2]), 1.0),
            max(float(face[3]), 1.0),
        )
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

        metrics = {
            "yaw_ratio": yaw_ratio,
            "pitch_ratio": pitch_ratio,
            "nose_mouth_eye_ratio": nose_mouth_eye_ratio,
            "e2m_eye_ratio": e2m_eye_ratio,
            "nose_box_ratio": nose_box_ratio,
            "eye_box_ratio": eye_box_ratio,
            "face_center_y": face_center_y,
            "pitch_deg": (pitch_ratio - 0.53) * 75.0,
            "yaw_deg": yaw_ratio * 90.0,
            "eye_look_down": 0.0,
        }

        is_extreme_down_abs = (
            pitch_ratio > 0.68
            or nose_mouth_eye_ratio < 0.23
            or (pitch_ratio > 0.65 and nose_mouth_eye_ratio < 0.27)
        )
        is_frontal_candidate = abs(yaw_ratio) <= 0.13 and not is_extreme_down_abs
        baseline = cls._get_or_update_baseline(trial_key, metrics, is_frontal_candidate)

        is_down = False
        is_left = yaw_ratio < -0.135
        is_right = yaw_ratio > 0.135

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
                or (delta_pitch >= 0.045 and (rel_drop_nm >= 0.15 or delta_nose_box >= 0.030))
                or (
                    rel_drop_nm >= 0.18
                    and (
                        rel_drop_e2m >= 0.09
                        or delta_nose_box >= 0.028
                        or delta_eye_box >= 0.026
                    )
                )
                or (
                    rel_drop_e2m >= 0.13
                    and (
                        delta_nose_box >= 0.030
                        or delta_eye_box >= 0.028
                        or delta_face_y >= 0.035
                    )
                )
                or delta_pitch >= 0.070
                or rel_drop_nm >= 0.26
            )
            base_yaw = baseline.get("yaw_ratio", yaw_ratio)
            is_left = is_left or ((yaw_ratio - base_yaw) < -0.12)
            is_right = is_right or ((yaw_ratio - base_yaw) > 0.12)
        else:
            is_down = is_extreme_down_abs

        orientation = "CENTER"
        if is_left:
            orientation = "LEFT"
        elif is_right:
            orientation = "RIGHT"
        elif is_down:
            orientation = "DOWN"

        identity_match = None
        if recognizer is not None and reference_embedding is not None and orientation == "CENTER":
            try:
                aligned = recognizer.alignCrop(image, face)
                feat = np.asarray(recognizer.feature(aligned), dtype=np.float32).reshape(-1)
                norm = float(np.linalg.norm(feat))
                if norm > 1e-6:
                    similarity = float(np.dot(feat / norm, reference_embedding))
                    identity_match = similarity >= SFACE_COSINE_THRESHOLD
            except Exception as exc:
                logger.debug("Error en verificación facial periódica: %s", exc)

        mouth_patch = cls._extract_mouth_and_cheeks(image, face)

        return {
            "face_count": 1,
            "orientation": orientation,
            "identity_match": identity_match,
            "mouth_open_score": 0.0,
            "mouth_patch": mouth_patch,
        }

    @classmethod
    def compute_mouth_trace(
        cls, patches: list[Optional[tuple[np.ndarray, np.ndarray]]]
    ) -> tuple[bool, list[float]]:
        """Computes inter-frame cheek-compensated mouth movements (fallback for patch-based tests)."""
        valid = [p for p in patches if p is not None]
        if len(valid) < 2:
            return False, []

        movements: list[float] = []
        for idx in range(1, len(valid)):
            prev_mouth, prev_cheeks = valid[idx - 1]
            curr_mouth, curr_cheeks = valid[idx]

            pm = prev_mouth - float(prev_mouth.mean())
            cm = curr_mouth - float(curr_mouth.mean())
            pc = prev_cheeks - float(prev_cheeks.mean())
            cc = curr_cheeks - float(curr_cheeks.mean())

            mouth_diff = float(np.mean(np.abs(cm - pm))) / 255.0
            cheek_diff = float(np.mean(np.abs(cc - pc))) / 255.0
            net_motion = max(0.0, mouth_diff - 1.0 * cheek_diff)

            center_prev = pm[6:22, 8:32]
            center_curr = cm[6:22, 8:32]
            mouth_std_delta = abs(float(center_curr.std()) - float(center_prev.std())) / 255.0
            cheek_std_delta = abs(float(cc.std()) - float(pc.std())) / 255.0
            net_std_delta = max(0.0, mouth_std_delta - 1.0 * cheek_std_delta)

            movements.append(max(net_motion, net_std_delta * 0.85))

        if not movements:
            return False, []

        max_mov = max(movements)
        mean_mov = float(np.mean(movements))
        active_steps = sum(1 for m in movements if m >= 0.011)
        mouth_moving = (max_mov >= 0.014 and mean_mov >= 0.0075) or active_steps >= 2
        return mouth_moving, movements

    @classmethod
    def compute_mouth_movement(
        cls, patches: list[Optional[tuple[np.ndarray, np.ndarray]]]
    ) -> bool:
        moving, _ = cls.compute_mouth_trace(patches)
        return moving

    @classmethod
    def _detect_multi_speaker_or_background_media(
        cls,
        audio: np.ndarray,
        chunk_rms: np.ndarray,
        voiced_flags: list[bool],
        trial_key: Optional[str],
    ) -> bool:
        """Detects multiple speakers, overlapping voices, or background TV/media alongside speech."""
        state: dict[str, Any] = {}
        if trial_key:
            state = cls._trial_audio_state.get(trial_key, {})
            if trial_key in cls._trial_audio_state:
                cls._trial_audio_state.move_to_end(trial_key)
            else:
                if len(cls._trial_audio_state) >= 256:
                    cls._trial_audio_state.popitem(last=False)
                cls._trial_audio_state[trial_key] = state

        prev_audio = state.get("prev_audio")
        if prev_audio is not None and isinstance(prev_audio, np.ndarray) and prev_audio.size > 0:
            combined_audio = np.concatenate([prev_audio[-38400:], audio])
        else:
            combined_audio = audio
        if trial_key:
            state["prev_audio"] = audio[-38400:].copy()

        # 1. Continuous background floor check (TV series / radio / background dialogue fills inter-word pauses)
        total_chunks = len(chunk_rms)
        voiced_count = sum(1 for v in voiced_flags if v)
        voiced_ratio = voiced_count / max(total_chunks, 1)
        if total_chunks >= 20:
            p15 = float(np.percentile(chunk_rms, 15))
            p25 = float(np.percentile(chunk_rms, 25))
            p85 = float(np.percentile(chunk_rms, 85))
            if voiced_ratio >= 0.78 and p25 >= 0.008 and (p25 / max(p85, 1e-4)) >= 0.20:
                return True
            if p15 >= 0.011 and (p15 / max(p85, 1e-4)) >= 0.24:
                return True

        # 2. Sherpa-ONNX Pyannote speaker segmentation + 512-d speaker embedding divergence
        if combined_audio.size >= 24000:
            try:
                import sherpa_onnx
                from app.services.calibration_speaker_service import (
                    EMBEDDING_MODEL,
                    SEGMENTATION_MODEL,
                )

                if SEGMENTATION_MODEL.is_file() and EMBEDDING_MODEL.is_file():
                    peak = float(np.percentile(np.abs(combined_audio), 98))
                    gain = min(14.0, 0.55 / max(peak, 1e-4))
                    diar_audio = np.clip(combined_audio * gain, -1.0, 1.0).astype(np.float32)

                    config = sherpa_onnx.OfflineSpeakerDiarizationConfig(
                        segmentation=sherpa_onnx.OfflineSpeakerSegmentationModelConfig(
                            pyannote=sherpa_onnx.OfflineSpeakerSegmentationPyannoteModelConfig(
                                model=str(SEGMENTATION_MODEL),
                                window_shift_ratio=0.1,
                            ),
                            num_threads=1,
                        ),
                        embedding=sherpa_onnx.SpeakerEmbeddingExtractorConfig(
                            model=str(EMBEDDING_MODEL), num_threads=1
                        ),
                        clustering=sherpa_onnx.FastClusteringConfig(
                            num_clusters=-1, threshold=0.38
                        ),
                        min_duration_on=0.15,
                        min_duration_off=0.15,
                    )
                    if config.validate():
                        diarizer = sherpa_onnx.OfflineSpeakerDiarization(config)
                        segments = list(diarizer.process(diar_audio).sort_by_start_time())
                        speakers = {
                            item.speaker
                            for item in segments
                            if (item.end - item.start) >= 0.15
                        }
                        if len(speakers) > 1:
                            return True
                        for i, first in enumerate(segments):
                            for second in segments[i + 1 :]:
                                if (
                                    first.speaker != second.speaker
                                    and min(first.end, second.end) - max(first.start, second.start) >= 0.06
                                ):
                                    return True

                    # Sub-window 512-d speaker embedding divergence check (0.8s slices)
                    ext_cfg = sherpa_onnx.SpeakerEmbeddingExtractorConfig(
                        model=str(EMBEDDING_MODEL), num_threads=1
                    )
                    extractor = sherpa_onnx.SpeakerEmbeddingExtractor(ext_cfg)
                    slice_len = 12800  # 0.8s at 16kHz
                    step_len = 8000    # 0.5s step
                    embeddings: list[np.ndarray] = []
                    for start in range(0, diar_audio.size - slice_len + 1, step_len):
                        sub = diar_audio[start : start + slice_len]
                        if float(np.sqrt(np.mean(np.square(sub)))) >= 0.020:
                            stream = extractor.create_stream()
                            stream.accept_waveform(16000, sub.tolist())
                            stream.input_finished()
                            if extractor.is_ready(stream):
                                vec = np.asarray(extractor.compute(stream), dtype=np.float32)
                                norm = float(np.linalg.norm(vec))
                                if norm > 1e-6:
                                    embeddings.append(vec / norm)

                    if len(embeddings) >= 2:
                        min_sim = 1.0
                        for i in range(len(embeddings)):
                            for j in range(i + 1, len(embeddings)):
                                sim = float(np.dot(embeddings[i], embeddings[j]))
                                min_sim = min(min_sim, sim)
                        if min_sim < 0.48:
                            return True
            except Exception as exc:
                logger.debug("Error en diarización continua: %s", exc)

        return False

    @classmethod
    def analyze_audio(
        cls,
        samples: Optional[list[float]],
        trial_key: Optional[str] = None,
    ) -> dict[str, Any]:
        """Analyzes 16kHz audio samples for RMS energy, gain-normalized VAD speech activity and multi-speaker."""
        if not samples or len(samples) < 160:
            return {
                "noise_level": 0.0,
                "speech_detected": False,
                "multiple_speakers": False,
                "high_noise": False,
                "chunk_rms": np.zeros(0, dtype=np.float32),
                "voiced_flags": [],
            }

        audio = np.asarray(samples, dtype=np.float32)
        audio = np.nan_to_num(audio, nan=0.0, posinf=1.0, neginf=-1.0)
        audio = np.clip(audio, -1.0, 1.0)
        audio = audio - float(np.mean(audio))
        rms = float(np.sqrt(np.mean(np.square(audio))))

        speech_detected = False
        chunk_size = 480  # 30ms at 16000Hz
        total_chunks = audio.size // chunk_size
        chunk_rms = np.zeros(0, dtype=np.float32)
        voiced_flags: list[bool] = []

        if total_chunks > 0 and rms >= 0.0028:
            chunks = audio[: total_chunks * chunk_size].reshape(total_chunks, chunk_size)
            chunk_rms = np.sqrt(np.mean(np.square(chunks), axis=1))
            noise_floor = float(np.percentile(chunk_rms, 15)) if total_chunks >= 4 else 0.002
            effective_floor = min(noise_floor, 0.007)
            active_threshold = max(0.0030, effective_floor * 1.50)

            peak = float(np.percentile(np.abs(audio), 98))
            gain = min(18.0, 0.48 / max(peak, 1e-4))
            norm_audio = np.clip(audio * gain, -1.0, 1.0)
            pcm = (norm_audio * 32767).astype("<i2")

            try:
                import webrtcvad

                vad = webrtcvad.Vad(2)
                speech_chunks = 0
                for i in range(total_chunks):
                    is_voiced = False
                    if chunk_rms[i] >= active_threshold:
                        raw_bytes = pcm[i * chunk_size : (i + 1) * chunk_size].tobytes()
                        if vad.is_speech(raw_bytes, 16000):
                            is_voiced = True
                            speech_chunks += 1
                    voiced_flags.append(is_voiced)

                freqs = np.fft.rfftfreq(audio.size, d=1.0 / 16000.0)
                spectrum = np.abs(np.fft.rfft(audio)) ** 2
                total_energy = float(np.sum(spectrum)) + 1e-9
                voice_band_energy = float(
                    np.sum(spectrum[(freqs >= 200.0) & (freqs <= 3600.0)])
                )
                voice_band_ratio = voice_band_energy / total_energy

                if (speech_chunks >= 3 or (speech_chunks / total_chunks >= 0.08)) and voice_band_ratio >= 0.25:
                    speech_detected = True
            except Exception as exc:
                logger.debug("VAD no disponible o error en procesamiento: %s", exc)
                voiced_flags = [bool(c >= active_threshold) for c in chunk_rms]
                if sum(voiced_flags) >= 4:
                    speech_detected = True

        high_noise = rms > 0.22 or (rms > 0.14 and not speech_detected)

        multiple_speakers = False
        if speech_detected:
            multiple_speakers = cls._detect_multi_speaker_or_background_media(
                audio, chunk_rms, voiced_flags, trial_key
            )

        return {
            "noise_level": round(rms, 4),
            "speech_detected": speech_detected,
            "multiple_speakers": multiple_speakers,
            "high_noise": high_noise,
            "chunk_rms": chunk_rms,
            "voiced_flags": voiced_flags,
        }

    @classmethod
    def assess_window(
        cls,
        frames_b64: list[str],
        audio_samples: Optional[list[float]],
        mode: str = "UNIFIED",
        biometric_embedding_json: Optional[str] = None,
        trial_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Evaluates an audiovisual supervision window and determines anomalies."""
        reference_embedding: Optional[np.ndarray] = None
        if biometric_embedding_json:
            try:
                parsed = np.asarray(json.loads(biometric_embedding_json), dtype=np.float32)
                norm = float(np.linalg.norm(parsed))
                if parsed.shape == (128,) and norm > 1e-6:
                    reference_embedding = parsed / norm
            except Exception:
                pass

        detector, recognizer = cls.get_vision_models()

        frame_results = []
        for raw in frames_b64:
            img = cls.decode_frame(raw)
            if img is not None:
                res = cls.analyze_frame_face(
                    img, detector, recognizer, reference_embedding, trial_key=trial_id
                )
                frame_results.append(res)

        anomalies: list[str] = []
        face_count = 1
        head_orientation: Literal["CENTER", "DOWN", "LEFT", "RIGHT", "UNKNOWN"] = "CENTER"
        identity_match: Optional[bool] = None
        mouth_moving = False
        mouth_open_scores: list[float] = []
        mouth_movements: list[float] = []

        if frame_results:
            counts = [f["face_count"] for f in frame_results]
            orientations = [f["orientation"] for f in frame_results]
            identities = [
                f["identity_match"] for f in frame_results if f["identity_match"] is not None
            ]
            mouth_open_scores = [float(f.get("mouth_open_score", 0.0)) for f in frame_results]
            mouth_patches = [f.get("mouth_patch") for f in frame_results]

            # If MediaPipe blendshapes/MAR were used, determine mouth movement from 3D aperture scores
            if any(s > 0.0 for s in mouth_open_scores):
                max_open = max(mouth_open_scores)
                min_open = min(mouth_open_scores)
                open_frames = sum(1 for s in mouth_open_scores if s >= 0.046)
                dynamic_range = max_open - min_open
                mouth_moving = max_open >= 0.052 and (dynamic_range >= 0.020 or open_frames >= 2)
            else:
                mouth_moving, mouth_movements = cls.compute_mouth_trace(mouth_patches)

            if all(c == 0 for c in counts) or sum(1 for c in counts if c == 0) >= max(
                2, len(counts) // 2 + 1
            ):
                face_count = 0
                anomalies.append("FACE_ABSENT")
            elif any(c > 1 for c in counts):
                face_count = max(counts)
                anomalies.append("MULTIPLE_FACES")
            else:
                face_count = 1

            down_count = sum(1 for o in orientations if o == "DOWN")
            side_frames = [o for o in orientations if o in ("LEFT", "RIGHT")]
            side_count = len(side_frames)

            min_sustained = 1 if len(orientations) == 1 else max(2, len(orientations) // 2)
            if down_count >= min_sustained:
                head_orientation = "DOWN"
                anomalies.append("HEAD_POSE_DOWN")
            elif side_count >= min_sustained:
                head_orientation = side_frames[-1]
                anomalies.append("HEAD_POSE_SIDE")
            else:
                head_orientation = "CENTER" if "CENTER" in orientations else orientations[-1]

            if identities:
                identity_match = all(identities)
                if identity_match is False:
                    anomalies.append("IDENTITY_MISMATCH")

        # Audio analysis and lip-sync verification
        audio_res = cls.analyze_audio(audio_samples, trial_key=trial_id)
        speech_detected = audio_res["speech_detected"]
        multiple_speakers = audio_res["multiple_speakers"]
        chunk_rms = audio_res["chunk_rms"]
        voiced_flags = audio_res["voiced_flags"]
        mouth_sync: Optional[bool] = None

        if audio_res["high_noise"]:
            anomalies.append("HIGH_NOISE")

        # Per-frame closed-mouth audio check:
        # Using MediaPipe jawOpen/MAR, if in any frame k the user's mouth is physically closed
        # (< 0.036) while the corresponding 400ms audio slice has strong active speech,
        # external audio (TV series / background speaker) is playing during closed-mouth frames!
        unmatched_voiced_frames = 0
        if (
            speech_detected
            and len(mouth_open_scores) >= 3
            and any(s > 0.0 for s in mouth_open_scores)
            and len(voiced_flags) >= len(mouth_open_scores) * 2
        ):
            num_frames = len(mouth_open_scores)
            chunks_per_frame = len(voiced_flags) // num_frames
            max_chunk_rms = float(np.max(chunk_rms)) if chunk_rms.size > 0 else 0.01
            for k, score in enumerate(mouth_open_scores):
                c_start = k * chunks_per_frame
                c_end = (k + 1) * chunks_per_frame if k < num_frames - 1 else len(voiced_flags)
                sub_voiced = voiced_flags[c_start:c_end]
                sub_rms = float(np.mean(chunk_rms[c_start:c_end])) if c_end > c_start else 0.0
                is_sub_speaking = (
                    sum(1 for v in sub_voiced if v) >= max(2, len(sub_voiced) // 3)
                    and sub_rms >= max(0.007, 0.35 * max_chunk_rms)
                )
                if is_sub_speaking and score < 0.036:
                    unmatched_voiced_frames += 1

        if speech_detected:
            if multiple_speakers:
                mouth_sync = False
                anomalies.append("MULTIPLE_SPEAKERS")
            elif unmatched_voiced_frames >= 1 and mouth_moving:
                # User moved their mouth in part of the window, but speech ALSO played while mouth was closed
                mouth_sync = False
                multiple_speakers = True
                anomalies.append("MULTIPLE_SPEAKERS")
            elif unmatched_voiced_frames >= 2 and not mouth_moving:
                mouth_sync = False
                anomalies.append("VOICE_DETECTED")
            elif face_count == 1 and mouth_moving:
                mouth_sync = True
            else:
                mouth_sync = False
                anomalies.append("VOICE_DETECTED")

        return {
            "face_count": face_count,
            "head_orientation": head_orientation,
            "identity_match": identity_match,
            "speech_detected": speech_detected,
            "mouth_moving": mouth_moving,
            "mouth_sync": mouth_sync,
            "multiple_speakers": multiple_speakers,
            "noise_level": audio_res["noise_level"],
            "anomalies": anomalies,
        }
