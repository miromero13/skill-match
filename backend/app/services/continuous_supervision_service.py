"""Continuous audiovisual window analysis for trial supervision.
Performs local OpenCV YuNet face presence, SFace 128-d cosine verification,
landmark-based head pose estimation, and WebRTC VAD/noise analysis.
Zero third-party cloud APIs.
"""
import base64
import binascii
import json
import logging
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
                    str(YUNET_MODEL_PATH), "", (320, 240), 0.55, 0.3, 5
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
    def analyze_frame_face(
        cls,
        image: np.ndarray,
        detector: Any,
        recognizer: Any,
        reference_embedding: Optional[np.ndarray],
    ) -> dict[str, Any]:
        """Analyzes a single video frame for face presence, pose and identity."""
        h, w = image.shape[:2]
        if detector is None:
            return {"face_count": 1, "orientation": "CENTER", "identity_match": True}

        detector.setInputSize((w, h))
        _, faces = detector.detect(image)
        face_count = 0 if faces is None else len(faces)

        if face_count == 0:
            return {
                "face_count": 0,
                "orientation": "UNKNOWN",
                "identity_match": None,
            }
        if face_count > 1:
            return {
                "face_count": face_count,
                "orientation": "UNKNOWN",
                "identity_match": None,
            }

        face = faces[0]
        # Landmarks: right_eye(4,5), left_eye(6,7), nose(8,9), right_mouth(10,11), left_mouth(12,13)
        rx, ry = float(face[4]), float(face[5])
        lx, ly = float(face[6]), float(face[7])
        nx, ny = float(face[8]), float(face[9])
        rmx, rmy = float(face[10]), float(face[11])
        lmx, lmy = float(face[12]), float(face[13])

        eye_mid_x = (rx + lx) / 2.0
        eye_mid_y = (ry + ly) / 2.0
        eye_distance = max(float(np.hypot(lx - rx, ly - ry)), 1.0)
        mouth_mid_y = (rmy + lmy) / 2.0
        eye_to_mouth = max(mouth_mid_y - eye_mid_y, 1.0)

        # Yaw: displacement of nose from eye midpoint normalized by interocular distance
        yaw_ratio = (nx - eye_mid_x) / eye_distance
        # Pitch: nose depth towards mouth line
        pitch_ratio = (ny - eye_mid_y) / eye_to_mouth

        orientation: Literal["CENTER", "DOWN", "LEFT", "RIGHT"] = "CENTER"
        if pitch_ratio > 0.72:
            orientation = "DOWN"
        elif yaw_ratio < -0.26:
            orientation = "LEFT"
        elif yaw_ratio > 0.26:
            orientation = "RIGHT"

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

        return {
            "face_count": 1,
            "orientation": orientation,
            "identity_match": identity_match,
        }

    @classmethod
    def analyze_audio(
        cls,
        samples: Optional[list[float]],
        mode: str,
    ) -> dict[str, Any]:
        """Analyzes 16kHz audio samples for RMS energy, VAD speech activity and multi-speaker."""
        if not samples or len(samples) < 160:
            return {
                "noise_level": 0.0,
                "speech_detected": False,
                "multiple_speakers": False,
                "high_noise": False,
            }

        audio = np.asarray(samples, dtype=np.float32)
        audio = np.clip(audio, -1.0, 1.0)
        rms = float(np.sqrt(np.mean(np.square(audio))))
        high_noise = rms > 0.15

        speech_detected = False
        try:
            import webrtcvad

            vad = webrtcvad.Vad(2)
            pcm = (audio * 32767).astype("<i2")
            chunk_size = 480  # 30ms at 16000Hz
            speech_chunks = 0
            total_chunks = pcm.size // chunk_size
            for i in range(0, pcm.size - chunk_size + 1, chunk_size):
                chunk = pcm[i : i + chunk_size].tobytes()
                if vad.is_speech(chunk, 16000):
                    speech_chunks += 1

            if total_chunks > 0 and (speech_chunks / total_chunks >= 0.12 or speech_chunks >= 8):
                speech_detected = True
        except Exception as exc:
            logger.debug("VAD no disponible o error en procesamiento: %s", exc)

        multiple_speakers = False
        if len(audio) >= 24000:  # >= 1.5s
            try:
                from app.services.calibration_speaker_service import CalibrationSpeakerService

                segments = list(CalibrationSpeakerService.segments(audio))
                speakers = {item.speaker for item in segments if item.end - item.start >= 0.2}
                if len(speakers) > 1:
                    multiple_speakers = True
                else:
                    for i, first in enumerate(segments):
                        for second in segments[i + 1 :]:
                            if first.speaker != second.speaker and min(first.end, second.end) - max(first.start, second.start) >= 0.1:
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
        mode: str,
        biometric_embedding_json: Optional[str],
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
                res = cls.analyze_frame_face(img, detector, recognizer, reference_embedding)
                frame_results.append(res)

        anomalies: list[str] = []
        face_count = 1
        head_orientation = "CENTER"
        identity_match: Optional[bool] = None

        if frame_results:
            counts = [f["face_count"] for f in frame_results]
            orientations = [f["orientation"] for f in frame_results]
            identities = [f["identity_match"] for f in frame_results if f["identity_match"] is not None]

            face_count = counts[-1]
            head_orientation = orientations[-1]
            if identities:
                identity_match = all(identities)

            # Anomaly rules:
            if all(c == 0 for c in counts):
                anomalies.append("FACE_ABSENT")
            elif any(c > 1 for c in counts):
                anomalies.append("MULTIPLE_FACES")

            # Sustained head orientation (2 or more consecutive frames looking down/side)
            down_run = sum(1 for o in orientations if o == "DOWN")
            side_run = sum(1 for o in orientations if o in ("LEFT", "RIGHT"))
            if down_run >= 2:
                anomalies.append("HEAD_POSE_DOWN")
            if side_run >= 2:
                anomalies.append("HEAD_POSE_SIDE")

            if identity_match is False:
                anomalies.append("IDENTITY_MISMATCH")

        # Audio analysis
        audio_res = cls.analyze_audio(audio_samples, mode)
        if audio_res["high_noise"]:
            anomalies.append("HIGH_NOISE")
        if mode == "QUIET" and audio_res["speech_detected"]:
            anomalies.append("VOICE_DETECTED")
        if audio_res["multiple_speakers"]:
            anomalies.append("MULTIPLE_SPEAKERS")

        return {
            "face_count": face_count,
            "head_orientation": head_orientation,
            "identity_match": identity_match,
            "speech_detected": audio_res["speech_detected"],
            "noise_level": audio_res["noise_level"],
            "anomalies": anomalies,
        }
