import pytest
from app.services.content_moderation_service import ContentModerationService


def test_content_moderation_clean_text():
    is_valid, error = ContentModerationService.validate_content("Excelente tutor, explicó muy bien los conceptos.")
    assert is_valid is True
    assert error == ""


def test_content_moderation_offensive_text():
    is_valid, error = ContentModerationService.validate_content("Este tipo es un estafador y un incompetente")
    assert is_valid is False
    assert "términos inapropiados" in error


def test_content_moderation_sanitization():
    raw = "   Muchas    gracias   por  la   clase!   "
    cleaned = ContentModerationService.sanitize(raw)
    assert cleaned == "Muchas gracias por la clase!"
