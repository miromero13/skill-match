"""Synthetic timing policy tests; not real-device/lip-reading efficacy evidence.

Rewritten in T9: the old tests stubbed ``CalibrationAVService.voice_activity`` / ``mouth_trace`` (mouth-patch
statistics, removed). The same rules are asserted on the engine: voice must follow the mouth the server measures on the
spoken frames (lip-sync correlation), nothing may be said in the pause, and sparse or old video cannot stand in.
"""
import pytest

from app.services.integrity import messages as m
from audio_fixtures import syllables, voice
from integrity_fixtures import face_b64  # noqa: F401
from test_integrity_calibration import AMBIENT_MS, Calibration, face


@pytest.fixture
def good(monkeypatch):
    return Calibration(monkeypatch)


def set_mouth(good, level_at):
    """The server measures ``level_at(seconds into the speech segment)`` on every spoken frame."""
    for frame, at in zip(good.voice, good.times):
        good.fake.by_frame[frame] = face(mouth_open_score=level_at((at - AMBIENT_MS) / 1000))


def follow(good, level_at):
    """Browser telemetry and the server's own frames agree on ``level_at`` (so only lip-sync judges the voice)."""
    set_mouth(good, level_at)
    return [(at, level_at((at - AMBIENT_MS) / 1000)) for at, _ in good.mouth]


def run(good, **changes):
    return good.rejected(**changes)


def after_the_phrase(t):
    return 0.05 + 0.25 * float(syllables(5, chunks=400)[int(t * 33)]) if t >= 5 else 0.05


@pytest.mark.parametrize("level_at", [lambda t: 0.05, after_the_phrase])
def test_voice_without_corresponding_mouth_activity_rejects(good, level_at):
    error = run(good, mouth=follow(good, level_at))  # a still mouth, or one that only moves after the phrase
    assert (error.check, error.status, error.message) == ("mouth_audio_sync", 400, m.VOICE_WITHOUT_MOUTH)


def test_synchronized_motion_and_voice_can_pass_but_does_not_prove_words(good):
    output = good.run()
    assert output.checks["mouth_audio_sync"] and output.checks["speech_pause"]


def test_speech_during_requested_pause_never_approves(good):
    audio = good.audio.copy()
    start = (AMBIENT_MS + 5000) * 16  # five seconds into the speech segment: the pause has begun
    audio[start:start + 16000] = voice(1.0)
    error = run(good, audio=audio)
    assert (error.check, error.message) == ("speech_pause", m.SPEECH_DURING_PAUSE)


def test_sparse_or_old_video_cannot_substitute_spoken_video(good):
    frames = list(zip(good.times, good.voice))
    for bad in (frames[:12], frames[::5], list(reversed(frames))):
        error = run(good, voice_frames=bad)
        assert (error.check, error.status, error.message) == ("frames", 400, m.VOICE_VIDEO)
