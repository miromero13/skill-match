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


def test_flute_note_and_variation_inference():
    from app.services.flute_training_service import (
        _infer_note_from_sample,
        _infer_variation_from_sample,
    )

    sample = DatasetSample(
        discipline="musica",
        challenge="Flauta - Nota FA (rapida)",
        hardware_info="Webcam + Mic",
        signed_consent=True,
        file_format="mp4",
        file_size_bytes=2048,
        file_hash_sha256="c" * 64,
        storage_path="datasets/musica/flauta.mp4",
        level_label="FA",
        surface="rapida",
        manual_touch_count=698,
    )
    assert _infer_note_from_sample(sample) == "FA"
    assert _infer_variation_from_sample(sample) == "rapida"

    sample.surface = None
    sample.challenge = "Flauta - Nota FA (angulo_suave)"
    assert _infer_variation_from_sample(sample) == "angulo_suave"
    sample.challenge = "Flauta - Nota FA"
    assert _infer_variation_from_sample(sample) == "sostenida"
