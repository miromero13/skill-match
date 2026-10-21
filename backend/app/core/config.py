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

    # Proveedores de Autenticación Social & OTP (Opcionales / Se cargan de .env)
    GOOGLE_CLIENT_ID: Optional[str] = Field(default=None, description="Google OAuth Client ID")
    GOOGLE_CLIENT_SECRET: Optional[SecretStr] = Field(default=None, description="Google OAuth Client Secret (Secreto .env)")

    GITHUB_CLIENT_ID: Optional[str] = Field(default=None, description="GitHub OAuth Client ID")
    GITHUB_CLIENT_SECRET: Optional[SecretStr] = Field(default=None, description="GitHub OAuth Client Secret (Secreto .env)")

    WHATSAPP_API_KEY: Optional[SecretStr] = Field(default=None, description="WhatsApp API Key (Secreto .env)")
    WHATSAPP_PHONE_NUMBER_ID: Optional[str] = Field(default=None, description="WhatsApp Business Phone Number ID")

    # Almacenamiento MinIO / S3
    MINIO_ENDPOINT: str = Field(default="localhost:9000", description="Endpoint de MinIO/S3")
    MINIO_ROOT_USER: str = Field(default="minioadmin", description="Usuario root de MinIO")
    MINIO_ROOT_PASSWORD: Optional[SecretStr] = Field(default=None, description="Contraseña de MinIO (Secreto .env)")
    MINIO_SECURE: bool = Field(default=False, description="Uso de HTTPS para MinIO")
    MINIO_DEFAULT_BUCKET: str = Field(default="skillmatch-media", description="Bucket por defecto")

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, list):
            return v
        return ["*"]

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
