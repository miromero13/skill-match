import uuid
from typing import Optional, Tuple
from fastapi import UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import SkillMatchException
from app.models.dataset_sample import DatasetSample
from app.schemas.dataset_sample import DatasetSampleCreate, DatasetSampleResponse
from app.services.dataset_storage_service import DatasetStorageService


class DatasetSampleService:
    @staticmethod
    async def list_samples(
        db: AsyncSession,
        page: int = 1,
        page_size: int = 50,
        discipline: Optional[str] = None,
    ) -> Tuple[list[DatasetSampleResponse], int]:
        """Lista muestras recolectadas con paginación y conteo total."""
        query = select(DatasetSample)
        count_query = select(func.count()).select_from(DatasetSample)

        if discipline:
            clean_discipline = discipline.strip().lower()
            query = query.where(func.lower(DatasetSample.discipline) == clean_discipline)
            count_query = count_query.where(func.lower(DatasetSample.discipline) == clean_discipline)

        total_count = await db.scalar(count_query) or 0

        query = (
            query.order_by(DatasetSample.created_at.desc(), DatasetSample.id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )

        result = await db.scalars(query)
        items = result.all()

        return [DatasetSampleResponse.model_validate(item) for item in items], total_count

    @staticmethod
    async def get_sample(db: AsyncSession, sample_id: uuid.UUID) -> DatasetSample:
        """Obtiene una muestra específica por ID."""
        sample = await db.scalar(
            select(DatasetSample).where(DatasetSample.id == sample_id)
        )
        if not sample:
            raise SkillMatchException(
                statuscode=404,
                message="Muestra de dataset no encontrada.",
            )
        return sample

    @staticmethod
    async def create_sample(
        db: AsyncSession,
        file: UploadFile,
        metadata: DatasetSampleCreate,
        uploaded_by_id: Optional[uuid.UUID] = None,
    ) -> DatasetSampleResponse:
        """
        Almacena el archivo validando hash SHA-256 y registra los metadatos de forma atómica.
        """
        if not metadata.signed_consent:
            raise SkillMatchException(
                statuscode=400,
                message="El consentimiento informado firmado es obligatorio.",
            )

        sample_id = uuid.uuid4()

        # Almacenar archivo y verificar hash SHA-256
        storage_path, calculated_hash, file_size, file_format = (
            await DatasetStorageService.save_upload_file(
                upload_file=file,
                sample_id=str(sample_id),
                discipline=metadata.discipline,
                expected_hash=metadata.file_hash_sha256,
            )
        )

        sample = DatasetSample(
            id=sample_id,
            discipline=metadata.discipline,
            challenge=metadata.challenge,
            hardware_info=metadata.hardware_info,
            signed_consent=True,
            file_format=file_format,
            file_size_bytes=file_size,
            file_hash_sha256=calculated_hash,
            storage_path=storage_path,
            uploaded_by_id=uploaded_by_id,
        )

        try:
            db.add(sample)
            await db.flush()
        except Exception:
            # Limpiar archivo en caso de fallo de persistencia
            DatasetStorageService.delete_file(storage_path)
            raise

        return DatasetSampleResponse.model_validate(sample)

    @staticmethod
    async def delete_sample(db: AsyncSession, sample_id: uuid.UUID) -> None:
        """Elimina una muestra defectuosa y su archivo asociado."""
        sample = await DatasetSampleService.get_sample(db, sample_id)
        storage_path = sample.storage_path

        await db.delete(sample)
        await db.flush()

        # Eliminar archivo físico
        DatasetStorageService.delete_file(storage_path)
