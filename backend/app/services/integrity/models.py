"""Typed observations exchanged between the integrity analyzers, the engine and the policy profiles.

Observations are measurements only. Whether a measurement is an incident is decided by a profile
(``policy.py``), never here.
"""
from dataclasses import dataclass, field
from typing import Any, Literal, Mapping, Optional

import numpy as np

Orientation = Literal["CENTER", "DOWN", "LEFT", "RIGHT", "UNKNOWN"]
# (aligned 28x40 mouth crop, cheek pixels): the patch-based mouth fallback used when only YuNet ran.
MouthPatch = tuple[np.ndarray, np.ndarray]


@dataclass(frozen=True)
class FrameObservation:
    """Everything measured on one decoded frame."""

    face_count: int
    orientation: Orientation = "UNKNOWN"
    pitch_deg: Optional[float] = None
    yaw_deg: Optional[float] = None
    # Every MediaPipe blendshape score by name, including eyeLook* (gaze, T6).
    blendshapes: Mapping[str, float] = field(default_factory=dict)
    mouth_open_score: float = 0.0
    identity_similarity: Optional[float] = None  # cosine to the reference embedding when it was computed
    identity_match: Optional[bool] = None
    mouth_patch: Optional[MouthPatch] = None
    landmarks: Optional[np.ndarray] = None  # (N, 3) normalized landmarks, only when the analyzer keeps them
    # Eye gaze (T6): iris position in [-1, 1] (h: + image right, v: + down); None when the eyes could not be measured.
    gaze_h: Optional[float] = None
    gaze_v: Optional[float] = None
    blink: bool = False  # eyes (nearly) closed: the frame says nothing about where the candidate looks
    model_unavailable: bool = False

    @classmethod
    def unavailable(cls) -> "FrameObservation":
        """No vision model produced a result: never a clean face (fail closed)."""
        return cls(face_count=0, model_unavailable=True)

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "FrameObservation":
        """Adapts the legacy dict shape (face_count, orientation, mouth_open_score, ...)."""
        return cls(
            face_count=int(raw["face_count"]),
            orientation=raw.get("orientation", "UNKNOWN"),
            pitch_deg=raw.get("pitch_deg"),
            yaw_deg=raw.get("yaw_deg"),
            blendshapes=dict(raw.get("blendshapes") or {}),
            mouth_open_score=float(raw.get("mouth_open_score", 0.0)),
            identity_similarity=raw.get("identity_similarity"),
            identity_match=raw.get("identity_match"),
            mouth_patch=raw.get("mouth_patch"),
            landmarks=raw.get("landmarks"),
            gaze_h=raw.get("gaze_h"),
            gaze_v=raw.get("gaze_v"),
            blink=bool(raw.get("blink", False)),
            model_unavailable=bool(raw.get("model_unavailable", False)),
        )

    def to_legacy_dict(self) -> dict[str, Any]:
        """The shape ``ContinuousSupervisionService.analyze_frame_face`` has always returned."""
        legacy: dict[str, Any] = {
            "face_count": self.face_count,
            "orientation": self.orientation,
            "identity_match": self.identity_match,
            "mouth_open_score": self.mouth_open_score,
            "mouth_patch": self.mouth_patch,
        }
        if self.model_unavailable:
            legacy["model_unavailable"] = True
        return legacy


@dataclass(frozen=True)
class AudioObservation:
    """Everything measured on one audio window (16 kHz mono)."""

    rms: float = 0.0
    speech_detected: bool = False
    multiple_speakers: bool = False
    high_noise: bool = False
    chunk_rms: np.ndarray = field(default_factory=lambda: np.zeros(0, dtype=np.float32))
    voiced_flags: list[bool] = field(default_factory=list)

    @property
    def noise_level(self) -> float:
        return round(self.rms, 4)

    def to_legacy_dict(self) -> dict[str, Any]:
        """The shape ``ContinuousSupervisionService.analyze_audio`` has always returned."""
        return {
            "noise_level": self.noise_level,
            "speech_detected": self.speech_detected,
            "multiple_speakers": self.multiple_speakers,
            "high_noise": self.high_noise,
            "chunk_rms": self.chunk_rms,
            "voiced_flags": self.voiced_flags,
        }


@dataclass(frozen=True)
class WindowObservation:
    """All measurements of one audiovisual window, ready for a policy profile."""

    frames: tuple[FrameObservation, ...] = ()  # usable frames only (model-unavailable ones are dropped)
    video_missing: bool = False  # no frame could be decoded
    model_unavailable: bool = False
    audio: AudioObservation = field(default_factory=AudioObservation)
    audio_missing: bool = False
    mouth_moving: bool = False
    mouth_movements: tuple[float, ...] = ()
    duration_ms: Optional[int] = None

    @property
    def visual_unavailable(self) -> bool:
        return (self.model_unavailable or self.video_missing) and not self.frames


@dataclass(frozen=True)
class WindowAssessment:
    """A profile's verdict on a window; ``to_dict`` is the dict the supervision API has always returned."""

    face_count: int
    head_orientation: Orientation
    identity_match: Optional[bool]
    speech_detected: bool
    mouth_moving: bool
    mouth_sync: Optional[bool]
    multiple_speakers: bool
    noise_level: float
    anomalies: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "face_count": self.face_count,
            "head_orientation": self.head_orientation,
            "identity_match": self.identity_match,
            "speech_detected": self.speech_detected,
            "mouth_moving": self.mouth_moving,
            "mouth_sync": self.mouth_sync,
            "multiple_speakers": self.multiple_speakers,
            "noise_level": self.noise_level,
            "anomalies": list(self.anomalies),
        }


@dataclass(frozen=True)
class FrameBatch:
    """Result of analyzing every frame of a window."""

    frames: tuple[FrameObservation, ...] = ()  # usable observations only
    video_missing: bool = False  # nothing decodable
    model_unavailable: bool = False  # no vision model, or a frame no model could judge
