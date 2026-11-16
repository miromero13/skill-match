from __future__ import annotations

import hashlib
import hmac
import json
import random
from typing import Any

from app.core.config import settings
from app.football.config import load_football_config

CHALLENGE_TYPES: tuple[str, ...] = ("LOW", "HIGH", "SLOW", "FAST")


def generate_plan(seed: int) -> tuple[list[dict[str, Any]], str]:
    """
    Generate a deterministic 4-6 segment dynamic challenge plan ("the coach says")
    without consecutive duplicate challenge types, signed with HMAC-SHA256.
    """
    cfg = load_football_config()
    rng = random.Random(seed)
    num_segments = rng.randint(cfg.challenges.min_segments, cfg.challenges.max_segments)

    segments: list[dict[str, Any]] = []
    current_offset_ms = 0
    previous_type: str | None = None

    for idx in range(num_segments):
        candidates = [t for t in CHALLENGE_TYPES if t != previous_type]
        selected_type = rng.choice(candidates)
        duration_ms = rng.randrange(
            cfg.challenges.segment_min_duration_ms,
            cfg.challenges.segment_max_duration_ms + 1,
            500,
        )
        segments.append(
            {
                "indice": idx,
                "tipo": selected_type,
                "inicio_servidor_ms": current_offset_ms,
                "duracion_ms": duration_ms,
            }
        )
        current_offset_ms += duration_ms
        previous_type = selected_type

    payload_obj = {"seed": seed, "segments": segments}
    canonical_json = json.dumps(payload_obj, sort_keys=True, separators=(",", ":"))
    secret_bytes = settings.SECRET_KEY.get_secret_value().encode("utf-8")
    signature = hmac.new(
        secret_bytes, canonical_json.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    signed_plan = json.dumps(
        {"payload": payload_obj, "signature": signature},
        sort_keys=True,
    )
    return segments, signed_plan


def verify_signed_plan(signed_plan_str: str) -> bool:
    """Verify HMAC-SHA256 signature of a stored challenge plan."""
    try:
        parsed = json.loads(signed_plan_str)
        payload_obj = parsed["payload"]
        signature = str(parsed["signature"])
    except (KeyError, ValueError, TypeError):
        return False

    canonical_json = json.dumps(payload_obj, sort_keys=True, separators=(",", ":"))
    secret_bytes = settings.SECRET_KEY.get_secret_value().encode("utf-8")
    expected_sig = hmac.new(
        secret_bytes, canonical_json.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(signature, expected_sig)
