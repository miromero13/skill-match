"""S5 / T6: the sustained-gaze rule (>= 1000 ms outside the screen zone) and the server cross-check of telemetry."""
import uuid

import numpy as np
import pytest

from gaze_fixtures import FakeLandmarker, eye_points, face_result

from app.services.integrity.models import GazeEvidence, GazeSample, GazeZone
from app.services.integrity.state import InMemoryStateStore

ZONE = GazeZone(-9.0, 13.0, -13.0, 13.0, -0.65, 0.65, -0.45, 0.55)
STEP = 100  # ms between samples in the unit cases


def sample(kind, t, **extra):
    base = {
        "in": dict(head_pitch=0.0, head_yaw=0.0, gaze_h=0.0, gaze_v=0.0),
        "down": dict(head_pitch=30.0, head_yaw=0.0, gaze_h=0.0, gaze_v=0.0),
        "up": dict(head_pitch=-25.0, head_yaw=0.0, gaze_h=0.0, gaze_v=0.0),
        "side": dict(head_pitch=0.0, head_yaw=30.0, gaze_h=0.0, gaze_v=0.0),
        "eyes": dict(head_pitch=0.0, head_yaw=0.0, gaze_h=0.0, gaze_v=0.95),
        "blink": dict(head_pitch=0.0, head_yaw=0.0, gaze_h=0.0, gaze_v=0.95, blink=True),
    }
    if kind == "none":
        return GazeSample(t_ms=t, face_count=0)
    return GazeSample(t_ms=t, face_count=1, **base[kind], **extra)


def series(*parts, start=0, step=STEP):
    """``series(("in", 3), ("eyes", 9))`` -> evenly spaced samples, one per ``step`` ms."""
    out, t = [], start
    for kind, count in parts:
        for _ in range(count):
            out.append(sample(kind, t))
            t += step
    return out


def evaluate(tracker, samples, client=(), start=1_000_000, zone=ZONE, key="trial-a", mismatch=False):
    evidence = GazeEvidence(server=tuple(samples), client=tuple(client), client_mismatch=mismatch,
                            window_start_ms=start, zone=zone, session_key=key)
    return tracker.evaluate(evidence)


@pytest.fixture
def tracker():
    from app.services.integrity.gaze import GazeRunTracker

    return GazeRunTracker(InMemoryStateStore())


# ---- per-sample classification -------------------------------------------------------------------

