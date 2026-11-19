"""Explicit deployment-only provisioning of the local face models (YuNet, SFace, MediaPipe FaceLandmarker).

No request path imports or runs this script. Every artifact is pinned by SHA-256: it is verified after
download and again on every run, written atomically (temp file + rename) and never overwritten when
an existing file does not match the pin.
"""
import argparse
import hashlib
import os
from pathlib import Path
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1] / "app/models/weights"
MAX_MODEL_BYTES = 60_000_000
OPENCV_ZOO = "https://github.com/opencv/opencv_zoo/raw/main/models/"
MEDIAPIPE = "https://storage.googleapis.com/mediapipe-models/"

# name -> (download URL, pinned SHA-256)
MODELS: dict[str, tuple[str, str]] = {
    "face_detection_yunet_2023mar.onnx": (
        OPENCV_ZOO + "face_detection_yunet/face_detection_yunet_2023mar.onnx",
        "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4",
    ),
    "face_recognition_sface_2021dec.onnx": (
        OPENCV_ZOO + "face_recognition_sface/face_recognition_sface_2021dec.onnx",
        "0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79",
    ),
    "face_landmarker.task": (
        MEDIAPIPE + "face_landmarker/face_landmarker/float16/1/face_landmarker.task",
        "64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff",
    ),
}


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def download(url: str, target: Path, expected: str) -> None:
    """Download to ``target`` (must not exist) and refuse unless the SHA-256 matches ``expected``."""
    if not url.startswith("https://"):
        raise RuntimeError("Refusing a non-HTTPS model URL")
    with urllib.request.urlopen(url, timeout=60) as response, target.open("xb") as output:
        if not response.url.startswith("https://"):
            raise RuntimeError("Refusing an insecure model redirect")
        size = 0
        while chunk := response.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_MODEL_BYTES:
                raise RuntimeError("Model download exceeds the fixed size limit")
            output.write(chunk)
    if digest(target) != expected:
        raise RuntimeError("Downloaded model checksum does not match the pinned artifact")


def install_atomically(root: Path, name: str, expected: str, fetch) -> None:
    """Fetch into a temp file inside ``root``, verify the pin, then rename it into place.

    ``fetch(temp_path)`` must write the artifact to ``temp_path``. A mismatch removes only the temp
    file and never touches an existing final file.
    """
    root.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{name}.", suffix=".part", dir=root)
    os.close(fd)
    temp = Path(temp_name)
    try:
        temp.unlink()  # download() creates it exclusively ("xb")
        fetch(temp)
        if digest(temp) != expected:
            raise RuntimeError(f"Checksum mismatch for {name}; refusing to install")
        os.replace(temp, root / name)
    finally:
        temp.unlink(missing_ok=True)


def verify_existing(root: Path, models: dict[str, tuple[str, str]]) -> list[str]:
    """Return the missing names; raise when a present file does not match its pin."""
    missing = []
    for name, (_, expected) in models.items():
        path = root / name
        if path.exists():
            if not path.is_file() or digest(path) != expected:
                raise RuntimeError(f"Refusing to overwrite invalid existing model: {name}")
        else:
            missing.append(name)
    return missing


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Install pinned local face models (YuNet, SFace, MediaPipe FaceLandmarker); never overwrite existing files."
    )
    parser.add_argument("--verify-only", action="store_true", help="Check existing SHA256 hashes without network or file writes.")
    args = parser.parse_args()
    try:
        missing = verify_existing(ROOT, MODELS)
        if missing and args.verify_only:
            raise RuntimeError("Missing vision models: " + ", ".join(missing) + "; run without --verify-only to install")
        for name in missing:
            url, expected = MODELS[name]
            install_atomically(ROOT, name, expected, lambda temp, url=url, expected=expected: download(url, temp, expected))
        print(f"Verified {len(MODELS)} local vision models (SHA256).")
    except (OSError, RuntimeError) as exc:
        parser.exit(1, f"Model setup failed: {exc}\n")


if __name__ == "__main__":
    main()
