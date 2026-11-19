"""S6 / S8 / T7: extra faces, an empty camera and identity are confirmed over time, never on one frame."""
import numpy as np
import pytest

from integrity_fixtures import (
    FAR_FACE, NEUTRAL, REFERENCE, SECOND, WEAK_FACE, Harness, ScriptedRecognizer, landmarks_result, mp_faces, one_hot,
)

from app.services.integrity.frame_analyzer import FrameAnalyzer
from app.services.integrity.models import GazeSample
from app.services.integrity.state import InMemoryStateStore

TWO = [NEUTRAL, SECOND]


# ---- S6: more people in the video ----------------------------------------------------------------

def test_a_second_face_in_a_single_frame_is_not_an_incident():
    res = Harness().window([[NEUTRAL], TWO, [NEUTRAL], [NEUTRAL]])
    assert res["anomalies"] == []
    assert res["face_count"] == 1


def test_a_second_face_in_two_consecutive_frames_is_multiple_faces():
    res = Harness().window([[NEUTRAL], TWO, TWO, [NEUTRAL]])
    assert res["anomalies"] == ["MULTIPLE_FACES"]
    assert res["face_count"] == 2


def test_a_second_face_that_flickers_is_not_consecutive():
    assert Harness().window([TWO, [NEUTRAL], TWO, [NEUTRAL]])["anomalies"] == []


def test_a_far_small_face_is_not_a_person():
    res = Harness().window([[NEUTRAL, FAR_FACE]] * 4)
    assert res["anomalies"] == []
    assert (res["face_count"], res["head_orientation"]) == (1, "CENTER")


def test_a_low_confidence_second_face_is_not_a_person():
    assert Harness().window([[NEUTRAL, WEAK_FACE]] * 4)["anomalies"] == []


def test_one_detector_alone_needs_the_second_face_to_persist_across_windows():
    harness = Harness(mediapipe=[mp_faces(1)])
    first = harness.window([[NEUTRAL], TWO, TWO], times=[0, 800, 1600], mediapipe=[mp_faces(1)])
    assert first["anomalies"] == []  # YuNet sees two people, MediaPipe one: no agreement
    second = harness.window([TWO, TWO, [NEUTRAL]], times=[0, 800, 1600], mediapipe=[mp_faces(1)])
    assert second["anomalies"] == ["MULTIPLE_FACES"]


def test_a_single_detector_sighting_that_does_not_persist_is_dropped():
    harness = Harness(mediapipe=[mp_faces(1)])
    harness.window([[NEUTRAL], TWO, TWO], times=[0, 900, 1800], mediapipe=[mp_faces(1)])
    res = harness.window([[NEUTRAL]] * 3, mediapipe=[mp_faces(1)])
    assert res["anomalies"] == []


def test_both_detectors_agreeing_confirm_within_one_window():
    harness = Harness(mediapipe=[mp_faces(1), mp_faces(2), mp_faces(2), mp_faces(1)])
    res = harness.window([[NEUTRAL], TWO, TWO, [NEUTRAL]])
    assert res["anomalies"] == ["MULTIPLE_FACES"]


def test_a_tiny_mediapipe_face_is_ignored_and_the_main_face_is_still_measured():
    clouds = landmarks_result([(0.5, 0.5, 0.6), (0.9, 0.9, 0.03)])
    analyzer = FrameAnalyzer(InMemoryStateStore(), vision_provider=lambda: (None, None),
                             landmarker_provider=lambda: None)
    obs = analyzer.analyze_frame(np.zeros((240, 320, 3), np.uint8), None, None, None,
                                 landmarker=type("L", (), {"detect": lambda self, _image: clouds})())
    assert obs.face_count == 1
    assert obs.orientation != "UNKNOWN"
    both = landmarks_result([(0.3, 0.5, 0.5), (0.8, 0.5, 0.4)])
    two = analyzer.analyze_frame(np.zeros((240, 320, 3), np.uint8), None, None, None,
                                 landmarker=type("L", (), {"detect": lambda self, _image: both})())
    assert two.face_count == 2


def test_trusted_browser_telemetry_confirms_a_single_server_sighting():
    harness = Harness()
    client = tuple(
        GazeSample(t_ms=at, face_count=2 if 300 <= at <= 900 else 1, head_pitch=0.0, head_yaw=0.0)
        for at in range(0, 1300, 100)
    )
    res = harness.window([[NEUTRAL], TWO, [NEUTRAL]], times=[0, 600, 1200], gaze_samples=client)
    assert res["anomalies"] == ["MULTIPLE_FACES"]


