"""S5 / T6: gaze features from MediaPipe landmarks and the calibrated screen zone (pure engine, no API)."""
import numpy as np
import pytest

from gaze_fixtures import GEOMETRY_CASES, FakeLandmarker, eye_points, face_result

from app.services.integrity.models import FrameBatch, FrameObservation


def measure(points, blendshapes=None):
    from app.services.integrity.gaze import measure_gaze

    return measure_gaze(points, blendshapes or {})


@pytest.mark.parametrize("name", list(GEOMETRY_CASES))
def test_gaze_from_iris_geometry(name):
    dx, dy, expected_h, expected_v = GEOMETRY_CASES[name]
    gaze = measure(eye_points(dx, dy))
    assert gaze.gaze_h == pytest.approx(expected_h, abs=1e-6)
    assert gaze.gaze_v == pytest.approx(expected_v, abs=1e-6)
    assert gaze.blink is False


def test_blendshapes_are_blended_with_the_geometry():
    # ARKit semantics: the subject's left eye is the image-right one, so lookOutLeft / lookInRight = image right.
    right = measure(eye_points(), {"eyeLookOutLeft": 0.8, "eyeLookInRight": 0.8})
    assert right.gaze_h == pytest.approx(0.4) and right.gaze_v == pytest.approx(0.0)
    left = measure(eye_points(), {"eyeLookInLeft": 0.8, "eyeLookOutRight": 0.8})
    assert left.gaze_h == pytest.approx(-0.4)
    down = measure(eye_points(), {"eyeLookDownLeft": 0.6, "eyeLookDownRight": 0.6})
    assert down.gaze_v == pytest.approx(0.3)
    up = measure(eye_points(), {"eyeLookUpLeft": 0.6, "eyeLookUpRight": 0.6})
    assert up.gaze_v == pytest.approx(-0.3)


def test_blink_is_detected_from_blendshapes_and_from_closed_lids():
    assert measure(eye_points(), {"eyeBlinkLeft": 0.9, "eyeBlinkRight": 0.8}).blink is True
    assert measure(eye_points(), {"eyeBlinkLeft": 0.2, "eyeBlinkRight": 0.3}).blink is False
    # Without blendshapes the lids decide: an opening of 4 % of the eye width is a closed eye.
    assert measure(eye_points(opening=0.0024)).blink is True


def test_degenerate_eye_geometry_gives_no_gaze_instead_of_a_clean_center():
    flat = np.full((478, 3), 0.5)
    gaze = measure(flat)
    assert gaze.gaze_h is None and gaze.gaze_v is None
    assert measure(np.full((10, 3), 0.5)).gaze_h is None  # a mesh without iris landmarks


def test_frame_analyzer_exposes_gaze_and_blink():
    from app.services.integrity.frame_analyzer import FrameAnalyzer
    from app.services.integrity.state import InMemoryStateStore

    analyzer = FrameAnalyzer(InMemoryStateStore(), vision_provider=lambda: (None, None),
                             landmarker_provider=lambda: None)
    image = np.full((120, 160, 3), 128, dtype=np.uint8)
    looking = FakeLandmarker(face_result(eye_points(0.0, 0.006)))
    obs = analyzer.analyze_frame(image, None, None, None, landmarker=looking)
    assert obs.face_count == 1
    assert obs.gaze_h == pytest.approx(0.0, abs=1e-6) and obs.gaze_v == pytest.approx(0.9, abs=1e-6)
    assert obs.blink is False
    blinking = FakeLandmarker(face_result(eye_points(), {"eyeBlinkLeft": 0.9, "eyeBlinkRight": 0.9}))
    assert analyzer.analyze_frame(image, None, None, None, landmarker=blinking).blink is True


# ---- screen zone ---------------------------------------------------------------------------------

def sample(pitch, yaw, gaze_h, gaze_v, **extra):
    return FrameObservation(face_count=1, pitch_deg=pitch, yaw_deg=yaw, gaze_h=gaze_h, gaze_v=gaze_v, **extra)


def batch(*frames, **flags):
    return FrameBatch(frames=tuple(frames), **flags)


def corners(center=(0.0, 0.0, 0.0, 0.0)):
    targets = {
        "CENTER": center,
        "TOP_LEFT": (-4.0, -8.0, -0.5, -0.3),
        "TOP_RIGHT": (-4.0, 8.0, 0.5, -0.3),
        "BOTTOM_LEFT": (8.0, -8.0, -0.5, 0.4),
        "BOTTOM_RIGHT": (8.0, 8.0, 0.5, 0.4),
    }
    return {name: batch(sample(*vals), sample(*vals)) for name, vals in targets.items()}


