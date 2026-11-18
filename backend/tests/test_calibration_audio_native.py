"""Exercise the installed native VAD without claiming real-speech accuracy."""
import pytest
from app.core.exceptions import SkillMatchException
from app.services.calibration_audio_service import CalibrationAudioService


def test_native_vad_does_not_approve_two_silent_windows():
    with pytest.raises(SkillMatchException) as caught:
        CalibrationAudioService.assess([0.0] * 48000, [0.0] * 128000)
    assert caught.value.statuscode == 400
    assert caught.value.message == "No se detectó voz suficiente. Decí «Estoy listo para comenzar» cuando se indique y repetí la comprobación."
