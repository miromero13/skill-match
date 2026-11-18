"""Explicit deployment-only provisioning. No request path imports this script."""
import argparse
import hashlib
from pathlib import Path
import shutil
import tarfile
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1] / "app/models/weights/audio-integrity"
HASHES = {
    "speaker_segmentation.onnx": "220ad67ca923bef2fa91f2390c786097bf305bceb5e261d4af67b38e938e1079",
    "speaker_embedding.onnx": "1a331345f04805badbb495c775a6ddffcdd1a732567d5ec8b3d5749e3c7a5e4b",
}
ARCHIVE_HASH = "24615ee884c897d9d2ba09bb4d30da6bb1b15e685065962db5b02e76e4996488"
RELEASE = "https://github.com/k2-fsa/sherpa-onnx/releases/download/"
SEGMENTATION_URL = RELEASE + "speaker-segmentation-models/sherpa-onnx-pyannote-segmentation-3-0.tar.bz2"
EMBEDDING_URL = RELEASE + "speaker-recongition-models/3dspeaker_speech_eres2net_base_sv_zh-cn_3dspeaker_16k.onnx"


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def download(url, target, expected):
    with urllib.request.urlopen(url, timeout=30) as response, target.open("xb") as output:
        if not response.url.startswith("https://"):
            raise RuntimeError("Refusing an insecure model redirect")
        size = 0
        while chunk := response.read(1024 * 1024):
            size += len(chunk)
            if size > 50_000_000:
                raise RuntimeError("Model download exceeds the fixed size limit")
            output.write(chunk)
    if digest(target) != expected:
        raise RuntimeError("Downloaded model checksum does not match the pinned artifact")


def main():
    parser = argparse.ArgumentParser(description="Install pinned local calibration speaker models; never overwrite existing files.")
    parser.add_argument("--verify-only", action="store_true", help="Check existing SHA256 hashes without network or file writes.")
    args = parser.parse_args()
    try:
        missing = []
        for name, expected in HASHES.items():
            path = ROOT / name
            if path.exists():
                if not path.is_file() or digest(path) != expected:
                    raise RuntimeError(f"Refusing to overwrite invalid existing model: {name}")
            else:
                missing.append(name)
        if missing and args.verify_only:
            raise RuntimeError("Missing audio-integrity models; run without --verify-only to install")
        if missing:
            ROOT.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix="model-install-", dir=ROOT) as directory:
                staging = Path(directory)
                if "speaker_segmentation.onnx" in missing:
                    archive = staging / "segmentation.tar.bz2"
                    download(SEGMENTATION_URL, archive, ARCHIVE_HASH)
                    with tarfile.open(archive) as bundle:
                        candidates = [entry for entry in bundle.getmembers() if Path(entry.name).name == "model.onnx"]
                        if len(candidates) != 1 or not candidates[0].isfile() or candidates[0].size > 20_000_000:
                            raise RuntimeError("Unexpected segmentation archive layout")
                        extracted = bundle.extractfile(candidates[0])
                        if extracted is None:
                            raise RuntimeError("Missing segmentation model in archive")
                        with extracted, (staging / "speaker_segmentation.onnx").open("xb") as output:
                            shutil.copyfileobj(extracted, output)
                if "speaker_embedding.onnx" in missing:
                    download(EMBEDDING_URL, staging / "speaker_embedding.onnx", HASHES["speaker_embedding.onnx"])
                for name in missing:
                    if digest(staging / name) != HASHES[name]:
                        raise RuntimeError(f"Extracted model checksum mismatch: {name}")
                for name in missing:
                    with (ROOT / name).open("xb") as output, (staging / name).open("rb") as source:
                        shutil.copyfileobj(source, output)
        print("Verified 2 local audio-integrity models (SHA256).")
    except (OSError, RuntimeError, tarfile.TarError) as exc:
        parser.exit(1, f"Model setup failed: {exc}\n")


if __name__ == "__main__":
    main()