def test_zone_is_the_bounds_of_the_five_targets_plus_a_margin():
    from app.services.integrity.gaze import compute_zone

    zone = compute_zone(corners())
    assert (zone.pitch_min, zone.pitch_max) == pytest.approx((-9.0, 13.0))
    assert (zone.yaw_min, zone.yaw_max) == pytest.approx((-13.0, 13.0))
    assert (zone.gaze_h_min, zone.gaze_h_max) == pytest.approx((-0.65, 0.65))
    assert (zone.gaze_v_min, zone.gaze_v_max) == pytest.approx((-0.45, 0.55))


def test_zone_uses_the_median_so_one_stray_frame_does_not_widen_it():
    from app.services.integrity.gaze import compute_zone

    data = corners()
    stray = sample(40.0, 40.0, 0.9, 0.9)
    data["CENTER"] = batch(sample(0, 0, 0, 0), sample(0, 0, 0, 0), stray)
    assert compute_zone(data).pitch_max == pytest.approx(13.0)


def test_zone_ignores_blinks_and_round_trips_through_json():
    from app.services.integrity.gaze import GazeZone, compute_zone

    data = corners()
    data["CENTER"] = batch(sample(0, 0, 0, 0), sample(0, 0, 0, 0), sample(30, 30, 1, 1, blink=True))
    zone = compute_zone(data)
    assert zone.pitch_max == pytest.approx(13.0)
    assert GazeZone.from_dict(zone.to_dict()) == zone


@pytest.mark.parametrize(
    ("mutate", "code"),
    [
        (lambda d: d.update(TOP_LEFT=batch()), "FACE_MISSING"),
        (lambda d: d.update(TOP_LEFT=batch(FrameObservation(face_count=0), FrameObservation(face_count=0))),
         "FACE_MISSING"),
        (lambda d: d.update(TOP_LEFT=batch(sample(0, 0, 0, 0), sample(0, 0, 0, 0, blink=True))), "FACE_MISSING"),
        (lambda d: d.update(CENTER=batch(FrameObservation(face_count=2), sample(0, 0, 0, 0))), "MULTIPLE_FACES"),
        (lambda d: d.update(CENTER=batch(model_unavailable=True)), "MODEL_UNAVAILABLE"),
        (lambda d: d.update(CENTER=batch(FrameObservation(face_count=1, pitch_deg=0.0, yaw_deg=0.0),
                                         FrameObservation(face_count=1, pitch_deg=0.0, yaw_deg=0.0))),
         "MODEL_UNAVAILABLE"),
    ],
)
def test_calibration_is_rejected_when_the_face_cannot_be_measured(mutate, code):
    from app.services.integrity.gaze import GazeCalibrationError, compute_zone

    data = corners()
    mutate(data)
    with pytest.raises(GazeCalibrationError) as error:
        compute_zone(data)
    assert error.value.code == code


def test_calibration_is_rejected_when_the_targets_are_not_distinguishable():
    from app.services.integrity.gaze import GazeCalibrationError, compute_zone

    still = {name: batch(sample(0, 0, 0, 0), sample(0, 0, 0, 0)) for name in corners()}
    with pytest.raises(GazeCalibrationError) as error:
        compute_zone(still)
    assert error.value.code == "NOT_DISTINGUISHABLE"
    # Only the horizontal axis moves: the vertical one is still degenerate.
    flat = {name: batch(sample(0, yaw, h, 0.0), sample(0, yaw, h, 0.0))
            for name, (yaw, h) in {"CENTER": (0, 0), "TOP_LEFT": (-8, -0.5), "TOP_RIGHT": (8, 0.5),
                                   "BOTTOM_LEFT": (-8, -0.5), "BOTTOM_RIGHT": (8, 0.5)}.items()}
    with pytest.raises(GazeCalibrationError):
        compute_zone(flat)


def test_eyes_only_movements_are_enough_to_distinguish_the_targets():
    from app.services.integrity.gaze import compute_zone

    # The head stays still; only the eyes visit the corners.
    eyes = {name: batch(sample(0, 0, h, v), sample(0, 0, h, v))
            for name, (h, v) in {"CENTER": (0, 0), "TOP_LEFT": (-0.5, -0.3), "TOP_RIGHT": (0.5, -0.3),
                                 "BOTTOM_LEFT": (-0.5, 0.4), "BOTTOM_RIGHT": (0.5, 0.4)}.items()}
    zone = compute_zone(eyes)
    assert zone.pitch_max == pytest.approx(5.0) and zone.gaze_h_max == pytest.approx(0.65)
