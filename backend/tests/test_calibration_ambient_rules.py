"""The calibration silence check: it judges speech, not the step transition or isolated 90 ms bursts."""
import numpy as np
import pytest

from app.services.integrity import thresholds as t
from app.services.integrity.calibration import CalibrationProfile
from app.services.integrity.models import AudioObservation

CHUNKS = 100  # 3 s of 30 ms chunks


def _observation(voiced_at_ms: list[int]) -> AudioObservation:
    flags = [False] * CHUNKS
    for at in voiced_at_ms:
        flags[at // 30] = True
    return AudioObservation(voiced_flags=flags)


def _segment(rms: float = 0.004) -> np.ndarray:
    return np.full(CHUNKS * t.VAD_CHUNK_SAMPLES, rms, dtype=np.float32)


def _check(voiced_at_ms: list[int], rms: float = 0.004):
    (check,) = CalibrationProfile().ambient(_observation(voiced_at_ms), _segment(rms))
    return check


def test_a_quiet_room_passes() -> None:
    assert _check([]).passed


def test_the_step_transition_at_the_start_is_not_judged() -> None:
    assert _check([0, 30, 60, 90, 120, 150, 180, 210, 240]).passed


def test_a_real_measured_recording_with_two_isolated_bursts_passes() -> None:
    """Measured on a laptop microphone in a quiet room: voiced at [0, 30, 60] and [1680, 1710, 1740]."""
    assert _check([0, 30, 60, 1680, 1710, 1740], rms=0.0103).passed


def test_raw_laptop_mic_hum_bursts_in_a_quiet_room_pass() -> None:
    """Measured raw mic floor without noiseSuppression: 29 scattered chunks, max run 6, rms 0.01441."""
    assert _check(
        [
            360, 390, 420, 450, 660, 690, 720, 750, 780, 1380, 1410, 1440, 1470, 1500, 1530,
            1590, 1620, 1650, 1830, 1860, 1890, 1920, 2250, 2280, 2310, 2430, 2460, 2490, 2520,
        ],
        rms=0.01441,
    ).passed


def test_continuous_speech_is_rejected() -> None:
    check = _check(list(range(600, 2970, 30)))
    assert not check.passed and "voz" in check.reason


@pytest.mark.parametrize("burst_chunks", [t.CAL_AMBIENT_MAX_RUN_CHUNKS, t.CAL_AMBIENT_MAX_RUN_CHUNKS + 3])
def test_a_word_sized_run_is_rejected(burst_chunks: int) -> None:
    assert not _check([1000 + 30 * i for i in range(burst_chunks)]).passed


def test_many_scattered_chunks_are_rejected() -> None:
    assert not _check([300 + 60 * i for i in range(t.CAL_AMBIENT_MAX_VOICED_CHUNKS)]).passed


def test_too_much_background_noise_is_rejected() -> None:
    assert not _check([], rms=t.CAL_AMBIENT_MAX_RMS * 1.5).passed
