"""Per-session state of the integrity engine behind an interface.

Baselines (neutral head pose) and the rolling voiced-audio buffer are kept per session key. The bundled
implementation is in-memory, bounded (LRU) and lock-protected; a Redis-backed store can replace it by
implementing ``SessionStateStore`` without touching the analyzers.
"""
import copy
import threading
from collections import OrderedDict
from typing import Any, Optional, Protocol

import numpy as np

from app.services.integrity.thresholds import (
    BASELINE_ADAPT_ALPHA,
    BASELINE_NOSE_MOUTH_TOLERANCE,
    BASELINE_PITCH_TOLERANCE_DEG,
    BASELINE_WARMUP_SAMPLES,
    DIARIZATION_BUFFER_SAMPLES,
    MAX_TRACKED_SESSIONS,
)

__all__ = ["InMemoryStateStore", "SessionStateStore", "MAX_TRACKED_SESSIONS"]


class SessionStateStore(Protocol):
    """What the analyzers need to remember between frames and windows of the same session."""

    def update_baseline(
        self, session_key: Optional[str], metrics: dict[str, float], is_frontal_candidate: bool
    ) -> Optional[dict[str, float]]:
        """Folds a frame into the session's neutral-pose baseline and returns a copy of it (None if unknown)."""

    def combine_with_previous(
        self, session_key: Optional[str], audio: np.ndarray, remember: bool
    ) -> np.ndarray:
        """Returns the previous voiced audio of the session followed by ``audio``; optionally remembers ``audio``."""

    def clear_voiced_audio(self, session_key: Optional[str]) -> None:
        """Forgets the session's buffered voiced audio (stale speech must not carry over a silent window)."""

    def get_gaze_run(self, session_key: Optional[str]) -> Optional[dict[str, Any]]:
        """The out-of-zone run still open at the end of the session's previous window, if any."""

    def set_gaze_run(self, session_key: Optional[str], run: Optional[dict[str, Any]]) -> None:
        """Remembers (or, with None, forgets) the session's open out-of-zone run."""

    def get_track(self, session_key: Optional[str], name: str) -> Optional[dict[str, Any]]:
        """A named per-session record (open runs, streaks, references, ...), or None."""

    def set_track(self, session_key: Optional[str], name: str, value: Optional[dict[str, Any]]) -> None:
        """Remembers (or, with None, forgets) a named per-session record."""


