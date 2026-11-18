"""Stable, accent/case/Unicode/whitespace-insensitive catalog identity keys."""
import hashlib
import unicodedata


def normalize_catalog_name(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value).casefold()
    return " ".join("".join(char for char in decomposed if not unicodedata.combining(char)).split())


def catalog_name_key(value: str) -> str:
    # Fixed-size keys keep PostgreSQL indexes safe for long normalized Unicode names.
    return hashlib.sha256(normalize_catalog_name(value).encode("utf-8")).hexdigest()