def test_short_browser_telemetry_does_not_confirm():
    client = tuple(
        GazeSample(t_ms=at, face_count=2 if 500 <= at <= 700 else 1, head_pitch=0.0, head_yaw=0.0)
        for at in range(0, 1300, 100)
    )
    res = Harness().window([[NEUTRAL], TWO, [NEUTRAL]], times=[0, 600, 1200], gaze_samples=client)
    assert res["anomalies"] == []


# ---- S8: an empty camera ---------------------------------------------------------------------------

def test_an_empty_camera_run_continues_across_windows():
    harness = Harness()
    first = harness.window([[NEUTRAL], [NEUTRAL], []], times=[0, 900, 1800])
    assert first["anomalies"] == []  # one empty frame is not enough
    second = harness.window([[], [NEUTRAL], [NEUTRAL]], times=[0, 900, 1800])
    assert second["anomalies"] == ["FACE_ABSENT"]  # the empty stretch lasted ~1.1 s across the two windows


def test_a_face_coming_back_ends_the_empty_run():
    harness = Harness()
    harness.window([[NEUTRAL], [NEUTRAL], []], times=[0, 900, 1800])
    assert harness.window([[NEUTRAL]] * 3)["anomalies"] == []
    assert harness.window([[], [NEUTRAL], [NEUTRAL]], times=[0, 900, 1800])["anomalies"] == []


def test_an_absent_face_window_is_still_flagged():
    res = Harness().window([[]] * 3)
    assert res["anomalies"] == ["FACE_ABSENT"]
    assert res["face_count"] == 0


# ---- S3 / identity ---------------------------------------------------------------------------------

def mismatching(per_frame):
    """Recognizer whose frames match (feature 0) or not (feature 1), one entry per call."""
    return ScriptedRecognizer([one_hot(0 if ok else 1) for ok in per_frame])


def test_one_bad_identity_frame_is_not_a_mismatch():
    harness = Harness(recognizer=mismatching([True, False, True, True]), reference=REFERENCE)
    res = harness.window([[NEUTRAL]] * 4)
    assert res["anomalies"] == []
    assert res["identity_match"] is True


def test_a_mismatching_window_is_pending_until_a_second_one_confirms():
    harness = Harness(recognizer=mismatching([False] * 8), reference=REFERENCE)
    first = harness.window([[NEUTRAL]] * 4)
    assert first["anomalies"] == []
    assert first["identity_match"] is None  # reported as pending, not as a verdict
    second = harness.window([[NEUTRAL]] * 4)
    assert second["anomalies"] == ["IDENTITY_MISMATCH"]
    assert second["identity_match"] is False


def test_a_good_window_resets_the_identity_confirmation():
    harness = Harness(recognizer=mismatching([False] * 4 + [True] * 4 + [False] * 4), reference=REFERENCE)
    results = [harness.window([[NEUTRAL]] * 4) for _ in range(3)]
    assert [r["anomalies"] for r in results] == [[], [], []]
    assert [r["identity_match"] for r in results] == [None, True, None]


def test_identity_needs_a_majority_of_non_matching_frames():
    harness = Harness(recognizer=mismatching([False, False, True, True, False, False, True, True]),
                      reference=REFERENCE)
    results = [harness.window([[NEUTRAL]] * 4) for _ in range(2)]
    assert [r["anomalies"] for r in results] == [[], []]  # exactly half is below 60 %


def test_a_window_with_a_single_judged_frame_cannot_accuse():
    harness = Harness(recognizer=mismatching([False] * 6), reference=REFERENCE)
    results = [harness.window([[NEUTRAL]]) for _ in range(3)]
    assert [r["anomalies"] for r in results] == [[], [], []]
    assert [r["identity_match"] for r in results] == [None, None, None]


def test_without_per_trial_state_one_window_needs_three_judged_frames():
    few = Harness(recognizer=mismatching([False] * 2), reference=REFERENCE, stateful=False)
    assert few.window([[NEUTRAL]] * 2)["anomalies"] == []
    many = Harness(recognizer=mismatching([False] * 4), reference=REFERENCE, stateful=False)
    assert many.window([[NEUTRAL]] * 4)["anomalies"] == ["IDENTITY_MISMATCH"]


def test_identity_is_not_judged_without_a_reference():
    res = Harness(recognizer=mismatching([False] * 4)).window([[NEUTRAL]] * 4)
    assert (res["identity_match"], res["anomalies"]) == (None, [])


@pytest.mark.parametrize("frames", [1, 3])
def test_a_clean_window_stays_clean(frames):
    res = Harness().window([[NEUTRAL]] * frames)
    assert res["anomalies"] == []
    assert res["face_count"] == 1