@pytest.mark.parametrize(
    ("sample_", "zone", "label"),
    [
        (sample("in", 0), ZONE, "IN"),
        (sample("down", 0), ZONE, "HEAD_POSE_DOWN"),
        (sample("up", 0), ZONE, "HEAD_POSE_UP"),
        (sample("side", 0), ZONE, "HEAD_POSE_SIDE"),
        (sample("eyes", 0), ZONE, "GAZE_AWAY_DOWN"),
        (sample("blink", 0), ZONE, "BLINK"),  # eyes away but closed: no gaze verdict
        (sample("none", 0), ZONE, "NEUTRAL"),
        (GazeSample(t_ms=0, face_count=2, head_pitch=0.0, head_yaw=0.0, gaze_h=0.0, gaze_v=0.0), ZONE, "NEUTRAL"),
        (GazeSample(t_ms=0, face_count=1, head_pitch=30.0, head_yaw=0.0, gaze_h=0.0, gaze_v=0.0, blink=True),
         ZONE, "HEAD_POSE_DOWN"),  # a blink never excuses the head
        (GazeSample(t_ms=0, face_count=1, head_pitch=None, head_yaw=None, gaze_h=None, gaze_v=None), ZONE,
         "NEUTRAL"),
        # Only the zone decides: 18 degrees is outside the conservative default (20 is its limit) only for a
        # tighter calibrated zone, and inside a wide one.
        (GazeSample(t_ms=0, face_count=1, head_pitch=18.0, head_yaw=0.0, gaze_h=0.0, gaze_v=0.0), ZONE,
         "HEAD_POSE_DOWN"),
        (GazeSample(t_ms=0, face_count=1, head_pitch=18.0, head_yaw=0.0, gaze_h=0.0, gaze_v=0.0), None, "IN"),
        (GazeSample(t_ms=0, face_count=1, head_pitch=-18.0, head_yaw=0.0, gaze_h=0.0, gaze_v=0.0), None,
         "HEAD_POSE_UP"),
        (GazeSample(t_ms=0, face_count=1, head_pitch=0.0, head_yaw=0.0, gaze_h=0.7, gaze_v=0.0), None, "GAZE_AWAY_LEFT"),
        (GazeSample(t_ms=0, face_count=1, head_pitch=0.0, head_yaw=0.0, gaze_h=-0.7, gaze_v=0.0), None, "GAZE_AWAY_RIGHT"),
        (GazeSample(t_ms=0, face_count=1, head_pitch=0.0, head_yaw=0.0, gaze_h=0.0, gaze_v=-0.7), None, "GAZE_AWAY_UP"),
        # Without a gaze measurement (YuNet only) the baseline-adaptive orientation is the only signal.
        (GazeSample(t_ms=0, face_count=1, head_pitch=0.0, head_yaw=0.0, orientation="DOWN"), ZONE,
         "HEAD_POSE_DOWN"),
        (GazeSample(t_ms=0, face_count=1, head_pitch=0.0, head_yaw=0.0, orientation="LEFT"), ZONE,
         "HEAD_POSE_SIDE"),
        (GazeSample(t_ms=0, face_count=1, head_pitch=0.0, head_yaw=0.0, orientation="CENTER"), ZONE, "IN"),
        # Uncalibrated, the adaptive orientation of a server frame still counts next to the default limits.
        (GazeSample(t_ms=0, face_count=1, head_pitch=5.0, head_yaw=0.0, gaze_h=0.0, gaze_v=0.0,
                    orientation="DOWN"), None, "HEAD_POSE_DOWN"),
    ],
)
def test_classification(sample_, zone, label):
    from app.services.integrity.gaze import classify

    assert classify(sample_, zone) == label


# ---- duration -------------------------------------------------------------------------------------

def test_tolerance_constant_is_one_second():
    from app.services.integrity.thresholds import GAZE_TOLERANCE_MS

    assert GAZE_TOLERANCE_MS == 1000


@pytest.mark.parametrize(("away", "expected"), [(1, False), (8, False), (9, False), (10, True), (11, True), (30, True)])
def test_only_a_continuous_run_of_one_second_is_an_incident(tracker, away, expected):
    # 900 ms away (9 samples, 100 ms each) is tolerated, 1000 ms and more is not.
    verdict = evaluate(tracker, series(("in", 3), ("eyes", away), ("in", 3)))
    assert verdict.kinds == (("GAZE_AWAY_DOWN",) if expected else ())


@pytest.mark.parametrize("kind", ["down", "up", "side", "eyes"])
def test_every_away_direction_maps_to_its_incident(tracker, kind):
    expected = {"down": "HEAD_POSE_DOWN", "up": "HEAD_POSE_UP", "side": "HEAD_POSE_SIDE", "eyes": "GAZE_AWAY_DOWN"}[kind]
    assert evaluate(tracker, series(("in", 2), (kind, 11), ("in", 2))).kinds == (expected,)


def test_returning_to_the_screen_breaks_the_run(tracker):
    assert evaluate(tracker, series(("eyes", 6), ("in", 1), ("eyes", 6))).kinds == ()


def test_blinks_neither_break_nor_start_a_run(tracker):
    # away 5 + blink 2 + away 5: one run of 12 samples = 1200 ms.
    assert evaluate(tracker, series(("eyes", 5), ("blink", 2), ("eyes", 5))).kinds == ("GAZE_AWAY_DOWN",)
    # a run that only exists because blinks are counted as away is not an incident: 8 away samples = 800 ms.
    assert evaluate(tracker, series(("blink", 3), ("eyes", 8), ("blink", 3)), key="b").kinds == ()
    # an isolated blink while looking at the screen is nothing.
    assert evaluate(tracker, series(("in", 5), ("blink", 3), ("in", 5)), key="c").kinds == ()


