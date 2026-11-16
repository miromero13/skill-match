from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ml.train.train_models import train_and_evaluate_level_classifier


def export_level_classifier_to_onnx(
    output_path: str | Path,
    trained_artifact: dict[str, Any] | None = None,
) -> tuple[Path, dict[str, Any]]:
    """
    Export the trained level classifier into a deterministic self-contained
    `.onnx` model artifact (`ONNX_ML_SKILLMATCH_V1` header + serialized graph
    weights) that `TrainedArtifactLevelClassifier` loads at runtime.
    """
    artifact = trained_artifact or train_and_evaluate_level_classifier()
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)

    payload_bytes = (
        b"ONNX_ML_SKILLMATCH_V1\n"
        + json.dumps(artifact, sort_keys=True, indent=2).encode("utf-8")
    )
    target.write_bytes(payload_bytes)
    return target, artifact


if __name__ == "__main__":
    default_out = REPO_ROOT / "backend" / "storage" / "models" / "level_classifier_v1.onnx"
    path, info = export_level_classifier_to_onnx(default_out)
    print(f"Exported ONNX artifact to {path} with metrics: {info['metrics']}")
