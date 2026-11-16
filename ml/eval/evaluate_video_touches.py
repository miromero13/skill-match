from __future__ import annotations

import argparse
import csv
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.football.pipeline.ball_tracker import track_ball_in_video
from app.football.pipeline.touch_events import detect_video_touch_events
from tests.football.synthetic import (
    SyntheticJugglingSpec,
    generate_synthetic_juggling_clip,
)


def evaluate_clip(video_path: Path, manual_touch_count: int) -> dict[str, Any]:
    track = track_ball_in_video(video_path)
    detected_touches = detect_video_touch_events(track)
    predicted_count = len(detected_touches)
    abs_error = abs(predicted_count - manual_touch_count)
    return {
        "video_path": str(video_path),
        "manual_touch_count": manual_touch_count,
        "predicted_touch_count": predicted_count,
        "abs_error": abs_error,
        "detected_timestamps_ms": [t.t_ms for t in detected_touches],
    }


def evaluate_manifest_or_benchmark(
    manifest_csv: Path | None = None,
    num_clips: int = 20,
) -> dict[str, Any]:
    """
    Evaluate `ball_tracker` + `touch_events` against `manifest_csv` if provided,
    or against a 20-clip benchmark suite with varying touch counts, speeds, noise,
    and frame occlusions.
    """
    results: list[dict[str, Any]] = []

    if manifest_csv is not None and manifest_csv.exists():
        with manifest_csv.open("r", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                clip_path = Path(row["path"])
                if not clip_path.is_absolute():
                    clip_path = (manifest_csv.parent / clip_path).resolve()
                manual_count = int(row["manual_touch_count"])
                results.append(evaluate_clip(clip_path, manual_count))
    else:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp_dir = Path(tmp_str)
            for i in range(num_clips):
                num_touches = 4 + (i % 9)  # 4 to 12 touches per clip
                interval_ms = 650 + (i % 4) * 100
                touch_times = [900 + k * interval_ms for k in range(num_touches)]
                duration_s = (touch_times[-1] + 1100) / 1000.0
                spec = SyntheticJugglingSpec(
                    duration_s=duration_s,
                    touch_times_ms=touch_times,
                    peak_height_diameters=1.8 + (i % 3) * 0.4,
                    background_noise_std=1.5 + (i % 4) * 1.0,
                    missing_frame_ranges=[(35, 37)] if (i % 3 == 0) else [],
                    seed=1000 + i,
                )
                clip = generate_synthetic_juggling_clip(
                    output_dir=tmp_dir,
                    spec=spec,
                    clip_name=f"eval_clip_{i:02d}",
                    include_audio=False,
                )
                results.append(evaluate_clip(clip.video_path, num_touches))

    errors = [int(r["abs_error"]) for r in results]
    mean_abs_error = sum(errors) / float(len(errors)) if errors else 0.0
    exact_matches = sum(1 for e in errors if e == 0)

    return {
        "num_clips": len(results),
        "mean_abs_error": round(mean_abs_error, 4),
        "max_abs_error": max(errors) if errors else 0,
        "exact_match_rate": round(exact_matches / float(len(results)), 4)
        if results
        else 0.0,
        "passes_phase2_target_mae_le_2": mean_abs_error <= 2.0,
        "clips": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate Football Phase 2 video touch detection against manual counts."
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=None,
        help="Optional path to ml/data/manifest.csv",
    )
    parser.add_argument(
        "--num-clips",
        type=int,
        default=20,
        help="Number of benchmark clips when manifest is not provided",
    )
    args = parser.parse_args()
    report = evaluate_manifest_or_benchmark(
        manifest_csv=args.manifest,
        num_clips=args.num_clips,
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
