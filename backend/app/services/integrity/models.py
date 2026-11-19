"""Typed observations exchanged between the integrity analyzers, the engine and the policy profiles.

Observations are measurements only. Whether a measurement is an incident is decided by a profile
(``policy.py``), never here.
"""
from dataclasses import dataclass, field
from typing import Any, Literal, Mapping, Optional

import numpy as np

Orientation = Literal["CENTER", "DOWN", "UP", "LEFT", "RIGHT", "UNKNOWN"]
# (aligned 28x40 mouth crop, cheek pixels): the patch-based mouth fallback used when only YuNet ran.
MouthPatch = tuple[np.ndarray, np.ndarray]


@dataclass(frozen=True)
class GazeZone:
    """Bounds of (head pitch/yaw in degrees, gaze_h/gaze_v) while the candidate looks at the screen (T6)."""

    pitch_min: float
    pitch_max: float
    yaw_min: float
    yaw_max: float
    gaze_h_min: float
    gaze_h_max: float
    gaze_v_min: float
    gaze_v_max: float

    def to_dict(self) -> dict[str, float]:
        return {name: float(getattr(self, name)) for name in self.__dataclass_fields__}

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "GazeZone":
        return cls(**{name: float(raw[name]) for name in cls.__dataclass_fields__})


@dataclass(frozen=True)
class GazeSample:
    """One timed gaze/head reading: a server-measured JPEG frame or a browser telemetry sample.

    ``t_ms`` is the offset from the window start. ``orientation`` (the baseline-adaptive head class) only exists
    for server frames and is the head signal when no gaze could be measured (YuNet-only fallback).
    """

    t_ms: int
    face_count: int
    head_pitch: Optional[float] = None
    head_yaw: Optional[float] = None
    gaze_h: Optional[float] = None
    gaze_v: Optional[float] = None
    blink: bool = False
    orientation: Optional[str] = None
    # Mouth aperture score (the ``mouth_open_score`` formula, jawOpen + inner-lip MAR); None when not measured.
    mouth_open: Optional[float] = None


@dataclass(frozen=True)
class LipSyncResult:
    """How well the voice's energy follows the mouth aperture over one window (``lipsync.evaluate``)."""

    verdict: Literal["synced", "unsynced", "insufficient"] = "insufficient"
    correlation: Optional[float] = None  # best normalized cross-correlation over the tolerated lags
    overlap: Optional[float] = None  # fraction of voiced time during which the mouth aperture varies
    lag_ms: Optional[int] = None  # the mouth-vs-audio offset of the best correlation
    source: Optional[str] = None  # "telemetry" (trusted browser samples) or "server" (sampled JPEG frames)


@dataclass(frozen=True)
class GazeEvidence:
    """Everything the sustained-gaze rule needs for one window."""

    server: tuple[GazeSample, ...] = ()  # authoritative: measured on the JPEG frames the server decoded
    client: tuple[GazeSample, ...] = ()  # browser telemetry, present only when consistent with the server frames
    client_mismatch: bool = False  # the browser contradicted the server on the same frames
    window_start_ms: Optional[int] = None  # absolute epoch ms; None disables the cross-window run state
    zone: Optional[GazeZone] = None  # the trial's calibrated screen zone; None means the default limits
    session_key: Optional[str] = None


@dataclass(frozen=True)
class FrameOcclusion:
    """Per-frame occlusion verdict (``occlusion.judge``); an incident needs a continuous run of these."""

    face: bool = False
    mouth: bool = False
    measured: bool = False  # False: no reference yet or nothing measurable, so no verdict
    signals: tuple[str, ...] = ()  # what looked wrong: regions (eyes/nose/mouth), skin_shift, detector, identity


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
    # With face_count > 1 (extra faces already filtered by size and score): every detector that ran saw them.
    faces_agreed: bool = True
    # (right eye, left eye, nose, right and left mouth corner) in pixels: where the occlusion patches go.
    face_geometry: Optional[tuple[float, ...]] = None
    occlusion: Optional[FrameOcclusion] = None
    # Camera health (T7 / S8): a near-black or near-uniform image, and the mean abs difference to the previous frame.
    camera_blocked: bool = False
    frame_delta: Optional[float] = None

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
            faces_agreed=bool(raw.get("faces_agreed", True)),
            face_geometry=raw.get("face_geometry"),
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
    # Diarization over the trial's rolling voiced buffer (S2): the policy confirms ``multiple_speakers`` over time.
    diarized: bool = False  # diarization actually ran on this window's buffer
    speakers: int = 0
    overlap_s: float = 0.0  # the longest overlap between two different speakers
    foreign_voice: bool = False  # a cluster is not the enrolled voice while another one is
    speaker_model_unavailable: bool = False  # the speaker models could not run: never a clean audio verdict
    # Per 30 ms chunk: True = sustained-audio candidate (non-speech above the ambient floor), None = no verdict.
    background_flags: list[Optional[bool]] = field(default_factory=list)

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
    gaze: Optional[GazeEvidence] = None
    frame_times_ms: tuple[int, ...] = ()  # capture offset of each frame (window start = 0); empty: evenly spaced

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
    occlusion_face: bool = False  # a confirmed run of covered-face frames (FACE_OCCLUDED)
    occlusion_mouth: bool = False  # a confirmed run of covered-mouth frames (MOUTH_OCCLUDED)
    camera_blocked: bool = False  # a confirmed blocked or frozen camera (CAMERA_BLOCKED)

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
            "occlusion": {"face": self.occlusion_face, "mouth": self.occlusion_mouth},
            "camera_blocked": self.camera_blocked,
        }


@dataclass(frozen=True)
class FrameBatch:
    """Result of analyzing every frame of a window."""

    frames: tuple[FrameObservation, ...] = ()  # usable observations only
    video_missing: bool = False  # nothing decodable
    model_unavailable: bool = False  # no vision model, or a frame no model could judge
    times_ms: tuple[int, ...] = ()  # capture offset of each usable frame (window start = 0), when requested
