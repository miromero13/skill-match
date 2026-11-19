"""Gaze measurement and the calibrated screen zone (S5).

Everything here is pure math over MediaPipe FaceLandmarker output so that supervision and calibration (T9)
share it. The browser computes the same features in ``frontend/src/services/gaze-tracking.ts``; the formulas
below are the contract and both sides are pinned by the same synthetic landmark fixtures.

Conventions: landmark coordinates are normalized image coordinates of the *unmirrored* camera frame.
``gaze_h`` is positive when the iris is toward the image right, ``gaze_v`` positive when it is down.
Head ``pitch`` is positive looking down and ``yaw`` positive toward the image right (see frame_analyzer).
"""
from dataclasses import dataclass
from statistics import median
from typing import Any, Mapping, Optional, Sequence

import numpy as np

from app.services.integrity import thresholds as t
from app.services.integrity.models import FrameBatch, FrameObservation, GazeEvidence, GazeSample, GazeZone

# (corner at the image-left, corner at the image-right, upper lid, lower lid, iris center)
EYES = (
    (33, 133, 159, 145, 468),
    (362, 263, 386, 374, 473),
)
IRIS_LANDMARK_COUNT = 478
TARGETS = ("CENTER", "TOP_LEFT", "TOP_RIGHT", "BOTTOM_LEFT", "BOTTOM_RIGHT")


@dataclass(frozen=True)
class GazeMeasurement:
    gaze_h: Optional[float]
    gaze_v: Optional[float]
    blink: bool


def _clip(value: float) -> float:
    return max(-1.0, min(1.0, value))


def measure_gaze(points: Any, blendshapes: Mapping[str, float]) -> GazeMeasurement:
    """Gaze from the iris centers relative to the eye corners (h) and lids (v), blended with eyeLook* blendshapes.

    ``points`` is an (N, >=2) array of normalized landmarks. Without iris landmarks (N < 478) or with a
    degenerate eye the gaze is ``None`` (never a clean "centered" reading).
    """
    pts = np.asarray(points, dtype=np.float64)
    horizontal: list[float] = []
    vertical: list[float] = []
    openings: list[float] = []
    if pts.ndim == 2 and pts.shape[0] >= IRIS_LANDMARK_COUNT and pts.shape[1] >= 2:
        for left, right, upper, lower, iris in EYES:
            axis = pts[right, :2] - pts[left, :2]
            width = float(np.hypot(axis[0], axis[1]))
            if width < 1e-4:
                continue
            u = axis / width
            down = np.array([-u[1], u[0]])  # the in-image perpendicular pointing down for an upright eye
            mid = (pts[left, :2] + pts[right, :2]) / 2.0
            horizontal.append(_clip(t.GAZE_GAIN_H * float(np.dot(pts[iris, :2] - mid, u)) / (width / 2.0)))
            opening = float(np.dot(pts[lower, :2] - pts[upper, :2], down))
            openings.append(opening / width)
            if opening > 1e-6:
                lid_mid = (pts[upper, :2] + pts[lower, :2]) / 2.0
                vertical.append(_clip(t.GAZE_GAIN_V * float(np.dot(pts[iris, :2] - lid_mid, down)) / (opening / 2.0)))

    blink = _is_blink(blendshapes, openings)
    if not horizontal or not vertical:
        return GazeMeasurement(None, None, blink)
    geo_h = sum(horizontal) / len(horizontal)
    geo_v = sum(vertical) / len(vertical)
    w = t.GAZE_BLENDSHAPE_WEIGHT
    if _has_gaze_blendshapes(blendshapes):
        bs = blendshapes.get
        bs_h = ((bs("eyeLookOutLeft", 0.0) + bs("eyeLookInRight", 0.0))
                - (bs("eyeLookInLeft", 0.0) + bs("eyeLookOutRight", 0.0))) / 2.0
        bs_v = ((bs("eyeLookDownLeft", 0.0) + bs("eyeLookDownRight", 0.0))
                - (bs("eyeLookUpLeft", 0.0) + bs("eyeLookUpRight", 0.0))) / 2.0
        return GazeMeasurement((1 - w) * geo_h + w * bs_h, (1 - w) * geo_v + w * bs_v, blink)
    return GazeMeasurement(geo_h, geo_v, blink)