def test_eyes_that_stay_closed_are_not_a_blink(tracker):
    # 1000 ms of closed eyes (10 consecutive blink samples) is not a blink: attention cannot be verified.
    assert evaluate(tracker, series(("in", 2), ("blink", 10), ("in", 2))).kinds == ("EYES_CLOSED",)
    assert evaluate(tracker, series(("in", 2), ("blink", 7), ("in", 2)), key="short").kinds == ()


def test_a_face_that_is_not_measurable_neither_breaks_nor_extends_the_run(tracker):
    assert evaluate(tracker, series(("eyes", 5), ("none", 2), ("eyes", 5))).kinds == ("GAZE_AWAY_DOWN",)
    assert evaluate(tracker, series(("none", 8), ("eyes", 5)), key="b").kinds == ()


def test_the_dominant_direction_names_the_incident(tracker):
    verdict = evaluate(tracker, series(("down", 7), ("eyes", 4)))
    assert verdict.kinds == ("HEAD_POSE_DOWN",) and verdict.orientation == "DOWN"
    verdict = evaluate(tracker, series(("side", 11)), key="b")
    assert verdict.kinds == ("HEAD_POSE_SIDE",) and verdict.orientation == "RIGHT"
    assert evaluate(tracker, series(("up", 11)), key="c").orientation == "UP"
    assert evaluate(tracker, series(("eyes", 11)), key="d").orientation is None  # the head stays centered


def test_the_run_continues_across_windows(tracker):
    first = series(("in", 18), ("eyes", 6))  # window A (t 0..2300): 600 ms away at its end
    second = series(("eyes", 5), ("in", 19))  # window B starts at 2400: 500 ms more away, then back
    assert evaluate(tracker, first, start=1_000_000).kinds == ()
    assert evaluate(tracker, second, start=1_002_400).kinds == ("GAZE_AWAY_DOWN",)
    # A run that already ended is not reported again by the next window.
    assert evaluate(tracker, series(("in", 24)), start=1_004_800).kinds == ()


def test_a_run_interrupted_between_windows_is_not_chained(tracker):
    assert evaluate(tracker, series(("in", 18), ("eyes", 6)), start=1_000_000).kinds == ()
    assert evaluate(tracker, series(("in", 1), ("eyes", 5), ("in", 18)), start=1_002_400).kinds == ()


def test_a_long_gap_between_windows_starts_a_new_run(tracker):
    assert evaluate(tracker, series(("in", 18), ("eyes", 6)), start=1_000_000).kinds == ()
    assert evaluate(tracker, series(("eyes", 5), ("in", 19)), start=1_010_000).kinds == ()


def test_a_long_run_is_reported_by_every_window_it_touches(tracker):
    assert evaluate(tracker, series(("eyes", 24)), start=1_000_000).kinds == ("GAZE_AWAY_DOWN",)
    assert evaluate(tracker, series(("eyes", 24)), start=1_002_400).kinds == ("GAZE_AWAY_DOWN",)


def test_runs_are_tracked_per_trial_and_without_a_window_start(tracker):
    evaluate(tracker, series(("in", 18), ("eyes", 6)), key="one")
    assert evaluate(tracker, series(("eyes", 5), ("in", 19)), start=1_002_400, key="two").kinds == ()
    evaluate(tracker, series(("in", 18), ("eyes", 6)), key="three", start=None)
    assert evaluate(tracker, series(("eyes", 5), ("in", 19)), key="three", start=None).kinds == ()


def test_server_frames_are_sparse_but_three_consecutive_ones_are_a_run(tracker):
    # JPEG frames arrive every ~350 ms: two away frames are 700 ms, three are 1050 ms.
    assert evaluate(tracker, series(("in", 1), ("down", 2), ("in", 3), step=350)).kinds == ()
    assert evaluate(tracker, series(("in", 1), ("down", 3), ("in", 3), step=350), key="b").kinds == (
        "HEAD_POSE_DOWN",)


