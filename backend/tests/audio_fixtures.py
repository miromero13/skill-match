"""Shared helpers for the T8 audio tests: a faked VAD, synthetic voices and one trial's engine.

The fake VAD calls a 30 ms chunk speech when its RMS is at least ``SPEECH_RMS``: a sine at amplitude 0.1
(RMS 0.07) is "a voice", a 0.03 sine (RMS 0.021) is "music or a tone". Speakers are told apart by amplitude
(``LevelExtractor``), which stands in for the speaker embedding model.
"""
import itertools
import sys
import types

import numpy as np

from app.services.integrity.audio_analyzer import AudioAnalyzer
from app.services.integrity.engine import IntegrityEngine
from app.services.integrity.frame_analyzer import FrameAnalyzer
from app.services.integrity.policy import SupervisionProfile
from app.services.integrity.state import InMemoryStateStore
from integrity_fixtures import BASE_MS, NEUTRAL, Scripted, textured_b64

SR = 16_000
SPEECH_RMS = 0.04
WINDOW_MS = 2400
SPEAKER_AMPLITUDE = {1: 0.10, 2: 0.20, 3: 0.30}


def seconds(value):
    return int(round(value * SR))


def sine(duration_s, amplitude, freq=200.0):
    n = seconds(duration_s)
    return (amplitude * np.sin(2 * np.pi * freq * np.arange(n) / SR)).astype(np.float32)


def voice(duration_s, speaker=1):
    return sine(duration_s, SPEAKER_AMPLITUDE[speaker])


def tone(duration_s, amplitude=0.03):
    return sine(duration_s, amplitude, freq=440.0)


def silence(duration_s):
    return np.zeros(seconds(duration_s), dtype=np.float32)


def pad(*parts, total_ms=WINDOW_MS):
    """Concatenates ``parts`` and pads with silence (or trims) to a whole window."""
    audio = np.concatenate(parts) if parts else silence(0)
    n = total_ms * SR // 1000
    return np.concatenate([audio, np.zeros(max(0, n - audio.size), dtype=np.float32)])[:n]


def install_fake_vad(monkeypatch):
    def is_speech(raw, _rate):
        pcm = np.frombuffer(raw, dtype="<i2").astype(np.float64) / 32768.0
        return float(np.sqrt(np.mean(pcm ** 2))) >= SPEECH_RMS

    module = types.ModuleType("webrtcvad")
    module.Vad = lambda _mode: types.SimpleNamespace(is_speech=is_speech)
    monkeypatch.setitem(sys.modules, "webrtcvad", module)


class Segment:
    def __init__(self, start, end, speaker):
        self.start, self.end, self.speaker = start, end, speaker


class LevelExtractor:
    """Speaker id = how loud the audio is; the embedding is that speaker's unit vector (times 3)."""

    def __init__(self):
        self.calls = []
        self.fail = None

    def embed(self, audio):
        if self.fail:
            raise self.fail
        self.calls.append(len(audio))
        level = float(np.mean(np.abs(audio))) / (2 / np.pi * SPEAKER_AMPLITUDE[1])
        vec = np.zeros(16, dtype=np.float32)
        vec[int(round(level)) % 16] = 3.0
        return vec


class Trial:
    """One trial's engine over a shared state store; every ``window`` is 2.4 s starting where the last ended."""

    def __init__(self, monkeypatch, segments=None, extractor=None):
        install_fake_vad(monkeypatch)
        self.segments = segments if segments is not None else []
        self.diarized_lengths = []
        self.extractor = extractor or LevelExtractor()
        self.state = InMemoryStateStore()
        audio = AudioAnalyzer(self.state, speaker_segments=self._diarize, extractor=self.extractor)
        frames = FrameAnalyzer(self.state, vision_provider=lambda: (Scripted([[NEUTRAL]]), None),
                               landmarker_provider=lambda: None)
        self.engine = IntegrityEngine(frames, audio)
        self.profile = SupervisionProfile(gaze_runs=self.state)
        self.clock = 0
        self.counter = itertools.count(1)

    def _diarize(self, audio):
        self.diarized_lengths.append(len(audio))
        if isinstance(self.segments, Exception):
            raise self.segments
        return self.segments(audio) if callable(self.segments) else self.segments

    def window(self, audio, *, gaze_samples=(), stateful=True, voiceprint=None, frames=2, duration_ms=WINDOW_MS):
        images = [textured_b64(next(self.counter) * 7919) for _ in range(frames)]
        times = [round(i * duration_ms / frames) for i in range(frames)]
        result = self.engine.assess_window(
            images, [float(v) for v in audio], duration_ms=duration_ms, session_key="trial", profile=self.profile,
            frame_times_ms=times, gaze_samples=list(gaze_samples), voiceprint=voiceprint,
            window_start_ms=BASE_MS + self.clock if stateful else None,
        )
        self.clock += duration_ms
        return result.to_dict()
