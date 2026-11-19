import os
import tempfile
from pathlib import Path
from typing import List, Union, Optional
from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Rutas absolutas para resolución de archivos .env (ejecución desde /backend o raíz)
BASE_DIR = Path(__file__).resolve().parent.parent.parent  # backend/
ROOT_DIR = BASE_DIR.parent                               # raíz del monorepo

ENV_FILES = [
    str(BASE_DIR / ".env"),
    str(ROOT_DIR / ".env"),
    ".env",
]

class Settings(BaseSettings):
    """
    Configuración global de la aplicación.
    TODAS las variables y credenciales deben provenir estrictamente de las variables
    de entorno o del archivo .env. Ningún secreto o parámetro crítico tiene valor
    harcodeado en el código fuente.
    """
    # Configuración de Entorno
    PROJECT_NAME: str = Field(..., description="Nombre del proyecto (definido en .env)")
    VERSION: str = Field(..., description="Versión de la API (definida en .env)")
    DESCRIPTION: str = Field(
        default="SkillMatch API: Plataforma colaborativa de intercambio de habilidades con IA propia",
        description="Descripción de la API"
    )
    ENVIRONMENT: str = Field(..., description="Entorno de ejecución ('development', 'staging', 'production')")
    DEBUG: bool = Field(..., description="Modo debug booleano (definido en .env)")

    # Red y CORS
    ALLOWED_ORIGINS: Union[List[str], str] = Field(
        ...,
        description="Lista o cadena separada por comas de orígenes CORS permitidos"
    )

    # Base de Datos PostgreSQL Asíncrona (Valores obligatorios desde .env)
    POSTGRES_HOST: str = Field(..., description="Host de PostgreSQL")
    POSTGRES_PORT: int = Field(..., description="Puerto de PostgreSQL")
    POSTGRES_USER: str = Field(..., description="Usuario de PostgreSQL")
    POSTGRES_PASSWORD: SecretStr = Field(..., description="Contraseña de PostgreSQL (Secreto .env)")
    POSTGRES_DB: str = Field(..., description="Nombre de la base de datos")
    DATABASE_URL: Optional[SecretStr] = Field(
        default=None,
        description="DSN completa opcional de conexión a base de datos (Secreto .env)"
    )

    # Pool de Conexiones
    DB_POOL_SIZE: int = Field(default=10, description="Tamaño base del pool de conexiones")
    DB_MAX_OVERFLOW: int = Field(default=20, description="Máximo overflow de conexiones")
    DB_POOL_TIMEOUT: int = Field(default=30, description="Timeout en segundos para adquirir conexión")

    # Seguridad y JWT (Valores obligatorios desde .env)
    SECRET_KEY: SecretStr = Field(..., description="Clave criptográfica para firma de JWT (Secreto .env)")
    ALGORITHM: str = Field(default="HS256", description="Algoritmo de firma de tokens JWT")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=1440, description="Minutos de expiración de Access Token")
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=30, description="Días de expiración de Refresh Token")
    WS_TICKET_EXPIRE_SECONDS: int = Field(
        default=30,
        ge=5,
        le=120,
        description="Segundos de vigencia del ticket temporal para handshake WebSocket",
    )

    # Administrador Inicial por Defecto (Cargado estrictamente desde .env)
    ADMIN_EMAIL: str = Field(..., description="Correo institucional del Administrador inicial del sistema")
    ADMIN_PASSWORD: SecretStr = Field(..., description="Contraseña maestra del Administrador inicial (Secreto .env)")
    ADMIN_FULL_NAME: str = Field(default="Administrador Principal", description="Nombre completo del Administrador inicial")

    # Google Identity Services: ID-token flow, no client secret or other providers.
    GOOGLE_CLIENT_ID: Optional[str] = Field(default=None, description="Google OAuth Web Client ID; must match the frontend")

    # Optional text-only theory grading; selecting a provider requires explicit consent.
    THEORY_GRADING_PROVIDER: str = Field(default="disabled", description="disabled | openai | gemini")
    THEORY_GRADING_MODEL: str = Field(default="", description="Explicit provider model identifier; no implicit default")
    OPENAI_API_KEY: Optional[SecretStr] = Field(default=None, description="OpenAI API key for theory grading")
    GEMINI_API_KEY: Optional[SecretStr] = Field(default=None, description="Gemini API key for theory grading")
    THEORY_GRADING_TIMEOUT_SECONDS: int = Field(default=20, ge=1, le=60)
    THEORY_ASR_ENABLED: bool = Field(default=True, description="Enable the installed local ASR runtime for theory exams")

    # Browser/audiovisual supervision trial (SM-43): never reachable in production.
    BROWSER_SUPERVISION_TRIAL_ENABLED: Optional[bool] = Field(
        default=None,
        description=(
            "Expose the browser supervision trial routes. Unset = on only in development/test; "
            "always off in production, even if set to true"
        ),
    )

    # Integrity tuning diagnostics (T11): numeric per-window measurements, never reachable in production.
    INTEGRITY_DIAGNOSTICS_ENABLED: bool = Field(
        default=False,
        description="Append one numeric JSON line per audiovisual window to INTEGRITY_DIAGNOSTICS_DIR; off in production",
    )
    INTEGRITY_DIAGNOSTICS_DIR: str = Field(
        default_factory=lambda: os.path.join(tempfile.gettempdir(), "skillmatch-integrity-diagnostics"),
        description="Directory of the <trial_id>.jsonl diagnostics files (only created when enabled)",
    )

    # Deterministic programming sandbox. The image must be pre-pulled by deployment; the
    # request path never enables Docker networking or downloads an image.
    SANDBOX_DOCKER_IMAGE: str = Field(default="python:3.12-slim", description="Pinned Python image used by the programming sandbox")
    SANDBOX_DOCKER_BINARY: str = Field(default="docker", description="Docker-compatible executable for isolated code execution")
    SANDBOX_MAX_CONCURRENT_RUNS: int = Field(default=2, ge=1, le=16, description="Maximum concurrent sandbox executions")

    # Almacenamiento MinIO / S3
    MINIO_ENDPOINT: str = Field(default="localhost:9000", description="Endpoint de MinIO/S3")
    MINIO_ROOT_USER: str = Field(default="minioadmin", description="Usuario root de MinIO")
    MINIO_ROOT_PASSWORD: Optional[SecretStr] = Field(default=None, description="Contraseña de MinIO (Secreto .env)")
    MINIO_SECURE: bool = Field(default=False, description="Uso de HTTPS para MinIO")
    MINIO_DEFAULT_BUCKET: str = Field(default="skillmatch-media", description="Bucket por defecto")

    # Almacenamiento Garage S3 (Coolify VPS propio)
    GARAGE_S3_ENDPOINT_URL: str = Field(
        default="https://s3.devhooh.com",
        description="Endpoint S3 de Garage S3 desplegado en Coolify",
    )
    GARAGE_S3_ADMIN_URL: Optional[str] = Field(
        default="https://garage-admin.devhooh.com",
        description="Endpoint Admin API v2 de Garage S3 desplegado en Coolify",
    )
    GARAGE_S3_WEB_URL: Optional[str] = Field(
        default="https://garage-web.devhooh.com",
        description="Endpoint Web de Garage S3 desplegado en Coolify",
    )
    GARAGE_S3_REGION: str = Field(
        default="garage",
        description="Región configurada en Garage S3",
    )
    GARAGE_S3_ACCESS_KEY_ID: Optional[str] = Field(
        default=None,
        description="Access Key ID de Garage S3",
    )
    GARAGE_S3_SECRET_ACCESS_KEY: Optional[SecretStr] = Field(
        default=None,
        description="Secret Access Key de Garage S3 (Secreto .env)",
    )
    GARAGE_S3_ADMIN_TOKEN: Optional[SecretStr] = Field(
        default=None,
        description="Token administrativo de Garage S3 (Secreto .env)",
    )
    GARAGE_S3_BUCKET: str = Field(
        default="skillmatch-football",
        description="Bucket de Garage S3 para sesiones y evidencias de fútbol",
    )
    GARAGE_S3_FORCE_PATH_STYLE: bool = Field(
        default=True,
        description="Usar direccionamiento path-style (recomendado para Garage S3)",
    )

    # Cola de Tareas Asíncronas (Celery + Redis)
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="URL de conexión a Redis para broker y backend de Celery",
    )
    CELERY_TASK_ALWAYS_EAGER: bool = Field(
        default=False,
        description="Ejecutar tareas Celery en proceso (True para pruebas sin broker activo)",
    )

    # Economía de Puntos y Pasarela de Pagos (HU-42 / RF-SES-09 / RF-WAL-02)
    PAYMENT_GATEWAY_PROVIDER: str = Field(
        default="sandbox",
        description="Proveedor de pasarela de pagos: sandbox | stripe | paypal",
    )
    STRIPE_SECRET_KEY: Optional[SecretStr] = Field(
        default=None,
        description="Clave secreta de Stripe para recargas en vivo (Secreto .env)",
    )
    STRIPE_PUBLISHABLE_KEY: Optional[str] = Field(
        default=None,
        description="Clave pública de Stripe para integración de frontend",
    )
    PAYPAL_CLIENT_ID: Optional[str] = Field(
        default=None,
        description="Client ID de PayPal para checkout",
    )
    PAYPAL_CLIENT_SECRET: Optional[SecretStr] = Field(
        default=None,
        description="Client Secret de PayPal para checkout (Secreto .env)",
    )
    WALLET_POINTS_PER_USD: int = Field(
        default=10,
        description="Tasa de conversión canónica: 10 SkillPoints (SP) equivalen a $1.00 USD",
    )
    WALLET_CASHOUT_MIN_POINTS: int = Field(
        default=100,
        ge=10,
        description="Monto mínimo en SkillPoints para solicitar retiro a cuenta bancaria",
    )
    WALLET_PLATFORM_FEE_PERCENTAGE: float = Field(
        default=15.0,
        ge=0.0,
        le=50.0,
        description="Comisión institucional porcentual retenida por la plataforma en retiros (ej. 15.0%)",
    )

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, list):
            return v
        return ["*"]

    @property
    def integrity_diagnostics_enabled(self) -> bool:
        """Hard deny in production; otherwise the explicit flag (default off)."""
        return self.ENVIRONMENT.strip().lower() != "production" and self.INTEGRITY_DIAGNOSTICS_ENABLED

    @property
    def browser_supervision_trial_enabled(self) -> bool:
        """Hard deny in production; otherwise the explicit flag, else on only in development/test."""
        environment = self.ENVIRONMENT.strip().lower()
        if environment == "production":
            return False
        if self.BROWSER_SUPERVISION_TRIAL_ENABLED is not None:
            return self.BROWSER_SUPERVISION_TRIAL_ENABLED
        return environment in ("development", "test", "testing")

    @property
    def async_database_url(self) -> str:
        """Construye la URL asíncrona segura extrayendo los secretos cargados desde .env."""
        if self.DATABASE_URL:
            raw_url = self.DATABASE_URL.get_secret_value()
            if raw_url.startswith("postgresql://"):
                return raw_url.replace("postgresql://", "postgresql+asyncpg://", 1)
            return raw_url

        pwd = self.POSTGRES_PASSWORD.get_secret_value()
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{pwd}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # Configuración estricta de Pydantic Settings
    # 1. Variables de entorno del SO / Docker (máxima prioridad)
    # 2. Archivos .env (backend/.env, raíz .env)
    model_config = SettingsConfigDict(
        env_file=ENV_FILES,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

settings = Settings()