def test_trusted_telemetry_adds_short_away_runs_between_server_frames(tracker):
    server = series(("in", 1), ("down", 2), ("in", 4), step=400)  # away at 400 and 800 only: 800 ms
    assert evaluate(tracker, server).kinds == ()
    # The browser saw the head leave at 100 and come back at 1150, between the sampled frames.
    client = series(("in", 1), ("down", 16), ("in", 8), step=66)
    assert evaluate(tracker, server, client=client, key="with").kinds == ("HEAD_POSE_DOWN",)


def test_telemetry_can_only_add_evidence_never_clear_it(tracker):
    server = series(("in", 1), ("down", 4), ("in", 2), step=350)  # 1400 ms away on the server frames
    client = series(("in", 40), step=66)  # the browser claims it never looked away
    assert evaluate(tracker, server, client=client).kinds == ("HEAD_POSE_DOWN",)


# ---- consistency of telemetry with the server frames ----------------------------------------------

def test_consistent_telemetry_is_trusted():
    from app.services.integrity.gaze import check_telemetry

    server = series(("in", 4), step=400)
    client = series(("in", 25), step=66)
    check = check_telemetry(server, client)
    assert (check.trusted, check.mismatch, check.disagreements) == (True, False, 0)


def test_contradicting_telemetry_is_a_mismatch_and_not_trusted():
    from app.services.integrity.gaze import check_telemetry

    server = series(("down", 4), step=400)  # the server sees the head down at every sampled frame
    client = series(("in", 25), step=66)  # the browser says it is straight
    check = check_telemetry(server, client)
    assert (check.mismatch, check.trusted) == (True, False) and check.disagreements >= 2


def test_a_face_count_disagreement_counts():
    from app.services.integrity.gaze import check_telemetry

    server = series(("in", 4), step=400)
    client = series(("none", 25), step=66)
    assert check_telemetry(server, client).mismatch is True


def test_a_single_disagreeing_frame_is_not_a_mismatch():
    from app.services.integrity.gaze import check_telemetry

    server = series(("in", 1), ("down", 1), ("in", 2), step=400)
    client = series(("in", 25), step=66)
    check = check_telemetry(server, client)
    assert (check.disagreements, check.mismatch, check.trusted) == (1, False, True)


def test_transient_two_frame_disagreement_is_not_a_mismatch():
    from app.services.integrity.gaze import check_telemetry

    server = series(("in", 2), ("down", 3), ("in", 2), step=400)
    client = series(("in", 42), step=66)
    check = check_telemetry(server, client)
    assert (check.disagreements, check.mismatch, check.trusted) == (3, False, True)


def test_server_missed_face_on_low_res_frame_is_not_a_client_mismatch():
    from app.services.integrity.gaze import check_telemetry

    server = series(("none", 4), step=400)
    client = series(("in", 25), step=66)
    check = check_telemetry(server, client)
    assert (check.disagreements, check.mismatch) == (0, False)


def test_small_measurement_differences_are_tolerated():
    from app.services.integrity.gaze import check_telemetry

    server = [sample("in", t) for t in (0, 400, 800, 1200)]
    client = [GazeSample(t_ms=t, face_count=1, head_pitch=15.0, head_yaw=-15.0, gaze_h=0.5, gaze_v=-0.5)
              for t in range(0, 1300, 66)]
    assert check_telemetry(server, client).trusted is True


def test_telemetry_that_cannot_be_compared_is_ignored_without_an_accusation():
    from app.services.integrity.gaze import check_telemetry

    server = series(("down", 4), step=400)
    shifted = series(("in", 10), start=5000, step=66)  # no sample near any server frame
    check = check_telemetry(server, shifted)
    assert (check.trusted, check.mismatch) == (False, False)
    assert check_telemetry([], series(("in", 5))).trusted is False  # nothing to verify it against
    assert check_telemetry(server, []).trusted is False


