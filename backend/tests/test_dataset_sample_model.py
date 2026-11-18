import pytest
from pydantic import ValidationError

from app.models.dataset_sample import DatasetSample
from app.schemas.dataset_sample import DatasetSampleCreate, DatasetSampleResponse


def test_dataset_sample_create_valid():
    payload = DatasetSampleCreate(
        discipline="musica",
        challenge="guitarra-acustica",
        hardware_info="Webcam Logitech C920 + Mic Samson Go",
        signed_consent=True,
        file_hash_sha256="a" * 64,
    )
    assert payload.discipline == "musica"
    assert payload.signed_consent is True
    assert payload.file_hash_sha256 == "a" * 64


def test_dataset_sample_create_requires_consent():
    with pytest.raises(ValidationError) as exc:
        DatasetSampleCreate(
            discipline="musica",
            challenge="guitarra-acustica",
            hardware_info="Mic",
            signed_consent=False,
        )
    assert "El consentimiento informado firmado es obligatorio" in str(exc.value)


def test_dataset_sample_create_validates_hash_hex():
    with pytest.raises(ValidationError) as exc:
        DatasetSampleCreate(
            discipline="musica",
            challenge="guitarra-acustica",
            hardware_info="Mic",
            signed_consent=True,
            file_hash_sha256="invalid-non-hex-hash",
        )
    assert "hash SHA-256 debe tener exactamente 64 caracteres hexadecimales" in str(exc.value)


def test_dataset_sample_model_representation():
    sample = DatasetSample(
        discipline="futbol",
        challenge="dominadas",
        hardware_info="iPhone 13 Front Camera",
        signed_consent=True,
        file_format="mp4",
        file_size_bytes=1048576,
        file_hash_sha256="b" * 64,
        storage_path="datasets/futbol/sample.mp4",
    )
    assert sample.discipline == "futbol"
    assert sample.file_format == "mp4"
    assert sample.file_hash_sha256 == "b" * 64
