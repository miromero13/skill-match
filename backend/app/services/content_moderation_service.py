import re
from typing import Tuple

# Lista canónica de términos ofensivos/soeces y patrones vulgares comunes (Español/Inglés)
# Implementación 100% algorítmica y determinística (Zero Third-Party LLMs - AGENTS.md)
_OFFENSIVE_WORDS = {
    "estafador", "estafa", "ladron", "idiota", "imbecil", "maldito", "puta", "puto",
    "mierda", "estupido", "estupida", "pendejo", "pendeja", "cabron", "cabrona",
    "malparido", "hdp", "tarado", "incompetente", "estafadora", "scam", "scammer",
    "fuck", "bitch", "asshole", "shit", "bastard"
}

_OFFENSIVE_PATTERNS = [
    re.compile(rf"\b{re.escape(word)}\b", re.IGNORECASE) for word in _OFFENSIVE_WORDS
]


class ContentModerationService:
    """
    Filtro determinístico de lenguaje ofensivo para reseñas de sesiones y textos públicos.
    No requiere llamadas externas a LLMs (conforme a AGENTS.md).
    """

    @classmethod
    def validate_content(cls, text: str | None) -> Tuple[bool, str]:
        if not text or not text.strip():
            return True, ""

        normalized = text.strip()

        for pattern in _OFFENSIVE_PATTERNS:
            if pattern.search(normalized):
                return False, "El comentario contiene términos inapropiados o contrarios a las normas de convivencia."

        return True, ""

    @classmethod
    def sanitize(cls, text: str | None) -> str | None:
        if not text:
            return None
        cleaned = re.sub(r"\s+", " ", text).strip()
        return cleaned if cleaned else None