def test_a_blink_on_one_side_is_not_a_gaze_disagreement():
    from app.services.integrity.gaze import check_telemetry

    server = [sample("eyes", t) for t in (0, 400, 800, 1200)]
    client = [sample("blink", t) for t in range(0, 1300, 66)]
    assert check_telemetry(server, client).mismatch is False


# ---- frame timestamps -------------------------------------------------------------------------------

def test_frame_times_are_spread_evenly_when_missing_or_implausible():
    from app.services.integrity.gaze import normalize_frame_times

    assert normalize_frame_times(None, 4, 2400) == [0, 600, 1200, 1800]
    assert normalize_frame_times([0, 600, 1200, 1800], 4, 2400) == [0, 600, 1200, 1800]
    assert normalize_frame_times([10, 590, 1230, 1790], 4, 2400) == [10, 590, 1230, 1790]  # jitter is fine
    # Bunching the frames of a stretch together to make it look short is not honored.
    assert normalize_frame_times([0, 5, 10, 15], 4, 2400) == [0, 600, 1200, 1800]
    assert normalize_frame_times([0, 600], 4, 2400) == [0, 600, 1200, 1800]  # misaligned with the frames
    assert normalize_frame_times(None, 0, 2400) == []
    assert normalize_frame_times(None, 2, None) == [0, 1200]


# ---- through the engine, from decoded frames ---------------------------------------------------------

class ScriptedLandmarker:
    """Returns one scripted MediaPipe result per detect() call."""

    def __init__(self, results):
        self.results = list(results)
        self.calls = 0

    def detect(self, _image):
        result = self.results[self.calls % len(self.results)]
        self.calls += 1
        return result


def rotation(pitch_deg=0.0, yaw_deg=0.0):
    p, y = np.radians(pitch_deg), np.radians(yaw_deg)
    pitch = np.array([[1, 0, 0], [0, np.cos(p), -np.sin(p)], [0, np.sin(p), np.cos(p)]])
    yaw = np.array([[np.cos(y), 0, np.sin(y)], [0, 1, 0], [-np.sin(y), 0, np.cos(y)]])
    matrix = np.eye(4)
    matrix[:3, :3] = yaw @ pitch
    return matrix


def looking(kind):
    if kind == "in":
        return face_result(eye_points())
    if kind == "eyes":
        return face_result(eye_points(0.0, 0.006))
    if kind == "up":
        return face_result(eye_points(), matrix=rotation(pitch_deg=-60.0))
    if kind == "down":
        return face_result(eye_points(), matrix=rotation(pitch_deg=60.0))
    if kind == "side":
        return face_result(eye_points(), matrix=rotation(yaw_deg=60.0))
    raise AssertionError(kind)


def engine_for(results, state=None):
    from app.services.integrity.audio_analyzer import AudioAnalyzer
    from app.services.integrity.engine import IntegrityEngine
    from app.services.integrity.frame_analyzer import FrameAnalyzer
    from app.services.integrity.policy import SupervisionProfile

    store = state or InMemoryStateStore()
    landmarker = ScriptedLandmarker(results)
    engine = IntegrityEngine(
        FrameAnalyzer(store, vision_provider=lambda: (None, None), landmarker_provider=lambda: landmarker),
        AudioAnalyzer(store),
    )
    return engine, SupervisionProfile(gaze_runs=store)


def frame():
    from test_integrity_engine import frame_b64

    return frame_b64()  # a different noisy image on every call: a live camera


def assess(engine, profile, kinds, *, zone=None, times=None, samples=(), start=1_000_000, key=None):
    return engine.assess_window(
        [frame() for _ in kinds], [0.0] * 38_400, duration_ms=2400, session_key=key or f"t-{uuid.uuid4()}",
        profile=profile, gaze_zone=zone, frame_times_ms=times, gaze_samples=list(samples), window_start_ms=start,
    )


