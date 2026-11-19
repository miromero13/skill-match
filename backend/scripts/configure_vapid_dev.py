"""Configure ignored local environment values from an ignored VAPID dev key pair."""

import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
PRIVATE_KEY = BACKEND / "storage" / "vapid" / "private_key.pem"
ENV_FILE = BACKEND / ".env"


def replace_or_append(source: str, name: str, value: str) -> str:
    line = f'{name}="{value}"'
    rows = source.splitlines()
    for index, current in enumerate(rows):
        if current.startswith(f"{name}="):
            rows[index] = line
            break
    else:
        rows.append(line)
    return "\n".join(rows) + "\n"


def main() -> int:
    if not PRIVATE_KEY.is_file() or not ENV_FILE.is_file():
        print("Faltan backend/.env o las claves ignoradas de storage/vapid.")
        return 1
    vapid_executable = Path(sys.executable).with_name("vapid.exe")
    result = subprocess.run(
        [
            str(vapid_executable),
            "--applicationServerKey",
            "--private-key",
            str(PRIVATE_KEY),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    public_key = result.stdout.split()[-1]
    if len(public_key) < 80 or not all(
        character.isalnum() or character in "-_" for character in public_key
    ):
        raise RuntimeError("La clave pública VAPID generada no es válida")
    content = ENV_FILE.read_text(encoding="utf-8")
    values = {
        "WEB_PUSH_ENABLED": "True",
        "VAPID_PUBLIC_KEY": public_key,
        "VAPID_PRIVATE_KEY": PRIVATE_KEY.as_posix(),
        "VAPID_SUBJECT": "mailto:qa-webpush@skillmatch.local",
    }
    for name, value in values.items():
        content = replace_or_append(content, name, value)
    ENV_FILE.write_text(content, encoding="utf-8")
    print("Web Push de desarrollo configurado sin exponer claves.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
