"""Continuous audiovisual window analysis for trial supervision.
Performs local OpenCV YuNet face presence, SFace 128-d cosine verification,
landmark-based head pose estimation (with per-trial adaptive baseline),
affine-stabilized mouth movement tracking, and WebRTC VAD/noise analysis.
Zero third-party cloud APIs.
"""
import base64
import binascii
import json
import logging
from collections import OrderedDict
from typing import Any, Literal, Optional

import cv2
import numpy as np

from app.services.biometric_service import (
    SFACE_COSINE_THRESHOLD,
    SFACE_MODEL_PATH,
    YUNET_MODEL_PATH,
)

logger = logging.getLogger("skillmatch.continuous_supervision")


class ContinuousSupervisionService:
    # Bounded in-memory per-trial neutral pose baselines (max 256 active trials)
    _trial_baselines: OrderedDict[str, dict[str, float]] = OrderedDict()

    @classmethod
    def _get_or_update_baseline(
        cls,
        trial_key: Optional[str],
        metrics: dict[str, float],
        is_candidate_neutral: bool,
    ) -> Optional[dict[str, float]]:
        if not trial_key:
            return None
        existing = cls._trial_baselines.get(trial_key)
        if existing is None:
            if is_candidate_neutral:
                if len(cls._trial_baselines) >= 256:
                    cls._trial_baselines.popitem(last=False)
                cls._trial_baselines[trial_key] = dict(metrics)
                return cls._trial_baselines[trial_key]
            return None

        cls._trial_baselines.move_to_end(trial_key)
        # Slowly adapt baseline only on clearly centered, neutral frames
        if is_candidate_neutral:
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
        """Creates per-request detector and recognizer instances."""
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

    @staticmethod
    def _extract_mouth_and_cheeks(
        image: np.ndarray,
        face: np.ndarray,
    ) -> Optional[tuple[np.ndarray, np.ndarray]]:
        """Extracts affine-stabilized mouth and cheek grayscale patches (128x128 space)."""
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
            ).astype(np.float32)

            corners = cv2.transform(
                np.asarray([[[rmx, rmy], [lmx, lmy]]], dtype=np.float32), transform
            )[0]
            center = corners.mean(axis=0)
            box_w = float(np.clip(abs(corners[1, 0] - corners[0, 0]) * 1.55, 24.0, 62.0))
            box_h = box_w * 0.75
            x1 = int(np.clip(center[0] - box_w / 2.0, 0, 116))
            x2 = int(np.clip(center[0] + box_w / 2.0, x1 + 12, 128))
            y1 = int(np.clip(center[1] - box_h / 2.0, 52, 116))
            y2 = int(np.clip(center[1] + box_h / 2.0, y1 + 10, 128))

            mouth_crop = aligned[y1:y2, x1:x2]
            if mouth_crop.size == 0:
                return None
            mouth_norm = cv2.resize(mouth_crop, (40, 28), interpolation=cv2.INTER_LINEAR)
            cheeks = np.concatenate(
                [aligned[72:108, 16:32].ravel(), aligned[72:108, 96:112].ravel()]
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
        """Analyzes a single video frame for face presence, pose, mouth patch and identity."""
        h, w = image.shape[:2]
        if detector is None:
            return {
                "face_count": 1,
                "orientation": "CENTER",
                "identity_match": True,
                "mouth_patch": None,
            }

        detector.setInputSize((w, h))
        _, faces = detector.detect(image)
        face_count = 0 if faces is None else len(faces)

        if face_count == 0:
            return {
                "face_count": 0,
                "orientation": "UNKNOWN",
                "identity_match": None,
                "mouth_patch": None,
            }
        if face_count > 1:
            return {
                "face_count": face_count,
                "orientation": "UNKNOWN",
                "identity_match": None,
                "mouth_patch": None,
            }

        face = faces[0]
        bx, by, bw, bh = float(face[0]), float(face[1]), max(float(face[2]), 1.0), max(float(face[3]), 1.0)
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

        # Horizontal yaw (nose offset relative to eye midpoint and mouth midpoint)
        yaw_eye = (nx - eye_mid_x) / eye_distance
        yaw_mouth = (nx - mouth_mid_x) / eye_distance
        yaw_ratio = 0.75 * yaw_eye + 0.25 * yaw_mouth

        # Vertical pitch cues for downward head tilt
        pitch_ratio = (ny - eye_mid_y) / eye_to_mouth
        nose_mouth_eye_ratio = (mouth_mid_y - ny) / eye_distance
        nose_box_ratio = (ny - by) / bh
        eye_box_ratio = (eye_mid_y - by) / bh
        e2m_eye_ratio = eye_to_mouth / eye_distance
        face_center_y = (by + 0.5 * bh) / max(float(h), 1.0)

        metrics = {
            "yaw_ratio": yaw_ratio,
            "pitch_ratio": pitch_ratio,
            "nose_mouth_eye_ratio": nose_mouth_eye_ratio,
            "nose_box_ratio": nose_box_ratio,
            "eye_box_ratio": eye_box_ratio,
            "e2m_eye_ratio": e2m_eye_ratio,
            "face_center_y": face_center_y,
        }

        # Determine if frame looks plausibly frontal/neutral to seed/adapt baseline
        is_plausibly_neutral = (
            abs(yaw_ratio) <= 0.11
            and 0.44 <= pitch_ratio <= 0.575
            and nose_mouth_eye_ratio >= 0.39
            and eye_box_ratio <= 0.415
            and nose_box_ratio <= 0.605
        )
        baseline = cls._get_or_update_baseline(trial_key, metrics, is_plausibly_neutral)

        # Check lateral head turn first or downward head tilt
        is_down_abs = (
            pitch_ratio > 0.585
            or nose_mouth_eye_ratio < 0.375
            or nose_box_ratio > 0.612
            or eye_box_ratio > 0.422
            or (e2m_eye_ratio < 0.88 and pitch_ratio > 0.545)
        )
        is_down_rel = False
        is_left_rel = False
        is_right_rel = False
        if baseline is not None:
            is_down_rel = (
                (pitch_ratio - baseline["pitch_ratio"] >= 0.032)
                or (baseline["nose_mouth_eye_ratio"] - nose_mouth_eye_ratio >= 0.048)
                or (nose_box_ratio - baseline["nose_box_ratio"] >= 0.030)
                or (eye_box_ratio - baseline["eye_box_ratio"] >= 0.028)
                or (
                    baseline["e2m_eye_ratio"] - e2m_eye_ratio >= 0.070
                    and face_center_y - baseline["face_center_y"] >= 0.015
                )
            )
            is_left_rel = (yaw_ratio - baseline["yaw_ratio"]) < -0.115
            is_right_rel = (yaw_ratio - baseline["yaw_ratio"]) > 0.115

        orientation: Literal["CENTER", "DOWN", "LEFT", "RIGHT"] = "CENTER"
        if yaw_ratio < -0.135 or is_left_rel:
            orientation = "LEFT"
        elif yaw_ratio > 0.135 or is_right_rel:
            orientation = "RIGHT"
        elif is_down_abs or is_down_rel:
            orientation = "DOWN"

        identity_match: Optional[bool] = None
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
            "mouth_patch": mouth_patch,
        }

    @classmethod
    def compute_mouth_movement(cls, patches: list[Optional[tuple[np.ndarray, np.ndarray]]]) -> bool:
        """Determines whether the candidate's mouth moved significantly across consecutive frames."""
        valid = [p for p in patches if p is not None]
        if len(valid) < 2:
            return False

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
            net_motion = max(0.0, mouth_diff - 0.65 * cheek_diff)

            # Vertical lip opening contrast change inside the central mouth region
            center_prev = pm[6:22, 8:32]
            center_curr = cm[6:22, 8:32]
            std_delta = abs(float(center_curr.std()) - float(center_prev.std())) / 255.0

            movements.append(max(net_motion, std_delta * 0.85))

        if not movements:
            return False

        max_mov = max(movements)
        mean_mov = float(np.mean(movements))
        return max_mov >= 0.0065 or mean_mov >= 0.0038

    @classmethod
    def analyze_audio(
        cls,
        samples: Optional[list[float]],
    ) -> dict[str, Any]:
        """Analyzes 16kHz audio samples for RMS energy, gain-normalized VAD speech activity and multi-speaker."""
        if not samples or len(samples) < 160:
            return {
                "noise_level": 0.0,
                "speech_detected": False,
                "multiple_speakers": False,
                "high_noise": False,
            }

        audio = np.asarray(samples, dtype=np.float32)
        audio = np.nan_to_num(audio, nan=0.0, posinf=1.0, neginf=-1.0)
        audio = np.clip(audio, -1.0, 1.0)
        # Remove DC offset
        audio = audio - float(np.mean(audio))
        rms = float(np.sqrt(np.mean(np.square(audio))))

        speech_detected = False
        chunk_size = 480  # 30ms at 16000Hz
        total_chunks = audio.size // chunk_size

        if total_chunks > 0 and rms >= 0.003:
            chunks = audio[: total_chunks * chunk_size].reshape(total_chunks, chunk_size)
            chunk_rms = np.sqrt(np.mean(np.square(chunks), axis=1))
            noise_floor = float(np.percentile(chunk_rms, 20)) if total_chunks >= 4 else 0.002
            active_threshold = max(0.0032, noise_floor * 1.55)

            # Normalize gain for WebRTC VAD so normal/quiet speech on raw mics is detected reliably
            peak = float(np.percentile(np.abs(audio), 98))
            gain = min(18.0, 0.45 / max(peak, 1e-4))
            norm_audio = np.clip(audio * gain, -1.0, 1.0)
            pcm = (norm_audio * 32767).astype("<i2")

            try:
                import webrtcvad

                vad = webrtcvad.Vad(2)
                speech_chunks = 0
                for i in range(total_chunks):
                    if chunk_rms[i] >= active_threshold:
                        raw_bytes = pcm[i * chunk_size : (i + 1) * chunk_size].tobytes()
                        if vad.is_speech(raw_bytes, 16000):
                            speech_chunks += 1

                # Spectral check in human voice band (250Hz - 3400Hz) to avoid pure steady hum triggering VAD
                freqs = np.fft.rfftfreq(audio.size, d=1.0 / 16000.0)
                spectrum = np.abs(np.fft.rfft(audio)) ** 2
                total_energy = float(np.sum(spectrum)) + 1e-9
                voice_band_energy = float(
                    np.sum(spectrum[(freqs >= 220.0) & (freqs <= 3500.0)])
                )
                voice_band_ratio = voice_band_energy / total_energy

                if (speech_chunks >= 3 or (speech_chunks / total_chunks >= 0.08)) and voice_band_ratio >= 0.30:
                    speech_detected = True
            except Exception as exc:
                logger.debug("VAD no disponible o error en procesamiento: %s", exc)
                if np.sum(chunk_rms >= active_threshold) >= 4:
                    speech_detected = True

        # High ambient noise: very loud signal or sustained non-speech noise
        high_noise = rms > 0.22 or (rms > 0.14 and not speech_detected)

        multiple_speakers = False
        if speech_detected and len(audio) >= 24000:  # >= 1.5s
            try:
                from app.services.calibration_speaker_service import CalibrationSpeakerService

                segments = list(CalibrationSpeakerService.segments(audio))
                speakers = {item.speaker for item in segments if item.end - item.start >= 0.2}
                if len(speakers) > 1:
                    multiple_speakers = True
                else:
                    for i, first in enumerate(segments):
                        for second in segments[i + 1 :]:
                            if (
                                first.speaker != second.speaker
                                and min(first.end, second.end) - max(first.start, second.start) >= 0.1
                            ):
                                multiple_speakers = True
                                break
            except Exception:
                pass

        return {
            "noise_level": round(rms, 4),
            "speech_detected": speech_detected,
            "multiple_speakers": multiple_speakers,
            "high_noise": high_noise,
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

        if frame_results:
            counts = [f["face_count"] for f in frame_results]
            orientations = [f["orientation"] for f in frame_results]
            identities = [
                f["identity_match"] for f in frame_results if f["identity_match"] is not None
            ]
            mouth_patches = [f.get("mouth_patch") for f in frame_results]

            mouth_moving = cls.compute_mouth_movement(mouth_patches)

            # Determine representative face_count
            if all(c == 0 for c in counts) or sum(1 for c in counts if c == 0) >= max(2, len(counts) // 2 + 1):
                face_count = 0
                anomalies.append("FACE_ABSENT")
            elif any(c > 1 for c in counts):
                face_count = max(counts)
                anomalies.append("MULTIPLE_FACES")
            else:
                face_count = 1

            # Sustained head orientation: >= 2 frames in window (or majority of small window)
            down_count = sum(1 for o in orientations if o == "DOWN")
            side_frames = [o for o in orientations if o in ("LEFT", "RIGHT")]
            side_count = len(side_frames)

            min_sustained = 1 if len(orientations) == 1 else 2
            if down_count >= min_sustained:
                head_orientation = "DOWN"
                anomalies.append("HEAD_POSE_DOWN")
            elif side_count >= min_sustained:
                head_orientation = side_frames[-1]
                anomalies.append("HEAD_POSE_SIDE")
            else:
                head_orientation = orientations[-1]

            if identities:
                identity_match = all(identities)
                if identity_match is False:
                    anomalies.append("IDENTITY_MISMATCH")

        # Audio analysis and lip-sync verification
        audio_res = cls.analyze_audio(audio_samples)
        speech_detected = audio_res["speech_detected"]
        mouth_sync: Optional[bool] = None

        if audio_res["high_noise"]:
            anomalies.append("HIGH_NOISE")

        if speech_detected:
            # When the user speaks, check if their mouth moves in correspondence
            if face_count == 1 and mouth_moving:
                mouth_sync = True
            else:
                mouth_sync = False
                anomalies.append("VOICE_DETECTED")

        if audio_res["multiple_speakers"]:
            anomalies.append("MULTIPLE_SPEAKERS")

        return {
            "face_count": face_count,
            "head_orientation": head_orientation,
            "identity_match": identity_match,
            "speech_detected": speech_detected,
            "mouth_moving": mouth_moving,
            "mouth_sync": mouth_sync,
            "noise_level": audio_res["noise_level"],
            "anomalies": anomalies,
        }