class InMemoryStateStore:
    """Bounded in-memory store. Inference runs on worker threads, so every access takes the lock.

    ``baselines``, ``audio_state`` and ``lock`` can be supplied to share externally owned containers.
    """

    def __init__(
        self,
        baselines: Optional[OrderedDict[str, dict[str, float]]] = None,
        audio_state: Optional[OrderedDict[str, dict[str, Any]]] = None,
        lock: Optional[Any] = None,
        max_sessions: int = MAX_TRACKED_SESSIONS,
        gaze_runs: Optional[OrderedDict[str, dict[str, Any]]] = None,
        tracks: Optional[OrderedDict[str, dict[str, Any]]] = None,
    ) -> None:
        self.baselines: OrderedDict[str, dict[str, float]] = OrderedDict() if baselines is None else baselines
        self.audio_state: OrderedDict[str, dict[str, Any]] = OrderedDict() if audio_state is None else audio_state
        self.gaze_runs: OrderedDict[str, dict[str, Any]] = OrderedDict() if gaze_runs is None else gaze_runs
        self.tracks: OrderedDict[str, dict[str, Any]] = OrderedDict() if tracks is None else tracks
        self.lock = threading.RLock() if lock is None else lock
        self.max_sessions = max_sessions

    def update_baseline(
        self, session_key: Optional[str], metrics: dict[str, float], is_frontal_candidate: bool
    ) -> Optional[dict[str, float]]:
        if not session_key:
            return None
        with self.lock:
            baseline = self._update_baseline_locked(session_key, metrics, is_frontal_candidate)
            return dict(baseline) if baseline is not None else None

    def _update_baseline_locked(
        self, session_key: str, metrics: dict[str, float], is_frontal_candidate: bool
    ) -> Optional[dict[str, float]]:
        existing = self.baselines.get(session_key)
        if existing is None:
            if is_frontal_candidate:
                if len(self.baselines) >= self.max_sessions:
                    self.baselines.popitem(last=False)
                seeded = dict(metrics)
                seeded["samples"] = 1.0
                self.baselines[session_key] = seeded
                return seeded
            return None

        self.baselines.move_to_end(session_key)
        if is_frontal_candidate:
            samples = existing.get("samples", 1.0)
            if samples < BASELINE_WARMUP_SAMPLES:
                w_new = 1.0 / (samples + 1.0)
                w_old = 1.0 - w_new
                for k, v in metrics.items():
                    existing[k] = w_old * existing.get(k, v) + w_new * v
                existing["samples"] = samples + 1.0
            else:
                # Only adapt if posture is upright (never let downward tilt drift the baseline down)
                pitch_ok = (
                    metrics.get("pitch_deg", 0.0)
                    <= existing.get("pitch_deg", 0.0) + BASELINE_PITCH_TOLERANCE_DEG
                )
                nm_ok = (
                    metrics.get("nose_mouth_eye_ratio", 0.4)
                    >= existing.get("nose_mouth_eye_ratio", 0.4) - BASELINE_NOSE_MOUTH_TOLERANCE
                )
                if pitch_ok and nm_ok:
                    alpha = BASELINE_ADAPT_ALPHA
                    for k, v in metrics.items():
                        existing[k] = (1.0 - alpha) * existing.get(k, v) + alpha * v
        return existing

    def combine_with_previous(
        self, session_key: Optional[str], audio: np.ndarray, remember: bool
    ) -> np.ndarray:
        state: dict[str, Any] = {}
        with self.lock:
            if session_key:
                state = self.audio_state.get(session_key, {})
                if session_key in self.audio_state:
                    self.audio_state.move_to_end(session_key)
                else:
                    if len(self.audio_state) >= self.max_sessions:
                        self.audio_state.popitem(last=False)
                    self.audio_state[session_key] = state

            previous = state.get("prev_voiced_audio")
            if previous is not None and isinstance(previous, np.ndarray) and previous.size > 0:
                combined = np.concatenate([previous[-DIARIZATION_BUFFER_SAMPLES:], audio])
            else:
                combined = audio

            if session_key and remember:
                state["prev_voiced_audio"] = audio[-DIARIZATION_BUFFER_SAMPLES:].copy()
        return combined

    def clear_voiced_audio(self, session_key: Optional[str]) -> None:
        if not session_key:
            return
        with self.lock:
            if session_key in self.audio_state:
                self.audio_state[session_key].pop("prev_voiced_audio", None)

    def get_gaze_run(self, session_key: Optional[str]) -> Optional[dict[str, Any]]:
        if not session_key:
            return None
        with self.lock:
            run = self.gaze_runs.get(session_key)
            return None if run is None else {**run, "counts": dict(run["counts"])}

    def set_gaze_run(self, session_key: Optional[str], run: Optional[dict[str, Any]]) -> None:
        if not session_key:
            return
        with self.lock:
            if run is None:
                self.gaze_runs.pop(session_key, None)
                return
            if session_key not in self.gaze_runs and len(self.gaze_runs) >= self.max_sessions:
                self.gaze_runs.popitem(last=False)
            self.gaze_runs[session_key] = {**run, "counts": dict(run["counts"])}
            self.gaze_runs.move_to_end(session_key)

    def get_track(self, session_key: Optional[str], name: str) -> Optional[dict[str, Any]]:
        if not session_key:
            return None
        with self.lock:
            value = self.tracks.get(session_key, {}).get(name)
            return None if value is None else copy.deepcopy(value)

    def set_track(self, session_key: Optional[str], name: str, value: Optional[dict[str, Any]]) -> None:
        if not session_key:
            return
        with self.lock:
            if value is None:
                if session_key in self.tracks:
                    self.tracks[session_key].pop(name, None)
                return
            if session_key not in self.tracks and len(self.tracks) >= self.max_sessions:
                self.tracks.popitem(last=False)
            self.tracks.setdefault(session_key, {})[name] = copy.deepcopy(value)
            self.tracks.move_to_end(session_key)
