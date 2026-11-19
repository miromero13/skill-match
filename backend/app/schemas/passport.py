from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.reputation import RatingsBreakdown, ReputationBadge, TrustScoreFactors


class PassportSkillItem(BaseModel):
    id: UUID
    name: str
    category_name: str
    declared_level: str
    status: str  # DECLARADA, EN_EVALUACION, VERIFICADA
    years_of_experience: int
    verified_at: Optional[datetime] = None


class DockerTestCase(BaseModel):
    name: str
    status: str = "PASSED"
    duration_seconds: float
    percentage: int


class DockerSuiteReport(BaseModel):
    passed_count: int = 4
    total_count: int = 4
    execution_time_seconds: float = 0.18
    coverage_percentage: int = 100
    test_cases: List[DockerTestCase] = Field(default_factory=list)


class AuditedCodeChallenge(BaseModel):
    title: str = "Implementación de Endpoint FastAPI con Caché Redis"
    consigna: str = "Implementar /api/skills/{id}/stats con inyección de dependencias Depends() para Redis y Postgres, caché por 60s, serialización Pydantic y control de excepciones 404."
    file_name: str = "main.py"
    language: str = "Python 3.12"
    source_code: str
    docker_report: DockerSuiteReport


class OralDefenseAudit(BaseModel):
    score: float = 95.0
    question: str = (
        "¿Cómo interactúa el Global Interpreter Lock (GIL) en CPython con las tareas asíncronas "
        "de asyncio y en qué escenarios concretos un thread bloqueante congelaría el Event Loop de FastAPI?"
    )
    candidate_transcript: str = (
        "El Event Loop de asyncio se ejecuta en un único thread principal. Si una función hace una "
        "llamada sincrónica pesada sin delegarla a run_in_threadpool(), bloquea la ejecución de todas "
        "las corutinas independientemente de si el GIL está liberado en C. Para CPU-bound tasks, el GIL "
        "no permite paralelismo real multinúcleo en un mismo proceso de Python..."
    )
    ai_verdict: str = (
        "Dominio arquitectónico sobresaliente. Explicó con exactitud la diferencia entre concurrencia "
        "cooperativa y paralelismo preemptivo, y la necesidad de delegar I/O sincrónico."
    )


class AntiFraudAudit(BaseModel):
    facial_liveness_score: float = 100.0
    voice_verification_status: str = "Voz única confirmada en micrófono"
    screen_violations_count: int = 0
    clipboard_abuse_detected: bool = False


class TechnicalDossier(BaseModel):
    has_technical_audit: bool = False
    technical_score: Optional[float] = None
    oral_defense_score: Optional[float] = None
    evaluated_skill_name: Optional[str] = None
    code_challenge: Optional[AuditedCodeChallenge] = None
    oral_defense: Optional[OralDefenseAudit] = None
    anti_fraud: Optional[AntiFraudAudit] = None


class PublicPassportResponse(BaseModel):
    public_uuid: UUID
    certificate_id: str
    full_name: str
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    location_label: Optional[str] = None
    member_since: datetime
    issued_at: datetime
    verification_hash: str
    verification_node: str = "Nodo Central SkillMatch #04"
    qr_endpoint_url: str
    pdf_download_url: str
    public_shareable_url: str

    # Resumen de Confianza y Calificaciones (HU-40)
    trust_score: float
    overall_rating: float
    total_reviews: int
    ratings_breakdown: RatingsBreakdown
    factors: TrustScoreFactors
    badges: List[ReputationBadge]

    # Habilidades del usuario
    skills: List[PassportSkillItem]

    # Dossier Técnico de Rigor
    technical_dossier: TechnicalDossier


class MyPassportSummaryResponse(BaseModel):
    public_uuid: UUID
    shareable_url: str
    qr_endpoint_url: str
    pdf_download_url: str
