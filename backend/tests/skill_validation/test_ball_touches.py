"""S6 `BALL_TOUCH_STREAK`: dedicated juggling touch counter (pure trajectories + small generated videos).

No dependency on real footage: trajectories are built from ballistic key frames and videos draw a white ball that a
fake detector finds by brightness, so the whole video plumbing (sampling, chunks, crops) runs deterministically.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import cv2
import numpy as np
import pytest

from app.football.pipeline import efficientdet_ball_detector
from app.skill_validation import ENGINE_VERSION, analyze_video
from app.skill_validation import ball_touches as bt
from app.skill_validation.ball_touches import BallSample, PersonSample, count_touches

HZ = 25.0
D = 40.0  # ball diameter, px
FEET_Y = 600.0  # person's feet line, px (image y grows downwards)
FOOT_Y = FEET_Y - 2.0 * D  # ball centre at a foot touch: ball bottom 1.5 D above the feet line
APEX_Y = FOOT_Y - 4.0 * D
# Ball centre on the floor: a dropped ball lands in front of the player, so its bottom is below the feet line.
GROUND_Y = FEET_Y + 0.3 * D - D / 2
BALL_KEYS = {"ball_detected", "total_touches", "max_streak", "streaks", "ground_contacts"}

NOTE_NO_BALL = "No se detectó balón en el video."
NOTE_MODEL_MISSING = "Modelo EfficientDet-Lite0 no instalado; se usó solo el detector clásico de balón."
NOTE_MODEL_FAILED = "No se pudo cargar el modelo EfficientDet-Lite0; se usó solo el detector clásico."


def ballistic(keys: list[tuple[float, float]], t: float) -> float:
    """Ball centre y at ``t`` through key frames: accelerating falls, decelerating rises (sharp V at contacts)."""
    for (t0, y0), (t1, y1) in zip(keys, keys[1:]):
        if t0 <= t <= t1:
            u = (t - t0) / (t1 - t0)
            ease = u * u if y1 > y0 else 1.0 - (1.0 - u) ** 2
            return y0 + (y1 - y0) * ease
    return keys[-1][1]


def juggle_keys(n: int, start: float = 0.0, half: float = 0.3, apex: float = APEX_Y, low: float = FOOT_Y):
    """Key frames for ``n`` contacts: apex, (low, apex) * n."""
    keys = [(start, apex)]
    for i in range(n):
        keys += [(start + (2 * i + 1) * half, low), (start + (2 * i + 2) * half, apex)]
    return keys


def samples(keys, hz: float = HZ, hidden: tuple[float, float] | None = None, noise: float = 0.0, seed: int = 0):
    rng = np.random.default_rng(seed)
    out = []
    t = keys[0][0]
    while t <= keys[-1][0] + 1e-9:
        if hidden and hidden[0] < t < hidden[1]:
            out.append(BallSample(t=t))
        else:
            y = ballistic(keys, t) + (rng.normal(0, noise) if noise else 0.0)
            out.append(BallSample(t=t, x=300.0, y=y, diameter=D, score=0.9))
        t = round(t + 1.0 / hz, 6)
    return out


def feet(until: float) -> list[PersonSample]:
    return [PersonSample(t=t, feet_y=FEET_Y, height=8 * D) for t in np.arange(0.0, until + 0.5, 0.5)]


# ---------------------------------------------------------------------------------------------------------------
# Pure counting
# ---------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(("n", "half", "amplitude"), [(1, 0.3, 4.0), (5, 0.3, 4.0), (12, 0.3, 4.0), (10, 0.2, 0.8)])
def test_each_bounce_is_one_touch(n, half, amplitude):
    keys = juggle_keys(n, half=half, apex=FOOT_Y - amplitude * D)
    result = count_touches(samples(keys), feet(keys[-1][0]))
    assert result["ball_detected"] is True
    assert result["total_touches"] == n
    assert result["max_streak"] == n and result["streaks"] == [n]
    assert result["ground_contacts"] == 0
    assert len(result["touch_times"]) == n
    json.dumps(result, allow_nan=False)


def test_resting_or_jittering_ball_is_not_a_touch():
    still = [(0.0, FOOT_Y), (5.0, FOOT_Y)]
    result = count_touches(samples(still, noise=0.05 * D, seed=3), feet(5.0))
    assert result["ball_detected"] is True and result["total_touches"] == 0 and result["streaks"] == []
    tiny = juggle_keys(6, apex=FOOT_Y - 0.15 * D)  # bounces below the prominence threshold
    assert count_touches(samples(tiny))["total_touches"] == 0


def test_ground_contact_splits_streak_and_is_not_a_touch():
    first = juggle_keys(5)
    t = first[-1][0]
    bounce = [(t + 0.3, GROUND_Y), (t + 0.6, GROUND_Y - 2.5 * D)]  # weak rebound off the floor
    recovery = [(t + 0.9, FOOT_Y), (t + 1.2, APEX_Y)]  # the player catches it with the foot: touch 1 of run 2
    keys = first + bounce + recovery + juggle_keys(7, start=t + 1.2)[1:]
    result = count_touches(samples(keys), feet(keys[-1][0]))
    assert result["ground_contacts"] == 1
    assert result["ground_contact_times"] == [pytest.approx(t + 0.3, abs=0.05)]
    assert result["streaks"] == [5, 8]
    assert result["max_streak"] == 8 and result["total_touches"] == 13


def test_contact_at_feet_line_with_a_strong_rebound_is_a_touch():
    """Perspective: a ball juggled in front of the player reaches the feet line in the image; it is a touch."""
    keys = juggle_keys(4, low=GROUND_Y)
    result = count_touches(samples(keys), feet(keys[-1][0]))
    assert result["ground_contacts"] == 0 and result["streaks"] == [4]


def test_without_a_feet_line_there_are_no_ground_contacts():
    first = juggle_keys(3)
    t = first[-1][0]
    keys = first + [(t + 0.3, GROUND_Y), (t + 0.6, GROUND_Y - 2.5 * D)]
    result = count_touches(samples(keys))
    assert result["ground_contacts"] == 0 and result["total_touches"] == 4


@pytest.mark.parametrize(("lost_s", "streaks"), [(3.0, [4, 6]), (1.0, [10])])
def test_ball_lost_longer_than_drop_gap_splits_streak(lost_s, streaks):
    first = juggle_keys(4)
    t = first[-1][0]
    keys = first + [(t + lost_s, APEX_Y)] + juggle_keys(6, start=t + lost_s)[1:]
    result = count_touches(samples(keys, hidden=(t, t + lost_s)), feet(keys[-1][0]))
    assert result["total_touches"] == 10
    assert result["streaks"] == streaks and result["max_streak"] == max(streaks)


def test_no_ball_gives_zeros():
    result = count_touches([BallSample(t=i / HZ) for i in range(100)])
    assert result["ball_detected"] is False
    assert (result["total_touches"], result["max_streak"], result["streaks"], result["ground_contacts"]) == (0, 0, [], 0)
    assert result["detection_rate"] == 0.0
    assert count_touches([])["total_touches"] == 0


@pytest.mark.parametrize("garbage", [
    None, "abc", 42, [None, 3, "x"], [BallSample(t=math.nan, y=1.0, diameter=1.0)],
    [BallSample(t=0.0, y="a", diameter=-3)],  # type: ignore[arg-type]
    [BallSample(t=float(i), y=math.inf, diameter=D) for i in range(5)],
])
def test_counting_never_raises_on_garbage(garbage):
    result = count_touches(garbage, [object(), PersonSample(t="x", feet_y=None, height=0)])  # type: ignore[arg-type]
    assert BALL_KEYS <= set(result)
    assert result["total_touches"] == 0
    json.dumps(result, allow_nan=False)


def test_garbage_persons_do_not_hide_touches():
    keys = juggle_keys(3)
    result = count_touches(samples(keys), [None, "p", PersonSample(t=math.nan, feet_y=1.0, height=1.0)])
    assert result["total_touches"] == 3


# ---------------------------------------------------------------------------------------------------------------
# Generated videos through analyze_video
# ---------------------------------------------------------------------------------------------------------------

VIDEO_FPS = 30.0
VIDEO_KEYS = juggle_keys(7, half=0.45, apex=40.0, low=140.0)  # 7 contacts at 0.45 + 0.9 k s


class WhiteBlobDetector:
    """Stands in for EfficientDet: the brightest blob of the image is the 'sports ball'."""

    instances = 0

    def __init__(self, *_args, **_kwargs):
        WhiteBlobDetector.instances += 1

    def detect(self, image_bgr):
        mask = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY) > 200
        if not mask.any():
            return []
        ys, xs = np.nonzero(mask)
        x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
        return [("sports ball", 0.9, (x0 + x1) / 2.0, (y0 + y1) / 2.0, float(x1 - x0), float(y1 - y0))]

    def close(self):
        pass


class BrokenDetector:
    def __init__(self, *_args, **_kwargs):
        raise RuntimeError("model could not be loaded")


def write_video(path: Path, seconds: float, ball_y=None) -> Path:
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), VIDEO_FPS, (320, 240))
    assert writer.isOpened()
    for i in range(int(round(seconds * VIDEO_FPS))):
        frame = np.full((240, 320, 3), 40, dtype=np.uint8)
        if ball_y is not None:
            cv2.circle(frame, (160, int(round(ball_y(i / VIDEO_FPS)))), 10, (255, 255, 255), -1)
        writer.write(frame)
    writer.release()
    return path


@pytest.fixture
def bouncing_video(tmp_path):
    return write_video(tmp_path / "bounces.mp4", 6.3, lambda t: ballistic(VIDEO_KEYS, t))


@pytest.fixture
def ballless_video(tmp_path):
    return write_video(tmp_path / "noball.mp4", 2.0)


@pytest.fixture
def fake_model(monkeypatch, tmp_path):
    model = tmp_path / "efficientdet_lite0.tflite"
    model.write_bytes(b"fake")
    monkeypatch.setattr(efficientdet_ball_detector, "efficientdet_model_path", lambda: model)
    monkeypatch.setattr(bt, "EfficientDetObjectDetector", WhiteBlobDetector)
    WhiteBlobDetector.instances = 0
    return model


def test_video_bounces_are_counted_by_the_dedicated_counter(bouncing_video, fake_model):
    analysis = analyze_video(bouncing_video, need_pose=False, need_ball=True)
    assert analysis["ball_status"] == "ok" and analysis["notes"] == []
    ball = analysis["ball"]
    assert ball["detector"] == "efficientdet-lite0-roi"
    assert (ball["ball_detected"], ball["total_touches"], ball["max_streak"], ball["streaks"]) == (True, 7, 7, [7])
    assert ball["ground_contacts"] == 0
    assert ball["detection_rate"] >= 0.9 and ball["truncated"] is False
    assert ball["touch_times"] == pytest.approx([0.45 + 0.9 * k for k in range(7)], abs=0.08)
    assert WhiteBlobDetector.instances >= 1
    json.dumps(analysis, allow_nan=False)


def test_video_without_ball_reports_zeros_with_note(ballless_video, fake_model):
    analysis = analyze_video(ballless_video, need_pose=False, need_ball=True)
    ball = analysis["ball"]
    assert BALL_KEYS <= set(ball) and ball["detector"] == "efficientdet-lite0-roi"
    assert (ball["ball_detected"], ball["total_touches"], ball["max_streak"], ball["streaks"]) == (False, 0, 0, [])
    assert analysis["notes"] == [NOTE_NO_BALL]


def test_long_video_is_truncated_with_note(bouncing_video, fake_model, monkeypatch):
    monkeypatch.setattr(bt, "MAX_SECONDS", 2.0)
    analysis = analyze_video(bouncing_video, need_pose=False, need_ball=True)
    ball = analysis["ball"]
    assert ball["truncated"] is True and ball["analyzed_seconds"] == pytest.approx(2.0, abs=0.1)
    assert ball["total_touches"] == 2  # contacts at 0.45 s and 1.35 s
    assert analysis["notes"] == ["Se analizaron solo los primeros 2 s del video para contar los toques."]


def test_missing_model_falls_back_to_the_football_pipeline(bouncing_video, monkeypatch, tmp_path):
    monkeypatch.setattr(efficientdet_ball_detector, "efficientdet_model_path", lambda: tmp_path / "absent.tflite")
    monkeypatch.setattr(bt, "EfficientDetObjectDetector", BrokenDetector)  # must not even be tried
    analysis = analyze_video(bouncing_video, need_pose=False, need_ball=True)
    assert analysis["ball_status"] == "ok" and analysis["ball"]["detector"] == "classical"
    assert BALL_KEYS <= set(analysis["ball"])
    assert analysis["notes"][0] == NOTE_MODEL_MISSING
    json.dumps(analysis, allow_nan=False)


def test_model_failure_falls_back_to_the_football_pipeline(bouncing_video, fake_model, monkeypatch):
    monkeypatch.setattr(bt, "EfficientDetObjectDetector", BrokenDetector)
    analysis = analyze_video(bouncing_video, need_pose=False, need_ball=True)
    assert analysis["ball_status"] == "ok" and analysis["ball"]["detector"] == "classical"
    assert analysis["notes"][0] == NOTE_MODEL_FAILED


def test_detector_returning_garbage_never_raises(bouncing_video, fake_model, monkeypatch):
    class GarbageDetector(WhiteBlobDetector):
        def detect(self, image_bgr):
            return [None, ("sports ball",), ("sports ball", "high", 1, 2, 3, 4), 7]

    monkeypatch.setattr(bt, "EfficientDetObjectDetector", GarbageDetector)
    analysis = analyze_video(bouncing_video, need_pose=False, need_ball=True)
    assert analysis["readable"] is True and analysis["ball"] is not None
    assert analysis["ball"]["total_touches"] == 0
    json.dumps(analysis, allow_nan=False)


def test_engine_version_bumped_for_the_new_ball_counter():
    assert ENGINE_VERSION == "skill-validation-1.1"


REAL_MODEL = Path(bt.__file__).resolve().parents[1] / "models" / "weights" / "efficientdet_lite0.tflite"


@pytest.mark.skipif(not REAL_MODEL.is_file(), reason="efficientdet_lite0.tflite not installed")
def test_real_detector_loads_and_returns_a_list():
    detector = bt.EfficientDetObjectDetector(REAL_MODEL)
    try:
        assert detector.detect(np.zeros((240, 320, 3), dtype=np.uint8)) == []
    finally:
        detector.close()
