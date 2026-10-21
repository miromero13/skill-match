from typing import List, Union, Optional
from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """
    Configuración global de la aplicación validada estrictamente por variables de entorno.
    Los secretos críticos se encapsulan como SecretStr para prevenir fugas accidentales en logs.
    """
    PROJECT_NAME: str = "SkillMatch API"
    VERSION: str = "0.1.0"
    DESCRIPTION: str = (
        "API Backend para SkillMatch: Plataforma colaborativa de intercambio de habilidades "
        "con validación multi-modal asistida por Inteligencia Artificial propia."
    )
    ENVIRONMENT: str = Field(default="development", description="development | staging | production")
    DEBUG: bool = Field(default=True)

    # Configuración de Red y Seguridad
    ALLOWED_ORIGINS: Union[List[str], str] = Field(
        default=["http://localhost:3000", "http://localhost:5173", "http://127.0.0.1:3000", "http://127.0.0.1:5173"],
        description="Lista de orígenes permitidos para CORS"
    )

    # Base de Datos PostgreSQL Asíncrona
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "skillmatch_user"
    POSTGRES_PASSWORD: SecretStr = Field(
        default=SecretStr("skillmatch_password"),
        description="Contraseña de PostgreSQL (Secreto)"
    )
    POSTGRES_DB: str = "skillmatch_db"
    DATABASE_URL: Optional[SecretStr] = Field(
        default=None,
        description="DSN completa de base de datos opcional (Secreto)"
    )

    # Parámetros del Pool de Conexiones
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30

    # Seguridad y JWT (Secretos obligatorios)
    SECRET_KEY: SecretStr = Field(
        default=SecretStr("09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7"),
        description="Clave secreta criptográfica para firma de tokens JWT (Secreto)"
    )
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 1 día
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # Proveedores de Autenticación Externa (OAuth & OTP)
    GOOGLE_CLIENT_ID: Optional[str] = Field(default=None, description="Client ID de Google OAuth")
    GOOGLE_CLIENT_SECRET: Optional[SecretStr] = Field(default=None, description="Client Secret de Google (Secreto)")
    
    GITHUB_CLIENT_ID: Optional[str] = Field(default=None, description="Client ID de GitHub OAuth")
    GITHUB_CLIENT_SECRET: Optional[SecretStr] = Field(default=None, description="Client Secret de GitHub (Secreto)")

    WHATSAPP_API_KEY: Optional[SecretStr] = Field(default=None, description="API Key para envío de OTP WhatsApp (Secreto)")
    WHATSAPP_PHONE_NUMBER_ID: Optional[str] = Field(default=None, description="ID de teléfono emisor de WhatsApp Business")

    # Almacenamiento de Objetos S3 / MinIO (Auditorías, Videos y Datasets)
    MINIO_ENDPOINT: str = Field(default="localhost:9000", description="Host y puerto de MinIO/S3")
    MINIO_ROOT_USER: str = Field(default="minioadmin", description="Usuario root de MinIO")
    MINIO_ROOT_PASSWORD: SecretStr = Field(default=SecretStr("minioadmin"), description="Clave de MinIO (Secreto)")
    MINIO_SECURE: bool = Field(default=False, description="Usar HTTPS para MinIO")
    MINIO_DEFAULT_BUCKET: str = Field(default="skillmatch-media", description="Bucket por defecto")

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, list):
            return v
        return ["*"]

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
        """
        En producción y staging, impide arrancar si se usan claves por defecto o inseguras.
        """
        if self.ENVIRONMENT in ("production", "staging"):
            insecure_keys = (
                "replace-this-secret-key-in-production-with-openssl-rand-hex-32",
                "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7",
                "skillmatch_password",
                "minioadmin",
            )
            if self.SECRET_KEY.get_secret_value() in insecure_keys:
                raise ValueError("SECRET_KEY no puede ser una clave por defecto en entornos de producción o staging.")
            if self.POSTGRES_PASSWORD.get_secret_value() in insecure_keys:
                raise ValueError("POSTGRES_PASSWORD no puede ser la clave de desarrollo en producción.")
        return self

    @property
    def async_database_url(self) -> str:
        """Retorna la URL asíncrona segura extrayendo el valor de los SecretStr."""
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

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

settings = Settings()
