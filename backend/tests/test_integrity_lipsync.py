"""T8 / S3, S11: temporal lip-sync correlation on synthetic signals, and the mouth_open telemetry cross-check.

Speech is a band-limited random envelope (syllable-like, not periodic, so a wrong shift decorrelates); the
mouth is the same envelope delayed, inverted, replaced by an independent one, or held still.
"""
import numpy as np
import pytest

from app.services.integrity import lipsync
from app.services.integrity import thresholds as t
from app.services.integrity.gaze import check_telemetry, sample_from_frame
from app.services.integrity.models import FrameObservation, GazeSample

CHUNK_MS = 30
N = 100  # 3.0 s of audio


def smooth_noise(seed, n, width):
    rng = np.random.default_rng(seed)
    raw = rng.normal(0, 1, n + width)
    return np.convolve(raw, np.ones(width) / width, mode="valid")[:n]


def envelope(seed=3):
    """Positive syllable-like energy per 30 ms chunk."""
    x = smooth_noise(seed, N, 6)
    return 0.06 + 0.05 * (x - x.min()) / (x.max() - x.min())


def mouth_from(env_fn, fps=15, span_ms=N * CHUNK_MS, offset_ms=0, scale=0.25, base=0.05):
    """Mouth aperture sampled at ``fps``: ``env_fn(t_ms)`` evaluated ``offset_ms`` later than the audio."""
    times = np.arange(0, span_ms, 1000 / fps).round().astype(int)
    return [(int(at), float(base + scale * env_fn(at - offset_ms))) for at in times]


def interpolator(env):
    centers = (np.arange(N) + 0.5) * CHUNK_MS
    low, high = float(env.min()), float(env.max())
    return lambda at: (np.interp(at, centers, env) - low) / (high - low)


def run(env, mouth, voiced=None, source="telemetry"):
    voiced = np.ones(N, dtype=bool) if voiced is None else voiced
    return lipsync.evaluate(np.where(voiced, env, 0.0).astype(np.float32), list(voiced), mouth, source)


def test_matching_voice_and_mouth_are_synced():
    env = envelope()
    result = run(env, mouth_from(interpolator(env)))
    assert result.verdict == "synced"
    assert result.correlation > 0.8 and result.overlap > 0.9 and result.source == "telemetry"


@pytest.mark.parametrize("lag_ms", [-90, 0, 90, 210, 300])
def test_a_mouth_lagging_within_tolerance_is_still_synced(lag_ms):
    env = envelope()
    result = run(env, mouth_from(interpolator(env), offset_ms=lag_ms))
    assert result.verdict == "synced"
    assert abs(result.lag_ms - lag_ms) <= 30  # the correlation finds the offset


def test_a_mouth_lagging_far_outside_tolerance_is_not_synced():
    env = envelope()
    result = run(env, mouth_from(interpolator(env), offset_ms=900))
    assert result.verdict == "unsynced"


def test_anti_correlated_mouth_is_unsynced():
    env = envelope()
    follow = interpolator(env)
    result = run(env, mouth_from(lambda at: 1.0 - follow(at)))
    assert result.verdict == "unsynced"
    assert result.correlation < t.LIPSYNC_MIN_CORRELATION


def test_an_unrelated_moving_mouth_is_unsynced():
    env = envelope()
    other = envelope(seed=11)
    result = run(env, mouth_from(interpolator(other)))
    assert result.verdict == "unsynced"
    assert result.overlap > t.LIPSYNC_MIN_ACTIVITY_OVERLAP  # the mouth moves, just not with the voice


def test_a_still_mouth_while_voiced_is_unsynced():
    env = envelope()
    result = run(env, mouth_from(lambda _at: 0.0))
    assert result.verdict == "unsynced"
    assert result.overlap == pytest.approx(0.0)