def mouth_open_score(points: Any, blendshapes: Mapping[str, float]) -> float:
    """Mouth aperture: the largest of the (close-softened) jawOpen blendshape, the inner-lip aspect ratio (MAR,
    landmarks 13/14 over the mouth width 78/308, x1.4) and the funnel/pucker blendshapes (x0.55).

    The browser computes the same score in ``gaze-tracking.ts`` (``mouthOpenScore``); both sides are pinned by the
    same fixtures, and lip-sync compares the browser's readings with the server's on the same frames.
    """
    pts = np.asarray(points, dtype=np.float64)
    jaw_open = blendshapes.get("jawOpen", 0.0)
    mouth_close = blendshapes.get("mouthClose", 0.0)
    funnel = blendshapes.get("mouthFunnel", 0.0) + 0.5 * blendshapes.get("mouthPucker", 0.0)
    ratio = 0.0
    if pts.ndim == 2 and pts.shape[0] > 308 and pts.shape[1] >= 2:
        lip_vert = float(np.hypot(pts[14, 0] - pts[13, 0], pts[14, 1] - pts[13, 1]))
        mouth_width = max(float(np.hypot(pts[308, 0] - pts[78, 0], pts[308, 1] - pts[78, 1])), 1e-4)
        ratio = lip_vert / mouth_width
    return float(max(jaw_open * max(0.2, 1.0 - 0.55 * mouth_close), ratio * 1.4, funnel * 0.55))


def _has_gaze_blendshapes(blendshapes: Mapping[str, float]) -> bool:
    return any(name.startswith("eyeLook") for name in blendshapes)


def _is_blink(blendshapes: Mapping[str, float], opening_ratios: Sequence[float]) -> bool:
    if "eyeBlinkLeft" in blendshapes or "eyeBlinkRight" in blendshapes:
        score = (blendshapes.get("eyeBlinkLeft", 0.0) + blendshapes.get("eyeBlinkRight", 0.0)) / 2.0
        return score >= t.GAZE_BLINK_SCORE
    return bool(opening_ratios) and all(ratio < t.GAZE_CLOSED_LID_RATIO for ratio in opening_ratios)


# ---- calibrated screen zone -----------------------------------------------------------------------


DEFAULT_ZONE = GazeZone(
    t.DEFAULT_ZONE_PITCH_DEG[0], t.DEFAULT_ZONE_PITCH_DEG[1],
    t.DEFAULT_ZONE_YAW_DEG[0], t.DEFAULT_ZONE_YAW_DEG[1],
    t.DEFAULT_ZONE_GAZE_H[0], t.DEFAULT_ZONE_GAZE_H[1],
    t.DEFAULT_ZONE_GAZE_V[0], t.DEFAULT_ZONE_GAZE_V[1],
)


