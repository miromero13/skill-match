"""Exercise the installed native VAD without claiming real-speech accuracy.

Rewritten in T9: the old test called ``CalibrationAudioService.assess`` (removed); the same rule is asserted on the
engine's calibration profile over the real WebRTC VAD.
"""
import numpy as np

from app.services.integrity import messages as m
from app.services.integrity.audio_analyzer import AudioAnalyzer
from app.services.integrity.calibration import CalibrationProfile
from app.services.integrity.state import InMemoryStateStore


def test_native_vad_does_not_approve_two_silent_windows():
    analyzer = AudioAnalyzer(InMemoryStateStore(), vad_floor=0.0)
    background, spoken = np.zeros(48000, dtype=np.float32), np.zeros(128000, dtype=np.float32)
    profile = CalibrationProfile()
    assert all(check.passed for check in profile.ambient(analyzer.analyze(background), background))
    failed = [check for check in profile.speech(analyzer.analyze(spoken), spoken) if not check.passed]
    assert [(c.name, c.status, c.reason) for c in failed] == [("microphone", 400, m.NOT_ENOUGH_SPEECH)]