def test_mouth_jitter_is_not_activity():
    env = envelope()
    jitter = np.random.default_rng(0).normal(0, 0.002, 200)
    result = run(env, mouth_from(lambda at: float(jitter[int(at) % 200]) * 4))
    assert result.verdict == "unsynced"


def test_too_little_voiced_speech_is_insufficient():
    env = envelope()
    voiced = np.zeros(N, dtype=bool)
    voiced[: t.LIPSYNC_MIN_VOICED_MS // CHUNK_MS - 2] = True
    assert run(env, mouth_from(interpolator(env)), voiced).verdict == "insufficient"
    assert run(env, mouth_from(interpolator(env)), np.zeros(N, dtype=bool)).verdict == "insufficient"


def test_too_few_or_too_short_mouth_readings_are_insufficient():
    env = envelope()
    follow = interpolator(env)
    sparse = mouth_from(follow, fps=2)  # JPEG-frame cadence: ~6 readings
    assert len(sparse) < t.LIPSYNC_MIN_MOUTH_SAMPLES and run(env, sparse, source="server").verdict == "insufficient"
    brief = mouth_from(follow, span_ms=600, fps=30)  # enough readings, too little time
    assert len(brief) >= t.LIPSYNC_MIN_MOUTH_SAMPLES and run(env, brief).verdict == "insufficient"
    assert run(env, []).verdict == "insufficient"
    assert lipsync.evaluate(np.zeros(0, dtype=np.float32), [], mouth_from(follow), "telemetry").verdict == "insufficient"


def test_server_only_frames_can_support_a_verdict_when_dense_enough():
    env = envelope()
    result = run(env, mouth_from(interpolator(env), fps=10), source="server")
    assert result.verdict == "synced" and result.source == "server"


def test_non_finite_mouth_values_are_ignored_not_trusted():
    env = envelope()
    mouth = mouth_from(interpolator(env))
    mouth[3] = (mouth[3][0], float("nan"))
    assert run(env, mouth).verdict == "synced"


# ---- mouth_open telemetry vs server frames (S12) ---------------------------------------------------

def server(t_ms, mouth, **kw):
    return GazeSample(t_ms=t_ms, face_count=1, head_pitch=0.0, head_yaw=0.0, gaze_h=0.0, gaze_v=0.0,
                      mouth_open=mouth, **kw)


def test_server_sample_carries_the_measured_mouth_only_when_mediapipe_ran():
    measured = FrameObservation(face_count=1, mouth_open_score=0.31, blendshapes={"jawOpen": 0.3})
    assert sample_from_frame(measured, 0).mouth_open == pytest.approx(0.31)
    yunet_only = FrameObservation(face_count=1)  # no blendshapes, score 0.0: nothing was measured
    assert sample_from_frame(yunet_only, 0).mouth_open is None


def test_telemetry_mouth_contradicting_the_server_frames_is_a_mismatch():
    frames = [server(0, 0.02), server(300, 0.03), server(600, 0.02)]
    faked = [server(0, 0.60), server(300, 0.70), server(600, 0.60)]
    check = check_telemetry(frames, faked)
    assert check.mismatch and not check.trusted


def test_telemetry_mouth_agreeing_with_the_server_frames_is_trusted():
    frames = [server(0, 0.10), server(300, 0.35), server(600, 0.12)]
    honest = [server(0, 0.12), server(300, 0.30), server(600, 0.15)]
    check = check_telemetry(frames, honest)
    assert check.trusted and not check.mismatch


def test_telemetry_without_mouth_is_not_accused_of_a_mouth_mismatch():
    frames = [server(0, 0.02), server(300, 0.03)]
    plain = [GazeSample(t_ms=0, face_count=1, head_pitch=0.0, head_yaw=0.0, gaze_h=0.0, gaze_v=0.0),
             GazeSample(t_ms=300, face_count=1, head_pitch=0.0, head_yaw=0.0, gaze_h=0.0, gaze_v=0.0)]
    assert check_telemetry(frames, plain).trusted
