"""Temporal confirmation: an observation becomes an incident only after it persists (T7 / S6, S7, S8).

``RunTracker`` turns timed per-frame flags into runs, the way the sustained gaze rule does: a flagged frame
stands for the time up to the next frame (at most ``GAZE_MAX_SAMPLE_SPAN_MS``), flagged frames further apart
than ``GAZE_RUN_GAP_MS`` are different runs and an unflagged frame ends the run. The run still open when a window
ends is kept in the session state store (``get_track`` / ``set_track``) so it can continue in the next window;
without a store, a session key or a window start every window is judged on its own.
"""
from dataclasses import dataclass
from statistics import median
from typing import Any, Mapping, Optional, Sequence

from app.services.integrity import thresholds as t


@dataclass(frozen=True)
class FlagSample:
    """One frame's verdict: ``flag`` None means "no verdict" (neither extends nor ends a run)."""

    at: int  # ms from the window start
    flag: Optional[bool]
    strong: bool = True  # corroborated evidence (e.g. both detectors agreed)


@dataclass(frozen=True)
class RunSummary:
    duration_ms: int
    frames: int  # flagged frames in the run, across windows
    windows: int  # windows the run has been seen in
    strong_streak: int  # most consecutive strong flagged frames


@dataclass
class _Run:
    start: int
    last: int
    end: int
    frames: int = 0
    windows: int = 0
    window: int = -1
    strong_now: int = 0
    strong_best: int = 0
    touched: bool = False  # extended by a frame of the window being judged

    _FIELDS = ("start", "last", "end", "frames", "windows", "window", "strong_now", "strong_best")

    def to_dict(self) -> dict[str, int]:
        return {name: getattr(self, name) for name in self._FIELDS}

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "_Run":
        return cls(**{name: int(raw[name]) for name in cls._FIELDS})

    def summary(self) -> RunSummary:
        return RunSummary(self.end - self.start, self.frames, self.windows, self.strong_best)


def sample_spans(times: Sequence[int]) -> list[int]:
    """The time each sample stands for: up to the next one, at most ``GAZE_MAX_SAMPLE_SPAN_MS``."""
    gaps = [b - a for a, b in zip(times, times[1:])]
    positive = [g for g in gaps if g > 0]
    tail = min(t.GAZE_MAX_SAMPLE_SPAN_MS, int(median(positive))) if positive else t.GAZE_MAX_SAMPLE_SPAN_MS
    return [min(t.GAZE_MAX_SAMPLE_SPAN_MS, gap) for gap in gaps] + ([tail] if times else [])


class RunTracker:
    def __init__(self, store: Optional[Any] = None) -> None:
        self.store = store

    def _stateful(self, session_key: Optional[str], base_ms: Optional[int]) -> bool:
        return (
            self.store is not None and bool(session_key) and base_ms is not None
            and hasattr(self.store, "get_track")
        )

    def evaluate(
        self, name: str, session_key: Optional[str], base_ms: Optional[int], samples: Sequence[FlagSample]
    ) -> list[RunSummary]:
        """Summaries of the runs the window's flagged frames belong to (closed ones and the one still open)."""
        ordered = sorted(samples, key=lambda sample: sample.at)
        if not ordered:
            return []
        stateful = self._stateful(session_key, base_ms)
        offset = base_ms or 0
        times = [offset + sample.at for sample in ordered]
        spans = sample_spans(times)
        carried = self.store.get_track(session_key, name) if stateful and self.store else None
        current = _Run.from_dict(carried) if carried else None
        runs: list[_Run] = []
        decisive = False
        for sample, at, span in zip(ordered, times, spans):
            if sample.flag is None:
                continue
            decisive = True
            if not sample.flag:
                if current is not None and current.touched:
                    runs.append(current)
                current = None
                continue
            if current is not None and at - current.last > t.GAZE_RUN_GAP_MS:
                if current.touched:
                    runs.append(current)
                current = None
            if current is None:
                current = _Run(start=at, last=at, end=at + span)
            current.last = max(current.last, at)
            current.end = max(current.end, at + span)
            current.frames += 1
            if current.window != offset:
                current.window = offset
                current.windows += 1
            current.strong_now = current.strong_now + 1 if sample.strong else 0
            current.strong_best = max(current.strong_best, current.strong_now)
            current.touched = True
        if current is not None and current.touched:
            runs.append(current)
        if stateful and decisive and self.store is not None:
            self.store.set_track(session_key, name, current.to_dict() if current else None)
        return [run.summary() for run in runs]


def longest(runs: Sequence[RunSummary]) -> int:
    return max((run.duration_ms for run in runs), default=0)


class StreakTracker:
    """Consecutive evaluations of something per session (T8: VOICE_MISMATCH, MULTIPLE_SPEAKERS, LIP_SYNC_MISMATCH).

    ``update`` counts a flagged evaluation, resets on an unflagged one and leaves the count alone for ``None``
    (an evaluation that could not judge). Without a store or a session key nothing is remembered: a lone
    evaluation counts as one, so count-based confirmation can never fire from a single stateless window.
    """

    def __init__(self, store: Optional[Any] = None) -> None:
        self.store = store

    def _stateful(self, session_key: Optional[str]) -> bool:
        return self.store is not None and bool(session_key) and hasattr(self.store, "get_track")

    def update(self, name: str, session_key: Optional[str], flag: Optional[bool]) -> int:
        if not self._stateful(session_key) or self.store is None:
            return 1 if flag else 0
        carried = int((self.store.get_track(session_key, name) or {}).get("count", 0))
        if flag is None:
            return carried
        count = carried + 1 if flag else 0
        self.store.set_track(session_key, name, {"count": count} if count else None)
        return count
