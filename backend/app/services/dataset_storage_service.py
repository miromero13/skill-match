import hashlib
import os
import shutil
from pathlib import Path
from typing import Optional, Tuple
from fastapi import UploadFile

from app.core.config import settings
from app.core.exceptions import SkillMatchException

ALLOWED_EXTENSIONS = {"mp4", "wav", "py"}
MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024  # 100 MB


class DatasetStorageService:
    """
    Servicio de almacenamiento estructurado de muestras multimedia con validación criptográfica SHA-256.
    Almacena los artefactos en un directorio estructurado local (o MinIO bucket si está activo).
    """

    @classmethod
    def get_base_storage_dir(cls) -> Path:
        base_dir = Path("storage/datasets")
        base_dir.mkdir(parents=True, exist_ok=True)
        return base_dir

    @classmethod
    async def save_upload_file(
        cls,
        upload_file: UploadFile,
        sample_id: str,
        discipline: str,
        expected_hash: Optional[str] = None,
    ) -> Tuple[str, str, int, str]:
        """
        Lee el archivo en streaming, calcula el hash SHA-256 en vuelo, verifica el tamaño y formato,
        y persiste el archivo en el almacenamiento estructurado.

        Retorna: (storage_path, calculated_sha256, file_size_bytes, extension)
        """
        filename = upload_file.filename or "sample"
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

        if ext not in ALLOWED_EXTENSIONS:
            raise SkillMatchException(
                statuscode=400,
                message=f"Formato no permitido: '.{ext}'. Solo se permiten archivos {', '.join(sorted(ALLOWED_EXTENSIONS))}.",
            )

        clean_discipline = "".join(c for c in discipline.lower() if c.isalnum() or c in "-_") or "general"
        dest_dir = cls.get_base_storage_dir() / clean_discipline
        dest_dir.mkdir(parents=True, exist_ok=True)

        dest_filename = f"{sample_id}.{ext}"
        dest_path = dest_dir / dest_filename
        relative_storage_path = f"datasets/{clean_discipline}/{dest_filename}"

        sha256_hasher = hashlib.sha256()
        total_size = 0

        try:
            with open(dest_path, "wb") as buffer:
                while True:
                    chunk = await upload_file.read(64 * 1024)
                    if not chunk:
                        break
                    total_size += len(chunk)
                    if total_size > MAX_FILE_SIZE_BYTES:
                        raise SkillMatchException(
                            statuscode=400,
                            message=f"El tamaño del archivo supera el límite máximo permitido de {MAX_FILE_SIZE_BYTES // (1024 * 1024)} MB.",
                        )
                    sha256_hasher.update(chunk)
                    buffer.write(chunk)
        except Exception:
            if dest_path.exists():
                dest_path.unlink(missing_ok=True)
            raise

        calculated_hash = sha256_hasher.hexdigest().lower()

        if expected_hash:
            normalized_expected = expected_hash.strip().lower()
            if calculated_hash != normalized_expected:
                if dest_path.exists():
                    dest_path.unlink(missing_ok=True)
                raise SkillMatchException(
                    statuscode=400,
                    message="El hash SHA-256 verificado en el servidor no coincide con el hash suministrado por el cliente.",
                )

        return relative_storage_path, calculated_hash, total_size, ext

    @classmethod
    def delete_file(cls, relative_storage_path: str) -> None:
        """Elimina el archivo del almacenamiento si existe."""
        if not relative_storage_path:
            return
        base_dir = Path("storage")
        full_path = base_dir / relative_storage_path
        if full_path.exists() and full_path.is_file():
            full_path.unlink(missing_ok=True)
