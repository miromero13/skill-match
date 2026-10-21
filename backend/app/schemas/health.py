from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

class HealthData(BaseModel):
    """Estructura de datos para el endpoint de salud."""
    status: str = Field(..., description="Estado general de la aplicación ('healthy', 'degraded', 'unhealthy')")
    environment: str = Field(..., description="Entorno actual ('development', 'staging', 'production')")
    version: str = Field(..., description="Versión actual del backend")
    database: str = Field(..., description="Estado de conectividad a PostgreSQL ('connected', 'disconnected')")
    services: Dict[str, Any] = Field(default_factory=dict, description="Estado de subsistemas internos")