class GazeCalibrationError(Exception):
    """The calibration frames cannot yield a trustworthy zone; ``code`` says why (the API maps it to a message)."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _usable(frame: FrameObservation) -> bool:
    return (
        frame.face_count == 1 and not frame.blink and frame.gaze_h is not None and frame.gaze_v is not None
        and frame.pitch_deg is not None and frame.yaw_deg is not None
    )


def compute_zone(per_target: Mapping[str, FrameBatch]) -> GazeZone:
    """The zone spanned by the five calibration targets (center + four corners) plus a margin.

    Per target the median of its usable frames is taken so a stray frame cannot widen the zone. Raises
    ``GazeCalibrationError`` when a face is missing or doubled, the gaze models are unavailable or the
    targets cannot be told apart (the candidate did not really look at the corners).
    """
    batches = {name: per_target.get(name, FrameBatch()) for name in TARGETS}
    if any(batch.model_unavailable for batch in batches.values()):
        raise GazeCalibrationError("MODEL_UNAVAILABLE")
    if any(f.face_count > 1 for batch in batches.values() for f in batch.frames):
        raise GazeCalibrationError("MULTIPLE_FACES")
    medians: list[tuple[float, float, float, float]] = []
    for batch in batches.values():
        single = [f for f in batch.frames if f.face_count == 1]
        usable = [f for f in single if _usable(f)]
        if len(usable) < t.ZONE_MIN_USABLE_FRAMES:
            # One face was seen but the landmarker could not measure the eyes: the model is the problem.
            if any(f.gaze_h is None for f in single if not f.blink):
                raise GazeCalibrationError("MODEL_UNAVAILABLE")
            raise GazeCalibrationError("FACE_MISSING")
        medians.append((
            median(float(f.pitch_deg) for f in usable if f.pitch_deg is not None),
            median(float(f.yaw_deg) for f in usable if f.yaw_deg is not None),
            median(float(f.gaze_h) for f in usable if f.gaze_h is not None),
            median(float(f.gaze_v) for f in usable if f.gaze_v is not None),
        ))
    pitch, yaw, gaze_h, gaze_v = zip(*medians)

    def span(values: Sequence[float]) -> float:
        return max(values) - min(values)

    horizontal_ok = span(yaw) >= t.ZONE_MIN_HEAD_SPAN_DEG or span(gaze_h) >= t.ZONE_MIN_GAZE_SPAN
    vertical_ok = span(pitch) >= t.ZONE_MIN_HEAD_SPAN_DEG or span(gaze_v) >= t.ZONE_MIN_GAZE_SPAN
    if not (horizontal_ok and vertical_ok):
        raise GazeCalibrationError("NOT_DISTINGUISHABLE")
    head, eyes = t.ZONE_HEAD_MARGIN_DEG, t.ZONE_GAZE_MARGIN
    return GazeZone(
        pitch_min=min(pitch) - head, pitch_max=max(pitch) + head,
        yaw_min=min(yaw) - head, yaw_max=max(yaw) + head,
        gaze_h_min=min(gaze_h) - eyes, gaze_h_max=max(gaze_h) + eyes,
        gaze_v_min=min(gaze_v) - eyes, gaze_v_max=max(gaze_v) + eyes,
    )


# ---- per-sample classification ---------------------------------------------------------------------

IN = "IN"  # looking at the screen
NEUTRAL = "NEUTRAL"  # nothing can be said (no single face, no measurement): neither extends nor breaks a run
BLINK = "BLINK"  # eyes closed: no gaze verdict (the head can still be judged)
HEAD_DOWN = "HEAD_POSE_DOWN"
HEAD_UP = "HEAD_POSE_UP"
HEAD_SIDE = "HEAD_POSE_SIDE"
GAZE_AWAY = "GAZE_AWAY"
AWAY_KINDS = (HEAD_DOWN, HEAD_UP, HEAD_SIDE, GAZE_AWAY)
_ORIENTATION_KIND = {"DOWN": HEAD_DOWN, "LEFT": HEAD_SIDE, "RIGHT": HEAD_SIDE}


def sample_from_frame(frame: FrameObservation, t_ms: int) -> GazeSample:
    return GazeSample(
        t_ms=t_ms, face_count=frame.face_count, head_pitch=frame.pitch_deg, head_yaw=frame.yaw_deg,
        gaze_h=frame.gaze_h, gaze_v=frame.gaze_v, blink=frame.blink, orientation=frame.orientation,
        mouth_open=frame.mouth_open_score if (frame.blendshapes or frame.mouth_open_score > 0.0) else None,
    )


def classify(sample: GazeSample, zone: Optional[GazeZone]) -> str:
    """Where one sample looks: IN, NEUTRAL, BLINK or the away kind (head first, then the eyes).

    ``zone=None`` means no calibrated zone: the conservative default limits apply and, for server frames, the
    baseline-adaptive head orientation still counts. A sample without gaze (YuNet-only fallback) is judged by
    that orientation alone.
    """
    if sample.face_count != 1:
        return NEUTRAL
    if sample.gaze_h is None:
        return _ORIENTATION_KIND.get(sample.orientation or "", IN if sample.orientation == "CENTER" else NEUTRAL)
    if sample.head_pitch is None or sample.head_yaw is None:
        return NEUTRAL
    if zone is None and sample.orientation in _ORIENTATION_KIND:
        return _ORIENTATION_KIND[sample.orientation or ""]
    bounds = zone or DEFAULT_ZONE
    if sample.head_pitch > bounds.pitch_max:
        return HEAD_DOWN
    if sample.head_pitch < bounds.pitch_min:
        return HEAD_UP
    if not bounds.yaw_min <= sample.head_yaw <= bounds.yaw_max:
        return HEAD_SIDE
    if sample.blink:
        return BLINK
    if sample.gaze_v is None:
        return NEUTRAL
    if not (bounds.gaze_h_min <= sample.gaze_h <= bounds.gaze_h_max
            and bounds.gaze_v_min <= sample.gaze_v <= bounds.gaze_v_max):
        return GAZE_AWAY
    return IN


# ---- timestamps -----------------------------------------------------------------------------------------


def normalize_frame_times(times: Optional[Sequence[int]], count: int, duration_ms: Optional[int]) -> list[int]:
    """Capture offsets (ms from the window start) of the window's frames.

    Client timestamps are honored only when each one stays close to its evenly spaced slot; anything else
    (missing, misaligned, bunched together to make a stretch look short) falls back to even spacing, so a
    client cannot shorten a run by lying about when its frames were taken.
    """
    if count <= 0:
        return []
    nominal = duration_ms if duration_ms else 2400
    slot = nominal / count
    even = [round(i * slot) for i in range(count)]
    if times is None or len(times) != count:
        return even
    tolerance = max(t.FRAME_TIME_MIN_TOLERANCE_MS, slot / 2.0)
    if any(abs(actual - expected) > tolerance for actual, expected in zip(times, even)):
        return even
    return [int(v) for v in times]


# ---- browser telemetry vs server frames ---------------------------------------------------------------


@dataclass(frozen=True)
class TelemetryCheck:
    trusted: bool  # the telemetry may add evidence to the window
    mismatch: bool  # the browser contradicted the server on the same frames (an incident by itself)
    comparable: int = 0
    disagreements: int = 0


def _informative(sample: GazeSample) -> bool:
    return sample.face_count != 1 or (sample.head_pitch is not None and sample.head_yaw is not None)


def _disagree(server: GazeSample, client: GazeSample) -> bool:
    if server.face_count != client.face_count:
        return True
    if server.face_count != 1 or server.gaze_h is None or server.head_pitch is None or server.head_yaw is None:
        return False
    assert client.head_pitch is not None and client.head_yaw is not None
    if (abs(server.head_pitch - client.head_pitch) > t.CLIENT_MISMATCH_HEAD_DEG
            or abs(server.head_yaw - client.head_yaw) > t.CLIENT_MISMATCH_HEAD_DEG):
        return True
    if (server.mouth_open is not None and client.mouth_open is not None
            and abs(server.mouth_open - client.mouth_open) > t.CLIENT_MISMATCH_MOUTH):
        return True
    if server.blink or client.blink or client.gaze_h is None or client.gaze_v is None or server.gaze_v is None:
        return False
    return (abs(server.gaze_h - client.gaze_h) > t.CLIENT_MISMATCH_GAZE
            or abs(server.gaze_v - client.gaze_v) > t.CLIENT_MISMATCH_GAZE)


def check_telemetry(server: Sequence[GazeSample], client: Sequence[GazeSample]) -> TelemetryCheck:
    """Compares each server frame with the browser sample nearest in time.

    Trusted only when enough frames are comparable and fewer than ``CLIENT_MISMATCH_MIN_FRAMES`` of them
    disagree; telemetry that cannot be compared is ignored without accusing the browser.
    """
    if not server or not client:
        return TelemetryCheck(False, False)
    comparable = disagreements = 0
    for frame in server:
        nearest = min(client, key=lambda c: abs(c.t_ms - frame.t_ms))
        if abs(nearest.t_ms - frame.t_ms) > t.CLIENT_MATCH_MAX_DT_MS or not _informative(nearest):
            continue
        comparable += 1
        if _disagree(frame, nearest):
            disagreements += 1
    mismatch = disagreements > 0 and disagreements >= min(t.CLIENT_MISMATCH_MIN_FRAMES, comparable)
    trusted = not mismatch and comparable >= min(t.CLIENT_MIN_COMPARABLE, len(server))
    return TelemetryCheck(trusted, mismatch, comparable, disagreements)


# ---- the sustained rule -----------------------------------------------------------------------------


@dataclass(frozen=True)
class GazeVerdict:
    kinds: tuple[str, ...] = ()  # incident kinds of the qualifying runs, in order
    orientation: Optional[str] = None  # DOWN / UP / LEFT / RIGHT when the head caused one, else None


@dataclass
class _Run:
    start: int
    last: int
    end: int
    counts: dict[str, int]
    touched: bool = False  # extended by a sample of the window being judged

    @property
    def duration(self) -> int:
        return self.end - self.start

    def kind(self) -> str:
        return max(AWAY_KINDS, key=lambda kind: self.counts.get(kind, 0))

    def to_dict(self) -> dict[str, Any]:
        return {"start": self.start, "last": self.last, "end": self.end, "counts": dict(self.counts)}

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "_Run":
        return cls(int(raw["start"]), int(raw["last"]), int(raw["end"]), dict(raw["counts"]))


def _promote_long_blinks(labelled: list[tuple[GazeSample, str]], spans: list[int]) -> list[tuple[GazeSample, str]]:
    """Blink runs longer than ``GAZE_BLINK_MAX_MS`` are not blinks: the eyes stayed closed."""
    out = list(labelled)
    i = 0
    while i < len(out):
        if out[i][1] != BLINK:
            i += 1
            continue
        j = i
        while j + 1 < len(out) and out[j + 1][1] == BLINK:
            j += 1
        if out[j][0].t_ms + spans[j] - out[i][0].t_ms > t.GAZE_BLINK_MAX_MS:
            for k in range(i, j + 1):
                out[k] = (out[k][0], GAZE_AWAY)
        i = j + 1
    return out


class GazeRunTracker:
    """Applies the sustained rule: an incident needs a continuous run outside the zone of at least ``GAZE_TOLERANCE_MS``.

    The run still open when a window ends is kept in the session state store so it can continue in the next
    window. Server frames are authoritative; trusted browser telemetry can only add away samples (it never
    breaks or shortens a run the server saw).
    """

    def __init__(self, store: Optional[Any] = None) -> None:
        self.store = store

    def evaluate(self, evidence: GazeEvidence) -> GazeVerdict:
        base = evidence.window_start_ms
        stateful = self.store is not None and bool(evidence.session_key) and base is not None
        offset = base or 0
        zone = evidence.zone
        server = sorted(evidence.server, key=lambda s: s.t_ms)
        spans = self._spans([s.t_ms for s in server])
        labelled = _promote_long_blinks([(s, classify(s, zone)) for s in server], spans)
        for sample in sorted(evidence.client, key=lambda s: s.t_ms):
            label = classify(sample, zone)
            if label in AWAY_KINDS:
                labelled.append((sample, label))
        labelled.sort(key=lambda pair: pair[0].t_ms)  # stable: server frames stay first on ties
        if not labelled:
            return GazeVerdict()

        times = [offset + sample.t_ms for sample, _ in labelled]
        gaps = [b - a for a, b in zip(times, times[1:])]
        positive = [g for g in gaps if g > 0]
        tail = min(t.GAZE_MAX_SAMPLE_SPAN_MS, int(median(positive))) if positive else t.GAZE_MAX_SAMPLE_SPAN_MS
        spans = [min(t.GAZE_MAX_SAMPLE_SPAN_MS, gap) for gap in gaps] + [tail]

        carried = self.store.get_gaze_run(evidence.session_key) if stateful and self.store else None
        current = _Run.from_dict(carried) if carried else None
        runs: list[_Run] = []
        decisive = False
        last_side: Optional[GazeSample] = None
        for (sample, label), at, span in zip(labelled, times, spans):
            if label in (NEUTRAL, BLINK):
                continue
            decisive = True
            if label == IN:
                if current is not None and current.touched:
                    runs.append(current)
                current = None
                continue
            if current is not None and at - current.last > t.GAZE_RUN_GAP_MS:
                if current.touched:
                    runs.append(current)
                current = None
            if current is None:
                current = _Run(start=at, last=at, end=at + span, counts={})
            current.last = max(current.last, at)
            current.end = max(current.end, at + span)
            current.counts[label] = current.counts.get(label, 0) + 1
            current.touched = True
            if label == HEAD_SIDE:
                last_side = sample
        if current is not None and current.touched:
            runs.append(current)
        if stateful and decisive and self.store is not None:
            self.store.set_gaze_run(evidence.session_key, current.to_dict() if current else None)

        kinds: list[str] = []
        for run in runs:
            if run.duration >= t.GAZE_TOLERANCE_MS and run.kind() not in kinds:
                kinds.append(run.kind())
        return GazeVerdict(tuple(kinds), self._orientation(kinds, last_side))

    @staticmethod
    def _spans(times: Sequence[int]) -> list[int]:
        gaps = [b - a for a, b in zip(times, times[1:])]
        positive = [g for g in gaps if g > 0]
        tail = min(t.GAZE_MAX_SAMPLE_SPAN_MS, int(median(positive))) if positive else t.GAZE_MAX_SAMPLE_SPAN_MS
        return [min(t.GAZE_MAX_SAMPLE_SPAN_MS, gap) for gap in gaps] + ([tail] if times else [])

    @staticmethod
    def _orientation(kinds: Sequence[str], last_side: Optional[GazeSample]) -> Optional[str]:
        if HEAD_DOWN in kinds:
            return "DOWN"
        if HEAD_UP in kinds:
            return "UP"
        if HEAD_SIDE in kinds and last_side is not None:
            if last_side.orientation in ("LEFT", "RIGHT"):
                return last_side.orientation
            return "RIGHT" if (last_side.head_yaw or 0.0) >= 0 else "LEFT"
        return None
