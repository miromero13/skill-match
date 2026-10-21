import pytest
from httpx import AsyncClient
from pydantic import BaseModel, Field
from app.main import app
from app.schemas.response import APIResponse

class DummyPayload(BaseModel):
    name: str = Field(..., min_length=3)
    age: int = Field(..., ge=18)

# Registrar endpoint dummy para pruebas de validación evitando prefijo test_ en el nombre de función
@app.post("/api/mock-validation")
async def handle_mock_validation(payload: DummyPayload):
    return APIResponse(statuscode=200, message="Datos válidos", data=payload.model_dump())

@pytest.mark.asyncio
async def test_404_not_found_envelope(client: AsyncClient):
    """
    Verifica que rutas inexistentes devuelvan el sobre estándar con statuscode 404.
    """
    response = await client.get("/api/ruta-que-no-existe")
    assert response.status_code == 404
    payload = response.json()
    assert payload["statuscode"] == 404
    assert "Not Found" in payload["message"] or "error" in payload["message"].lower() or "encontrado" in payload["message"].lower()
    assert payload["data"] is None

@pytest.mark.asyncio
async def test_422_validation_error_envelope(client: AsyncClient):
    """
    Verifica que errores de validación de Pydantic devuelvan el sobre estándar con statuscode 422.
    """
    # Enviar payload con datos inválidos (nombre muy corto, edad menor a 18)
    response = await client.post("/api/mock-validation", json={"name": "a", "age": 10})
    assert response.status_code == 422
    payload = response.json()
    assert payload["statuscode"] == 422
    assert "Error de validación" in payload["message"]
    assert "errors" in payload["data"]
    assert payload["count"] >= 1

@pytest.mark.asyncio
async def test_200_success_envelope(client: AsyncClient):
    """
    Verifica que peticiones exitosas devuelvan el sobre estándar con statuscode 200.
    """
    response = await client.post("/api/mock-validation", json={"name": "Carlos", "age": 25})
    assert response.status_code == 200
    payload = response.json()
    assert payload["statuscode"] == 200
    assert payload["message"] == "Datos válidos"
    assert payload["data"]["name"] == "Carlos"
    assert payload["data"]["age"] == 25

@pytest.mark.asyncio
async def test_security_headers_and_timing(client: AsyncClient):
    """
    Verifica que los middlewares inyecten cabeceras preventivas y tiempo de respuesta.
    """
    response = await client.get("/api/health")
    assert "X-Content-Type-Options" in response.headers
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert "X-Frame-Options" in response.headers
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "X-Process-Time" in response.headers
