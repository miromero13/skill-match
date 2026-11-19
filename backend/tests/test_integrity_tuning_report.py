"""T11: the tuning report summarizes labelled diagnostics per label, with detection and false-alarm rates."""
import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "integrity_tuning_report.py"


def line(label, anomalies, pitch):
    return json.dumps({
        "ts": "2026-01-01T00:00:00+00:00", "window_id": "w", "label": label, "anomalies": anomalies,
        "window": {"duration_ms": 2400}, "frames": [{"t_ms": 0, "pitch_deg": pitch, "blink": False}],
        "audio": {"rms": 0.01, "speech_detected": False}, "lip_sync": {"verdict": "insufficient"},
    })


def run(target):
    return subprocess.run([sys.executable, "-I", str(SCRIPT), str(target)], capture_output=True, text=True, timeout=60)


def fixture(tmp_path):
    rows = [line("normal", [], 1.0), line("normal", [], 3.0), line("normal", [], 5.0),
            line("normal", ["GAZE_AWAY"], 7.0), "not json",
            line("mirando_abajo", ["HEAD_POSE_DOWN"], -30.0), line("mirando_abajo", [], -5.0),
            line("mirando_abajo", ["GAZE_AWAY", "HEAD_POSE_DOWN"], -25.0), line("mirando_abajo", ["HEAD_POSE_DOWN"], -28.0)]
    (tmp_path / "a.jsonl").write_text("\n".join(rows[:5]) + "\n")
    (tmp_path / "b.jsonl").write_text("\n".join(rows[5:]) + "\n")


def test_report_prints_rates_and_percentiles_for_a_directory(tmp_path):
    fixture(tmp_path)
    result = run(tmp_path)
    assert result.returncode == 0
    out = result.stdout
    assert "== normal: 4 ventanas" in out and "== mirando_abajo: 4 ventanas" in out
    assert "GAZE_AWAY 1/4" in out
    assert "frame.pitch_deg" in out and "min=1.000" in out and "med=4.000" in out and "max=7.000" in out
    assert "mirando_abajo: esperado HEAD_POSE_DOWN/GAZE_AWAY; detección 3/4 = 75%" in out
    assert "normal: falsas alarmas por tipo: GAZE_AWAY 1/4 = 25%" in out
    assert "no es JSON" in result.stderr
    assert "t_ms" not in out


def test_report_reads_a_single_file_and_fails_cleanly_on_bad_input(tmp_path):
    fixture(tmp_path)
    assert "== normal: 4 ventanas" in run(tmp_path / "a.jsonl").stdout
    missing = run(tmp_path / "nope")
    assert missing.returncode == 2 and missing.stdout == ""
    (tmp_path / "empty").mkdir()
    assert run(tmp_path / "empty").returncode == 1
