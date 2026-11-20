"""Synthetic video and audio generator for Football Skill Validation tests."""

from tests.football.synthetic.generator import (
    SyntheticClipResult,
    SyntheticJugglingSpec,
    build_synthetic_spec_for_plan,
    generate_synthetic_audio_wav,
    generate_synthetic_juggling_clip,
)

__all__ = [
    "SyntheticClipResult",
    "SyntheticJugglingSpec",
    "build_synthetic_spec_for_plan",
    "generate_synthetic_audio_wav",
    "generate_synthetic_juggling_clip",
]
