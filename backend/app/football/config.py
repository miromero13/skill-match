from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel

from app.core.config import settings

CONFIG_YAML_PATH = Path(__file__).resolve().parent / "config.yaml"


class SessionThresholdConfig(BaseModel):
    max_attempts_per_window: int = 3
    cooldown_minutes: int = 30
    chunk_duration_seconds: int = 5
    max_chunk_size_mb: int = 25
    retention_days: int = 30
    presigned_url_ttl_seconds: int = 900


class EnvCheckThresholdConfig(BaseModel):
    min_brightness: float = 40.0
    max_brightness: float = 245.0
    max_noise_db: float = 75.0
    max_latency_ms: float = 800.0
    require_face_detected: bool = True
    require_ball_detected: bool = True


class BallTrackerConfig(BaseModel):
    max_gap_frames: int = 5
    min_radius_px: int = 8
    max_radius_px: int = 160


class TouchEventsConfig(BaseModel):
    savgol_window_length: int = 7
    savgol_polyorder: int = 2
    min_velocity_delta: float = 0.35


class AudioEventsConfig(BaseModel):
    sample_rate_hz: int = 48000
    band_low_hz: float = 200.0
    band_high_hz: float = 4000.0
    mad_k: float = 3.5


class FusionConfig(BaseModel):
    tolerance_ms: int = 70
    min_coherence: float = 0.65
    max_drift_ms_per_min: float = 120.0


class ChallengesConfig(BaseModel):
    min_segments: int = 4
    max_segments: int = 6
    segment_min_duration_ms: int = 8000
    segment_max_duration_ms: int = 10000
    low_max_height_diameters: float = 1.5
    high_min_height_diameters: float = 3.0
    slow_min_interval_s: float = 1.0
    fast_max_interval_s: float = 0.6
    min_reaction_latency_s: float = 0.15


class ScoringConfig(BaseModel):
    min_confidence_for_auto_approval: float = 0.55
    beginner_max_streak: int = 7
    intermediate_max_streak: int = 25
    advanced_max_streak: int = 60


class FraudConfig(BaseModel):
    review_risk_threshold: float = 50.0
    invalid_risk_threshold: float = 80.0
    weights: dict[str, float]


class FootballPipelineConfig(BaseModel):
    version: str
    session: SessionThresholdConfig
    env_check: EnvCheckThresholdConfig = EnvCheckThresholdConfig()
    ball_tracker: BallTrackerConfig
    touch_events: TouchEventsConfig
    audio_events: AudioEventsConfig
    fusion: FusionConfig
    challenges: ChallengesConfig
    scoring: ScoringConfig
    fraud: FraudConfig

    @property
    def config_hash(self) -> str:
        """Compute deterministic SHA-256 hash of the active configuration."""
        canonical = json.dumps(self.model_dump(mode="json"), sort_keys=True)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, val in override.items():
        if isinstance(val, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], val)
        else:
            merged[key] = val
    return merged


@lru_cache(maxsize=4)
def load_football_config(env: str | None = None) -> FootballPipelineConfig:
    """Load `config.yaml` and merge environment-specific overrides."""
    target_env = (env or settings.ENVIRONMENT or "development").lower()
    with CONFIG_YAML_PATH.open("r", encoding="utf-8") as fh:
        raw_data: dict[str, Any] = yaml.safe_load(fh) or {}

    default_cfg: dict[str, Any] = raw_data.get("default", {})
    env_cfg: dict[str, Any] = raw_data.get(target_env, {})
    merged = _deep_merge(default_cfg, env_cfg)
    return FootballPipelineConfig.model_validate(merged)
