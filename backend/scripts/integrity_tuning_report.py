#!/usr/bin/env python3
"""Summarizes labelled integrity diagnostics (``INTEGRITY_DIAGNOSTICS_ENABLED``) to tune ``thresholds.py``.

Usage: python scripts/integrity_tuning_report.py <dir-or-file.jsonl>

Per label: windows, anomalies fired, and min / p5 / median / p95 / max of every numeric measurement; then, per label,
the detection rate of its expected anomaly kinds and, for ``normal``, the false-alarm rate of every kind.
Standard library only; the files are read with plain ``json`` parsing.
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

# What each recorded behaviour should make the engine report (any one of them counts as a detection).
EXPECTED = {
    "mirando_abajo": ("HEAD_POSE_DOWN", "GAZE_AWAY"),
    "mirando_costado": ("HEAD_POSE_SIDE", "GAZE_AWAY"),
    "mirando_arriba": ("HEAD_POSE_UP", "GAZE_AWAY"),
    "ojos_abajo": ("GAZE_AWAY",),
    "boca_tapada": ("MOUTH_OCCLUDED",),
    "cara_tapada": ("FACE_OCCLUDED", "FACE_ABSENT"),
    "camara_tapada": ("CAMERA_BLOCKED", "FACE_ABSENT"),
    "dos_personas": ("MULTIPLE_FACES",),
    "otra_voz": ("MULTIPLE_SPEAKERS", "VOICE_MISMATCH"),
    "audio_dispositivo": ("BACKGROUND_AUDIO",),
    "hablando_yo": (),  # my own voice, mouth moving: nothing should fire
}
NO_LABEL = "(sin etiqueta)"
SKIPPED = {"t_ms"}


def load(target: Path) -> list[dict]:
    files = sorted(target.glob("*.jsonl")) if target.is_dir() else [target]
    records = []
    for path in files:
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                print(f"aviso: {path.name}:{number} no es JSON, se omite", file=sys.stderr)
                continue
            if isinstance(record, dict):
                records.append(record)
    return records


def numeric(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def measurements(record: dict) -> dict[str, list[float]]:
    found: dict[str, list[float]] = defaultdict(list)
    for section in ("window", "audio", "lip_sync"):
        for key, value in (record.get(section) or {}).items():
            if numeric(value) and key not in SKIPPED:
                found[f"{section}.{key}"].append(float(value))
    for frame in record.get("frames") or []:
        for key, value in frame.items():
            if numeric(value) and key not in SKIPPED:
                found[f"frame.{key}"].append(float(value))
    return found


def percentile(ordered: list[float], q: float) -> float:
    position = (len(ordered) - 1) * q
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def summarize(values: list[float]) -> str:
    ordered = sorted(values)
    stats = (ordered[0], percentile(ordered, 0.05), percentile(ordered, 0.5), percentile(ordered, 0.95), ordered[-1])
    return f"n={len(ordered):<5} " + "  ".join(f"{name}={value:.3f}" for name, value in zip(
        ("min", "p5", "med", "p95", "max"), stats))


def report(records: list[dict]) -> str:
    groups: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        groups[record.get("label") or NO_LABEL].append(record)
    out: list[str] = []
    for label in sorted(groups):
        rows = groups[label]
        fired = Counter(kind for row in rows for kind in set(row.get("anomalies") or []))
        out.append(f"== {label}: {len(rows)} ventanas")
        out.append("  anomalías: " + (", ".join(f"{k} {n}/{len(rows)}" for k, n in sorted(fired.items())) or "ninguna"))
        merged: dict[str, list[float]] = defaultdict(list)
        for row in rows:
            for key, values in measurements(row).items():
                merged[key].extend(values)
        out.extend(f"  {key:<28} {summarize(values)}" for key, values in sorted(merged.items()))
    out.append("")
    out.append("== Detección y falsas alarmas")
    for label in sorted(groups):
        rows = groups[label]
        expected = EXPECTED.get(label)
        if expected:
            hits = sum(1 for row in rows if set(expected) & set(row.get("anomalies") or []))
            out.append(f"  {label}: esperado {'/'.join(expected)}; detección {hits}/{len(rows)} = {hits / len(rows):.0%}")
        elif label == "normal" or label == "hablando_yo":
            fired = Counter(kind for row in rows for kind in set(row.get("anomalies") or []))
            alarms = ", ".join(f"{k} {n}/{len(rows)} = {n / len(rows):.0%}" for k, n in sorted(fired.items()))
            out.append(f"  {label}: falsas alarmas por tipo: {alarms or 'ninguna (0%)'}")
    return "\n".join(out)


def main(argv: list[str]) -> int:
    if len(argv) != 2 or not Path(argv[1]).exists():
        print(__doc__, file=sys.stderr)
        return 2
    records = load(Path(argv[1]))
    if not records:
        print("No hay ventanas registradas.", file=sys.stderr)
        return 1
    print(report(records))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