@pytest.mark.parametrize(
    ("kind", "anomaly", "orientation"),
    [("eyes", "GAZE_AWAY_DOWN", "CENTER"), ("up", "HEAD_POSE_UP", "UP"), ("down", "HEAD_POSE_DOWN", "DOWN"),
     ("side", "HEAD_POSE_SIDE", "RIGHT")],
)
def test_engine_reports_sustained_away_frames(kind, anomaly, orientation):
    kinds = ["in", "in"] + [kind] * 4 + ["in", "in"]
    engine, profile = engine_for([looking(k) for k in kinds])
    result = assess(engine, profile, kinds)
    assert result.anomalies == [anomaly] and result.head_orientation == orientation


def test_engine_tolerates_a_short_look_away_and_reports_the_clean_window():
    kinds = ["in", "in", "eyes", "eyes", "in", "in", "in", "in"]
    engine, profile = engine_for([looking(k) for k in kinds])
    result = assess(engine, profile, kinds)
    assert result.anomalies == [] and result.head_orientation == "CENTER"


def test_engine_honors_the_calibrated_zone():
    kinds = ["in", "in"] + ["eyes"] * 4 + ["in", "in"]
    wide = GazeZone(-9.0, 13.0, -13.0, 13.0, -0.65, 0.65, -0.45, 1.5)  # looking down at the bottom edge is fine
    engine, profile = engine_for([looking(k) for k in kinds])
    assert assess(engine, profile, kinds, zone=wide).anomalies == []


def test_engine_run_spans_windows_through_the_state_store():
    state = InMemoryStateStore()
    first = ["in"] * 5 + ["eyes"] * 3
    second = ["eyes"] * 2 + ["in"] * 6
    engine, profile = engine_for([looking(k) for k in first + second], state)
    assert assess(engine, profile, first, key="trial", start=1_000_000).anomalies == []
    # frames at 300 ms: 3 away frames at the end of A (900 ms) are continued by 2 at the start of B
    assert assess(engine, profile, second, key="trial", start=1_002_400).anomalies == ["GAZE_AWAY_DOWN"]


def test_engine_without_a_zone_uses_default_limits_and_without_telemetry_is_still_judged():
    kinds = ["in", "in"] + ["up"] * 4 + ["in", "in"]
    engine, profile = engine_for([looking(k) for k in kinds])
    assert assess(engine, profile, kinds, zone=None, samples=[]).anomalies == ["HEAD_POSE_UP"]


def test_engine_flags_a_client_that_contradicts_the_server_and_ignores_its_telemetry():
    kinds = ["in", "in"] + ["down"] * 4 + ["in", "in"]
    engine, profile = engine_for([looking(k) for k in kinds])
    lying = [GazeSample(t_ms=t, face_count=1, head_pitch=0.0, head_yaw=0.0, gaze_h=0.0, gaze_v=0.0)
             for t in range(0, 2400, 66)]
    result = assess(engine, profile, kinds, samples=lying)
    assert result.anomalies == ["HEAD_POSE_DOWN", "CLIENT_MISMATCH"]


def test_engine_uses_trusted_telemetry_for_runs_between_sampled_frames():
    # Server frames every 400 ms see only 2 away frames (400, 800); the browser saw the head up from 100 to 1100.
    kinds = ["in", "up", "up", "in", "in", "in"]
    engine, profile = engine_for([looking(k) for k in kinds])
    client = [GazeSample(t_ms=t, face_count=1, head_pitch=-33.0 if 100 <= t <= 1100 else 0.0, head_yaw=0.0,
                         gaze_h=0.0, gaze_v=0.0) for t in range(0, 2400, 66)]
    assert assess(engine, profile, kinds, zone=ZONE).anomalies == []
    engine, profile = engine_for([looking(k) for k in kinds])
    assert assess(engine, profile, kinds, zone=ZONE, samples=client).anomalies == ["HEAD_POSE_UP"]


def test_engine_spreads_bunched_client_frame_times_instead_of_shortening_the_run():
    kinds = ["in", "in", "eyes", "eyes", "eyes", "eyes", "in", "in"]
    engine, profile = engine_for([looking(k) for k in kinds])
    bunched = [0, 1, 2, 3, 4, 5, 6, 7]
    assert assess(engine, profile, kinds, times=bunched).anomalies == ["GAZE_AWAY_DOWN"]
